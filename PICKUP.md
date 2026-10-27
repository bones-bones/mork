# Pickup: cards-into-db-sooner

**Branch:** `cards-into-db-sooner`  
**Status:** Phase 1–4 implemented; open as one PR.

## Phase 1 (promote / finalize)

| Step | Function | Meaning |
|------|----------|---------|
| Threshold / `reasonable_card` | `promote_from_submissions` → `intake_veto_poll_message` | Hellfall postcard + optional sheet; `#veto-polls` + `uuid:` thread line |
| `!compileveto` | `accept_card(..., existing_hcid=…)` | Official / vetoed — no second postcard when already promoted |

## Phases 2–4

See [migration-phases-tasks.md](docs/card-flows/migration-phases-tasks.md) (all checked).

- Catalog search: `bootstrap_card_cache` / `!syncDb`
- `SHEET_DUAL_WRITE` (default `1`)
- Printables: `--printable-source catalog`

## Before merge / deploy

1. Smoke: promote → veto thread has `uuid:` + hellpit → compile accept → no duplicate Firestore doc
2. Legacy veto poll without UUID → full `accept_card` still works
3. Keep `SHEET_DUAL_WRITE=1` in prod until catalog parity verified, then consider `0`
