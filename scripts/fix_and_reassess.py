"""
Read bot-assessed failures from Printable DB, apply targeted image fixes, reassess,
and update the sheet.

Pipeline (``--from-db``, default with ``--local-only``):

  1. Pull source art from Hellscube **Database**
  2. ``prepare_card_for_printing`` (border expand)
  3. Fix → reassess (``printable_image_fixes`` + ``printable_image_qa``)

Without ``--from-db``, uses the Printable DB GCS URL (already-prepared PNG).

GCS upload and sheet ``Y - Fixed`` only when post-fix reassessment returns verdict
``Y`` and every applied fixable defect is gone from PIL heuristics and review issues.
Each row runs at most two fix→assess cycles: if the first assess fails, one
vision-guided retry uses reassess feedback on the already-fixed PNG, then a final
assess decides upload vs sheet note. Retries require Ollama vision (``--vision-corners off`` skips retry).
Order is strict: reassess → upload to GCS → Printable DB ``Y - Fixed``.
If upload fails, sheets are left unchanged. Failed reassess leaves GCS untouched
and writes ``[post-fix]`` notes on the Printable DB only.

Use ``--re-eval-uploaded-since`` to strict-reassess a prior upload batch and revert
sheet rows that no longer pass (clears ledger ``uploaded`` so they can be retried).

With ``--high-confidence-only``: only rows with ``corner_color_mismatch`` among
fixable tags and no structural unfixables; upload only if the fix changed pixels
and reassess passes.

Example:
  python scripts/fix_and_reassess.py --dry-run --limit 5
  python scripts/fix_and_reassess.py --local-only --id 950 --id 957
  python scripts/fix_and_reassess.py --local-only --gcs-prepared --id 950
  python scripts/fix_and_reassess.py --id 765 --id 486
  python scripts/fix_and_reassess.py --limit 100 --high-confidence-only --vision-corners off
  python scripts/fix_and_reassess.py --re-eval-uploaded-since 2026-06-18T21:00:00+00:00

Local progress is stored in ``scripts/data/fix_reassess_state.json`` (override with
``--state-file``). By default only rows with a prior **uploaded** outcome are skipped;
failed / no-op attempts on sheet ``N`` rows are retried. Use ``--retry-uploaded`` to
re-run uploaded rows too. ``--local-only`` does not read or write the ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import mork_repo_root  # noqa: F401
import requests
from google.cloud import storage

# Prefer scripts/ over repo-root shadow of download_and_upload_images_gcs.
_scripts = str(Path(__file__).resolve().parent)
if _scripts in sys.path:
    sys.path.remove(_scripts)
sys.path.insert(0, _scripts)

from download_and_upload_images_gcs import _download as _download_source
from download_and_upload_images_gcs import prepare_card_for_printing
from printable_image_fixes import (
    FIXABLE,
    UNFIXABLE,
    FixRetryContext,
    _ollama_reachable,
    apply_fixes,
    apply_guided_retry_fixes,
    parse_defect_tags,
)
from printable_image_qa import (
    applied_fixes_cleared,
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
PRINTABLE_DB_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"
GCS_BUCKET = os.environ.get("GCS_PRINTABLE_BUCKET", "hellscube-printable-images")
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
DEFAULT_STATE_FILE = Path(__file__).resolve().parent / "data" / "fix_reassess_state.json"
STATE_VERSION = 1
MAX_FIX_ATTEMPTS = 2

# Database sheet side URL columns (0-based index into row values).
_DB_SIDE_COL = {1: 19, 2: 31, 3: 41, 4: 51}  # T, AF, AP, AZ
_DB_SIDE_URL_COLS = tuple(_DB_SIDE_COL.values())
# Database sheet type columns (semicolon-separated; same side layout as URLs).
_DB_TYPE_COL = {1: 12, 2: 24, 3: 34, 4: 44}  # M, Y, AI, AS
# Supertype(s) sits one column left of Card Type(s) on each side block.
_DB_SUPERTYPE_COL = {n: c - 1 for n, c in _DB_TYPE_COL.items()}

COL_ID = 1
COL_CARDNAME = 2
COL_SIDENAME = 3
COL_URL = 4
COL_IS_GOOD = 5
COL_BOT = 6
COL_BOT_COMMENT = 7

# Structural failures — skip under --high-confidence-only.
HIGH_CONFIDENCE_BLOCK_UNFIXABLE = frozenset({"wrong_silhouette", "multi_card_in_one_file"})


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(row: list[str], col: int) -> str:
    idx = col - 1
    return (row[idx] or "").strip() if idx < len(row) else ""


def _db_cell(row: list[str], col_0: int) -> str:
    return row[col_0].strip() if len(row) > col_0 else ""


def _load_database_index() -> tuple[list[list[str]], dict[str, int]]:
    rows = (
        googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)
        .worksheet("Database")
        .get_all_values()
    )
    id_to_row = {
        (row[0] if row else "").strip(): i
        for i, row in enumerate(rows[1:], start=2)
        if row and row[0].strip()
    }
    return rows, id_to_row


def _parse_side_num(side_name: str) -> int:
    m = re.match(r"side\s*(\d+)", (side_name or "").strip(), re.IGNORECASE)
    return int(m.group(1)) if m else 1


def _database_side_count(row_vals: list[str]) -> int:
    """Side count using the same rule as ``download_and_upload_images_gcs``."""
    if not _db_cell(row_vals, _DB_SIDE_COL[1]):
        return 1
    return sum(1 for col in _DB_SIDE_URL_COLS if _db_cell(row_vals, col)) or 1


def _database_has_side(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> bool:
    row_num = id_to_row.get(card_id)
    if not row_num:
        return False
    return _parse_side_num(side_name) <= _database_side_count(db_rows[row_num - 1])


def _database_source_url(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> str:
    row_num = id_to_row.get(card_id)
    if not row_num:
        raise ValueError(f"card {card_id} not found in Database sheet")
    row_vals = db_rows[row_num - 1]
    n = _parse_side_num(side_name)
    if n == 1:
        return _db_cell(row_vals, 19) or _db_cell(row_vals, 2)
    col = _DB_SIDE_COL.get(n)
    if col is None:
        raise ValueError(f"unsupported side name {side_name!r}")
    url = _db_cell(row_vals, col)
    if not url:
        raise ValueError(f"no Database URL for {card_id} {side_name}")
    return url


def _database_types(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> str:
    """Raw type cell for a card side (semicolon-separated)."""
    row_num = id_to_row.get(card_id)
    if not row_num:
        return ""
    row_vals = db_rows[row_num - 1]
    n = _parse_side_num(side_name)
    col = _DB_TYPE_COL.get(n)
    if col is None:
        return ""
    return _db_cell(row_vals, col)


def _database_supertypes(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> str:
    """Raw Supertype(s) cell for a card side."""
    row_num = id_to_row.get(card_id)
    if not row_num:
        return ""
    row_vals = db_rows[row_num - 1]
    n = _parse_side_num(side_name)
    col = _DB_SUPERTYPE_COL.get(n)
    if col is None:
        return ""
    return _db_cell(row_vals, col)


def _database_is_plane(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> bool:
    return types_include_plane(_database_types(db_rows, id_to_row, card_id, side_name))


def _database_is_legendary(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> bool:
    return supertypes_include_legendary(
        _database_supertypes(db_rows, id_to_row, card_id, side_name)
    )


def _pull_and_prepare(
    dest_prepared: str,
    *,
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
    source_copy: str | None = None,
) -> str:
    """Download Database source art and border-prep into ``dest_prepared``."""
    url = _database_source_url(db_rows, id_to_row, card_id, side_name)
    is_plane = _database_is_plane(db_rows, id_to_row, card_id, side_name)
    fd, tmp_raw = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        _download_source(url, tmp_raw)
        if source_copy:
            shutil.copy2(tmp_raw, source_copy)
        shutil.copy2(tmp_raw, dest_prepared)
        prepare_card_for_printing(dest_prepared, log_tag="fix", force_landscape=is_plane)
    finally:
        try:
            os.remove(tmp_raw)
        except OSError:
            pass
    return url


def _gcs_object_name(gcs_url: str) -> str:
    prefix = f"https://storage.googleapis.com/{GCS_BUCKET}/"
    if gcs_url.startswith(prefix):
        return unquote(gcs_url[len(prefix) :])
    return unquote(gcs_url.rsplit("/", 1)[-1])


def _download(url: str, dest: str) -> None:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)


def _upload(local_path: str, gcs_url: str, storage_client: storage.Client) -> None:
    bucket = storage_client.bucket(GCS_BUCKET)
    bucket.blob(_gcs_object_name(gcs_url)).upload_from_filename(
        local_path, content_type="image/png"
    )


def _record_reeval_fail(
    ws,
    row_1based: int,
    comment: str,
) -> None:
    """Strict re-eval failed — mark sheet N so the row can be fixed again."""
    is_good_cell = f"{_col_letter(COL_IS_GOOD)}{row_1based}"
    comment_cell = f"{_col_letter(COL_BOT_COMMENT)}{row_1based}"
    ws.update_acell(is_good_cell, "N")
    ws.update_acell(comment_cell, f"[re-eval] {comment}")


def _record_reassess_fail(
    ws,
    row_1based: int,
    new_comment: str,
) -> None:
    """Reassess did not pass — GCS unchanged; note the attempt on the sheet."""
    is_good_cell = f"{_col_letter(COL_IS_GOOD)}{row_1based}"
    comment_cell = f"{_col_letter(COL_BOT_COMMENT)}{row_1based}"
    ws.update_acell(is_good_cell, "N")
    ws.update_acell(comment_cell, f"[post-fix] {new_comment}")


def _normalize_card_id(raw: str) -> str:
    """Canonical card id from Printable DB (handles Sheets float cells)."""
    s = (raw or "").strip()
    if not s:
        return ""
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except ValueError:
        pass
    return s


def _high_confidence_eligible(fixable: list[str], unfixable: list[str]) -> bool:
    if not fixable or "corner_color_mismatch" not in fixable:
        return False
    return not any(u in HIGH_CONFIDENCE_BLOCK_UNFIXABLE for u in unfixable)


def _remaining_fixable(original_fixable: list[str], review) -> list[str]:
    """Fixable defects still flagged after a failed reassess (fallback: original list)."""
    if review is None:
        return list(original_fixable)
    remaining = set(review.heuristic_flags) | set(review.issues)
    retry = [d for d in original_fixable if d in remaining]
    return retry or list(original_fixable)


def _vision_retry_available(args) -> bool:
    if args.vision_corners == "off":
        return False
    if args.vision_corners == "on":
        return True
    return _ollama_reachable(args.ollama_host)


def _build_retry_context(
    *,
    original_defects: list[str],
    remaining_defects: list[str],
    review,
    upload_reason: str,
) -> FixRetryContext:
    return FixRetryContext(
        original_defects=list(original_defects),
        remaining_defects=list(remaining_defects),
        upload_reason=upload_reason,
        verdict=review.verdict,
        heuristic_flags=list(review.heuristic_flags),
        issues=list(review.issues),
        notes=review.notes or "",
    )


def _commit_success(
    ws,
    row_1based: int,
    local_path: str,
    gcs_url: str,
    storage_client: storage.Client,
) -> None:
    """Upload fixed PNG, then mark Printable DB Y - Fixed."""
    _upload(local_path, gcs_url, storage_client)
    is_good_cell = f"{_col_letter(COL_IS_GOOD)}{row_1based}"
    comment_cell = f"{_col_letter(COL_BOT_COMMENT)}{row_1based}"
    ws.update_acell(is_good_cell, "Y - Fixed")
    ws.update_acell(comment_cell, "")


def _post_fix_fail_comment(
    *,
    original_comment: str,
    review,
    upload_reason: str,
) -> str:
    """Sheet note when fix/reassess ran but upload was blocked — keep defect tags."""
    if review and review.verdict == "Y":
        tags = ", ".join(review.issues) if review.issues else ""
        if not tags:
            tags = ", ".join(parse_defect_tags(original_comment))
        parts = [
            p for p in (tags, review.notes.strip() if review.notes else "", upload_reason) if p
        ]
        return " — ".join(parts)
    if review:
        text = format_assessment_comment(review)
        if text:
            return text
    return upload_reason or original_comment


def _strict_upload_ok(
    review,
    *,
    applied_fixes: list[str],
    original_defects: list[str],
) -> tuple[bool, str]:
    if review.verdict != "Y":
        return False, f"reassess verdict={review.verdict}"
    cleared, reason = applied_fixes_cleared(
        applied_fixes=applied_fixes,
        original_defects=original_defects,
        review=review,
        fixable_tags=FIXABLE,
    )
    if not cleared:
        return False, reason
    return True, review.forced_n_reason or "reassess Y"


def _reassess(
    local_path: str,
    card_id: str,
    card_name: str,
    side_name: str,
    args,
    *,
    landscape_ok: bool = False,
    legendary_ok: bool = False,
):
    vision_path = local_path
    scaled = ""
    if args.max_image_side > 0:
        vision_path, extra = resize_for_vision(local_path, args.max_image_side)
        if extra:
            scaled = vision_path

    result = review_image(
        image_path=vision_path,
        card_id=card_id,
        card_name=card_name,
        side_name=side_name,
        host=args.ollama_host,
        model=args.model,
        timeout=120,
        temperature=0.0,
        use_corner_crops=True,
        two_step=True,
        landscape_ok=landscape_ok,
        legendary_ok=legendary_ok,
    )
    cleanup_temp_paths(scaled)
    return result


def _safe_slug(card_id: str, card_name: str, side_name: str) -> str:
    side = re.sub(r"[^\w]+", "_", side_name.strip().lower()) or "side"
    name = re.sub(r"[^\w]+", "_", card_name.strip())[:40] or "card"
    return f"{card_id}_{name}_{side}"


def _tracking_key(card_id: str, side_name: str) -> str:
    side = re.sub(r"\s+", " ", (side_name or "").strip().lower()) or "side"
    return f"{card_id}|{side}"


class FixReassessLedger:
    """Append-only local JSON ledger so reruns skip finished rows."""

    def __init__(self, path: Path, *, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled
        self.entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: could not read {self.path}: {e}", file=sys.stderr)
            return
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            self.entries = data["entries"]

    def _save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": STATE_VERSION, "entries": self.entries}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def should_skip(
        self,
        card_id: str,
        side_name: str,
        *,
        retry_uploaded: bool,
        force_ids: set[str],
        ignore_tracking: bool = False,
    ) -> tuple[bool, str]:
        if not self.enabled or ignore_tracking or card_id in force_ids:
            return False, ""
        key = _tracking_key(card_id, side_name)
        prev = self.entries.get(key)
        if not prev:
            return False, ""
        outcome = (prev.get("outcome") or "").strip()
        # Sheet row is still N — retry failed / no-op / error attempts by default.
        if outcome != "uploaded":
            return False, ""
        if retry_uploaded:
            return False, ""
        updated = prev.get("updated_at") or "?"
        return True, f"{outcome} @ {updated}"

    def record(
        self,
        *,
        card_id: str,
        side_name: str,
        printable_row: int,
        outcome: str,
        **fields: Any,
    ) -> None:
        if not self.enabled:
            return
        key = _tracking_key(card_id, side_name)
        entry: dict[str, Any] = {
            "card_id": card_id,
            "side_name": side_name,
            "printable_row": printable_row,
            "outcome": outcome,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        entry.update({k: v for k, v in fields.items() if v is not None and v != ""})
        self.entries[key] = entry
        self._save()


# Defects high-confidence uploads are expected to clear.
_RE_EVAL_TARGET_DEFECTS = frozenset(
    {"corner_color_mismatch", "border_seam_lines", "conversion_bleed"}
)


def _parse_since(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _strict_reeval_ok(review) -> tuple[bool, str]:
    if review.verdict != "Y":
        detail = review.forced_n_reason or f"reassess verdict={review.verdict}"
        return False, detail
    remaining = set(review.heuristic_flags) | set(review.issues)
    bad = sorted(remaining & _RE_EVAL_TARGET_DEFECTS)
    if bad:
        return False, f"still has: {', '.join(bad)}"
    return True, ""


def _run_re_eval_uploaded(args) -> None:
    since = _parse_since(args.re_eval_uploaded_since)
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)
    tracking_enabled = not args.no_tracking
    ledger = FixReassessLedger(args.state_file, enabled=tracking_enabled)

    targets = [
        e
        for e in ledger.entries.values()
        if e.get("outcome") == "uploaded" and _parse_since(e.get("updated_at", "")) >= since
    ]
    targets.sort(key=lambda e: e.get("updated_at", ""))
    if args.limit:
        targets = targets[: args.limit]

    print(
        f"Re-evaluating {len(targets)} uploaded rows since {since.isoformat()} "
        f"(ledger: {args.state_file})"
    )
    if not targets:
        return

    ws = googleClient.open_by_key(PRINTABLE_DB_KEY).get_worksheet(0)
    rows = ws.get_all_values()
    db_rows, db_id_to_row = _load_database_index()
    stats = {"pass": 0, "fail": 0, "skip": 0, "error": 0}

    for entry in targets:
        card_id = _normalize_card_id(str(entry.get("card_id", "")))
        side_name = str(entry.get("side_name", ""))
        row_1based = int(entry.get("printable_row") or 0)
        if not card_id or row_1based < 2 or row_1based > len(rows):
            print(f"\n[{card_id}] SKIP: bad ledger row {row_1based}")
            stats["skip"] += 1
            continue

        row = rows[row_1based - 1]
        card_name = _cell(row, COL_CARDNAME)
        url = _cell(row, COL_URL)
        is_good = _cell(row, COL_IS_GOOD)
        is_plane = _database_is_plane(db_rows, db_id_to_row, card_id, side_name)
        is_legendary = _database_is_legendary(db_rows, db_id_to_row, card_id, side_name)

        print(f"\n[{card_id}] {card_name} ({side_name}) row={row_1based} is_good={is_good!r}")
        if not url:
            print("  SKIP: no URL")
            stats["skip"] += 1
            continue

        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            _download(url, tmp)
            review = _reassess(
                tmp,
                card_id,
                card_name,
                side_name,
                args,
                landscape_ok=is_plane,
                legendary_ok=is_legendary,
            )
            comment = format_assessment_comment(review)
            print(
                f"  verdict={review.verdict} issues={review.issues} "
                f"heuristics={review.heuristic_flags}"
            )
            if review.forced_n_reason:
                print(f"  reason={review.forced_n_reason!r}")

            ok, reason = _strict_reeval_ok(review)
            if ok:
                print("  RE-EVAL PASS")
                ledger.record(
                    card_id=card_id,
                    side_name=side_name,
                    printable_row=row_1based,
                    outcome="re_eval_pass",
                    verdict=review.verdict,
                )
                stats["pass"] += 1
            else:
                print(f"  RE-EVAL FAIL: {reason}")
                if not args.dry_run:
                    fail_comment = comment or reason
                    _record_reeval_fail(ws, row_1based, fail_comment)
                    ledger.record(
                        card_id=card_id,
                        side_name=side_name,
                        printable_row=row_1based,
                        outcome="re_eval_fail",
                        verdict=review.verdict,
                        detail=reason,
                    )
                stats["fail"] += 1
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            stats["error"] += 1
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        time.sleep(1.5)

    print(f"\nRe-eval done. {stats}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Apply fixes locally; save before/after PNGs, no GCS upload or sheet writes",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Pull Database source art and run prepare_card_for_printing before fixing",
    )
    parser.add_argument(
        "--gcs-prepared",
        action="store_true",
        help="With --local-only, skip Database pull + border prep; use Printable DB GCS URL",
    )
    parser.add_argument(
        "--output-dir",
        default="scripts/data/fix_compare",
        help="Directory for before/after PNGs when --local-only (default: scripts/data/fix_compare)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-image-side", type=int, default=1280)
    parser.add_argument(
        "--vision-corners",
        choices=["auto", "on", "off"],
        default="auto",
        help=(
            "Corner-fix strategy: auto (vision when Ollama is reachable, else "
            "heuristics), on (force vision corner location), off (deterministic "
            "heuristic corner pipeline validated on the local fix_compare set)"
        ),
    )
    parser.add_argument("--skip-reassess", action="store_true", help="Skip Ollama reassessment")
    parser.add_argument(
        "--high-confidence-only",
        action="store_true",
        help=(
            "Only corner_color_mismatch fixable rows without structural unfixables; "
            "upload only when pixels changed and reassess is Y"
        ),
    )
    parser.add_argument("--id", dest="only_ids", action="append", default=[])
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help=f"Local JSON ledger of processed rows (default: {DEFAULT_STATE_FILE.name})",
    )
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Do not read or write the local state file",
    )
    parser.add_argument(
        "--retry-uploaded",
        action="store_true",
        help="Re-run rows already tracked as uploaded (default: only skip uploaded)",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help=argparse.SUPPRESS,  # deprecated: retrying non-uploaded rows is now the default
    )
    parser.add_argument(
        "--re-eval-uploaded-since",
        metavar="ISO",
        help=(
            "Strict-reassess ledger uploads since an ISO timestamp (e.g. "
            "2026-06-18T21:00:00+00:00); revert sheet rows that fail"
        ),
    )
    args = parser.parse_args()

    if args.re_eval_uploaded_since:
        _run_re_eval_uploaded(args)
        return

    if args.local_only and not args.gcs_prepared:
        args.from_db = True

    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)
    storage_client = storage.Client() if not args.local_only and not args.dry_run else None
    if args.local_only:
        os.makedirs(args.output_dir, exist_ok=True)
        print(f"Local compare output: {os.path.abspath(args.output_dir)}")

    db_rows: list[list[str]] = []
    db_id_to_row: dict[str, int] = {}
    if args.from_db:
        print("Pipeline: Database → prepare_card_for_printing → fix → reassess")
    # Always index Database types so Plane sides get landscape_ok on reassess.
    db_rows, db_id_to_row = _load_database_index()
    if not args.from_db:
        print("Loaded Database type index for Plane landscape QA")

    ws = googleClient.open_by_key(PRINTABLE_DB_KEY).get_worksheet(0)
    rows = ws.get_all_values()

    only_ids = {_normalize_card_id(x) for x in args.only_ids if _normalize_card_id(x)}
    effective_limit = args.limit if args.limit is not None else 10
    tracking_enabled = not args.no_tracking and not args.dry_run and not args.local_only
    ledger = FixReassessLedger(args.state_file, enabled=tracking_enabled)
    if tracking_enabled:
        print(f"Tracking: {args.state_file.resolve()} ({len(ledger.entries)} entries)")
    stats = {
        "processed": 0,
        "fixed_pass": 0,
        "fixed_fail": 0,
        "skipped": 0,
        "already_tracked": 0,
    }

    def _track(
        outcome: str,
        *,
        card_id: str,
        side_name: str,
        printable_row: int,
        **fields: Any,
    ) -> None:
        ledger.record(
            card_id=card_id,
            side_name=side_name,
            printable_row=printable_row,
            outcome=outcome,
            **fields,
        )

    for row_1based, row in enumerate(rows, start=1):
        if row_1based < 2:
            continue

        card_id = _normalize_card_id(_cell(row, COL_ID))
        if not card_id:
            continue
        is_fail_row = _cell(row, COL_IS_GOOD) == "N" and _cell(row, COL_BOT) == "bot"
        demo_row = args.local_only and args.from_db and only_ids and card_id in only_ids
        if not is_fail_row and not demo_row:
            continue
        if only_ids and card_id not in only_ids:
            continue

        side_name = _cell(row, COL_SIDENAME)
        comment = _cell(row, COL_BOT_COMMENT)
        defects = parse_defect_tags(comment)
        if not defects:
            prev = ledger.entries.get(_tracking_key(card_id, side_name), {})
            stored = prev.get("original_defects")
            if isinstance(stored, list) and stored:
                defects = stored
                print(f"  restored defects from ledger: {defects}")
        if not defects:
            if only_ids and card_id in only_ids:
                print(
                    f"\n[{card_id}] SKIP: bot comment has no defect tags "
                    f"(comment={comment!r}); restore tags or add original_defects to ledger"
                )
                stats["skipped"] += 1
            continue

        fixable = [d for d in defects if d in FIXABLE]
        unfixable = [d for d in defects if d in UNFIXABLE]

        card_name = _cell(row, COL_CARDNAME)
        url = _cell(row, COL_URL)
        is_plane = _database_is_plane(db_rows, db_id_to_row, card_id, side_name)
        is_legendary = _database_is_legendary(db_rows, db_id_to_row, card_id, side_name)

        print(f"\n[{card_id}] {card_name} ({side_name})")
        print(f"  defects={defects}  fixable={fixable}  unfixable={unfixable}")
        if is_plane:
            print("  Plane type: landscape_ok for assess")
        if is_legendary:
            print("  Legendary supertype: legend crown ok for assess")

        skip_tracked, tracked_reason = ledger.should_skip(
            card_id,
            side_name,
            retry_uploaded=args.retry_uploaded,
            force_ids=only_ids,
            ignore_tracking=args.local_only,
        )
        if skip_tracked:
            print(f"  SKIP: already tracked ({tracked_reason})")
            stats["already_tracked"] += 1
            continue

        if not fixable:
            print("  SKIP: no automatable fixes for these defects")
            stats["skipped"] += 1
            continue

        if args.high_confidence_only and not _high_confidence_eligible(fixable, unfixable):
            print(
                "  SKIP: not high-confidence (need corner_color_mismatch, no structural unfixable)"
            )
            stats["skipped"] += 1
            continue

        if args.dry_run:
            print(
                f"  DRY-RUN: would apply {fixable}, reassess (up to {MAX_FIX_ATTEMPTS} "
                f"fix→assess cycles), update sheet"
            )
            stats["processed"] += 1
            if effective_limit and stats["processed"] >= effective_limit:
                break
            continue

        run_tag = "high_confidence" if args.high_confidence_only else "default"
        slug = _safe_slug(card_id, card_name, side_name)
        before_path = os.path.join(args.output_dir, f"{slug}_before.png") if args.local_only else ""
        after_path = os.path.join(args.output_dir, f"{slug}_after.png") if args.local_only else ""
        source_path = (
            os.path.join(args.output_dir, f"{slug}_source.png")
            if args.local_only and args.from_db
            else ""
        )

        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        fd2, tmp_after = tempfile.mkstemp(suffix=".png")
        os.close(fd2)
        try:
            if args.from_db:
                db_url = _pull_and_prepare(
                    tmp,
                    db_rows=db_rows,
                    id_to_row=db_id_to_row,
                    card_id=card_id,
                    side_name=side_name,
                    source_copy=source_path or None,
                )
                print(f"  Database source: {db_url[:90]}...")
                if args.local_only:
                    shutil.copy2(tmp, before_path)
                    if source_path:
                        print(f"  saved source: {source_path}")
            else:
                _download(url, tmp)
                if args.local_only:
                    shutil.copy2(tmp, before_path)

            vision_corners = {"auto": None, "on": True, "off": False}[args.vision_corners]
            all_applied: list[str] = []
            total_pixels_changed = 0
            review = None
            upload_ok = False
            upload_reason = ""
            fix_attempts = 0
            skip_row = False

            for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
                if attempt == 1:
                    attempt_fixable = fixable
                    fix_input = tmp
                else:
                    if review is None or args.skip_reassess:
                        break
                    upload_ok, upload_reason = _strict_upload_ok(
                        review,
                        applied_fixes=all_applied,
                        original_defects=defects,
                    )
                    if upload_ok:
                        break
                    attempt_fixable = _remaining_fixable(fixable, review)
                    if not attempt_fixable:
                        print("  RETRY SKIP: no fixable defects remain")
                        break
                    if not _vision_retry_available(args):
                        print(
                            "  RETRY SKIP: vision-guided retry requires Ollama "
                            "(--vision-corners off or unreachable)"
                        )
                        break
                    fix_input = tmp_after
                    print(
                        f"  First assess failed ({upload_reason}) — "
                        f"vision-guided retry for {attempt_fixable}..."
                    )

                if attempt == 1:
                    fix_result = apply_fixes(
                        fix_input,
                        attempt_fixable,
                        out_path=tmp_after,
                        use_vision_corners=vision_corners,
                        ollama_host=args.ollama_host,
                        vision_model=args.model,
                    )
                else:
                    retry_ctx = _build_retry_context(
                        original_defects=defects,
                        remaining_defects=attempt_fixable,
                        review=review,
                        upload_reason=upload_reason,
                    )
                    fix_result = apply_guided_retry_fixes(
                        fix_input,
                        attempt_fixable,
                        retry_ctx,
                        out_path=tmp_after,
                        ollama_host=args.ollama_host,
                        vision_model=args.model,
                    )
                fix_attempts = attempt
                print(
                    f"  attempt={attempt} applied={fix_result.applied}  "
                    f"pixels_changed={fix_result.pixels_changed}  notes={fix_result.notes}"
                )

                if attempt == 1 and not fix_result.applied:
                    print("  FIX SKIPPED: nothing applied")
                    _track(
                        "no_fix_applied",
                        card_id=card_id,
                        side_name=side_name,
                        printable_row=row_1based,
                        mode=run_tag,
                        original_defects=defects,
                    )
                    stats["skipped"] += 1
                    skip_row = True
                    break

                if attempt == 1 and args.high_confidence_only and fix_result.pixels_changed == 0:
                    print("  SKIP UPLOAD: high-confidence requires pixel changes")
                    _track(
                        "no_pixels_changed",
                        card_id=card_id,
                        side_name=side_name,
                        printable_row=row_1based,
                        mode=run_tag,
                        pixels_changed=0,
                        original_defects=defects,
                    )
                    stats["skipped"] += 1
                    skip_row = True
                    break

                if attempt == 2 and not fix_result.applied:
                    print("  RETRY: guided pass changed no pixels")
                    break

                for tag in fix_result.applied:
                    if tag not in all_applied:
                        all_applied.append(tag)
                total_pixels_changed += fix_result.pixels_changed

                if args.skip_reassess:
                    break

                print(f"  Reassessing (attempt {attempt})...")
                review = _reassess(
                    tmp_after,
                    card_id,
                    card_name,
                    side_name,
                    args,
                    landscape_ok=is_plane,
                    legendary_ok=is_legendary,
                )
                new_comment = format_assessment_comment(review)
                print(
                    f"  verdict={review.verdict} issues={review.issues} "
                    f"heuristics={review.heuristic_flags}"
                )
                if review.notes:
                    print(f"  notes={review.notes!r}")
                if new_comment:
                    print(f"  comment={new_comment!r}")

                upload_ok, upload_reason = _strict_upload_ok(
                    review,
                    applied_fixes=all_applied,
                    original_defects=defects,
                )
                if upload_ok:
                    if attempt > 1:
                        print(f"  Reassess pass on retry (attempt {attempt})")
                    break
                if attempt < MAX_FIX_ATTEMPTS:
                    print(f"  Reassess fail (attempt {attempt}): {upload_reason} — will retry fix")
                else:
                    print(f"  Reassess fail (final): {upload_reason}")

            if skip_row:
                continue

            if fix_attempts == 0:
                continue

            if args.local_only:
                shutil.copy2(tmp_after, after_path)
                print(f"  saved: {before_path}")
                print(f"  saved: {after_path}")

            if args.skip_reassess and not args.local_only:
                print("  SKIP UPLOAD: reassessment required (--skip-reassess)")
                stats["skipped"] += 1
                continue

            if not args.local_only:
                assert storage_client is not None
                if not upload_ok:
                    verdict = review.verdict if review else "?"
                    print(f"  SKIP UPLOAD: {upload_reason} (verdict={verdict}, GCS unchanged)")
                    if review is not None:
                        fail_comment = _post_fix_fail_comment(
                            original_comment=comment,
                            review=review,
                            upload_reason=upload_reason,
                        )
                        _record_reassess_fail(ws, row_1based, fail_comment)
                    _track(
                        "reassess_fail",
                        card_id=card_id,
                        side_name=side_name,
                        printable_row=row_1based,
                        mode=run_tag,
                        pixels_changed=total_pixels_changed,
                        verdict=review.verdict if review else None,
                        detail=upload_reason,
                        original_defects=defects,
                        fix_attempts=fix_attempts,
                    )
                    stats["fixed_fail"] += 1
                    stats["processed"] += 1
                    continue

                if review and review.forced_n_reason:
                    print(f"  Reassess: {review.forced_n_reason}")
                print("  Reassess pass — uploading to GCS...")
                _commit_success(
                    ws,
                    row_1based,
                    tmp_after,
                    url,
                    storage_client,
                )
                print("  uploaded + Printable DB Y - Fixed")
                _track(
                    "uploaded",
                    card_id=card_id,
                    side_name=side_name,
                    printable_row=row_1based,
                    mode=run_tag,
                    pixels_changed=total_pixels_changed,
                    verdict="Y",
                    original_defects=defects,
                    fix_attempts=fix_attempts,
                )
                stats["fixed_pass"] += 1
            elif review is not None:
                if review.verdict == "Y":
                    stats["fixed_pass"] += 1
                    _track(
                        "reassess_pass_local",
                        card_id=card_id,
                        side_name=side_name,
                        printable_row=row_1based,
                        mode=run_tag,
                        pixels_changed=total_pixels_changed,
                        verdict="Y",
                        fix_attempts=fix_attempts,
                    )
                else:
                    stats["fixed_fail"] += 1
                    _track(
                        "reassess_fail",
                        card_id=card_id,
                        side_name=side_name,
                        printable_row=row_1based,
                        mode=run_tag,
                        pixels_changed=total_pixels_changed,
                        verdict=review.verdict,
                        fix_attempts=fix_attempts,
                    )

            stats["processed"] += 1
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            _track(
                "error",
                card_id=card_id,
                side_name=side_name,
                printable_row=row_1based,
                mode=run_tag,
                error=str(e),
            )
        finally:
            for path in (tmp, tmp_after):
                try:
                    os.remove(path)
                except OSError:
                    pass

        if effective_limit and stats["processed"] >= effective_limit:
            break
        time.sleep(1.5)

    print(f"\nDone. {stats}")


if __name__ == "__main__":
    main()
