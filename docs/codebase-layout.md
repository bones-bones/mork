# Codebase layout

## Design choice: flat root for the bot

Mork loads cogs with `await self.load_extension("cogs.General")` and those modules import **top-level packages by filename** (for example `from acceptCard import acceptCard`, `from shared_vars import googleClient`). Python’s import path is the repository root when you run `python Mork.py` from that root.

Because of that, the “application” modules stay next to `Mork.py`. **Do not move** `acceptCard.py`, `getVetoPollsResults.py`, `printCardImages.py`, and similar files into a subfolder unless you refactor imports (for example a proper `pip install -e .` package).

## Directories

| Path | Role |
|------|------|
| `Mork.py` | Discord bot entrypoint |
| `cogs/` | Extensions loaded in `Mork.setup_hook` |
| `cogs/lifecycle/` | Reddit / daily post helpers used by `Lifecycle` |
| `submissions/` | Async checks for token, masterpiece, and errata flows |
| `scripts/` | One-off CLIs (sheets, Drive, GCS). Always run from repo root: `python scripts/<name>.py` |
| `bot_secrets/` | Local credentials (gitignored); use `*.template.py` as a guide |
| `docs/` | Deployment and layout notes (this file, GCP + Actions guide) |
| `.github/workflows/` | CI (pre-commit) and optional deploy workflows |

## Root modules (libraries used by cogs)

These are imported directly by cogs or each other:

- `hc_constants.py` — Discord IDs, sheet names, shared constants  
- `shared_vars.py` — gspread / PyDrive clients, Discord intents, global card cache  
- `CardClasses.py`, `cardNameRequest.py`, `getters.py`, `is_mork.py`, `is_admin.py`, `isRealCard.py`  
- Lifecycle pipeline: `acceptCard.py`, `checkSubmissions.py`, `getCardMessage.py`, `getVetoPollsResults.py`, `handleVetoPost.py`, `printCardImages.py`, `reddit_functions.py`  

## Scripts

See [scripts/README.md](../scripts/README.md) for a short index and how to run them.

## Tooling

- `pyproject.toml` — Ruff rules used by pre-commit (syntax / undefined-name checks)  
- `.pre-commit-config.yaml` — hooks  
- `requirements-dev.txt` — `pre-commit`, `ruff` for contributors  
- `Dockerfile` — minimal runtime image for GCP or other hosts  
