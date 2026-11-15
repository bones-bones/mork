# hellscube-bridge — deferred Reddit queue

Replaces Mork’s `deferred_reddit/` filesystem queue when `REDDIT_DEFERRED_VIA_DEVVIT=1`. Large compile-veto batches (`> 5` Reddit-eligible cards) enqueue Hellfall GCS `imageUrl`s into Devvit Redis; `!redditcatchup` / hourly catchup / mod menu drain them via `submitImagePost`.

## Redis layout

| Key | Type | Role |
| --- | ---- | ---- |
| `deferred:queue` | sorted set | FIFO by enqueue timestamp (`score`); `member` = item id |
| `deferred:items` | hash | `field` = item id → JSON `{ id, title, imageUrl, flairId?, subredditName?, enqueuedAt }` |

Devvit Redis has no list type; sorted sets are the supported queue pattern.

## External endpoints

All use the managed App Token (`Authorization: Bearer devvit_at_…`), same host as `/external/post-card`.

### `POST /external/deferred-enqueue`

```json
{
  "title": "Card Name by Author was accepted into SET",
  "imageUrl": "https://storage.googleapis.com/.../card.png",
  "flairId": "optional-flair-uuid",
  "subredditName": "HellsCube"
}
```

Success: `{ "ok": true, "id": "…", "pending": 12 }`

### `POST /external/deferred-drain`

```json
{ "count": 1 }
```

Success: `{ "ok": true, "posted": 1, "pending": 11, "errors": [] }`

Failed posts stay at the front of the queue (errors listed); later items in the same drain still run.

### `POST /external/deferred-status`

Body optional (`{}`). Success: `{ "ok": true, "pending": 11 }`

## Mork flags

| Env | Default | Behavior |
| --- | ------- | -------- |
| `REDDIT_DEFERRED_VIA_DEVVIT=1` | off | Enqueue + drain via Devvit; filesystem/`asyncpraw` fallback on enqueue/drain failure |
| unset / `0` | — | Legacy `deferred_reddit/` + `asyncpraw` only |

`!redditcatchup N` and the hourly Lifecycle drain still orchestrate from Discord; pending count is filesystem + Devvit when the flag is on.

## Mod menu

Subreddit menu (moderators): **Post 1 deferred Reddit card** → `/internal/menu/drain-deferred` (drains one item; toast with remaining count).

## Cutover

1. External endpoints approved + `DEVVIT_POST_CARD_*` on the VM.
2. Publish hellscube-bridge with deferred routes.
3. Drain any leftover `deferred_reddit/` batches (or leave flag off until empty).
4. Set `REDDIT_DEFERRED_VIA_DEVVIT=1` and restart Mork.
