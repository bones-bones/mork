# hellscube-bridge (Devvit)

Devvit app that posts image submissions to a subreddit on behalf of an external backend (Discord bot, webhook, cron job, etc.).

## API

`POST /api/post-card`

Bearer auth must match the global app setting `postCardSecret`.

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

## Settings

Set `postCardSecret` via the Devvit CLI. Use the same value wherever your backend sends `Authorization: Bearer …`.

## External backend

Point your caller at the deployed endpoint URL and shared secret:

```bash
REDDIT_ACCEPT_VIA_DEVVIT=1
DEVVIT_POST_CARD_URL=https://…/api/post-card
DEVVIT_POST_CARD_SECRET=…
```

If the caller runs outside Reddit, confirm the route is reachable from that network. External services may need [external endpoints](https://developers.reddit.com/docs/capabilities/server/external-endpoints) (`/external/…`) instead of `/api/*`.
