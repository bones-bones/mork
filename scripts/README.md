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
| `download_and_upload_images_gcs.py` | [Tokens Database](https://docs.google.com/spreadsheets/d/1qqGCedHmQ8bwi-YFjmv-pNKKMjubZQUAaF7ItJN5d1g/edit?gid=2123813197) tab (cols A=name, B=image) → GCS; defaults to tab gid `2123813197`; `--help` for flags |
| `fix_borders_gcs.py` | Pull printable images from GCS, fix borders, re-upload |
| `bonus.py` | Small ad-hoc sheet range dump (edit indices in file as needed) |
