"""
Migrate token images from the Hellscube **Tokens Database** tab: Drive/lh3 → GCS.

Source spreadsheet (``hc_constants.HELLSCUBE_DATABASE``):
https://docs.google.com/spreadsheets/d/1qqGCedHmQ8bwi-YFjmv-pNKKMjubZQUAaF7ItJN5d1g/edit?gid=2123813197

For each row (default from row 2):
  1. Download the image from column B (lh3/Drive URL; HTTP first, Drive API fallback).
  2. Upload to GCS (``hellscube-token-images`` by default).
  3. Write the public GCS URL to column B and sync Hellfall (card DB) via postcard API.

Drive files are **not** deleted.

Expected columns (row 1 is headers):
  - **A** — Name (e.g. ``Angel1``)
  - **B** — Image URL
  - **H** — Creator (used for Hellfall sync; optional but recommended)

Requires:
  - ``bot_secrets/client_secrets.json`` (gspread + Drive + GCS)
  - GCS bucket write access; objects should be publicly readable for consumers
  - For Hellfall sync: ``HELLFALL_API_URL`` and ``HELLFALL_POSTCARD_API_KEY``
"""

from __future__ import annotations

import mork_repo_root  # noqa: E402

import argparse
import asyncio
import os
import random
import re
import sys
import tempfile
import time
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import quote, unquote, urlparse

import requests
from google.cloud import storage
from gspread.exceptions import APIError

import hc_constants
from hellfall_postcard import PostcardSyncError, sync_accepted_card
from shared_vars import drive, googleClient

T = TypeVar("T")

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
DEFAULT_BUCKET = os.environ.get("GCS_TOKEN_BUCKET", "hellscube-token-images")
TOKEN_SET_ID = "HCT"
LH3_PREFIX = "https://lh3.googleusercontent.com/d/"


def _slug_for_gcs(name: str, row_1based: int) -> str:
    base = name.strip() or f"token_{row_1based}"
    base = base.replace("/", "|")
    base = re.sub(r"[^\w\-.]+", "_", base, flags=re.UNICODE)
    return f"{row_1based:05d}_{base[:180]}"


def _drive_id_from_url(url: str) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith(LH3_PREFIX):
        return url.removeprefix(LH3_PREFIX).split("/")[0].split("?")[0] or None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def _guess_extension_from_response(resp: requests.Response, url: str) -> str:
    cd = resp.headers.get("Content-Disposition") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd, re.I)
    if m:
        fname = unquote(m.group(1).strip('"'))
        if "." in fname:
            return os.path.splitext(fname)[1].lower() or ".png"
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return ext if ext != ".jpeg" else ".jpg"
    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if "png" in ctype:
        return ".png"
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "webp" in ctype:
        return ".webp"
    return ".png"


def _content_type_for_ext(ext: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext.lower(), "application/octet-stream")


def _guess_extension_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return ext if ext != ".jpeg" else ".jpg"
    return ".png"


def _download_http(url: str, dest_path: str, timeout: int = 120) -> str:
    headers = {
        "User-Agent": "MorkTokenImageSync/1.0 (+https://github.com/hellscube/mork)"
    }
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        ext = _guess_extension_from_response(resp, url)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    return ext


def _download_drive(file_id: str) -> tuple[str, str]:
    f = drive.CreateFile({"id": file_id})
    suffix = ".bin"
    title = (f.get("title") or "") or ""
    ext = os.path.splitext(title)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        suffix = ext if ext != ".jpeg" else ".jpg"
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    f.GetContentFile(path)
    return path, _guess_extension_from_path(path)


def _download_image(url: str) -> tuple[str, str]:
    """Return (temp_path, extension). Caller must remove temp_path."""
    with tempfile.NamedTemporaryFile(prefix="mork_token_", delete=False) as tf:
        tmp_path = tf.name
    try:
        ext = _download_http(url, tmp_path)
        return tmp_path, ext
    except Exception as http_err:
        file_id = _drive_id_from_url(url)
        if not file_id:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
            raise http_err
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
        path, ext = _download_drive(file_id)
        return path, ext


def _public_gcs_url(bucket_name: str, object_name: str) -> str:
    return (
        f"https://storage.googleapis.com/{bucket_name}/{quote(object_name, safe='/')}"
    )


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


def _column_letter(n: int) -> str:
    if n < 1:
        raise ValueError("column must be >= 1")
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(row: list[str], col_1based: int) -> str:
    idx = col_1based - 1
    if idx < 0 or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


async def _sync_token_to_hellfall(
    *,
    name: str,
    gcs_url: str,
    creators: str,
) -> None:
    await sync_accepted_card(
        name=name,
        image=gcs_url,
        creators=creators or "unknown",
        set_id=TOKEN_SET_ID,
        hcid=name,
        kind="token",
        require_sync=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS),
        help="Service account JSON path",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help="GCS bucket name (or set GCS_TOKEN_BUCKET)",
    )
    parser.add_argument(
        "--sheet-title",
        default=hc_constants.TOKEN_SHEET,
        help=f"Worksheet title (default: {hc_constants.TOKEN_SHEET!r})",
    )
    parser.add_argument(
        "--worksheet-gid",
        type=int,
        default=None,
        help=f"Open tab by gid instead of title (default gid: {hc_constants.TOKEN_SHEET_GID})",
    )
    parser.add_argument(
        "--first-row",
        type=int,
        default=2,
        help="First 1-based sheet row (default 2 skips header)",
    )
    parser.add_argument(
        "--last-row",
        type=int,
        default=None,
        help="Last 1-based sheet row inclusive",
    )
    parser.add_argument(
        "--write-column",
        type=int,
        default=2,
        help="1-based column for GCS URL (default 2 = column B)",
    )
    parser.add_argument(
        "--creator-column",
        type=int,
        default=8,
        help="1-based column for creator name (default 8 = column H)",
    )
    parser.add_argument(
        "--prefix",
        default="tokens/",
        help="GCS object name prefix",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds between rows (rate limiting)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without uploading or writing",
    )
    parser.add_argument(
        "--skip-if-gcs",
        action="store_true",
        help="Skip rows whose image URL already points at this bucket",
    )
    parser.add_argument(
        "--sync-hellfall",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Update Hellfall card DB via postcard API after GCS upload (default: on)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N rows needing migration (0 = no limit)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.credentials):
        print(f"Missing credentials file: {args.credentials}", file=sys.stderr)
        sys.exit(1)

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)
    client = storage.Client.from_service_account_json(args.credentials)
    bucket = client.bucket(args.bucket)

    workbook = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)
    if args.worksheet_gid is not None:
        sheet = workbook.get_worksheet_by_id(args.worksheet_gid)
    else:
        sheet = workbook.worksheet(args.sheet_title)

    max_col = max(args.write_column, args.creator_column, 2)
    col_letter_end = _column_letter(max_col)
    if args.last_row:
        cell_range = f"A{args.first_row}:{col_letter_end}{args.last_row}"
    else:
        cell_range = f"A{args.first_row}:{col_letter_end}"
    all_rows = sheet.get_values(cell_range)
    if not all_rows:
        print("No rows in range.")
        return

    prefix = args.prefix
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    migrated = 0
    for offset, row in enumerate(all_rows):
        if args.limit and migrated >= args.limit:
            break

        row_1based = args.first_row + offset
        name = _cell(row, 1)
        url = _cell(row, args.write_column)
        creator = _cell(row, args.creator_column)

        if not url:
            continue
        if not url.startswith("http"):
            print(f"row {row_1based}: skip non-URL: {url!r}")
            continue

        if args.skip_if_gcs and f"storage.googleapis.com/{args.bucket}/" in url:
            print(f"row {row_1based}: already GCS ({name})")
            continue

        slug = _slug_for_gcs(name, row_1based)
        if args.dry_run:
            hellfall_note = " + Hellfall sync" if args.sync_hellfall else ""
            print(
                f"row {row_1based}: DRY-RUN would download {url!r} → "
                f"gs://{args.bucket}/{prefix}{slug}.<ext> → sheet col "
                f"{_column_letter(args.write_column)}{hellfall_note}"
            )
            migrated += 1
            continue

        tmp_path = ""
        try:
            tmp_path, ext = _download_image(url)
            object_name = f"{prefix}{slug}{ext}"
            gcs_url = _public_gcs_url(args.bucket, object_name)

            blob = bucket.blob(object_name)
            blob.upload_from_filename(tmp_path, content_type=_content_type_for_ext(ext))

            col_letter = _column_letter(args.write_column)
            _google_call_with_retry(
                lambda: sheet.update_acell(f"{col_letter}{row_1based}", gcs_url),
                what=f"row {row_1based} sheet write",
                max_tries=5,
                base_delay=2.0,
            )
            print(f"row {row_1based}: uploaded {name!r} -> {gcs_url}")

            if args.sync_hellfall:
                try:
                    asyncio.run(
                        _sync_token_to_hellfall(
                            name=name,
                            gcs_url=gcs_url,
                            creators=creator,
                        )
                    )
                    print(f"row {row_1based}: Hellfall synced")
                except PostcardSyncError as e:
                    print(
                        f"row {row_1based}: Hellfall sync failed (sheet/GCS ok): {e}",
                        file=sys.stderr,
                    )

            migrated += 1
        except Exception as e:
            print(f"row {row_1based}: ERROR {name!r}: {e}", file=sys.stderr)
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                os.remove(tmp_path)

        if args.sleep:
            time.sleep(args.sleep)

    print(f"Done. Migrated {migrated} row(s).")


if __name__ == "__main__":
    main()
