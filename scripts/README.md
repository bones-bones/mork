# Maintenance scripts

Run from the **repository root** so paths like `./bot_secrets/client_secrets.json` match `shared_vars` and the scripts’ defaults.

```bash
cd /path/to/mork
python scripts/download_and_upload_images_gcs.py --dry-run
```

Each script starts with `import mork_repo_root`, which adds the repo root to `sys.path` so imports such as `shared_vars` and `hc_constants` resolve when the file lives under `scripts/`.

| Script | Purpose |
|--------|---------|
| `mork_repo_root.py` | Not run directly; adjusts `sys.path` for other scripts |
| `download_and_upload_images.py` | Sheet → download art → process borders → Google Drive / printable sheet flow |
| `download_and_upload_images_gcs.py` | **Default:** Tokens tab + Database → printable GCS in parallel. Tokens: [Tokens Database](https://docs.google.com/spreadsheets/d/1qqGCedHmQ8bwi-YFjmv-pNKKMjubZQUAaF7ItJN5d1g/edit?gid=2123813197) → token bucket. Printable: Database → arc-aware border prep → optional Ollama assess (`--assess auto\|on\|off`, verdict in cols E–G) → `hellscube-printable-images` → [Printable DB](https://docs.google.com/spreadsheets/d/1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs). `--tokens-only` / `--printable-only` |
| `process_printable_card.py` | Local one-stop pipeline: card image(s) → arc-aware border transform → Ollama vision assessment. `python scripts/process_printable_card.py card.png -o out/`; exit 1 if any card fails |
| `prepare_card_for_printing_stretch.py` | The border transform itself (edge stretch + arc corner fill); used by the GCS sync and `process_printable_card.py`. Debug: `--highlight-samples`, `--highlight-arc` |
| `fix_borders_gcs.py` | Pull printable images from GCS, fix borders, re-upload |
| `printable_image_qa.py` | Shared QA: PIL heuristics, corner crops, two-step Ollama prompts, ``finalize_verdict()`` |
| `review_printable_images.py` | [Printable DB](https://docs.google.com/spreadsheets/d/1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs/edit?gid=0): vision QA → ``Is good?`` (E), ``Bot?`` (F), ``Bot comment`` (G, defect summary when N); ``--n-only`` |
| `review_printable_benchmark.py` | Regression benchmark: labels in ``scripts/data/printable_qa_labels.json`` vs ``review_image()`` |
| `review_printable_harness.py` | Harness: same labels + notes, optional ``--from-compare`` mismatch CSV, ``--verbose`` per-id report |
| `data/printable_qa_labels.json` | Human verdicts and notes for benchmark / harness ids |
| `upload_fixed_fuckups_to_gcs.py` | Printable Fuckups fixed files → GCS + ``Is good?`` = ``Y - Fixed`` |
| `bonus.py` | Small ad-hoc sheet range dump (edit indices in file as needed) |
| `sync_hellfall_ids_to_ba.py` | Hellfall JSON ``id`` → **unapproved**: `Database (Unapproved)` col **BB**, `Tokens Database (Unapproved)` col **L** (headers: UUID) |
| `sync_hellfall_oracle_ids.py` | Hellfall JSON ``oracle_id`` → **unapproved**: cards col **BC**, tokens col **M** (headers: Oracle ID) |
| `sync_tags_to_unapproved.py` | [Hellfall catalog](https://storage.googleapis.com/hellfall-489004-hellfall-catalog/catalog.json) `base_tags` → `Database (Unapproved)` col **V** (keeps all sheet tags; adds missing set tags only; `--overwrite` to replace) |

```bash
python scripts/sync_hellfall_ids_to_ba.py --dry-run
python scripts/sync_hellfall_ids_to_ba.py --limit 5
python scripts/sync_hellfall_oracle_ids.py --dry-run
python scripts/sync_hellfall_oracle_ids.py --limit 5
python scripts/sync_hellfall_oracle_ids.py
python scripts/sync_tags_to_unapproved.py --dry-run
python scripts/sync_tags_to_unapproved.py --limit 50
python scripts/sync_tags_to_unapproved.py
```


### Printable QA benchmark

Human labels live in ``scripts/data/printable_qa_labels.json`` (loaded via ``printable_image_qa.load_benchmark_labels()``). Cache PNGs under ``/tmp/hc-review-test/{id}.png`` to avoid re-downloading from the sheet.

```bash
python scripts/review_printable_harness.py --ids 75,175,186,135 --verbose
python scripts/review_printable_harness.py --from-compare /tmp/printable-compare-300-merged.csv
```

```bash
# Fast sanity check (PIL heuristics only, no Ollama)
python scripts/review_printable_benchmark.py --heuristics-only

# Full vision pipeline (requires Ollama + pulled model)
ollama pull qwen2.5vl:7b
python scripts/review_printable_benchmark.py

# Flags: --model, --no-corner-crops, --single-step, --heuristics-only
python scripts/review_printable_benchmark.py --model qwen2.5vl:7b --single-step
```

Exit code ``0`` only when every benchmark id matches expected; otherwise ``1``.

### Printable sheet review

Add a **Bot comment** header in column **G** (row 1) on the Printable DB sheet if it is not there yet.

```bash
python scripts/review_printable_benchmark.py   # run benchmark first
python scripts/review_printable_images.py --dry-run --limit 5
python scripts/review_printable_images.py --n-only --limit 100   # only write N rows (+ comment in col G)
python scripts/review_printable_compare.py --limit 300 --output /tmp/compare-300.csv
```
