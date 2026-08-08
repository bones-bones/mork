#!/usr/bin/env python3
"""
Re-convert + assess Printable DB cards from fresh Database sources.

Unlike ``download_and_upload_images_gcs.py --printable-only``, this **reprocesses**
rows already on the Printable DB — including prior ``Is good?=N`` / unfixable
failures — with the current ``prepare_card_for_printing_stretch`` pipeline.

If a Printable row's card id is missing from Hellscube Database, the Printable
row is deleted (orphan cleanup). If the id still exists but Database no longer
has that side — e.g. a former ``Side A // Side B`` entry was split into
separate cards — the stale Printable side row is deleted too.

Resume: existing ``batch_summary.json`` entries with a verdict (no error) or
``removed`` are skipped so restarts do not redo successful work. Connection /
sheet errors are retried.

Example:
  python scripts/reconvert_assess_batch.py --limit 50
  python scripts/reconvert_assess_batch.py --limit 50 --dry-run
  python scripts/reconvert_assess_batch.py --limit 50 --n-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import traceback
from pathlib import Path

import requests

import mork_repo_root  # noqa: F401

_scripts = str(Path(__file__).resolve().parent)
if _scripts in sys.path:
    sys.path.remove(_scripts)
sys.path.insert(0, _scripts)

from google.cloud import storage

from download_and_upload_images_gcs import (
    DEFAULT_BAD_URL_LOG,
    DEFAULT_CREDENTIALS,
    _append_bad_url_log,
    _column_letter,
    _database_url_col_1based,
    _google_call_with_retry,
    _handle_bad_printable_url,
    _is_plausible_image_url,
    _printable_object_key,
    _safe_card_filename,
    assess_prepared_card,
)
from fix_and_reassess import (
    COL_BOT,
    COL_BOT_COMMENT,
    COL_CARDNAME,
    COL_ID,
    COL_IS_GOOD,
    COL_SIDENAME,
    COL_URL,
    PRINTABLE_DB_KEY,
    _DB_SIDE_COL,
    _cell,
    _col_letter,
    _database_is_plane,
    _database_has_side,
    _database_is_legendary,
    _db_cell,
    _download,
    _load_database_index,
    _normalize_card_id,
    _parse_side_num,
)
from prepare_card_for_printing_stretch import prepare_card_for_printing_stretch
from printable_image_fixes import UNFIXABLE, parse_defect_tags
from shared_vars import googleClient

DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
GCS_BUCKET = os.environ.get("GCS_PRINTABLE_BUCKET", "hellscube-printable-images")


def _target_key(card_id: str, side: str) -> tuple[str, str]:
    return (str(card_id), side or "side 1")


def _load_summary(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _completed_keys(summary: list[dict]) -> set[tuple[str, str]]:
    """Keys that should not be reprocessed on resume."""
    done: set[tuple[str, str]] = set()
    for e in summary:
        cid = e.get("card_id")
        if not cid:
            continue
        key = _target_key(str(cid), e.get("side") or "side 1")
        if e.get("removed"):
            done.add(key)
        elif e.get("verdict") and not e.get("error"):
            done.add(key)
    return done


def _pick_targets(rows: list[list[str]], *, limit: int, n_only: bool) -> list[dict]:
    """Prefer Is good?=N (incl. unfixable), then fill with other bot rows."""
    n_rows: list[dict] = []
    other: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row_1based, row in enumerate(rows, start=1):
        if row_1based < 2:
            continue
        card_id = _normalize_card_id(_cell(row, COL_ID))
        if not card_id:
            continue
        side = _cell(row, COL_SIDENAME) or "side 1"
        key = (card_id, side)
        if key in seen:
            continue
        seen.add(key)
        is_good = _cell(row, COL_IS_GOOD)
        bot = _cell(row, COL_BOT)
        comment = _cell(row, COL_BOT_COMMENT)
        defects = parse_defect_tags(comment)
        entry = {
            "printable_row": row_1based,
            "card_id": card_id,
            "name": _cell(row, COL_CARDNAME),
            "side": side,
            "url": _cell(row, COL_URL),
            "is_good": is_good,
            "bot": bot,
            "comment": comment,
            "defects": defects,
            "unfixable_only": bool(defects)
            and all(d in UNFIXABLE for d in defects),
        }
        if is_good == "N":
            n_rows.append(entry)
        elif not n_only and bot == "bot":
            other.append(entry)

    # Unfixable-only N first, then other N, then Y/bot fillers.
    n_rows.sort(key=lambda e: (0 if e["unfixable_only"] else 1, e["printable_row"]))
    picked = n_rows[:limit]
    if not n_only and len(picked) < limit:
        for e in other:
            if len(picked) >= limit:
                break
            picked.append(e)
    return picked


def _shift_printable_rows(targets: list[dict], *, deleted_row: int) -> None:
    """After deleting a sheet row, shift later cached row numbers down by 1."""
    for t in targets:
        if t["printable_row"] > deleted_row:
            t["printable_row"] -= 1


def _database_url_meta(
    db_rows: list[list[str]],
    id_to_row: dict[str, int],
    card_id: str,
    side_name: str,
) -> tuple[str, int, int, bool]:
    """Return url, Database row (1-based), side_idx (0-based), uses_primary."""
    row_num = id_to_row.get(card_id)
    if not row_num:
        raise ValueError(f"card {card_id} not found in Database sheet")
    row_vals = db_rows[row_num - 1]
    n = _parse_side_num(side_name)
    if n == 1:
        side_url = _db_cell(row_vals, 19)
        if side_url:
            return side_url, row_num, 0, False
        return _db_cell(row_vals, 2), row_num, 0, True
    col = _DB_SIDE_COL.get(n)
    if col is None:
        raise ValueError(f"unsupported side name {side_name!r}")
    return _db_cell(row_vals, col), row_num, n - 1, False


def _log_bad_url_only(
    log_path: Path,
    *,
    card_id: str,
    name: str,
    side_num: int,
    url: str,
    error: str,
    db_row: int,
    side_idx: int,
    uses_primary: bool,
) -> None:
    col = _database_url_col_1based(side_idx, uses_primary=uses_primary)
    _append_bad_url_log(
        log_path,
        card_id=str(card_id),
        name=name,
        side_num=side_num,
        url=url,
        error=error,
        db_row=db_row,
        db_col=_column_letter(col),
    )


def _delete_printable_row(ws, row_1based: int) -> None:
    _google_call_with_retry(
        lambda: ws.delete_rows(row_1based),
        what=f"delete Printable row {row_1based}",
    )


def _remove_printable_row(
    ws,
    *,
    targets: list[dict],
    from_index: int,
    row_1based: int,
    reason: str,
) -> None:
    _delete_printable_row(ws, row_1based)
    _shift_printable_rows(targets[from_index + 1 :], deleted_row=row_1based)
    print(f"  removed Printable row {row_1based}: {reason}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--n-only",
        action="store_true",
        help="Only reprocess Is good?=N rows (still includes unfixable)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sleep", type=float, default=2.0)
    parser.add_argument(
        "--output-dir",
        default="scripts/data/fix_compare/db_batch_50_reconvert",
    )
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS)
    parser.add_argument("--bucket", default=GCS_BUCKET)
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--vision-model", default=DEFAULT_MODEL)
    parser.add_argument("--assess-max-image-side", type=int, default=1280)
    parser.add_argument("--skip-upload", action="store_true", help="Local convert+assess only")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore batch_summary.json and reprocess from scratch",
    )
    parser.add_argument(
        "--bad-url-log",
        default=str(DEFAULT_BAD_URL_LOG),
        help="JSONL log for bad/missing Database image URLs",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    src_dir = out_dir / "sources"
    summary_path = out_dir / "batch_summary.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(parents=True, exist_ok=True)

    prior_summary = [] if args.no_resume else _load_summary(summary_path)
    done_keys = _completed_keys(prior_summary)
    # Keep successful / removed history; drop failed entries so they can retry cleanly.
    summary: list[dict] = [
        e
        for e in prior_summary
        if e.get("card_id")
        and _target_key(str(e["card_id"]), e.get("side") or "side 1") in done_keys
    ]
    if done_keys:
        print(
            f"Resume: {len(done_keys)} completed keys in {summary_path.name}; "
            f"retrying failures / continuing.",
            flush=True,
        )

    print("Loading Printable DB + Database index...")
    ws = googleClient.open_by_key(PRINTABLE_DB_KEY).get_worksheet(0)
    rows = ws.get_all_values()
    targets = _pick_targets(rows, limit=args.limit, n_only=args.n_only)
    if done_keys:
        before = len(targets)
        targets = [
            t
            for t in targets
            if _target_key(t["card_id"], t["side"]) not in done_keys
        ]
        print(
            f"Selected {before} cards, {len(targets)} remaining after resume skip "
            f"(N-pool fill toward --limit {args.limit})",
            flush=True,
        )
    else:
        print(
            f"Selected {len(targets)} cards "
            f"(N={sum(1 for t in targets if t['is_good']=='N')}, "
            f"unfixable_only={sum(1 for t in targets if t['unfixable_only'])})",
            flush=True,
        )
    if not targets:
        print("Nothing to process.")
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        return 0

    db_rows, id_to_row = _load_database_index()
    sheet_lock = threading.Lock()
    bad_url_log = Path(args.bad_url_log)
    storage_client = None
    bucket = None
    if not args.dry_run and not args.skip_upload:
        os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", args.credentials)
        storage_client = storage.Client.from_service_account_json(args.credentials)
        bucket = storage_client.bucket(args.bucket)

    assess_ns = argparse.Namespace(
        ollama_host=args.ollama_host,
        vision_model=args.vision_model,
        assess_max_image_side=args.assess_max_image_side,
    )

    total = len(targets)
    for i, t in enumerate(targets):
        cid, name, side = t["card_id"], t["name"], t["side"]
        side_tag = side.replace(" ", "_")
        print(
            f"\n[{i + 1}/{total}] {name} ({cid}) {side} "
            f"row={t['printable_row']} prior={t['is_good']!r} "
            f"unfixable_only={t['unfixable_only']}",
            flush=True,
        )
        if args.dry_run:
            if cid not in id_to_row:
                print(
                    f"  DRY-RUN: would delete Printable row {t['printable_row']} "
                    f"(not in Database)",
                    flush=True,
                )
                summary.append({**t, "removed": True, "dry_run": True})
            else:
                summary.append({**t, "dry_run": True})
            continue

        src_path = src_dir / _safe_card_filename(cid, name, side_tag, label="source")
        printable_path = out_dir / _safe_card_filename(
            cid, name, side_tag, label="printable"
        )
        entry = {**t, "source": str(src_path), "printable": str(printable_path)}

        if cid not in id_to_row:
            r = t["printable_row"]
            try:
                _remove_printable_row(
                    ws,
                    targets=targets,
                    from_index=i,
                    row_1based=r,
                    reason=f"card {cid} not in Database",
                )
                entry["removed"] = True
                entry["removed_reason"] = "not in Database"
            except Exception as e:
                traceback.print_exc()
                entry["error"] = str(e)
                print(f"  ERROR deleting orphan row {r}: {e}", flush=True)
            summary.append(entry)
            summary_path.write_text(json.dumps(summary, indent=2) + "\n")
            if args.sleep and i + 1 < total:
                time.sleep(args.sleep)
            continue

        if not _database_has_side(db_rows, id_to_row, cid, side):
            r = t["printable_row"]
            if args.dry_run:
                print(
                    f"  DRY-RUN: would delete Printable row {r} "
                    f"(Database no longer has {cid} {side})",
                    flush=True,
                )
                entry["removed"] = True
                entry["removed_reason"] = "Database side removed"
                entry["dry_run"] = True
            else:
                try:
                    _remove_printable_row(
                        ws,
                        targets=targets,
                        from_index=i,
                        row_1based=r,
                        reason=(
                            f"Database no longer has {cid} {side} "
                            f"(likely split from a former // card)"
                        ),
                    )
                    entry["removed"] = True
                    entry["removed_reason"] = "Database side removed"
                except Exception as e:
                    traceback.print_exc()
                    entry["error"] = str(e)
                    print(f"  ERROR deleting stale side row {r}: {e}", flush=True)
            summary.append(entry)
            summary_path.write_text(json.dumps(summary, indent=2) + "\n")
            if args.sleep and i + 1 < total:
                time.sleep(args.sleep)
            continue

        try:
            url, db_row, side_idx, uses_primary = _database_url_meta(
                db_rows, id_to_row, cid, side
            )
            side_num = _parse_side_num(side)

            if not url.strip():
                url_problem = f"no Database URL for {cid} {side}"
                _log_bad_url_only(
                    bad_url_log,
                    card_id=cid,
                    name=name,
                    side_num=side_num,
                    url=url,
                    error=url_problem,
                    db_row=db_row,
                    side_idx=side_idx,
                    uses_primary=uses_primary,
                )
                entry["error"] = url_problem
                print(f"  ERROR: {url_problem}", flush=True)
            elif not _is_plausible_image_url(url):
                url_problem = f"invalid Database URL for {cid} {side}"
                if args.dry_run:
                    print(
                        f"  DRY-RUN: would log bad Database source URL and clear "
                        f"Printable D{t['printable_row']} ({url[:48]}...)",
                        flush=True,
                    )
                else:
                    _handle_bad_printable_url(
                        log_path=bad_url_log,
                        log_tag="reconvert",
                        dry_run=False,
                        card_id=cid,
                        name=name,
                        side_num=side_num,
                        side_idx=side_idx,
                        uses_primary=uses_primary,
                        db_row=db_row,
                        url=url,
                        error=url_problem,
                        printable_sheet=ws,
                        printable_row=t["printable_row"],
                        sheet_lock=sheet_lock,
                    )
                entry["error"] = url_problem
                print(f"  ERROR: {url_problem}", flush=True)
            else:
                is_plane = _database_is_plane(db_rows, id_to_row, cid, side)
                is_legendary = _database_is_legendary(db_rows, id_to_row, cid, side)
                if is_plane:
                    print("  Plane type → horizontal (landscape) prep + QA", flush=True)
                if is_legendary:
                    print("  Legendary supertype → legend crown ok for QA", flush=True)
                print(f"  download {url[:72]}...", flush=True)
                try:
                    _download(url, str(src_path))
                except requests.RequestException as e:
                    url_problem = str(e)
                    if args.dry_run:
                        print(
                            f"  DRY-RUN: would log bad Database source URL and clear "
                            f"Printable D{t['printable_row']}: {e}",
                            flush=True,
                        )
                    else:
                        _handle_bad_printable_url(
                            log_path=bad_url_log,
                            log_tag="reconvert",
                            dry_run=False,
                            card_id=cid,
                            name=name,
                            side_num=side_num,
                            side_idx=side_idx,
                            uses_primary=uses_primary,
                            db_row=db_row,
                            url=url,
                            error=url_problem,
                            printable_sheet=ws,
                            printable_row=t["printable_row"],
                            sheet_lock=sheet_lock,
                        )
                    entry["error"] = url_problem
                    print(f"  ERROR: {url_problem}", flush=True)
                else:
                    prepare_card_for_printing_stretch(
                        str(src_path),
                        out_path=str(printable_path),
                        log_tag="reconvert",
                        force_landscape=is_plane,
                    )

                    verdict, bot, comment = assess_prepared_card(
                        str(printable_path),
                        card_id=cid,
                        card_name=name,
                        side_name=side,
                        args=assess_ns,
                        landscape_ok=is_plane,
                        legendary_ok=is_legendary,
                    )
                    entry.update(
                        verdict=verdict,
                        is_good=verdict,
                        bot=bot,
                        assess_comment=comment,
                        comment=comment,
                    )
                    print(
                        f"  assess: {verdict}" + (f" — {comment}" if comment else ""),
                        flush=True,
                    )

                    if not args.skip_upload and bucket is not None:
                        object_key = _printable_object_key(
                            f"{name.replace('/', '|')}.png", cid, side_num - 1
                        )
                        blob = bucket.blob(object_key)
                        blob.upload_from_filename(
                            str(printable_path), content_type="image/png"
                        )
                        gcs_url = blob.public_url
                        entry["gcs_url"] = gcs_url
                        r = t["printable_row"]
                        _google_call_with_retry(
                            lambda: ws.update(
                                values=[[gcs_url, verdict, bot, comment]],
                                range_name=(
                                    f"{_col_letter(COL_URL)}{r}:"
                                    f"{_col_letter(COL_BOT_COMMENT)}{r}"
                                ),
                            ),
                            what=f"reconvert sheet update row {r}",
                        )
                        print(
                            f"  sheet row {r} updated Is good?={verdict}; gcs={gcs_url}",
                            flush=True,
                        )

        except Exception as e:
            traceback.print_exc()
            entry["error"] = str(e)
            print(f"  ERROR: {e}", flush=True)

        summary.append(entry)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        if args.sleep and i + 1 < total:
            time.sleep(args.sleep)

    y = sum(1 for s in summary if s.get("verdict") == "Y")
    n = sum(1 for s in summary if s.get("verdict") == "N")
    removed = sum(1 for s in summary if s.get("removed"))
    err = sum(1 for s in summary if s.get("error"))
    print(
        f"\nDone. Y={y} N={n} removed={removed} errors={err} → {summary_path}"
    )
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
