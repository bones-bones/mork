# Post–Google Sheets (target)

[← Card flows](README.md)

Target architecture once card data lives in **Hellfall** (via postcard API + catalog) instead of Google Sheets. Discord submission and veto flows stay the same; only the persistence and lookup layers change.

**Status:** acceptance uploads images via Hellfall postcard only (`imageBase64`); unapproved/approved sheets are still written and bot search still loads from the approved sheet.

---

## Current vs target

```mermaid
flowchart LR
  subgraph today["Today"]
    D1["Discord lifecycle"] --> A1["accept"]
    A1 --> G1["GCS images"]
    A1 --> H1["Hellfall postcard<br/>(optional)"]
    A1 --> S1["Unapproved sheet"]
    S1 -->|"manual mod"| S2["Approved sheet"]
    S2 --> B1["Bot search / Hellfall / print scripts"]
  end

  subgraph target["Target"]
    D2["Discord lifecycle<br/>(unchanged)"] --> A2["accept"]
    A2 --> H2["Hellfall postcard<br/>(GCS + catalog)"]
    H2 --> C2["Hellfall catalog / API"]
    C2 --> B2["Bot search / Hellfall / print scripts"]
  end
```

| Concern | Today | Target |
|---------|-------|--------|
| Card record on accept | Row on unapproved sheet | Hellfall document via postcard API |
| Image URL | Mork uploads GCS + copied to sheet col C | Hellfall uploads GCS via postcard; `imageUrl` from response |
| HC numeric id | Sheet col A (increment) | `hcid` passed to postcard; Hellfall assigns UUID |
| Bot `!search`, `!info`, etc. | Load approved **Database** sheet at startup | Load Hellfall catalog (or API) |
| Mod percolation | Manual sheet copy | **Removed** — postcard write is approval |
| Rulings / tags | Unapproved sheet columns | Hellfall fields or dedicated API (TBD) |
| Tokens | Unapproved token sheet + postcard | Postcard only |
| Printable pipeline | Reads Database / Printable DB sheets | Reads Hellfall catalog + GCS |
| Rollback on failed accept | Postcard rollback + no sheet commit if error mid-flight | Postcard rollback (Hellfall may revert GCS object); no sheet step |

---

## End-to-end lifecycle (target)

```mermaid
flowchart TD
  subgraph discord["Discord (unchanged)"]
    SUB["#submissions → veto → !compileveto"] --> ACC["Accept"]
  end

  subgraph persist["Persistence (Hellfall-first)"]
    ACC --> PC["POST /api/cards/postcard<br/>(imageBase64)"]
    PC --> HF[("Hellfall: GCS upload + card store")]
    HF --> CAT["Catalog JSON refresh"]
  end

  subgraph consumers["Consumers"]
    CAT --> MORK["Bot search / card lookup"]
    CAT --> HFWEB["Hellfall site"]
    CAT --> PRINT["Printable pipeline"]
    CAT --> DRAFT["Draftmancer / cube XML"]
  end

  ACC --> CL["Discord card-list channel"]
  ACC --> RED["Reddit (unchanged)"]
```

---

## Acceptance (target)

Replaces the current accept flow where sheet rows are the system of record.

```mermaid
flowchart TD
  IN["Accept card<br/>(compile-veto, errata, design hell, …)"] --> RES["Resolve author names"]
  RES --> ID{"Errata / existing hcid?"}
  ID -->|yes| UPD["Postcard update<br/>hcid = existing id"]
  ID -->|no| NEW["Postcard create<br/>hcid = next numeric id or Hellfall-assigned"]

  UPD --> PC
  NEW --> PC
  PC["POST /api/cards/postcard<br/>imageBase64 → Hellfall uploads GCS<br/>require_sync = true"]
  PC --> OK{"ok?"}
  OK -->|no| RB["POST /api/cards/postcard/rollback"]
  RB --> FAIL["Accept fails — no Discord card-list post"]
  OK -->|yes| URL["Use imageUrl from response"]
  URL --> CL["Post to card-list channel"]
  CL --> RD{"Errata or defer Reddit?"}
  RD -->|no| RED["Reddit"]
  RD -->|yes| DONE["Done"]
  RED --> DONE
```

**Design Hell** already sends `imageBase64` to Hellfall first — that becomes the default for all accepts. Mork stops calling GCS directly; Hellfall owns upload to `hellscube-images` and returns `imageUrl`.

**Errata:** lookup existing card by hcid in Hellfall, not sheet row; update image and metadata via postcard with same `hcid` (Hellfall overwrites the GCS object when applicable).

**No sheet write:** UUID / oracle_id from postcard response are stored in Hellfall only (not mirrored to sheet columns).

---

## Lookup & metadata (target)

```mermaid
flowchart TD
  START["Bot startup / !syncDb"] --> CAT["Fetch Hellfall catalog<br/>(or incremental API)"]
  CAT --> CACHE["In-memory card index<br/>(same CardSearch shape)"]

  subgraph commands["Commands (unchanged UX)"]
    C1["!random !info !search !creator !rulings"]
    C2["!tag / !removetag"]
    C3["!judgement"]
  end

  CACHE --> commands
  BR["{{card name}} in chat"] --> IMG["Post card images from catalog URLs"]
  CACHE --> BR
```

**Open questions for implementation:**

- Rulings and tags: extend postcard API, separate Hellfall admin endpoints, or keep a thin metadata store
- Username mappings: today a sheet tab; move to config file or Hellfall creator normalization
- Errata submission validation: resolve card by hcid via catalog instead of approved sheet

---

## Token acceptance (target)

```mermaid
flowchart TD
  CHK["Token threshold met"] --> PC["POST /api/cards/postcard<br/>kind=token, set=HCT, imageBase64"]
  PC --> HF[("Hellfall: GCS + token record")]
  HF --> CL["#token-list"]
```

Token flow matches target: postcard required, Hellfall owns GCS upload via `imageBase64`.

---

## Printable pipeline (target)

```mermaid
flowchart TD
  CAT["Hellfall catalog"] --> IDS["Card ids + Hellfall image URLs + sides"]
  IDS --> DL["Download from hellscube-images<br/>(uploaded by Hellfall on accept)"]
  DL --> ST["Border stretch transform"]
  ST --> PGCS["hellscube-printable-images bucket"]
  PGCS --> QA["Vision QA"]
```

Sheet-based Printable DB and Database column scans become optional backfill tools, not production path.

---

## Migration phases (suggested)

```mermaid
flowchart LR
  P1["Phase 1<br/>Postcard required on all accepts<br/>Sheet write kept for backup"] --> P2["Phase 2<br/>Bot search reads catalog<br/>Sheet write optional flag"]
  P2 --> P3["Phase 3<br/>Rulings/tags migrated<br/>Remove sheet writes"]
  P3 --> P4["Phase 4<br/>Print scripts catalog-only<br/>Retire mod percolation"]
```

| Phase | Discord | Accept | Read path | Sheets |
|-------|---------|--------|-----------|--------|
| 1 (partial now) | unchanged | mork GCS + postcard; sheet still updated | approved sheet | source of truth for search |
| 2 | unchanged | postcard required; Hellfall GCS | catalog + sheet fallback | dual-write |
| 3 | unchanged | postcard only; Hellfall GCS | catalog | read-only / deprecated |
| 4 | unchanged | postcard only; Hellfall GCS | catalog | removed |

---

## What does not change

- Submission, veto, errata, and compile-veto **Discord** flows
- Reaction-driven state (no enum)
- Card-list channel posts and Reddit deferral
- Cooldown files and background submission checks
- Hellpit threads and veto poll triage logic

See [Overview](overview.md) for the current Discord lifecycle; this doc only replaces the persistence tail.
