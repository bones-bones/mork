"""
Sync Hellscube images to Google Cloud Storage from two sheet flows (run in parallel by default).

**Tokens** — [Tokens Database](https://docs.google.com/spreadsheets/d/1qqGCedHmQ8bwi-YFjmv-pNKKMjubZQUAaF7ItJN5d1g/edit?gid=2123813197)
tab (cols A=name, B=image URL). Uploads raw images to the token bucket and writes the GCS URL
back to column B (or ``--write-column``).

**Printable** — Hellscube **Database** tab → border prep (arc-aware edge stretch from
``prepare_card_for_printing_stretch``) → ``hellscube-printable-images`` GCS →
append or update rows on the [Printable DB](https://docs.google.com/spreadsheets/d/1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs/edit?gid=0)
sheet: missing sides are appended; when a new side 2+ appears, side 1 is
re-processed in place too. With ``--assess`` (default ``auto``: on when
Ollama is reachable), each prepared card gets a vision QA verdict written to the
appended row (``Is good?`` E, ``Bot?`` F, ``Bot comment`` G).

Use ``--tokens-only`` or ``--printable-only`` to run one flow. Default runs both concurrently
(two threads; sheet API calls are serialized with a lock).

Requires:
  - bot_secrets/client_secrets.json (same service account as shared_vars / gspread)
  - GCS buckets with object create permission for that account
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import random
import re
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TypeVar, cast
from urllib.parse import quote, unquote, urlparse

import mork_repo_root  # noqa: F401
import requests
import urllib3
from google.cloud import storage
from gspread.exceptions import APIError
from PIL import Image

from image_response_filename import extension_from_image_bytes

T = TypeVar("T")

# Prefer scripts/ over any repo-root shadow copies of sibling modules.
_scripts = str(Path(__file__).resolve().parent)
if _scripts in sys.path:
    sys.path.remove(_scripts)
sys.path.insert(0, _scripts)

from prepare_card_for_printing_stretch import prepare_card_for_printing_stretch
from printable_image_qa import (
    cleanup_temp_paths,
    format_assessment_comment,
    resize_for_vision,
    review_image,
    supertypes_include_legendary,
    types_include_plane,
)

import hc_constants
from shared_vars import googleClient

DEFAULT_CREDENTIALS = "./bot_secrets/client_secrets.json"
DEFAULT_TOKEN_BUCKET = os.environ.get("GCS_TOKEN_BUCKET", "hellscube-token-images")
DEFAULT_PRINTABLE_BUCKET = os.environ.get("GCS_PRINTABLE_BUCKET", "hellscube-printable-images")
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
PRINTABLE_DB_SPREADSHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"
SOURCE_SHEET_NAME = "Database"
GCS_OBJECT_NAME_MAX = 1024
LOCAL_FILENAME_MAX = 255  # macOS NAME_MAX for a single path component
DEFAULT_BAD_URL_LOG = Path("scripts/data/bad_printable_urls.jsonl")
_DB_PRIMARY_URL_COL = 3  # C
_DB_SIDE_URL_COL = {0: 20, 1: 32, 2: 42, 3: 52}  # T, AF, AP, AZ
_PRINTABLE_URL_COL = 4  # Printable DB column D

_print_lock = threading.Lock()


def _log(tag: str, message: str, *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    with _print_lock:
        print(f"[{tag}] {message}", file=stream)


def _is_retryable_google_error(exc: BaseException) -> bool:
    """True for quota/5xx Sheets errors and transient connection drops."""
    if isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            http.client.RemoteDisconnected,
            urllib3.exceptions.ProtocolError,
            urllib3.exceptions.HTTPError,
        ),
    ):
        return True
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
            "connection aborted",
            "remote end closed",
            "connection reset",
            "temporarily unavailable",
        )
    )


def _google_call_with_retry(
    fn: Callable[[], T],
    *,
    what: str,
    max_tries: int = 6,
    base_delay: float = 2.0,
    log_tag: str | None = None,
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
            msg = (
                f"{what}: retryable error ({e!s}); sleeping {wait:.1f}s "
                f"(attempt {attempt + 1}/{max_tries})"
            )
            if log_tag:
                _log(log_tag, msg, err=True)
            else:
                print(msg, file=sys.stderr, flush=True)
            time.sleep(wait)
    assert last is not None
    raise last


def _truncate_utf8(s: str, max_bytes: int) -> str:
    raw = s.encode("utf-8")
    if len(raw) <= max_bytes:
        return s
    return raw[:max_bytes].decode("utf-8", errors="ignore")


def _safe_card_filename(
    card_id: str,
    name: str,
    side_tag: str,
    *,
    label: str,
) -> str:
    """Build ``{id}_{name}_{side}_{label}.png`` within ``LOCAL_FILENAME_MAX`` bytes."""
    safe_name = name.replace("/", "|")
    suffix = f"_{side_tag}_{label}.png"
    prefix = f"{card_id}_"
    budget = LOCAL_FILENAME_MAX - len((prefix + suffix).encode("utf-8"))
    budget = max(budget, 1)
    safe_name = _truncate_utf8(safe_name, budget)
    return f"{prefix}{safe_name}{suffix}"


def _printable_object_key(local_name: str, card_id: str, side_index: int) -> str:
    """GCS object name for a printable side; truncates long card names to fit the 1024-char limit."""
    suffix = f"-{card_id}-side {side_index + 1}"
    max_name_len = GCS_OBJECT_NAME_MAX - len(suffix)
    if max_name_len < 1:
        raise ValueError(f"card_id suffix too long for GCS: {suffix!r}")
    name = local_name if len(local_name) <= max_name_len else local_name[:max_name_len]
    return f"{name}{suffix}"


def _database_url_col_1based(side_idx: int, *, uses_primary: bool) -> int:
    if uses_primary:
        return _DB_PRIMARY_URL_COL
    return _DB_SIDE_URL_COL[side_idx]


def _is_plausible_image_url(url: str) -> bool:
    url = (url or "").strip()
    if not url or url.startswith(('"', "'")):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    path = (parsed.path or "").rstrip("/")
    if path in ("", "/"):
        return False
    if "googleusercontent.com" in parsed.netloc.lower() and path.endswith("/d"):  # noqa: SIM103
        return False
    return True


def _append_bad_url_log(
    log_path: Path,
    *,
    card_id: str,
    name: str,
    side_num: int,
    url: str,
    error: str,
    db_row: int,
    db_col: str,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "card_id": str(card_id),
        "name": name,
        "side": side_num,
        "url": url,
        "error": error,
        "db_row": db_row,
        "db_col": db_col,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _clear_printable_url_cell(
    worksheet,
    row_1based: int,
    *,
    sheet_lock: threading.Lock | None,
    log_tag: str,
    dry_run: bool,
) -> None:
    cell = f"{_column_letter(_PRINTABLE_URL_COL)}{row_1based}"
    if dry_run:
        _log(log_tag, f"DRY-RUN would clear Printable DB {cell}")
        return

    def _clear() -> None:
        worksheet.update_acell(cell, "")

    if sheet_lock is not None:
        with sheet_lock:
            _google_call_with_retry(
                _clear,
                what=f"clear Printable DB {cell}",
                log_tag=log_tag,
            )
    else:
        _google_call_with_retry(
            _clear,
            what=f"clear Printable DB {cell}",
            log_tag=log_tag,
        )
    _log(log_tag, f"cleared bad URL from Printable DB {cell}")


def _handle_bad_printable_url(
    *,
    log_path: Path,
    log_tag: str,
    dry_run: bool,
    card_id: str,
    name: str,
    side_num: int,
    side_idx: int,
    uses_primary: bool,
    db_row: int,
    url: str,
    error: str,
    printable_sheet=None,
    printable_row: int | None = None,
    sheet_lock: threading.Lock | None = None,
) -> None:
    col = _database_url_col_1based(side_idx, uses_primary=uses_primary)
    col_letter = _column_letter(col)
    _append_bad_url_log(
        log_path,
        card_id=str(card_id),
        name=name,
        side_num=side_num,
        url=url,
        error=error,
        db_row=db_row,
        db_col=col_letter,
    )
    if printable_sheet is not None and printable_row is not None:
        _log(
            log_tag,
            f"bad URL {name!r} side {side_num}: {error} "
            f"(logged; clearing Printable DB D{printable_row}; "
            f"Database source was {col_letter}{db_row})",
            err=True,
        )
        _clear_printable_url_cell(
            printable_sheet,
            printable_row,
            sheet_lock=sheet_lock,
            log_tag=log_tag,
            dry_run=dry_run,
        )
    else:
        _log(
            log_tag,
            f"bad URL {name!r} side {side_num}: {error} "
            f"(logged; Database source {col_letter}{db_row} left unchanged)",
            err=True,
        )


def _download_printable_image(
    url: str,
    dest_path: str,
    *,
    log_tag: str = "printable",
    max_attempts: int = 2,
) -> None:
    """Download side art; retry once on corrupt/unopenable bytes (not on HTTP errors)."""
    last: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(response.content)
            with Image.open(dest_path) as im:
                im.load()
            return
        except requests.RequestException:
            raise
        except (OSError, Image.UnidentifiedImageError) as e:
            last = e
            if attempt >= max_attempts - 1:
                raise
            _log(
                log_tag,
                f"corrupt download, retrying ({attempt + 2}/{max_attempts}): {e}",
                err=True,
            )
            time.sleep(1.0)
    if last is not None:
        raise last


def _slug_for_gcs(name: str, row_1based: int) -> str:
    base = name.strip() or f"token_{row_1based}"
    base = base.replace("/", "|")
    base = re.sub(r"[^\w\-.]+", "_", base, flags=re.UNICODE)
    return f"{row_1based:05d}_{base[:180]}"


def _token_is_from_scryfall(url: str, tags: str) -> bool:
    """True when the image is Scryfall-hosted or tagged ``uses-scryfall-image``."""
    if "scryfall" in (url or "").lower():
        return True
    return "uses-scryfall-image" in (tags or "").lower()


def _guess_extension_from_response(resp: requests.Response, url: str) -> str:
    cd = resp.headers.get("Content-Disposition") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd, re.IGNORECASE)
    if m:
        fname = unquote(m.group(1).strip('"'))
        if "." in fname:
            return os.path.splitext(fname)[1].lower() or ".png"
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return ext if ext != ".jpeg" else ".jpg"
    ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if "gif" in ctype:
        return ".gif"
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
    headers = {"User-Agent": "MorkTokenImageSync/1.0 (+https://github.com/hellscube/mork)"}
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        ext = _guess_extension_from_response(resp, url)
        ct = resp.headers.get("Content-Type", "").split(";")[0].strip() or _content_type_for_ext(
            ext
        )
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    with open(dest_path, "rb") as f:
        sniffed = extension_from_image_bytes(f.read(16))
    if sniffed:
        ext = sniffed
        ct = _content_type_for_ext(ext)
    return ext, ct


def _public_gcs_url(bucket_name: str, object_name: str) -> str:
    return f"https://storage.googleapis.com/{bucket_name}/{quote(object_name, safe='/')}"


def _column_letter(n: int) -> str:
    """1 -> A, 2 -> B, ... 27 -> AA."""
    if n < 1:
        raise ValueError("column must be >= 1")
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def prepare_card_for_printing(
    image_path: str,
    *,
    log_tag: str = "printable",
    force_landscape: bool = False,
) -> str:
    """Border-expand a card image (arc-aware edge stretch); saves as PNG beside the input path."""
    base, _ext = os.path.splitext(image_path)
    new_path = f"{base}.png"
    prepare_card_for_printing_stretch(
        image_path,
        out_path=new_path,
        log_tag=log_tag,
        force_landscape=force_landscape,
    )
    return new_path


def _ollama_reachable(host: str, timeout: float = 3.0) -> bool:
    try:
        return requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout).ok
    except requests.RequestException:
        return False


def assess_prepared_card(
    prepared_path: str,
    *,
    card_id: str,
    card_name: str,
    side_name: str,
    args: argparse.Namespace,
    landscape_ok: bool = False,
    legendary_ok: bool = False,
) -> tuple[str, str, str]:
    """Vision + heuristic QA on a prepared PNG → (``Is good?``, ``Bot?``, comment)."""
    vision_path, resized = resize_for_vision(prepared_path, args.assess_max_image_side)
    try:
        review = review_image(
            image_path=vision_path,
            card_id=card_id,
            card_name=card_name,
            side_name=side_name,
            host=args.ollama_host,
            model=args.vision_model,
            timeout=120,
            temperature=0.0,
            use_corner_crops=True,
            two_step=True,
            landscape_ok=landscape_ok,
            legendary_ok=legendary_ok,
        )
    finally:
        if resized:
            cleanup_temp_paths(vision_path)
    return review.verdict, "bot", format_assessment_comment(review)


def run_tokens(
    args: argparse.Namespace,
    *,
    sheet_lock: threading.Lock,
    storage_client: storage.Client,
) -> None:
    tag = "tokens"
    bucket = storage_client.bucket(args.bucket)

    workbook = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)
    if args.worksheet_gid is not None:
        sheet = workbook.get_worksheet_by_id(args.worksheet_gid)
    else:
        sheet = workbook.worksheet(args.sheet_title)

    # A=name, B=image URL, … I=Tags (uses-scryfall-image, etc.)
    with sheet_lock:
        all_rows = sheet.get_values(f"A{args.first_row}:I")
    if not all_rows:
        _log(tag, "No rows in range.")
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
        tags = row[8].strip() if len(row) > 8 and row[8] else ""
        if not url:
            continue
        if not url.startswith("http"):
            _log(tag, f"row {row_1based}: skip non-URL in column B: {url!r}")
            continue

        if args.skip_scryfall and _token_is_from_scryfall(url, tags):
            _log(tag, f"row {row_1based}: skip scryfall-sourced ({name})")
            continue

        if args.skip_if_gcs and f"storage.googleapis.com/{args.bucket}/" in url:
            _log(tag, f"row {row_1based}: already GCS ({name})")
            continue

        slug = _slug_for_gcs(name, row_1based)
        if args.dry_run:
            _log(
                tag,
                f"row {row_1based}: DRY-RUN would download {url!r} then upload "
                f"{prefix}{slug}.<ext>",
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
            if args.write_sheet:
                col_letter = _column_letter(args.write_column)
                try:
                    with sheet_lock:
                        _google_call_with_retry(
                            partial(sheet.update_acell, f"{col_letter}{row_1based}", gcs_url),
                            what=f"token sheet write row {row_1based}",
                            log_tag=tag,
                        )
                except Exception as e:
                    _log(
                        tag,
                        f"row {row_1based}: uploaded {name!r} -> {gcs_url} "
                        f"(sheet write failed: {e})",
                        err=True,
                    )
                else:
                    _log(tag, f"row {row_1based}: uploaded {name!r} -> {gcs_url}")
            else:
                _log(
                    tag,
                    f"row {row_1based}: uploaded {name!r} -> {gcs_url} (sheet write skipped)",
                )
        except Exception as e:
            _log(tag, f"row {row_1based}: ERROR {name!r}: {e}", err=True)
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                os.remove(tmp_path)

        if args.sleep:
            time.sleep(args.sleep)


def _cell_values(worksheet, a1_range: str) -> list[str]:
    return [cell.value or "" for cell in worksheet.range(a1_range)]


def _parse_side_num(side_name: str) -> int:
    m = re.match(r"side\s*(\d+)", (side_name or "").strip(), re.IGNORECASE)
    return int(m.group(1)) if m else 1


def _load_printable_side_index(rows: list[list[str]]) -> dict[tuple[str, str], int]:
    """Map ``(card_id, sidename)`` → 1-based Printable DB row."""
    index: dict[tuple[str, str], int] = {}
    for row_1based, row in enumerate(rows, start=1):
        if row_1based < 2:
            continue
        card_id = (row[0] if row else "").strip()
        if not card_id:
            continue
        sidename = (row[2] if len(row) > 2 else "").strip() or "side 1"
        index[(card_id, sidename)] = row_1based
    return index


def _printable_sides_to_sync(
    card_id: str,
    side_entries: list[tuple[str, str, str, int]],
    *,
    uses_primary: bool,
    printable_index: dict[tuple[str, str], int],
) -> dict[str, int | None]:
    """Sidenames to process → existing row (``None`` = append).

    When any side 2+ is missing from Printable DB, also refresh side 1 in place
    if it already exists (new back face usually means side 1 art changed too).
    """
    db_sidenames = [
        f"side {side_idx + 1 if not uses_primary else 1}" for *_rest, side_idx in side_entries
    ]
    missing = [s for s in db_sidenames if (card_id, s) not in printable_index]
    if not missing:
        return {}

    to_process: dict[str, int | None] = {s: None for s in missing}
    if any(_parse_side_num(s) >= 2 for s in missing):
        side1_key = (card_id, "side 1")
        if side1_key in printable_index:
            to_process["side 1"] = printable_index[side1_key]
    return to_process


def run_printable(
    args: argparse.Namespace,
    *,
    sheet_lock: threading.Lock,
    storage_client: storage.Client,
) -> None:
    tag = "printable"
    bucket = storage_client.bucket(args.printable_bucket)

    database = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)
    main_sheet = database.worksheet(SOURCE_SHEET_NAME)
    target_db = googleClient.open_by_key(args.printable_sheet_key)
    target_sheet = target_db.get_worksheet(args.printable_worksheet)

    start = args.printable_first_row
    end = args.printable_last_row
    if end is None:
        end = main_sheet.row_count

    with sheet_lock:
        printable_rows = target_sheet.get_all_values()
        printable_index = _load_printable_side_index(printable_rows)
        card_ids = _cell_values(main_sheet, f"A{start}:A{end}")
        card_names = _cell_values(main_sheet, f"B{start}:B{end}")
        primary_urls = _cell_values(main_sheet, f"C{start}:C{end}")
        side1_urls = _cell_values(main_sheet, f"T{start}:T{end}")
        side2_urls = _cell_values(main_sheet, f"AF{start}:AF{end}")
        side3_urls = _cell_values(main_sheet, f"AP{start}:AP{end}")
        side4_urls = _cell_values(main_sheet, f"AZ{start}:AZ{end}")
        side1_types = _cell_values(main_sheet, f"M{start}:M{end}")
        side2_types = _cell_values(main_sheet, f"Y{start}:Y{end}")
        side3_types = _cell_values(main_sheet, f"AI{start}:AI{end}")
        side4_types = _cell_values(main_sheet, f"AS{start}:AS{end}")
        side1_supertypes = _cell_values(main_sheet, f"L{start}:L{end}")
        side2_supertypes = _cell_values(main_sheet, f"X{start}:X{end}")
        side3_supertypes = _cell_values(main_sheet, f"AH{start}:AH{end}")
        side4_supertypes = _cell_values(main_sheet, f"AR{start}:AR{end}")
        card_sets = _cell_values(main_sheet, f"E{start}:E{end}")

    _log(
        tag,
        f"Printable DB has {len(printable_index)} side rows; processing {len(card_ids)} cards",
    )

    assess = args.assess != "off"
    if assess and not _ollama_reachable(args.ollama_host):
        if args.assess == "on":
            raise RuntimeError(f"--assess on but Ollama unreachable at {args.ollama_host}")
        _log(tag, f"Ollama unreachable at {args.ollama_host}; skipping assessment")
        assess = False

    bad_url_log = Path(args.bad_url_log)

    for row_offset, (
        card_id,
        name,
        primary_url,
        side1,
        side2,
        side3,
        side4,
        type1,
        type2,
        type3,
        type4,
        sup1,
        sup2,
        sup3,
        sup4,
        card_set,
    ) in enumerate(
        zip(
            card_ids,
            card_names,
            primary_urls,
            side1_urls,
            side2_urls,
            side3_urls,
            side4_urls,
            side1_types,
            side2_types,
            side3_types,
            side4_types,
            side1_supertypes,
            side2_supertypes,
            side3_supertypes,
            side4_supertypes,
            card_sets,
        )
    ):
        db_row = start + row_offset
        if card_set == "HCV":
            continue

        uses_primary = side1 == ""
        if uses_primary:
            side_entries = [(primary_url, type1, sup1, 0)]
        else:
            side_entries = [
                (u, t, s, idx)
                for idx, (u, t, s) in enumerate(
                    zip(
                        (side1, side2, side3, side4),
                        (type1, type2, type3, type4),
                        (sup1, sup2, sup3, sup4),
                    )
                )
                if u
            ]
        if not side_entries:
            continue

        sides_to_sync = _printable_sides_to_sync(
            str(card_id),
            side_entries,
            uses_primary=uses_primary,
            printable_index=printable_index,
        )
        if not sides_to_sync:
            continue

        if args.dry_run:
            for sidename in sorted(sides_to_sync, key=_parse_side_num):
                existing_row = sides_to_sync[sidename]
                action = "update" if existing_row else "append"
                where = f"row {existing_row}" if existing_row else "new row"
                _log(
                    tag,
                    f"DRY-RUN would {action} {name!r} {sidename} ({where})",
                )
            continue

        if args.printable_sleep:
            time.sleep(args.printable_sleep)

        safe_name = cast(str, name).replace("/", "|")
        side_entry_by_name = {
            f"side {side_idx + 1 if not uses_primary else 1}": (
                side_url,
                side_type,
                side_supertype,
                side_idx,
            )
            for side_url, side_type, side_supertype, side_idx in side_entries
        }

        for sidename in sorted(sides_to_sync, key=_parse_side_num):
            side_url, side_type, side_supertype, side_idx = side_entry_by_name[sidename]
            side_num = _parse_side_num(sidename)
            printable_row = sides_to_sync[sidename]
            is_update = printable_row is not None
            is_plane = types_include_plane(side_type)
            is_legendary = supertypes_include_legendary(side_supertype)

            if not _is_plausible_image_url(side_url):
                _handle_bad_printable_url(
                    log_path=bad_url_log,
                    log_tag=tag,
                    dry_run=args.dry_run,
                    card_id=str(card_id),
                    name=str(name),
                    side_num=side_num,
                    side_idx=side_idx,
                    uses_primary=uses_primary,
                    db_row=db_row,
                    url=side_url,
                    error="invalid or missing URL",
                    printable_sheet=target_sheet if is_update else None,
                    printable_row=printable_row,
                    sheet_lock=sheet_lock if is_update else None,
                )
                continue

            action = "update" if is_update else "append"
            _log(tag, f"{name!r} {sidename}: {action} — download")
            local_name = f"{safe_name}.png"
            paths_to_remove: list[str] = []
            try:
                with tempfile.NamedTemporaryFile(
                    prefix="mork_printable_",
                    suffix=".png",
                    delete=False,
                ) as tf:
                    work_path = tf.name
                paths_to_remove.append(work_path)

                try:
                    _download_printable_image(side_url, work_path, log_tag=tag, max_attempts=2)
                except requests.RequestException as e:
                    _handle_bad_printable_url(
                        log_path=bad_url_log,
                        log_tag=tag,
                        dry_run=args.dry_run,
                        card_id=str(card_id),
                        name=str(name),
                        side_num=side_num,
                        side_idx=side_idx,
                        uses_primary=uses_primary,
                        db_row=db_row,
                        url=side_url,
                        error=str(e),
                        printable_sheet=target_sheet if is_update else None,
                        printable_row=printable_row,
                        sheet_lock=sheet_lock if is_update else None,
                    )
                    continue

                if work_path.endswith(".jpg"):
                    image = Image.open(work_path)
                    png_path = re.sub(r"\.jpg$", ".png", work_path)
                    image.save(png_path, "png")
                    paths_to_remove.append(png_path)
                    work_path = png_path

                prepared = prepare_card_for_printing(
                    work_path, log_tag=tag, force_landscape=is_plane
                )
                if prepared != work_path:
                    paths_to_remove.append(prepared)
                    work_path = prepared

                object_key = _printable_object_key(local_name, str(card_id), side_idx)
                blob = bucket.blob(object_key)
                blob.upload_from_filename(work_path, content_type="image/png")
                gcs_url = blob.public_url

                row_values = [card_id, name, sidename, gcs_url]
                if assess:
                    try:
                        verdict, bot, comment = assess_prepared_card(
                            work_path,
                            card_id=str(card_id),
                            card_name=str(name),
                            side_name=sidename,
                            args=args,
                            landscape_ok=is_plane,
                            legendary_ok=is_legendary,
                        )
                        row_values += [verdict, bot, comment]
                        _log(
                            tag,
                            f"{name!r} {sidename}: assessed {verdict}"
                            + (f" ({comment})" if comment else ""),
                        )
                    except Exception as e:
                        _log(
                            tag,
                            f"{name!r} {sidename}: assessment failed: {e}",
                            err=True,
                        )

                with sheet_lock:
                    if is_update:
                        assert printable_row is not None
                        last_col = 7 if assess and len(row_values) >= 7 else 4
                        col_end = _column_letter(last_col)
                        _google_call_with_retry(
                            lambda rv=row_values, r=printable_row, ce=col_end: target_sheet.update(
                                values=[rv],
                                range_name=f"A{r}:{ce}",
                            ),
                            what=f"printable update {name!r} {sidename} row {printable_row}",
                            log_tag=tag,
                        )
                        _log(
                            tag,
                            f"updated row {printable_row} {name!r} {sidename} -> {gcs_url}",
                        )
                    else:
                        _google_call_with_retry(
                            lambda rv=row_values: target_sheet.append_row(rv),
                            what=f"printable append {name!r} {sidename}",
                            log_tag=tag,
                        )
                        printable_row = len(printable_rows) + 1
                        printable_rows.append(row_values)
                        printable_index[(str(card_id), sidename)] = printable_row
                        _log(tag, f"appended {name!r} {sidename} -> {gcs_url}")
            except Exception as e:
                _log(tag, f"ERROR {name!r} {sidename}: {e}", err=True)
            finally:
                for path in set(paths_to_remove):
                    if os.path.isfile(path):
                        os.remove(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--tokens-only",
        action="store_true",
        help="Run only the Tokens Database → token bucket flow",
    )
    mode.add_argument(
        "--printable-only",
        action="store_true",
        help="Run only the Database → printable bucket → Printable DB flow",
    )

    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS),
        help="Service account JSON path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not upload or update sheets",
    )

    # --- Tokens ---
    parser.add_argument(
        "--bucket",
        default=DEFAULT_TOKEN_BUCKET,
        help="GCS bucket for token images (or GCS_TOKEN_BUCKET)",
    )
    parser.add_argument(
        "--sheet-title",
        default=hc_constants.TOKEN_SHEET,
        help="Tokens worksheet title (default: hc_constants.TOKEN_SHEET)",
    )
    parser.add_argument(
        "--worksheet-gid",
        type=int,
        default=None,
        help="If set, open the tokens tab by gid instead of --sheet-title",
    )
    parser.add_argument("--first-row", type=int, default=2, help="First token sheet row")
    parser.add_argument("--last-row", type=int, default=None, help="Last token sheet row")
    parser.add_argument(
        "--write-column",
        type=int,
        default=2,
        help="1-based column for GCS URL on token sheet (default 2 = B)",
    )
    parser.add_argument("--prefix", default="tokens/", help="GCS object prefix for tokens")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds between token rows",
    )
    parser.add_argument(
        "--skip-if-gcs",
        action="store_true",
        help="Skip token rows already pointing at this bucket",
    )
    parser.add_argument(
        "--skip-scryfall",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Skip tokens whose Tags include uses-scryfall-image or whose URL "
            "is on scryfall (default: on). Use --no-skip-scryfall to upload them."
        ),
    )
    parser.add_argument(
        "--write-sheet",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Write GCS URLs back to the token sheet (default: on). "
            "Use --no-write-sheet when the tab is protected."
        ),
    )

    # --- Printable ---
    parser.add_argument(
        "--printable-bucket",
        default=DEFAULT_PRINTABLE_BUCKET,
        help="GCS bucket for printable images",
    )
    parser.add_argument(
        "--printable-sheet-key",
        default=PRINTABLE_DB_SPREADSHEET_KEY,
        help="Printable DB spreadsheet id",
    )
    parser.add_argument(
        "--printable-worksheet",
        type=int,
        default=0,
        help="Printable DB worksheet index (default 0)",
    )
    parser.add_argument(
        "--printable-first-row",
        type=int,
        default=2,
        help="First Database sheet row for printable sync",
    )
    parser.add_argument(
        "--printable-last-row",
        type=int,
        default=None,
        help="Last Database sheet row inclusive (default: sheet row count)",
    )
    parser.add_argument(
        "--printable-sleep",
        type=float,
        default=15.0,
        help="Seconds between printable cards (rate limiting)",
    )
    parser.add_argument(
        "--bad-url-log",
        default=str(DEFAULT_BAD_URL_LOG),
        help="JSONL log for bad Database source image URLs",
    )
    parser.add_argument(
        "--assess",
        choices=["auto", "on", "off"],
        default="auto",
        help=(
            "Vision QA on each prepared card before the Printable DB append: "
            "auto (when Ollama is reachable), on (require), off. Writes "
            "Is good? (E), Bot? (F), Bot comment (G) on the appended row."
        ),
    )
    parser.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help="Ollama endpoint for assessment (or OLLAMA_HOST)",
    )
    parser.add_argument(
        "--vision-model",
        default=DEFAULT_VISION_MODEL,
        help="Ollama vision model for assessment (or OLLAMA_VISION_MODEL)",
    )
    parser.add_argument(
        "--assess-max-image-side",
        type=int,
        default=1280,
        help="Downscale assessment copies to this max side (0 = no scaling)",
    )

    args = parser.parse_args()
    run_tokens_flow = not args.printable_only
    run_printable_flow = not args.tokens_only

    if not os.path.isfile(args.credentials):
        print(f"Missing credentials file: {args.credentials}", file=sys.stderr)
        sys.exit(1)

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)
    storage_client = storage.Client.from_service_account_json(args.credentials)
    sheet_lock = threading.Lock()

    workers: list[tuple[str, threading.Thread]] = []
    errors: list[str] = []

    def _wrap(name: str, target) -> None:
        try:
            target()
        except Exception as e:
            errors.append(f"{name}: {e}")
            _log(name, f"fatal: {e}", err=True)

    if run_tokens_flow:
        t = threading.Thread(
            target=_wrap,
            args=(
                "tokens",
                lambda: run_tokens(args, sheet_lock=sheet_lock, storage_client=storage_client),
            ),
            name="tokens-sync",
            daemon=True,
        )
        workers.append(("tokens", t))

    if run_printable_flow:
        t = threading.Thread(
            target=_wrap,
            args=(
                "printable",
                lambda: run_printable(args, sheet_lock=sheet_lock, storage_client=storage_client),
            ),
            name="printable-sync",
            daemon=True,
        )
        workers.append(("printable", t))

    if not workers:
        print("Nothing to run.", file=sys.stderr)
        sys.exit(1)

    for _name, thread in workers:
        thread.start()
    for _name, thread in workers:
        thread.join()

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
