"""
For each row in the "Printable Fuckups" sheet with a Drive "Fixed file URL":

1. Download the file from Google Drive (service account must have access).
2. Upload to GCS bucket ``hellscube-printable-images``, replacing the object named
   by the existing Printable DB URL for that card (``Cardname.png-{id}-side N``).
3. Set Fuckups column ``Updated? (leave for sixel)`` to TRUE.
4. Set Printable DB ``Is good?`` to ``Y - Fixed`` for the matched row.

Split cards (same Id, multiple sides): Fuckups rows are paired to Printable DB rows
in **sheet order** for that Id with sides ordered ``side 1``, ``side 2``, … — keep
Fuckups rows in the same order as sides if both sides were fixed.

Requires: ``bot_secrets/client_secrets.json`` (same as ``shared_vars``), GCS write
access on the bucket, and sheet/Drive access for the service account.

Sheets/Drive calls use retries with backoff on 429/503/quota errors, plus configurable
pauses (``--sleep``, ``--after-read``, ``--after-drive``, ``--after-sheet-write``).

Use ``--limit 1`` (with or without ``--dry-run``) to exercise a single pending row first.
Already-updated rows still run queue sync and do not count toward the limit.

Rows whose column D (Weird Shaped) is ``Split`` are skipped when still pending (no
upload); if that row is already marked updated, queue sync still runs once so order
stays consistent on reruns.
"""

from __future__ import annotations

import mork_repo_root  # noqa: E402

import argparse
import os
import random
import re
import sys
import tempfile
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import unquote, urlparse

from google.cloud import storage
from gspread.exceptions import APIError
from PIL import Image

from shared_vars import drive, googleClient

T = TypeVar("T")

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
DEFAULT_BUCKET = os.environ.get("GCS_PRINTABLE_BUCKET", "hellscube-printable-images")

FUCKUPS_SPREADSHEET_KEY = "1Wm9gfLxu2-f_WMCWrqGu5PeSG5GKI1GYkR5vwilquBw"
PRINTABLE_DB_SPREADSHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"

# 1-based column indices (row 1 = header)
FUCKUPS_COL_CARD_ID = 1
FUCKUPS_COL_FIXED_URL = 2
FUCKUPS_COL_WEIRD_SHAPED = 4
FUCKUPS_COL_UPDATED = 5

PRINTABLE_COL_ID = 1
PRINTABLE_COL_SIDENAME = 3
PRINTABLE_COL_URL = 4
PRINTABLE_COL_IS_GOOD = 5
PRINTABLE_IS_GOOD_FIXED = "Y - Fixed"


def _column_letter(n: int) -> str:
    if n < 1:
        raise ValueError("column must be >= 1")
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _drive_file_id_from_url(url: str) -> str | None:
    url = (url or "").strip()
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def _gcs_object_from_public_url(url: str, bucket: str) -> str | None:
    url = (url or "").strip()
    if not url.startswith("http"):
        return None
    p = urlparse(url)
    if p.netloc != "storage.googleapis.com":
        return None
    path = unquote(p.path or "")
    prefix = f"/{bucket}/"
    if not path.startswith(prefix):
        return None
    return path[len(prefix) :].lstrip("/")


def _side_sort_key(sidename: str) -> int:
    m = re.search(r"(\d+)", sidename or "")
    return int(m.group(1)) if m else 999


def _truthy_cell(val: str) -> bool:
    v = (val or "").strip().upper()
    return v in ("TRUE", "Y", "YES", "1", "X", "✓")


def _fuckups_row_is_split_weird_shaped(weird_shaped_col: str) -> bool:
    return (weird_shaped_col or "").strip().casefold() == "split"


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


def _pause(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _download_drive_to_temp(file_id: str) -> str:
    f = drive.CreateFile({"id": file_id})
    suffix = ".bin"
    title = (f.get("title") or "") or ""
    ext = os.path.splitext(title)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        suffix = ext if ext != ".jpeg" else ".jpg"
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    f.GetContentFile(path)
    return path


def _to_png_for_upload(src_path: str, dest_png: str) -> None:
    with Image.open(src_path) as im:
        if im.mode == "P" and "transparency" in im.info:
            im = im.convert("RGBA")
        elif im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        im.save(dest_png, "PNG")


def _build_printable_queues(
    printable_ws,
    bucket: str,
) -> dict[str, deque[tuple[int, str, str]]]:
    """
    card_id -> deque of (sheet_row_1based, gcs_object_name, public_url) in side order.
    """
    all_rows = printable_ws.get_all_values()
    if not all_rows:
        return {}
    by_id: dict[str, list[tuple[int, str, str, str]]] = defaultdict(list)
    for row_1based, row in enumerate(all_rows[1:], start=2):
        if not row or not str(row[PRINTABLE_COL_ID - 1]).strip():
            continue
        cid = str(row[PRINTABLE_COL_ID - 1]).strip()
        sidename = (
            row[PRINTABLE_COL_SIDENAME - 1] if len(row) >= PRINTABLE_COL_SIDENAME else ""
        )
        url = row[PRINTABLE_COL_URL - 1] if len(row) >= PRINTABLE_COL_URL else ""
        url = (url or "").strip()
        if not url:
            continue
        obj = _gcs_object_from_public_url(url, bucket)
        if not obj:
            continue
        by_id[cid].append((row_1based, str(sidename), url, obj))

    out: dict[str, deque[tuple[int, str, str]]] = {}
    for cid, items in by_id.items():
        items.sort(key=lambda t: _side_sort_key(t[1]))
        out[cid] = deque((t[0], t[3], t[2]) for t in items)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS),
        help="Service account JSON (sets GOOGLE_APPLICATION_CREDENTIALS if unset)",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help="GCS bucket (default: hellscube-printable-images or GCS_PRINTABLE_BUCKET)",
    )
    parser.add_argument(
        "--fuckups-key",
        default=FUCKUPS_SPREADSHEET_KEY,
        help="Printable Fuckups spreadsheet id",
    )
    parser.add_argument(
        "--printable-key",
        default=PRINTABLE_DB_SPREADSHEET_KEY,
        help="Printable DB spreadsheet id",
    )
    parser.add_argument(
        "--fuckups-worksheet",
        default=0,
        type=int,
        help="0-based worksheet index for Fuckups (default 0 = gid=0)",
    )
    parser.add_argument(
        "--printable-worksheet",
        default=0,
        type=int,
        help="0-based worksheet index for Printable DB (default 0)",
    )
    parser.add_argument(
        "--first-row",
        type=int,
        default=2,
        help="First 1-based data row on Fuckups sheet (default 2)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.2,
        help="Seconds between rows after each processed/skipped row (rate limiting)",
    )
    parser.add_argument(
        "--after-read",
        type=float,
        default=0.45,
        help="Seconds to sleep after each Google Sheets read (get_values / get_all_values)",
    )
    parser.add_argument(
        "--after-drive",
        type=float,
        default=0.65,
        help="Seconds to sleep after each Drive file download",
    )
    parser.add_argument(
        "--after-sheet-write",
        type=float,
        default=1.15,
        help="Seconds to sleep after each Sheets update_acell (two writes per upload)",
    )
    parser.add_argument(
        "--api-retries",
        type=int,
        default=6,
        help="Max attempts for retryable Google API errors (429/503/quota)",
    )
    parser.add_argument(
        "--retry-base-delay",
        type=float,
        default=2.5,
        help="Base seconds for exponential backoff (doubled each retry, plus jitter)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No Drive download, GCS upload, or sheet writes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Process rows even if Updated? already looks true",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Process at most N pending rows (Drive→GCS+sheet); 0 = no limit. "
        "Sync-only rows for already-updated lines still run first.",
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

    fuckups_sh = _google_call_with_retry(
        lambda: googleClient.open_by_key(args.fuckups_key),
        what="open Fuckups spreadsheet",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    printable_sh = _google_call_with_retry(
        lambda: googleClient.open_by_key(args.printable_key),
        what="open Printable DB spreadsheet",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    fuckups_ws = _google_call_with_retry(
        lambda: fuckups_sh.get_worksheet(args.fuckups_worksheet),
        what="open Fuckups worksheet",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    printable_ws = _google_call_with_retry(
        lambda: printable_sh.get_worksheet(args.printable_worksheet),
        what="open Printable worksheet",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )

    queues_template = _google_call_with_retry(
        lambda: _build_printable_queues(printable_ws, args.bucket),
        what="Printable DB get_all_values",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    _pause(args.after_read)
    if not queues_template:
        print(
            "Warning: no Printable DB rows with GCS URLs for this bucket; "
            "check worksheet index and bucket name.",
            file=sys.stderr,
        )
    # Mutable copy so dry-run and skip-sync behave like a real pass.
    qmap: dict[str, deque[tuple[int, str, str]]] = {
        k: deque(list(v)) for k, v in queues_template.items()
    }

    gcs_client = storage.Client.from_service_account_json(args.credentials)
    bucket = gcs_client.bucket(args.bucket)

    last_col = max(
        FUCKUPS_COL_CARD_ID,
        FUCKUPS_COL_FIXED_URL,
        FUCKUPS_COL_WEIRD_SHAPED,
        FUCKUPS_COL_UPDATED,
    )
    col_a = _column_letter(1)
    col_end = _column_letter(last_col)
    range_a1 = f"{col_a}{args.first_row}:{col_end}"
    fuckups_rows = _google_call_with_retry(
        lambda: fuckups_ws.get_values(range_a1),
        what=f"Fuckups get_values {range_a1}",
        max_tries=args.api_retries,
        base_delay=args.retry_base_delay,
    )
    _pause(args.after_read)
    if not fuckups_rows:
        print("No Fuckups rows in range.")
        return

    updated_col_letter = _column_letter(FUCKUPS_COL_UPDATED)
    is_good_col_letter = _column_letter(PRINTABLE_COL_IS_GOOD)

    pending_handled = 0

    for offset, row in enumerate(fuckups_rows):
        row_1based = args.first_row + offset
        card_id = (
            row[FUCKUPS_COL_CARD_ID - 1].strip()
            if len(row) >= FUCKUPS_COL_CARD_ID
            else ""
        )
        fixed_url = (
            row[FUCKUPS_COL_FIXED_URL - 1].strip()
            if len(row) >= FUCKUPS_COL_FIXED_URL
            else ""
        )
        updated_cell = (
            row[FUCKUPS_COL_UPDATED - 1].strip()
            if len(row) >= FUCKUPS_COL_UPDATED
            else ""
        )
        weird_shaped = (
            row[FUCKUPS_COL_WEIRD_SHAPED - 1].strip()
            if len(row) >= FUCKUPS_COL_WEIRD_SHAPED
            else ""
        )

        if not fixed_url or not fixed_url.startswith("http"):
            continue
        if not card_id:
            print(f"row {row_1based}: skip empty card id", file=sys.stderr)
            continue

        is_split = _fuckups_row_is_split_weird_shaped(weird_shaped)
        already_done = _truthy_cell(updated_cell) and not args.force

        if is_split and not already_done:
            q = qmap.get(card_id)
            if not q:
                print(
                    f"row {row_1based}: no Printable DB GCS row for id {card_id!r} "
                    f"(also column D is Split; skipped)",
                    file=sys.stderr,
                )
            else:
                print(
                    f"row {row_1based}: skip (column D is Split) id {card_id!r}",
                    file=sys.stderr,
                )
            if args.sleep:
                time.sleep(args.sleep)
            continue

        file_id = _drive_file_id_from_url(fixed_url)
        if not file_id:
            print(
                f"row {row_1based}: could not parse Drive file id from {fixed_url!r}",
                file=sys.stderr,
            )
            continue

        q = qmap.get(card_id)
        if not q:
            print(
                f"row {row_1based}: no Printable DB GCS row for id {card_id!r}",
                file=sys.stderr,
            )
            continue

        if already_done:
            if args.dry_run:
                print(f"row {row_1based}: DRY-RUN sync queue (already updated) id {card_id!r}")
            if q:
                q.popleft()
            else:
                print(
                    f"row {row_1based}: warning — already updated but no queue entry "
                    f"left for id {card_id!r}",
                    file=sys.stderr,
                )
            if args.sleep:
                time.sleep(args.sleep)
            continue

        if args.limit and pending_handled >= args.limit:
            print(
                f"Stopping: --limit {args.limit} pending row(s) already handled",
                file=sys.stderr,
            )
            break

        if args.dry_run:
            printable_row, object_name, _public_url = q[0]
            print(
                f"row {row_1based}: DRY-RUN card {card_id} -> GCS {object_name!r} "
                f"(Printable row {printable_row}, Drive {file_id})"
            )
            pending_handled += 1
            if args.sleep:
                time.sleep(args.sleep)
            if args.limit and pending_handled >= args.limit:
                print(
                    f"Stopping: --limit {args.limit} reached",
                    file=sys.stderr,
                )
                break
            continue

        printable_row, object_name, _public_url = q.popleft()

        tmp_download = ""
        tmp_png = ""
        try:
            tmp_download = _google_call_with_retry(
                lambda: _download_drive_to_temp(file_id),
                what=f"Drive GetContentFile {file_id}",
                max_tries=args.api_retries,
                base_delay=args.retry_base_delay,
            )
            _pause(args.after_drive)
            fd, tmp_png = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            _to_png_for_upload(tmp_download, tmp_png)

            blob = bucket.blob(object_name)
            blob.upload_from_filename(tmp_png, content_type="image/png")

            _google_call_with_retry(
                lambda: fuckups_ws.update_acell(
                    f"{updated_col_letter}{row_1based}", "TRUE"
                ),
                what=f"Sheets update Fuckups {updated_col_letter}{row_1based}",
                max_tries=args.api_retries,
                base_delay=args.retry_base_delay,
            )
            _pause(args.after_sheet_write)
            _google_call_with_retry(
                lambda: printable_ws.update_acell(
                    f"{is_good_col_letter}{printable_row}", PRINTABLE_IS_GOOD_FIXED
                ),
                what=f"Sheets update Printable {is_good_col_letter}{printable_row}",
                max_tries=args.api_retries,
                base_delay=args.retry_base_delay,
            )
            _pause(args.after_sheet_write)

            print(
                f"row {row_1based}: uploaded id {card_id} -> {object_name!r} "
                f"(Printable row {printable_row} Is good?={PRINTABLE_IS_GOOD_FIXED!r})"
            )
            pending_handled += 1
            if args.limit and pending_handled >= args.limit:
                print(
                    f"Stopping: --limit {args.limit} reached",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"row {row_1based}: ERROR id {card_id!r}: {e}", file=sys.stderr)
            q.appendleft((printable_row, object_name, _public_url))
        finally:
            for p in (tmp_download, tmp_png):
                if p and os.path.isfile(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

        if args.sleep:
            time.sleep(args.sleep)

        if args.limit and pending_handled >= args.limit:
            break


if __name__ == "__main__":
    main()
