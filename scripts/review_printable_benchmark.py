"""
Regression benchmark for printable image QA against human-labeled ground truth.

Uses cached images under ``/tmp/hc-review-test/{id}.png`` when present; otherwise
downloads from the Printable DB sheet (same credentials as ``review_printable_images.py``).

Example:
  python scripts/review_printable_benchmark.py --heuristics-only
  python scripts/review_printable_benchmark.py --model qwen2.5vl:7b
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from collections.abc import Callable
from typing import TypeVar

import mork_repo_root  # noqa: F401
import requests
from gspread.exceptions import APIError
from printable_image_qa import (
    ReviewResult,
    benchmark_ground_truth,
    cleanup_temp_paths,
    heuristic_checks,
    resize_for_vision,
    review_image,
)

from shared_vars import googleClient

T = TypeVar("T")

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
PRINTABLE_DB_SPREADSHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
CACHE_DIR = "/tmp/hc-review-test"

COL_ID = 1
COL_CARDNAME = 2
COL_SIDENAME = 3
COL_URL = 4


def _cell(row: list[str], col_1based: int) -> str:
    idx = col_1based - 1
    if idx >= len(row):
        return ""
    return (row[idx] or "").strip()


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
                f"{what}: retryable error ({e!s}); sleeping {wait:.1f}s "
                f"(attempt {attempt + 1}/{max_tries})",
                file=sys.stderr,
            )
            time.sleep(wait)
    assert last is not None
    raise last


def _download_image(url: str, dest_path: str, timeout: float) -> None:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


def _load_printable_rows(
    *,
    credentials: str,
    sheet_key: str,
    worksheet: int,
    api_retries: int,
    retry_base_delay: float,
) -> list[list[str]]:
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", credentials)
    printable_ws = _google_call_with_retry(
        lambda: googleClient.open_by_key(sheet_key).get_worksheet(worksheet),
        what="open Printable DB worksheet",
        max_tries=api_retries,
        base_delay=retry_base_delay,
    )
    return _google_call_with_retry(
        printable_ws.get_all_values,
        what="get_all_values Printable DB",
        max_tries=api_retries,
        base_delay=retry_base_delay,
    )


def _row_by_id(rows: list[list[str]], card_id: str) -> list[str] | None:
    for row in rows:
        if _cell(row, COL_ID) == card_id:
            return row
    return None


def _cached_image_path(card_id: str) -> str:
    return os.path.join(CACHE_DIR, f"{card_id}.png")


def _resolve_image_path(
    card_id: str,
    rows: list[list[str]],
    *,
    http_timeout: float,
    need_sheet: bool,
) -> tuple[str, bool, str]:
    """Return (path, must_delete, source_label)."""
    cached = _cached_image_path(card_id)
    if os.path.isfile(cached):
        return cached, False, "cache"

    if not need_sheet:
        raise FileNotFoundError(f"no cached image at {cached!r} and sheet not loaded")

    row = _row_by_id(rows, card_id)
    if row is None:
        raise LookupError(f"id {card_id!r} not found in Printable DB")
    url = _cell(row, COL_URL)
    if not url.startswith("http"):
        raise ValueError(f"id {card_id}: bad Url {url!r}")

    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    _download_image(url, tmp, http_timeout)
    return tmp, True, "download"


def _heuristics_only_review(image_path: str) -> ReviewResult:
    flags = heuristic_checks(image_path)
    verdict = "N" if flags else "Y"
    forced = f"issues/heuristics: {', '.join(flags)}" if flags else ""
    return ReviewResult(
        verdict=verdict,
        issues=list(flags),
        heuristic_flags=flags,
        forced_n_reason=forced,
    )


def _print_results_table(
    rows_out: list[tuple[str, str, str, bool, list[str], list[str]]],
) -> None:
    headers = ("id", "expected", "predicted", "match", "issues", "heuristics")
    str_rows = [
        (
            cid,
            expected,
            predicted,
            "Y" if match else "N",
            ",".join(issues) or "-",
            ",".join(heuristics) or "-",
        )
        for cid, expected, predicted, match, issues, heuristics in rows_out
    ]
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in str_rows:
        print(fmt.format(*row))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS),
        help="Service account JSON",
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
        help="0-based worksheet index",
    )
    parser.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help="Ollama base URL",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama vision model name",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=120.0,
        help="Timeout for image download and Ollama",
    )
    parser.add_argument(
        "--max-image-side",
        type=int,
        default=1280,
        help="Resize longer edge before QA (0 = no resize)",
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
        help="Base seconds for Sheets exponential backoff",
    )
    parser.add_argument(
        "--no-corner-crops",
        action="store_true",
        help="Send only the full image to the vision model",
    )
    parser.add_argument(
        "--single-step",
        action="store_true",
        help="Skip step-1 defect scan; use step-2 verdict only",
    )
    parser.add_argument(
        "--heuristics-only",
        action="store_true",
        help="Run PIL heuristics only (no Ollama)",
    )
    parser.add_argument(
        "--skip-ollama-check",
        action="store_true",
        help="Do not verify the model is pulled before starting",
    )
    args = parser.parse_args()

    ground_truth = benchmark_ground_truth()
    benchmark_ids = sorted(ground_truth.keys(), key=int)
    need_sheet = any(not os.path.isfile(_cached_image_path(cid)) for cid in benchmark_ids)

    if need_sheet:
        if not os.path.isfile(args.credentials):
            print(f"Missing credentials file: {args.credentials}", file=sys.stderr)
            sys.exit(1)
        sheet_rows = _load_printable_rows(
            credentials=args.credentials,
            sheet_key=args.sheet_key,
            worksheet=args.worksheet,
            api_retries=args.api_retries,
            retry_base_delay=args.retry_base_delay,
        )
    else:
        sheet_rows = []

    if not args.heuristics_only and not args.skip_ollama_check:
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
                    f"Model {args.model!r} not found. Run: ollama pull {args.model}",
                    file=sys.stderr,
                )
                sys.exit(1)
        except requests.RequestException as e:
            print(
                f"Cannot reach Ollama at {args.ollama_host}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    results: list[tuple[str, str, str, bool, list[str], list[str]]] = []
    errors = 0

    for card_id in benchmark_ids:
        expected = ground_truth[card_id]
        image_path = ""
        delete_image = False
        scaled_path = ""
        delete_scaled = False
        try:
            image_path, delete_image, source = _resolve_image_path(
                card_id,
                sheet_rows,
                http_timeout=args.http_timeout,
                need_sheet=need_sheet,
            )
            row = _row_by_id(sheet_rows, card_id) if sheet_rows else None
            card_name = _cell(row, COL_CARDNAME) if row else ""
            side_name = _cell(row, COL_SIDENAME) if row else ""

            vision_path = image_path
            if args.max_image_side > 0:
                vision_path, delete_scaled = resize_for_vision(image_path, args.max_image_side)
                scaled_path = vision_path if delete_scaled else ""

            if args.heuristics_only:
                review = _heuristics_only_review(vision_path)
            else:
                review = review_image(
                    image_path=vision_path,
                    card_id=card_id,
                    card_name=card_name,
                    side_name=side_name,
                    host=args.ollama_host,
                    model=args.model,
                    timeout=args.http_timeout,
                    use_corner_crops=not args.no_corner_crops,
                    two_step=not args.single_step,
                )

            predicted = review.verdict
            match = predicted == expected
            results.append(
                (
                    card_id,
                    expected,
                    predicted,
                    match,
                    list(review.issues),
                    list(review.heuristic_flags),
                )
            )
            print(
                f"id {card_id} ({source}): expected={expected} predicted={predicted} "
                f"match={'yes' if match else 'NO'}",
                file=sys.stderr,
            )
        except Exception as e:
            errors += 1
            print(f"id {card_id}: ERROR {e}", file=sys.stderr)
        finally:
            cleanup_temp_paths(scaled_path, image_path if delete_image else "")

    print()
    if results:
        _print_results_table(results)
        correct = sum(1 for *_, m, _, _ in results if m)
        total = len(results)
        pct = 100.0 * correct / total if total else 0.0
        print()
        print(f"Accuracy: {correct}/{total} ({pct:.0f}%)")
    if errors:
        print(f"Errors: {errors}", file=sys.stderr)

    if errors or not results:
        sys.exit(1)
    if all(m for *_, m, _, _ in results):
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
