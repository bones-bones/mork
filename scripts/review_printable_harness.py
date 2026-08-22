"""
Assessment harness for printable image QA: human labels, benchmark, mismatch replay.

Loads labels from ``data/printable_qa_labels.json`` plus code defaults, runs
``review_image()`` (or heuristics-only), and reports per-id accuracy with notes.

Examples:
  python scripts/review_printable_harness.py
  python scripts/review_printable_harness.py --heuristics-only
  python scripts/review_printable_harness.py --ids 75,175,186,135 --verbose
  python scripts/review_printable_harness.py --from-compare /tmp/printable-compare-300-merged.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import mork_repo_root  # noqa: F401
from printable_image_qa import (
    cleanup_temp_paths,
    load_benchmark_labels,
    resize_for_vision,
    review_image,
)
from review_printable_benchmark import (
    CACHE_DIR,
    DEFAULT_CREDENTIALS,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_HOST,
    _heuristics_only_review,
    _load_printable_rows,
    _print_results_table,
    _resolve_image_path,
)


def _ids_from_compare_csv(path: str) -> list[str]:
    ids: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("agree") == "N" and row.get("id"):
                ids.append(row["id"].strip())
    return sorted(set(ids), key=int)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS)
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--heuristics-only", action="store_true")
    parser.add_argument("--skip-ollama-check", action="store_true")
    parser.add_argument("--ids", default="", help="Comma-separated card ids (default: all labels)")
    parser.add_argument("--from-compare", default="", help="CSV from review_printable_compare.py")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--max-image-side", type=int, default=1280)
    parser.add_argument("--http-timeout", type=float, default=120.0)
    args = parser.parse_args()

    labels = load_benchmark_labels()
    if args.from_compare:
        extra = _ids_from_compare_csv(args.from_compare)
        for cid in extra:
            labels.setdefault(
                cid, {"verdict": "?", "note": "compare mismatch (no human label yet)"}
            )

    if args.ids:
        wanted = [s.strip() for s in args.ids.split(",") if s.strip()]
        labels = {k: labels[k] for k in wanted if k in labels}
        missing = [k for k in wanted if k not in labels]
        if missing:
            print(f"Unknown ids (add to data/printable_qa_labels.json): {missing}", file=sys.stderr)
            sys.exit(1)

    benchmark_ids = sorted(labels.keys(), key=int)
    need_sheet = any(
        not os.path.isfile(os.path.join(CACHE_DIR, f"{cid}.png")) for cid in benchmark_ids
    )
    sheet_rows: list[list[str]] = []
    if need_sheet:
        if not os.path.isfile(args.credentials):
            print(f"Missing credentials: {args.credentials}", file=sys.stderr)
            sys.exit(1)
        sheet_rows = _load_printable_rows(
            credentials=args.credentials,
            sheet_key="1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs",
            worksheet=0,
            api_retries=6,
            retry_base_delay=2.5,
        )

    results: list[tuple[str, str, str, bool, list[str], list[str]]] = []
    errors = 0
    skipped = 0

    for card_id in benchmark_ids:
        entry = labels[card_id]
        expected = entry["verdict"]
        note = entry.get("note", "")
        if expected == "?":
            skipped += 1
            print(f"id {card_id}: skip (no human verdict) — {note}", file=sys.stderr)
            continue

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
            vision_path = image_path
            if args.max_image_side > 0:
                vision_path, delete_scaled = resize_for_vision(image_path, args.max_image_side)
                scaled_path = vision_path if delete_scaled else ""

            if args.heuristics_only:
                review = _heuristics_only_review(vision_path)
            else:
                from review_printable_benchmark import COL_CARDNAME, COL_SIDENAME, _cell, _row_by_id

                row = _row_by_id(sheet_rows, card_id) if sheet_rows else None
                review = review_image(
                    image_path=vision_path,
                    card_id=card_id,
                    card_name=_cell(row, COL_CARDNAME) if row else "",
                    side_name=_cell(row, COL_SIDENAME) if row else "",
                    host=args.ollama_host,
                    model=args.model,
                    timeout=args.http_timeout,
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
            status = "ok" if match else "FAIL"
            print(
                f"id {card_id} [{status}] expected={expected} predicted={predicted} "
                f"({source}) — {note}",
                file=sys.stderr,
            )
            if args.verbose or not match:
                print(
                    f"  issues={review.issues} heur={review.heuristic_flags} "
                    f"step1={review.step1_defects} forced={review.forced_n_reason or '-'}",
                    file=sys.stderr,
                )
                if review.notes:
                    print(f"  notes: {review.notes[:200]}", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"id {card_id}: ERROR {e}", file=sys.stderr)
        finally:
            cleanup_temp_paths(scaled_path, image_path if delete_image else "")

    print()
    if results:
        _print_results_table(results)
        labeled = [r for r in results if labels[r[0]]["verdict"] != "?"]
        correct = sum(1 for r in labeled if r[3])
        total = len(labeled)
        print()
        print(
            f"Accuracy: {correct}/{total} ({100.0 * correct / total:.0f}%)"
            if total
            else "No labeled results"
        )
    if skipped:
        print(f"Skipped (no label): {skipped}", file=sys.stderr)
    if errors:
        print(f"Errors: {errors}", file=sys.stderr)

    if errors or not results:
        sys.exit(1)
    if all(r[3] for r in results):
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
