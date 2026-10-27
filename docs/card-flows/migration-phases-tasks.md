# Migration phases 2–4 — task backlog

[← Post–Google Sheets (target)](post-sheets.md)

Concrete follow-ups after submission **promote** + compile **finalize** (Phase 1).

## Phase 2 — Bot search reads catalog

- [x] Hellfall catalog fetch on startup / `!syncDb` — `bootstrap_card_cache()` (bot never loaded approved sheet for search)
- [x] Search index = catalog — no sheet fallback needed; documented in `docs/codebase-layout.md`
- [x] Dual-write stays default on (`SHEET_DUAL_WRITE=1`) until ops set `0` after parity
- [x] Document env vars and cache TTL (no TTL; `!syncDb` refresh) in `docs/codebase-layout.md`

## Phase 3 — Rulings/tags + drop sheet writes

- [x] Decide rulings/tags store — tags via Hellfall `modifyTagWithServer`; rulings **read** from catalog (`SearchCard.rulings`); **write** via `!judgement` only when `SHEET_DUAL_WRITE=1` (Hellfall rulings API TBD)
- [x] Migrate username mappings — `config/username_mappings.json` or `USERNAME_MAPPINGS_PATH`; sheet tab fallback when file missing/empty
- [x] Gate unapproved/token sheet writes — `SHEET_DUAL_WRITE=0` skips writes; Hellfall postcard always runs (`sheet_dual_write.py`)
- [x] Errata validation — resolve by `hcid` via catalog (`getExactCard` / `get_id_by_hcid`); sheet row optional dual-write only

## Phase 4 — Print pipeline + retire percolation

- [x] Printable scripts read catalog + Hellfall image URLs (`--printable-source catalog`)
- [x] Remove manual mod “copy unapproved → approved” from runbooks once postcard is approval
- [x] Retire sheet as system of record; keep export/backfill tools only (`--printable-source sheet`)

## Out of scope here

- `hellfall_changesets.py` bot integration beyond tags
- Token flow (already postcard-first; no promote split)
- Hellfall rulings **write** API (judgement stays sheet-gated)
