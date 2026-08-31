"""
Review printable Hellscube card images with a local Ollama vision model and update
the Printable DB sheet.

For each row where ``Is good?`` is empty:
  1. Download the image from the ``Url`` column (GCS public URL).
  2. Run two-step vision QA + PIL heuristics (see ``printable_image_qa.py``).
  3. Delete the local copy.
  4. Set ``Is good?`` to ``Y`` or ``N``, ``Bot?`` for auditability, and column G
     (``Bot comment``) with what is wrong when verdict is ``N``.

Spreadsheet:
https://docs.google.com/spreadsheets/d/1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs/edit?gid=0

Requires:
  - ``bot_secrets/client_secrets.json`` (service account with edit access to the sheet)
  - Ollama running locally with a vision model (default: ``qwen2.5vl:7b``)

Example:
  ollama pull qwen2.5vl:7b
  python scripts/review_printable_benchmark.py
  python scripts/review_printable_images.py --dry-run --limit 3
  python scripts/review_printable_images.py --n-only --limit 50
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from collections.abc import Callable

import mork_repo_root  # noqa: F401
import requests
from gspread.exceptions import APIError
from printable_image_qa import (
    cleanup_temp_paths,
    format_assessment_comment,
    resize_for_vision,
    review_image,
)

from shared_vars import googleClient

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
PRINTABLE_DB_SPREADSHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
BOT_MARKER = "bot"

COL_ID = 1
COL_CARDNAME = 2
COL_SIDENAME = 3
COL_URL = 4
COL_IS_GOOD = 5
COL_BOT = 6
COL_BOT_COMMENT = 7  # column G, immediately right of Bot?


def _column_letter(n: int) -> str:
    if n < 1:
        raise ValueError("column must be >= 1")
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


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
            "userratelimitexceeded",
            "user rate limit",
            "backend error",
            "too many requests",
            "internal error",
        )
    )


def _google_call_with_retry[T](
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
                f"{what}: retryable error ({e!s}); sleeping {wait:.1f}s "
                f"(attempt {attempt + 1}/{max_tries})",
                file=sys.stderr,
            )
            time.sleep(wait)
    assert last is not None
    raise last


def _pause(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _cell(row: list[str], col_1based: int) -> str:
    idx = col_1based - 1
    if idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _is_good_empty(val: str) -> bool:
    return not (val or "").strip()


def _download_image(url: str, dest_path: str, timeout: float) -> None:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS),
        help="Service account JSON (sets GOOGLE_APPLICATION_CREDENTIALS if unset)",
    )
    parser.add_argument(
        "--sheet-key",
        default=PRINTABLE_DB_SPREADSHEET_KEY,
        help="Printable DB spreadsheet id",
    )
    parser.add_argument(
        "--worksheet",
        type=int,
        default=0,
        help="0-based worksheet index (default 0 = PrintableDb gid=0)",
    )
    parser.add_argument(
        "--first-row",
        type=int,
        default=2,
        help="First 1-based data row (default 2, below header)",
    )
    parser.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help="Ollama base URL (default OLLAMA_HOST or http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama vision model name (default OLLAMA_VISION_MODEL or qwen2.5vl:7b)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Ollama sampling temperature (default 0 for deterministic QA)",
    )
    parser.add_argument(
        "--max-image-side",
        type=int,
        default=1280,
        help="Resize longer edge before vision (0 = no resize)",
    )
    parser.add_argument(
        "--no-corner-crops",
        action="store_true",
        help="Send only the full image to the vision model",
    )
    parser.add_argument(
        "--single-step",
        action="store_true",
        help="Single-pass vision prompt instead of two-step defect scan",
    )
    parser.add_argument(
        "--n-only",
        action="store_true",
        help="Only write sheet rows when verdict is N (skip Y updates)",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=120.0,
        help="Timeout seconds for image download and Ollama request",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds between processed rows (Sheets rate limit)",
    )
    parser.add_argument(
        "--after-read",
        type=float,
        default=0.4,
        help="Seconds after loading sheet",
    )
    parser.add_argument(
        "--after-sheet-write",
        type=float,
        default=1.1,
        help="Seconds after each pair of sheet cell updates",
    )
    parser.add_argument(
        "--api-retries",
        type=int,
        default=6,
        help="Max attempts for retryable Google API errors",
    )
    parser.add_argument(
        "--retry-base-delay",
        type=float,
        default=2.5,
        help="Base seconds for exponential backoff on Sheets errors",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run vision only; do not write to the sheet",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Review at most N rows with empty Is good? (0 = no limit)",
    )
    parser.add_argument(
        "--id",
        dest="only_ids",
        action="append",
        default=[],
        metavar="CARD_ID",
        help="Only review rows with this Id (repeatable)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-review rows even if Is good? is already set",
    )
    parser.add_argument(
        "--skip-ollama-check",
        action="store_true",
        help="Do not verify the model is pulled before starting",
    )
    args = parser.parse_args()

    if args.limit < 0:
        print("--limit must be >= 0", file=sys.stderr)
        sys.exit(1)
    if args.api_retries < 1:
        print("--api-retries must be >= 1", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.credentials):
        print(f"Missing credentials file: {args.credentials}", file=sys.stderr)
        sys.exit(1)

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)

    if not args.skip_ollama_check:
        try:
            tags = requests.get(
                f"{args.ollama_host.rstrip('/')}/api/tags",
                timeout=15,
            )
            tags.raise_for_status()
            names = {m.get("name", "") for m in tags.json().get("models", [])}
            base = args.model.split(":")[0]
            if not any(n == args.model or n.startswith(f"{base}:") for n in names):
                print(
                    f"Model {args.model!r} not found in Ollama. Run: ollama pull {args.model}",
                    file=sys.stderr,
                )
                sys.exit(1)
        except requests.RequestException as e:
            print(
                f"Cannot reach Ollama at {args.ollama_host}: {e}. "
                "Start Ollama or pass --skip-ollama-check.",
                file=sys.stderr,
            )
            sys.exit(1)

    printable_ws = _google_call_with_retry(
        lambda: googleClient.open_by_key(args.sheet_key).get_worksheet(args.worksheet),
        what="open Printable DB worksheet",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    _pause(args.after_read)
    rows = _google_call_with_retry(
        printable_ws.get_all_values,
        what="get_all_values Printable DB",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    _pause(args.after_read)

    is_good_col = _column_letter(COL_IS_GOOD)
    bot_col = _column_letter(COL_BOT)
    comment_col = _column_letter(COL_BOT_COMMENT)
    bot_marker = BOT_MARKER

    only_ids = {s.strip() for s in args.only_ids if s.strip()}
    processed = 0
    skipped_filled = 0
    skipped_y_only = 0
    errors = 0

    for row_1based, row in enumerate(rows, start=1):
        if row_1based < args.first_row:
            continue

        card_id = _cell(row, COL_ID)
        if not card_id:
            continue
        if only_ids and card_id not in only_ids:
            continue

        is_good = _cell(row, COL_IS_GOOD)
        if not args.force and not _is_good_empty(is_good):
            skipped_filled += 1
            continue

        card_name = _cell(row, COL_CARDNAME)
        side_name = _cell(row, COL_SIDENAME)
        url = _cell(row, COL_URL)
        if not url.startswith("http"):
            print(f"row {row_1based} id {card_id}: skip, bad Url {url!r}", file=sys.stderr)
            errors += 1
            continue

        tmp_raw = ""
        tmp_scaled = ""
        try:
            fd, tmp_raw = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            _download_image(url, tmp_raw, args.http_timeout)

            vision_path = tmp_raw
            if args.max_image_side > 0:
                vision_path, scaled_extra = resize_for_vision(tmp_raw, args.max_image_side)
                if scaled_extra:
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
            verdict = review.verdict
            issues = review.issues
            notes = review.notes
            assessment_comment = format_assessment_comment(review)
            print(
                f"row {row_1based} id {card_id} {card_name!r} ({side_name}): "
                f"verdict={verdict} issues={issues!r} heuristics={review.heuristic_flags!r} "
                f"notes={notes!r}"
            )
            if assessment_comment:
                print(f"  comment: {assessment_comment!r}")
            if review.forced_n_reason:
                print(f"  finalize: {review.forced_n_reason}")

            if args.n_only and verdict == "Y":
                skipped_y_only += 1
                print("  --n-only: skip sheet write (verdict Y)")
            elif args.dry_run:
                print(
                    f"  DRY-RUN would set Is good?={verdict!r}, Bot?={bot_marker!r}, "
                    f"comment={assessment_comment!r}"
                )
            else:
                _google_call_with_retry(
                    lambda r=row_1based, v=verdict: printable_ws.update_acell(
                        f"{is_good_col}{r}", v
                    ),
                    what=f"update Is good? row {row_1based}",
                    max_tries=args.api_retries,
                    base_delay=args.retry_base_delay,
                )
                _pause(args.after_sheet_write)
                _google_call_with_retry(
                    lambda r=row_1based, m=bot_marker: printable_ws.update_acell(
                        f"{bot_col}{r}", m
                    ),
                    what=f"update Bot? row {row_1based}",
                    max_tries=args.api_retries,
                    base_delay=args.retry_base_delay,
                )
                _pause(args.after_sheet_write)
                _google_call_with_retry(
                    lambda r=row_1based, c=assessment_comment: printable_ws.update_acell(
                        f"{comment_col}{r}", c
                    ),
                    what=f"update Bot comment row {row_1based}",
                    max_tries=args.api_retries,
                    base_delay=args.retry_base_delay,
                )
                _pause(args.after_sheet_write)

            processed += 1
            if args.limit and processed >= args.limit:
                print(f"Stopping: --limit {args.limit} reached")
                break
            if args.sleep:
                time.sleep(args.sleep)

        except Exception as e:
            errors += 1
            print(
                f"row {row_1based} id {card_id!r}: ERROR {e}",
                file=sys.stderr,
            )
        finally:
            cleanup_temp_paths(tmp_scaled, tmp_raw)

    print(
        f"Done. reviewed={processed} skipped_already_filled={skipped_filled} "
        f"skipped_n_only_y={skipped_y_only} errors={errors} dry_run={args.dry_run}",
    )


if __name__ == "__main__":
    main()
