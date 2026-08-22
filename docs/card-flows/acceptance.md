# Acceptance

[← Card flows](README.md)

## accept_card (persistence)

Called from compile-veto, graveyard fast-track, instaerrata, sneak accept, scube lair, and errata flows.

```mermaid
flowchart TD
  IN["Accept card"] --> RES["Resolve author(s) names"]
  RES --> ROW{"Errata ID matches<br/>existing row?"}
  ROW -->|yes| UPD["Update row image URL"]
  ROW -->|no| NEW["Append id, name, author, set<br/>+ Hellfall UUID columns"]

  UPD --> IMG
  NEW --> IMG
  IMG["POST /api/cards/postcard (imageBase64)<br/>Hellfall uploads to GCS"]
  IMG --> CL["Post **Name** by **Author** + image<br/>to card-list Discord channel"]
  CL --> RD{"Errata or skip Reddit?"}
  RD -->|yes| DONE["Done"]
  RD -->|no| BATCH{"> 5 Reddit-eligible<br/>cards this compile?"}
  BATCH -->|yes| DEF["Defer to deferred_reddit/<br/>(asyncpraw via catchup)"]
  BATCH -->|no| IMM["Immediate Reddit post"]
  DEF --> DONE
  IMM --> DONE
```

### Reddit posting (immediate accepts only)

When compile-veto has **≤ 5** Reddit-eligible cards, each accept/veto posts immediately. Larger batches defer everything to `deferred_reddit/` (always asyncpraw today).

```mermaid
flowchart TD
  IN["Immediate post path<br/>(not deferred, not errata)"] --> TITLE["Title: … was accepted/vetoed from {setId}"]
  TITLE --> FLAG{"REDDIT_ACCEPT_VIA_DEVVIT=1?"}
  FLAG -->|yes| DV["POST mork-devvit /api/post-card<br/>imageUrl from Hellfall GCS"]
  DV --> OK{"Devvit ok?"}
  OK -->|yes| DONE["Done"]
  OK -->|no| FB["Fallback: post_to_reddit<br/>(local tempImages file)"]
  FLAG -->|no| PRAW["post_to_reddit<br/>(asyncpraw)"]
  FB --> DONE
  PRAW --> DONE
```

**Defaults:** set `ACTIVE_CUBE_ID` (`HC9.1`), card list `NINE_CARD_LIST`  
**Design Hell:** mandatory Hellfall postcard sync

**Reddit title:** `post_to_reddit` builds `"… was accepted into {set_id}"` (or `"… was vetoed from {set_id}"`) from the card's set — not `CUBE_NAME`. Scube Lair gold uses the pinned set (e.g. `SCL.X`); compile-veto accepts use `ACTIVE_CUBE_ID`.

**Stage-1 Devvit (optional):** when `REDDIT_ACCEPT_VIA_DEVVIT=1`, immediate posts go to `mork-devvit` `/api/post-card` using the Hellfall GCS `imageUrl`; falls back to asyncpraw on failure. Deferred batches still use `deferred_reddit/` + asyncpraw.

**Deferred overflow** (`deferred_reddit/` when batch > 5): manifest stores one JSON object per line (`filename`, `card_message`, `set_id`, `was_vetoed`) so Unicode, tabs, and quotes in card names round-trip safely. Older tab-separated manifests still parse.

---

## IMG step (image upload + Hellfall sync)

Runs after the sheet row is resolved (new append or errata update). Implemented in `accept_card.py` → `_resolve_accepted_image_url`.

### Input

Callers download the Discord attachment **before** `accept_card` — the pipeline never uses a Discord CDN URL directly.

| Caller                                               | How bytes arrive                |
| ---------------------------------------------------- | ------------------------------- |
| compile-veto, instaerrata, sneak accept, Scube Lair | `await attachment.to_file()`    |
| graveyard fast-track                                 | `attachment.read()` → `BytesIO` |

Inside `accept_card`, bytes are written to `tempImages/{cardName}{ext}` (slashes in the name become `|`) and kept for Reddit posting until the end of the flow.

### Sub-flow

```mermaid
flowchart TD
  IN["Discord attachment bytes"] --> TMP["Write tempImages/…"]
  TMP --> SYNC{"MORK_POSTCARD_SYNC on<br/>or Scube Lair?"}
  SYNC -->|no| FAIL["Accept fails"]
  SYNC -->|yes| B64["POST /api/cards/postcard<br/>imageBase64"]
  B64 --> OK{"imageUrl returned?"}
  OK -->|yes| URL["Sheet col C = Hellfall imageUrl"]
  OK -->|no| FAIL
  B64 -->|error| FAIL
```

### Image storage

Mork does **not** upload card or token images to GCS or Drive. Hellfall receives `imageBase64` via the postcard API, uploads to `hellscube-images` server-side, and returns `imageUrl`.

Discord card-list attachments and deferred Reddit files use the extension from **magic bytes** (GIF/PNG/JPEG/WebP), not a hardcoded `.png`. Postcard also sends `imageMimeType` (from those bytes) with `imageBase64` so Hellfall can store GIFs as `.gif`.

### Hellfall postcard sync

Optional for most accepts; **mandatory** for Scube Lair (`require_hellfall_postcard=True`).

| Env var                     | Role                                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------------------------- |
| `MORK_POSTCARD_SYNC`        | Default `"1"`. Set to `0` / `false` / `no` / `off` to skip optional sync. Ignored when sync is required. |
| `HELLFALL_API_URL`          | API base (required when sync runs)                                                                       |
| `HELLFALL_POSTCARD_API_KEY` | Bearer token                                                                                             |

**Endpoint:** `POST {HELLFALL_API_URL}/api/cards/postcard`

Payload includes `name`, `creators`, `set`, `kind: "card"`, `imageBase64`, and `imageMimeType` (`image/png`, `image/gif`, `image/jpeg`, or `image/webp` when sniffable). Errata and new cards both send `hcid` (existing id or next numeric id).

**Response used:** `imageUrl`, `id` (Hellfall UUID → sheet col BB), `oracle_id` (→ col BC). On new cards only, UUID columns are written when sync succeeds.

**Failure:** If anything after a successful postcard write throws, `POST …/postcard/rollback` runs before the error propagates. Scube Lair aborts acceptance entirely if sync does not complete.

### Default vs Scube Lair

|                    | New card / errata (`MORK_POSTCARD_SYNC` on) | Scube Lair                              |
| ------------------ | ------------------------------------------- | ---------------------------------------- |
| Image path         | `imageBase64` → Hellfall uploads to GCS     | Same                                     |
| Sync required?     | No — gated by `MORK_POSTCARD_SYNC`          | Yes — `require_sync=True`                |
| URL in sheet col C | Hellfall `imageUrl`                         | Hellfall `imageUrl`                      |

### Errata vs new card (image)

|                    | New card                           | Errata                                |
| ------------------ | ---------------------------------- | ------------------------------------- |
| `hcid` to Hellfall | Next numeric id                    | Existing `errataId`                   |
| Image upload       | Hellfall via `imageBase64`         | Hellfall via `imageBase64`            |
| Sheet write        | Cols A, B, C, D, E + BB/BC on sync | **Col C only** (image URL)            |
| Reddit             | Posted (unless batch deferred)     | Skipped                               |
| Reddit transport   | Devvit `/api/post-card` if flagged | N/A                                   |
