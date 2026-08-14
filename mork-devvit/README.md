# hellscube-bridge (Devvit)

Devvit server app that posts image submissions to a subreddit on behalf of an external backend (Discord bot, webhook, cron job, etc.).

## API

`POST /api/post-card`

Bearer auth must match the global app setting `postCardSecret` (see [Settings](#settings)).

**Request body:**

```json
{
  "title": "Card Name by Author was accepted into SET",
  "imageUrl": "https://storage.googleapis.com/.../card.png",
  "flairId": "optional-flair-uuid",
  "subredditName": "YourSubreddit"
}
```

**Success response:**

```json
{
  "ok": true,
  "postId": "t3_…",
  "permalink": "/r/YourSubreddit/comments/…"
}
```

`imageUrl` must be HTTPS. The host must be listed under `permissions.http.domains` in `devvit.json`.

## Requirements

- Node **≥ 22.20**
- Reddit developer account (`npx devvit login`)
- Moderator access on the target subreddit(s)

## Local development

```bash
npm install
npx devvit login
npm run dev          # playtest on a test subreddit
```

Build only:

```bash
npm run build
```

## Settings

Global secrets are set via CLI (not the developer portal UI):

```bash
npx devvit settings set postCardSecret
npx devvit settings list
```

Use the same value wherever your backend sends `Authorization: Bearer …`.

## Deploy

### Private (playtest / dev)

Upload creates a **private** version — fine for playtest and installs you manage manually:

```bash
npm run deploy         # devvit upload
# or: npx devvit upload --bump=patch
```

After upload, open the app in the [developer portal](https://developers.reddit.com/my/apps).

### Unlisted (recommended for production)

To move off private-only builds, **publish** the version. Unlisted apps can be installed on any subreddit where you are a moderator; they are not listed in the public app directory.

```bash
npm run launch         # devvit publish
# or: npx devvit publish --bump=patch
```

Because this app uses HTTP fetch, Reddit requires **terms & conditions** and a **privacy policy** before publish will succeed.

Source copies live in [`docs/hellscube-bridge/`](../docs/hellscube-bridge/). After GitHub Pages is enabled (see [Legal pages](#legal-pages)), paste these URLs into [developer settings](https://developers.reddit.com/apps/hellscube-bridge/developer-settings):

| Field | URL |
|-------|-----|
| Privacy policy | `https://hellscube.github.io/mork/hellscube-bridge/privacy.html` |
| Terms & conditions | `https://hellscube.github.io/mork/hellscube-bridge/terms.html` |

Then run `npx devvit publish` again.

After publishing, install or upgrade on each target sub:

```bash
npx devvit install r/YourSubreddit
```

Use **Update** in the portal if an existing install does not pick up the new version automatically.

### Public (optional)

To list the app in Reddit’s public Devvit directory (review required):

```bash
npx devvit publish --public --bump=patch
```

Most internal bridge apps only need **unlisted**, not public.

## External backend integration

Point your caller at the deployed endpoint URL and shared secret. Example environment variables:

```bash
REDDIT_ACCEPT_VIA_DEVVIT=1
DEVVIT_POST_CARD_URL=https://…/api/post-card
DEVVIT_POST_CARD_SECRET=…
```

If the caller runs outside Reddit (e.g. a VM or another service), confirm the route is reachable from that network. Devvit’s `/api/*` routes are intended for in-app clients; external services may need [external endpoints](https://developers.reddit.com/docs/capabilities/server/external-endpoints) (`/external/…`) instead.

## CI

GitHub Actions workflows live in the repo root:

- `.github/workflows/devvit-ci.yml` — typecheck + build on changes
- `.github/workflows/devvit-deploy.yml` — manual upload (requires `DEVVIT_TOKEN` secret)

## Permissions

Configured in `devvit.json`:

| Permission | Purpose |
|------------|---------|
| `reddit` (moderator) | Submit posts with flair via `reddit.submitPost` |
| `http` | Fetch remote image URLs before posting |

Add domains to `permissions.http.domains` for any image hosts your backend uses.

## Legal pages

Static policy pages for Reddit publish requirements:

- [`docs/hellscube-bridge/privacy.html`](../docs/hellscube-bridge/privacy.html)
- [`docs/hellscube-bridge/terms.html`](../docs/hellscube-bridge/terms.html)

**Enable GitHub Pages** (one-time, repo admins):

1. GitHub → **Settings** → **Pages**
2. **Build and deployment** → Source: **Deploy from a branch**
3. Branch: **main**, folder: **/docs**
4. Save; wait for the site at `https://hellscube.github.io/mork/`

Use the `privacy.html` and `terms.html` URLs above in the Devvit developer portal.
