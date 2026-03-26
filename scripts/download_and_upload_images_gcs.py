"""
Download token images from the Hellscube **Tokens Database** tab and upload them to GCS.

Source spreadsheet (same workbook as ``hc_constants.HELLSCUBE_DATABASE``):
https://docs.google.com/spreadsheets/d/1qqGCedHmQ8bwi-YFjmv-pNKKMjubZQUAaF7ItJN5d1g/edit?gid=2123813197

Expected columns (row 1 is headers; data from row 2):
  - **A** — Name (e.g. ``Angel1``, ``Ball1``)
  - **B** — Image (``https://lh3.googleusercontent.com/d/...`` or other HTTP(S) URL)

Other columns (Type, Power, Toughness, Related Cards, Notes, Creator) are not read or modified.

By default the worksheet is opened by tab id (``hc_constants.TOKEN_SHEET``) so the script
still works if the tab is renamed. Use ``--sheet-title`` to target a tab by name instead.

Writes the public GCS URL to column **B** by default (``--write-column`` to change), which
replaces the previous image link. Use a different ``--write-column`` if you want to keep the
original URL in column B.

Requires:
  - bot_secrets/client_secrets.json (same service account as shared_vars / gspread)
  - GCS bucket with object create permission for that account
  - Optional: make objects or the bucket publicly readable if consumers need anonymous GET
"""

from __future__ import annotations

import mork_repo_root  # noqa: E402

import argparse
import os
import re
import sys
import tempfile
import time
from urllib.parse import quote, unquote, urlparse

import requests
from google.cloud import storage

import hc_constants
from shared_vars import googleClient

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
DEFAULT_BUCKET = os.environ.get("GCS_TOKEN_BUCKET", "hellscube-token-images")


def _slug_for_gcs(name: str, row_1based: int) -> str:
    base = name.strip() or f"token_{row_1based}"
    base = base.replace("/", "|")
    base = re.sub(r"[^\w\-.]+", "_", base, flags=re.UNICODE)
    return f"{row_1based:05d}_{base[:180]}"


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


def _download(url: str, dest_path: str, timeout: int = 120) -> tuple[str, str]:
    headers = {
        "User-Agent": "MorkTokenImageSync/1.0 (+https://github.com/hellscube/mork)"
    }
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        ext = _guess_extension_from_response(resp, url)
        ct = resp.headers.get("Content-Type", "").split(";")[
            0
        ].strip() or _content_type_for_ext(ext)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    return ext, ct


def _public_gcs_url(bucket_name: str, object_name: str) -> str:
    return (
        f"https://storage.googleapis.com/{bucket_name}/{quote(object_name, safe='/')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS),
        help="Service account JSON path (defaults to GOOGLE_APPLICATION_CREDENTIALS or bot path)",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help="GCS bucket name (or set GCS_TOKEN_BUCKET)",
    )
    parser.add_argument(
        "--worksheet-gid",
        type=int,
        default=hc_constants.TOKEN_SHEET,
        help="Google Sheets tab gid from the URL (default: hc_constants.TOKEN_SHEET)",
    )
    parser.add_argument(
        "--sheet-title",
        default=None,
        metavar="NAME",
        help=(
            "If set, open this worksheet by title instead of by gid "
            f"(e.g. {hc_constants.TOKEN_SHEET!r})"
        ),
    )
    parser.add_argument(
        "--first-row",
        type=int,
        default=2,
        help="First 1-based sheet row (default 2 skips a header row)",
    )
    parser.add_argument(
        "--last-row",
        type=int,
        default=None,
        help="Last 1-based sheet row inclusive (default: end of data in A:B)",
    )
    parser.add_argument(
        "--write-column",
        type=int,
        default=2,
        help="1-based column index to write the GCS URL (default 2 = column B)",
    )
    parser.add_argument(
        "--prefix",
        default="tokens/",
        help="Object name prefix inside the bucket",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds to sleep between sheet rows (rate limiting)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not upload or update the sheet",
    )
    parser.add_argument(
        "--skip-if-gcs",
        action="store_true",
        help="Skip rows whose URL already points at this bucket",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.credentials):
        print(
            f"Missing credentials file: {args.credentials}",
            file=sys.stderr,
        )
        sys.exit(1)

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)
    client = storage.Client.from_service_account_json(args.credentials)
    bucket = client.bucket(args.bucket)

    workbook = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)
    if args.sheet_title:
        sheet = workbook.worksheet(args.sheet_title)
    else:
        sheet = workbook.get_worksheet_by_id(args.worksheet_gid)
    all_rows = sheet.get_values(f"A{args.first_row}:B")
    if not all_rows:
        print("No rows in range.")
        return

    last_idx = len(all_rows)
    if args.last_row is not None:
        end_rel = args.last_row - args.first_row + 1
        last_idx = min(last_idx, max(0, end_rel))

    prefix = args.prefix
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    for offset, row in enumerate(all_rows[:last_idx]):
        row_1based = args.first_row + offset
        name = row[0].strip() if len(row) > 0 and row[0] else ""
        url = row[1].strip() if len(row) > 1 and row[1] else ""
        if not url:
            continue
        if not url.startswith("http"):
            print(f"row {row_1based}: skip non-URL in column B: {url!r}")
            continue

        if args.skip_if_gcs and f"storage.googleapis.com/{args.bucket}/" in url:
            print(f"row {row_1based}: already GCS ({name})")
            continue

        slug = _slug_for_gcs(name, row_1based)
        if args.dry_run:
            print(
                f"row {row_1based}: DRY-RUN would download {url!r} then upload "
                f"{prefix}{slug}.<ext>"
            )
            continue

        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(prefix="mork_token_", delete=False) as tf:
                tmp_path = tf.name
            ext, _ = _download(url, tmp_path)
            object_name = f"{prefix}{slug}{ext}"
            gcs_url = _public_gcs_url(args.bucket, object_name)

            blob = bucket.blob(object_name)
            blob.upload_from_filename(tmp_path, content_type=_content_type_for_ext(ext))
            col_letter = _column_letter(args.write_column)
            sheet.update_acell(f"{col_letter}{row_1based}", gcs_url)
            print(f"row {row_1based}: uploaded {name!r} -> {gcs_url}")
        except Exception as e:
            print(f"row {row_1based}: ERROR {name!r}: {e}", file=sys.stderr)
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                os.remove(tmp_path)

        if args.sleep:
            time.sleep(args.sleep)


def _column_letter(n: int) -> str:
    """1 -> A, 2 -> B, ... 27 -> AA."""
    if n < 1:
        raise ValueError("column must be >= 1")
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


if __name__ == "__main__":
    main()
