# Background & lookup

[← Card flows](README.md)

## Lifecycle cron loop

Runs every 5 minutes. No idea which timezone the instance runs on.

```mermaid
flowchart TD
  LOOP["Every 5 minutes"] --> R1["Reset submission cooldowns<br/>(#submissions skips Tue/Sat Eastern)"]
  R1 --> R2["Ensure submissions day marker"]
  R2 --> R3["Check standard submissions"]
  R3 --> R4["Check masterpiece submissions"]
  R4 --> R5["Check token submissions"]
  R5 --> R6["Cross-post Reddit posts"]
  R6 --> R7["Check errata veto threshold"]

  LOOP --> T0{"Is <= the 4th minute of the hour?"}
  T0 -->|yes| RC["Redditcatchup — 1 deferred post"]
  LOOP --> T1{"Is it the <=4th minute of the 4th hour?"}
  T1 -->|yes| GAL["Daily submissions gallery → Reddit"]
  LOOP --> T2{"Is it the <=4th minute of the 10th hour<br/>and REDDIT_COTD_VIA_DEVVIT off?"}
  T2 -->|yes| COTD["HC6 card-of-the-day → Reddit (asyncpraw)"]
```

Flag `REDDIT_COTD_VIA_DEVVIT=1` skips the hour-10 branch here; Devvit scheduler handles COTD instead (when `cardOfTheDayViaDevvit` app setting is on).

`reset_countdowns` keeps `#submissions` cooldown rows until 22 **open** hours have passed (Tuesday and Saturday in US Eastern do not count). Masterpiece cooldowns still use wall-clock hours.

---

## Reddit → Discord

Cron: `check_reddit` every 5 minutes (see lifecycle loop above).

**Inbound flairs** (posts matching any of these are cross-posted to `#reddit`):

| Flair                                          | Discord prefix                             |
| ---------------------------------------------- | ------------------------------------------ |
| Card Idea, HellsCube Submission, Brainstorming | `reddit says:`                             |
| Hellscube Would Love This (Shitpost)           | `Reddit thinks Hellscube would love this:` |

```mermaid
flowchart LR
  R1["Reddit post<br/>(inbound flairs above)"] --> CH["#reddit channel"]
  CH --> REP["User reply in #reddit"]
  REP --> BOT["Bot replies on Reddit post<br/>(reddit says: only)"]
```

Reply bridge only fires when the prior Mork message starts with `reddit says:` — not the shitpost prefix.

---

## Discord → Reddit

**Outbound flair:** all posts use **Official HC** (`OFFICIAL_HC_REDDIT_FLAIR`). Accepted and vetoed cards share the same flair in code.

**Outbound titles:** card acceptance posts use the card's **set ID** in the title (e.g. `was accepted into SOH`, `was accepted into SCL.X`), not `CUBE_NAME`.

Stage 1 Devvit migration: **immediate acceptance/veto posts only** can route through `mork-devvit` when flagged. Everything else still uses asyncpraw.

```mermaid
flowchart TD
  subgraph immediate["Immediate accept/veto (accept_card)"]
    ACC["Card acceptance / veto<br/>(≤ 5 cards in compile batch)"] --> FLAG{"REDDIT_ACCEPT_VIA_DEVVIT?"}
    FLAG -->|yes| DEV["mork-devvit /api/post-card"]
    FLAG -->|no| PRAW1["asyncpraw post_to_reddit"]
    DEV -->|fail| PRAW1
    DEV --> RED["r/HellsCube · Official HC flair"]
    PRAW1 --> RED
  end

  subgraph asyncpraw_only["asyncpraw only (not yet ported)"]
    RC["Redditcatchup / deferred_reddit"] --> PRAW2["asyncpraw"]
    GAL["Daily submissions gallery"] --> PRAW2
    COTD_FLAG{"REDDIT_COTD_VIA_DEVVIT off?"} -->|yes| COTD["HC6 card-of-the-day"] --> PRAW2
    PRAW2 --> RED
  end

  subgraph devvit_scheduled["Devvit scheduler (flag on)"]
    COTD_FLAG2{"cardOfTheDayViaDevvit on?"} -->|yes| DEV2["hellscube-bridge scheduler"]
    DEV2 --> RED
  end
```

| Outbound path | Transport | Image source |
| ------------- | --------- | ------------ |
| Immediate accept/veto | Devvit (optional) → asyncpraw fallback | Hellfall GCS URL or `tempImages/` |
| Deferred batch (`> 5` cards) | asyncpraw | `deferred_reddit/` files |
| Daily gallery | asyncpraw | Discord submission attachments |
| Card of the day (Devvit) | Devvit scheduler when `REDDIT_COTD_VIA_DEVVIT=1` + app setting | [Hellfall catalog](https://storage.googleapis.com/hellfall-489004-hellfall-catalog/catalog.json) |
| Card of the day (legacy) | Lifecycle/asyncpraw when flag off | HC6 sheet image URL → temp file |
| Discord → Reddit reply | asyncpraw | — |

---

## Database lookup & metadata

**Entry:** Bot startup

| Trigger                 | Calls                             | Writes                       |
| ----------------------- | --------------------------------- | ---------------------------- |
| `!random`               | `api/cards/random` → random image | —                            |
| `!info`                 | `fuzzy` → info                    | —                            |
| `!search`               | `api/cards/search` → names        | —                            |
| `!creator`              | `fuzzy` → creators                | —                            |
| `!rulings`              | `fuzzy` → rulings                 | —                            |
| `{{card name}}` in chat | `multiple_fuzzy` → image          | —                            |
| `!judgement`            | `exact` → hcid                    | Unapproved · rulings (col 8) |
| `!tag` / `!removetag`   | `api/cards/:id/tags` via `exact`  | live db (adds changeset)     |

Lookup replies, errata images, and legacy COTD temp files name the attachment from **magic bytes** (then `Content-Type`), not the URL suffix — so a GIF stored at a `.png` GCS URL still posts as `.gif`.

---

## Auxiliary card-adjacent flows

```mermaid
flowchart TD
  subgraph social
    BR["!goodbye in card-brazil / one-word"] --> CUBE["Collapse → #cube"]
    MW["#modwork-requests"] --> VOTE["Vote thread on art request"]
    ART["📌 ×10 in #art-requests"] --> PIN["Pin art request"]
  end

  subgraph moderation
    DEL["❌ by mentioned author<br/>on Mork post"] --> RM["Delete Mork post"]
    JCT["!jct / !join_card_thread"] --> HP["Join hellpit thread<br/>(skeleton role)"]
  end
```
