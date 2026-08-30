# hellscube-bridge (Devvit)

Devvit app that posts image submissions to a subreddit on behalf of an external backend (Discord bot, webhook, cron job, etc.).

## External endpoint (GCP → Reddit)

Production callers outside Reddit use [external endpoints](https://developers.reddit.com/docs/capabilities/server/external-endpoints):

|                  |                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------- |
| **Manifest key** | `server.externalEndpoints.postCard` in `devvit.json`                                          |
| **Route**        | `POST /external/post-card`                                                                    |
| **Scopes**       | `global` (managed App Token)                                                                  |
| **Public URL**   | `https://hellscube-bridge-{subreddit-id}-external.devvit.net/external/post-card`              |
| **Auth header**  | `Authorization: Bearer devvit_at_…`                                                           |
| **Mod docs**     | [`docs/hellscube-bridge/external-endpoint.md`](../docs/hellscube-bridge/external-endpoint.md) |

Use the subreddit **t5 id without the `t5_` prefix** (e.g. `t5_21otlg` → `21otlg`).

**Request body:**

```json
{
  "title": "Card Name by Author was accepted into SET",
  "imageUrl": "https://storage.googleapis.com/.../card.png",
  "flairId": "optional-flair-uuid",
  "subredditName": "HellsCube"
}
```

**Success response:**

```json
{
  "ok": true,
  "postId": "t3_…",
  "permalink": "/r/HellsCube/comments/…"
}
```

## In-app route (optional)

`POST /api/post-card` — for Devvit webview clients only. Auth via global setting `postCardSecret` (CLI). **Not** reachable from GCP.

## Card of the day (scheduler)

Daily HC6 post at **10:00 UTC** via Devvit Scheduler when enabled. Reads the [Hellfall catalog](https://storage.googleapis.com/hellfall-489004-hellfall-catalog/catalog.json).

**Flag (pair with Discord):**

| Path                       | `REDDIT_COTD_VIA_DEVVIT` (VM) | `cardOfTheDayViaDevvit` (app setting) |
| -------------------------- | ----------------------------- | ------------------------------------- |
| Devvit                     | `1`                           | `true`                                |
| Legacy Lifecycle/asyncpraw | off                           | `false`                               |

|             |                                       |
| ----------- | ------------------------------------- |
| **Cron**    | `0 10 * * *`                          |
| **Handler** | `/internal/scheduler/card-of-the-day` |
| **Dedup**   | Redis `cotd:lastDate`                 |

Details: [`docs/hellscube-bridge/scheduler.md`](../docs/hellscube-bridge/scheduler.md).

## Reddit → Discord mirror (PostSubmit)

When enabled, mirrors inbound submission flairs to `#reddit` via Discord webhook.

|             |                                                      |
| ----------- | ---------------------------------------------------- |
| **Trigger** | `onPostSubmit` → `/internal/triggers/on-post-submit` |
| **Dedup**   | Redis `mirror:posted:{postId}`                       |
| **HTTP**    | `discord.com` (webhook)                              |

Details: [`docs/hellscube-bridge/mirror.md`](../docs/hellscube-bridge/mirror.md).

## Discord → Reddit reply

|                  |                                                         |
| ---------------- | ------------------------------------------------------- |
| **Manifest key** | `server.externalEndpoints.replyToPost` in `devvit.json` |
| **Route**        | `POST /external/reply-to-post`                          |
| **Auth**         | Managed App Token (`Authorization: Bearer devvit_at_…`) |
| **Body**         | `{ "postId": "abc123", "text": "…" }`                   |

Details: [`reply.md`](reply.md).

## Daily submissions gallery (scheduler prep)

Reads the GCS manifest Mork writes at `#submissions` intake. **Multi-image gallery posts are blocked** until Reddit exposes a gallery API in Devvit.

|             |                                                 |
| ----------- | ----------------------------------------------- |
| **Cron**    | `0 4 * * *`                                     |
| **Handler** | `/internal/scheduler/daily-submissions-gallery` |
| **Setting** | `dailyGalleryViaDevvit` (default `false`)       |
| **Dedup**   | Redis `gallery:lastDate`                        |

Details: [`gallery.md`](gallery.md).

## Readiness checklist

Config is in place for when Reddit enables external endpoints on your account:

- [x] `devvit.json` declares `server.externalEndpoints.postCard` → `/external/post-card` with `scopes: ["global"]`
- [x] Server handler at `src/server/routes/api.ts` (`external.post('/post-card', …)`)
- [x] `permissions.reddit` (moderator) + `permissions.http` (`storage.googleapis.com`, `lh3.googleusercontent.com`)
- [x] Card-of-the-day scheduler (`card-of-the-day` cron + catalog fetch)
- [x] Reddit → Discord mirror (`onPostSubmit` + webhook; default off)
- [x] Discord → Reddit replies (`/external/reply-to-post`; default off on VM)
- [x] Daily gallery scheduler + GCS manifest writer (multi-image blocked; default off)
- [x] Mork client (`reddit_devvit.py`) validates external URL + managed token format
- [x] Mod-facing endpoint documentation
- [ ] Reddit [external endpoints access](https://developers.reddit.com/docs/capabilities/server/external-endpoints) approved for your account
- [ ] `npx devvit publish` (needs privacy + terms URLs — see [Legal pages](#legal-pages))
- [ ] Managed App Token created in [developer settings](https://developers.reddit.com/apps/hellscube-bridge/developer-settings)
- [ ] Installed on r/HellsCube (`npx devvit install r/HellsCube`)
- [ ] VM `.env` set; `REDDIT_ACCEPT_VIA_DEVVIT=1`

### After approval

1. Upload/publish latest version: `npx devvit publish --bump=patch`
2. Developer settings → create **App Token** → copy `devvit_at_…` once
3. On the VM:

```bash
REDDIT_ACCEPT_VIA_DEVVIT=1
DEVVIT_POST_CARD_URL=https://hellscube-bridge-21otlg-external.devvit.net/external/post-card
DEVVIT_POST_CARD_SECRET=devvit_at_…
```

4. Smoke test from VM:

```bash
curl -sS -X POST "$DEVVIT_POST_CARD_URL" \
  -H "Authorization: Bearer $DEVVIT_POST_CARD_SECRET" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"title":"Test","imageUrl":"https://storage.googleapis.com/…/card.png","subredditName":"HellsCube"}'
```

Until approval, keep `REDDIT_ACCEPT_VIA_DEVVIT` off — asyncpraw fallback handles production.

## Local development

Requires Node **≥ 22.20**.

```bash
npm install
npx devvit login
npm run dev          # playtest on a test subreddit
```

## Deploy

```bash
npm run deploy       # private upload (playtest)
npm run launch       # publish (unlisted; needs legal URLs)
```

## Legal pages

Required for publish (HTTP fetch). Host from repo `docs/` via GitHub Pages:

- [`docs/hellscube-bridge/privacy.html`](../docs/hellscube-bridge/privacy.html)
- [`docs/hellscube-bridge/terms.html`](../docs/hellscube-bridge/terms.html)

URLs: `https://hellscube.github.io/mork/hellscube-bridge/privacy.html` (and `terms.html`).

## CI

- `.github/workflows/devvit-ci.yml` — typecheck + build
- `.github/workflows/devvit-deploy.yml` — manual upload (`DEVVIT_TOKEN`)
