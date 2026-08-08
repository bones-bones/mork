"""
Compare existing Printable DB ``Is good?`` values to bot QA verdicts (dry-run).

Does not write to the sheet. Downloads each image, runs ``review_image()``, reports
agreement and mismatches.

Example:
  python scripts/review_printable_compare.py --limit 300
  python scripts/review_printable_compare.py --limit 300 --output /tmp/compare.csv
"""

from __future__ import annotations

import mork_repo_root  # noqa: E402

import argparse
import csv
import os
import random
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from typing import TypeVar

import requests
from gspread.exceptions import APIError

from printable_image_qa import cleanup_temp_paths, resize_for_vision, review_image
from shared_vars import googleClient

T = TypeVar("T")

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
PRINTABLE_DB_SPREADSHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

COL_ID = 1
COL_CARDNAME = 2
COL_SIDENAME = 3
COL_URL = 4
COL_IS_GOOD = 5


def _is_retryable_google_error(exc: BaseException) -> bool:
    if isinstance(exc, APIError):
        resp = getattr(exc, "response", None)
        code = getattr(resp, "status_code", None) if resp is not None else None
        if code in (429, 500, 502, 503):
            return True
    msg = str(exc).lower()
    return any(
        needle in msg
        for needle in (
            "429",
            "503",
            "quota",
            "rate limit",
            "ratelimit",
            "backend error",
            "too many requests",
            "internal error",
        )
    )


def _google_call_with_retry(
    fn: Callable[[], T],
    *,
    what: str,
    max_tries: int,
    base_delay: float,
) -> T:
    last: Exception | None = None
    for attempt in range(max_tries):
        try:
            return fn()
        except Exception as e:
            last = e
            if not _is_retryable_google_error(e) or attempt >= max_tries - 1:
                raise
            wait = base_delay * (2**attempt) + random.uniform(0, 0.75)
            print(
                f"{what}: retryable error ({e!s}); sleeping {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    assert last is not None
    raise last


def _cell(row: list[str], col_1based: int) -> str:
    idx = col_1based - 1
    if idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _normalize_existing(val: str) -> str:
    v = (val or "").strip()
    if not v:
        return ""
    upper = v.upper()
    if upper.startswith("Y"):
        return "Y"
    if upper.startswith("N"):
        return "N"
    return v


def _download_image(url: str, dest_path: str, timeout: float) -> None:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS)
    parser.add_argument("--sheet-key", default=PRINTABLE_DB_SPREADSHEET_KEY)
    parser.add_argument("--worksheet", type=int, default=0)
    parser.add_argument("--first-row", type=int, default=2)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-image-side", type=int, default=1280)
    parser.add_argument("--no-corner-crops", action="store_true")
    parser.add_argument("--single-step", action="store_true")
    parser.add_argument("--http-timeout", type=float, default=120.0)
    parser.add_argument("--output", default="", help="Optional CSV path for full results")
    parser.add_argument("--mismatches-only", action="store_true")
    parser.add_argument("--skip-ollama-check", action="store_true")
    args = parser.parse_args()

    if not os.path.isfile(args.credentials):
        print(f"Missing credentials: {args.credentials}", file=sys.stderr)
        sys.exit(1)

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)

    if not args.skip_ollama_check:
        try:
            tags = requests.get(f"{args.ollama_host.rstrip('/')}/api/tags", timeout=15)
            tags.raise_for_status()
            names = {m.get("name", "") for m in tags.json().get("models", [])}
            base = args.model.split(":")[0]
            if not any(n == args.model or n.startswith(f"{base}:") for n in names):
                print(f"Model {args.model!r} not in Ollama", file=sys.stderr)
                sys.exit(1)
        except requests.RequestException as e:
            print(f"Ollama unreachable: {e}", file=sys.stderr)
            sys.exit(1)

    ws = _google_call_with_retry(
        lambda: googleClient.open_by_key(args.sheet_key).get_worksheet(args.worksheet),
        what="open sheet",
        max_tries=6,
        base_delay=2.5,
    )
    rows = _google_call_with_retry(ws.get_all_values, what="read sheet", max_tries=6, base_delay=2.5)

    end_row = args.first_row + args.limit - 1
    results: list[dict[str, str]] = []
    errors = 0
    processed = 0

    for row_1based, row in enumerate(rows, start=1):
        if row_1based < args.first_row or row_1based > end_row:
            continue
        card_id = _cell(row, COL_ID)
        if not card_id:
            continue

        existing_raw = _cell(row, COL_IS_GOOD)
        existing_norm = _normalize_existing(existing_raw)
        card_name = _cell(row, COL_CARDNAME)
        side_name = _cell(row, COL_SIDENAME)
        url = _cell(row, COL_URL)

        if not url.startswith("http"):
            errors += 1
            print(f"row {row_1based} id {card_id}: bad url", file=sys.stderr)
            continue

        tmp_raw = ""
        tmp_scaled = ""
        try:
            fd, tmp_raw = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            _download_image(url, tmp_raw, args.http_timeout)
            vision_path = tmp_raw
            if args.max_image_side > 0:
                vision_path, extra = resize_for_vision(tmp_raw, args.max_image_side)
                if extra:
                    tmp_scaled = vision_path

            review = review_image(
                image_path=vision_path,
                card_id=card_id,
                card_name=card_name,
                side_name=side_name,
                host=args.ollama_host,
                model=args.model,
                timeout=args.http_timeout,
                temperature=args.temperature,
                use_corner_crops=not args.no_corner_crops,
                two_step=not args.single_step,
            )
            bot = review.verdict
            agree = existing_norm == bot if existing_norm else None
            rec = {
                "row": str(row_1based),
                "id": card_id,
                "name": card_name[:60],
                "existing_raw": existing_raw,
                "existing": existing_norm,
                "bot": bot,
                "agree": "" if agree is None else ("Y" if agree else "N"),
                "issues": ",".join(review.issues),
                "heuristics": ",".join(review.heuristic_flags),
            }
            results.append(rec)
            processed += 1

            if not args.mismatches_only or agree is False:
                flag = "" if agree is None else ("OK" if agree else "DIFF")
                empty_note = " (empty)" if not existing_norm else ""
                print(
                    f"[{processed}/{args.limit}] row {row_1based} id {card_id} "
                    f"sheet={existing_raw!r}{empty_note} bot={bot} {flag} "
                    f"h={review.heuristic_flags or '-'}",
                    flush=True,
                )

        except Exception as e:
            errors += 1
            print(f"row {row_1based} id {card_id}: ERROR {e}", file=sys.stderr)
        finally:
            cleanup_temp_paths(tmp_scaled, tmp_raw)

    # Summary
    with_existing = [r for r in results if r["existing"]]
    mismatches = [r for r in with_existing if r["agree"] == "N"]
    empty = [r for r in results if not r["existing"]]
    bot_counts = Counter(r["bot"] for r in results)
    sheet_counts = Counter(r["existing"] for r in with_existing)

    print()
    print(f"Processed: {processed}  Errors: {errors}")
    print(f"Sheet labeled: {len(with_existing)}  Empty Is good?: {len(empty)}")
    print(f"Agree (Y/N only): {len(with_existing) - len(mismatches)}/{len(with_existing)}")
    print(f"Mismatches: {len(mismatches)}")
    print(f"Bot verdicts: {dict(bot_counts)}")
    print(f"Sheet verdicts: {dict(sheet_counts)}")

    if mismatches:
        print()
        print("--- Mismatches (sheet vs bot) ---")
        for r in mismatches:
            print(
                f"  row {r['row']} id {r['id']}: sheet={r['existing_raw']!r} -> bot={r['bot']} "
                f"({r['name']}) issues={r['issues'] or '-'}",
            )

    if empty:
        print()
        print(f"--- Empty sheet, bot would set ({len(empty)}) ---")
        bot_on_empty = Counter(r["bot"] for r in empty)
        print(f"  {dict(bot_on_empty)}")
        for r in empty[:20]:
            print(f"  row {r['row']} id {r['id']}: bot={r['bot']}")
        if len(empty) > 20:
            print(f"  ... and {len(empty) - 20} more")

    if args.output:
        fieldnames = [
            "row",
            "id",
            "name",
            "existing_raw",
            "existing",
            "bot",
            "agree",
            "issues",
            "heuristics",
        ]
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
