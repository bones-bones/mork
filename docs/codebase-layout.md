# Codebase layout

## Design choice: flat root for the bot

Mork loads cogs with `await self.load_extension("cogs.General")` and those modules import **top-level packages by filename** (for example `from accept_card import accept_card`, `from shared_vars import googleClient`). Python’s import path is the repository root when you run `python mork.py` from that root.

Because of that, the “application” modules stay next to `mork.py`. **Do not move** `accept_card.py`, `get_veto_polls_results.py`, `printCardImages.py`, and similar files into a subfolder unless you refactor imports (for example a proper `pip install -e .` package).

## Directories

| Path | Role |
|------|------|
| `mork.py` | Discord bot entrypoint |
| `cogs/` | Extensions loaded in `mork.setup_hook` |
| `cogs/lifecycle/` | Reddit / daily post helpers used by `Lifecycle` |
| `submissions/` | Async checks for token, masterpiece, and errata flows |
| `scripts/` | One-off CLIs (sheets, Drive, GCS). Always run from repo root: `python scripts/<name>.py` |
| `bot_secrets/` | Local credentials (gitignored); use `*.template.py` as a guide |
| `docs/` | Deployment and layout notes (this file, GCP + Actions guide, [card flows](card-flows/README.md)). Update card-flow docs when lifecycle behavior changes. |
| `.github/workflows/` | CI (pre-commit) and optional deploy workflows |

## Root modules (libraries used by cogs)

These are imported directly by cogs or each other:

- `hc_constants.py` — Discord IDs, sheet names, shared constants  
- `shared_vars.py` — gspread / PyDrive clients, Discord intents, global card cache  
- `hellfall_changesets.py`, `hellfall_fetcher.py`, `hellfall_postcard.py`, `hellfall_shared.py` - dealing with the hellfall server
- `getters.py`, `is_mork.py`, `is_admin.py`
- Lifecycle pipeline: `accept_card.py`, `check_submissions.py`, `get_card_message.py`, `get_veto_polls_results.py`, `handle_veto_post.py`, `printCardImages.py`, `reddit_functions.py`  

## Scripts

See [scripts/README.md](../scripts/README.md) for a short index and how to run them.

## Hellfall catalog / sheet dual-write

Bot card search does **not** load the approved Database sheet. Startup (`mork.setup_hook`) and `!syncDb` call `bootstrap_card_cache()` → GCS catalog JSON → in-memory maps.

| Env | Default | Role |
|-----|---------|------|
| `HELLFALL_API_URL` / `HELLFALL_POSTCARD_API_KEY` | (required for postcard) | Accept/promote ingest |
| `HELLFALL_CATALOG_URL` | GCS `…/catalog.json` | Search index source |
| `HELLFALL_SETS_URL` | hellfall `sets.json` | Used only when catalog is a raw `data[]` payload |
| `SHEET_DUAL_WRITE` | `1` | Mirror unapproved/token rows on accept/promote; `0` = postcard-only |
| `USERNAME_MAPPINGS_PATH` | `config/username_mappings.json` | Alias map; sheet tab fallback if missing/empty |
| `STILL_USING_CACHE` | hardcoded `True` in `hellfall_fetcher.py` | Local catalog vs live `/api/mork` |

**Cache TTL:** none. Bootstrap once at startup; refresh with `!syncDb` (`force=True`). Printables: `python scripts/download_and_upload_images_gcs.py --printable-only --printable-source catalog`.

## Tooling

- `pyproject.toml` — Ruff rules used by pre-commit (syntax / undefined-name checks)  
- `.pre-commit-config.yaml` — hooks  
- `requirements-dev.txt` — `pre-commit`, `ruff` for contributors  
- `Dockerfile` — minimal runtime image for GCP or other hosts  
