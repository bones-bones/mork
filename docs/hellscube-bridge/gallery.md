# hellscube-bridge daily submissions gallery

Daily gallery of recent `#submissions` cards posted to r/HellsCube (~04:00 UTC).

## Flow

```mermaid
sequenceDiagram
  participant CH as #submissions
  participant M as Mork VM
  participant GCS as hellscube-images
  participant D as hellscube-bridge
  participant R as r/HellsCube

  Note over M: Hour 4 UTC
  M->>CH: History last 24h (Mork polls)
  M->>M: Pick up to 10 cards + download
  M->>GCS: Stage images (allowlisted HTTPS)
  M->>D: POST /external/post-gallery<br/>{ title, imageUrls }
  D->>R: reddit.submitPost (image; native gallery TBD)
  D-->>M: { ok, postId, permalink }
  Note over M: On Devvit failure (incl. multi-image 501), asyncpraw fallback
```

Mork owns card selection from Discord. At post time it stages copies on GCS (`storage.googleapis.com`, already HTTP-allowlisted for Devvit), then posts through the bridge. There is no intake-time gallery manifest.

## Endpoint

| | |
|---|---|
| **Route** | `POST /external/post-gallery` |
| **Auth** | Managed App Token (`Authorization: Bearer devvit_at_…`) |
| **Body** | `{ "title"?: "…", "imageUrls": ["https://…"], "flairId"?: "…", "subredditName"?: "HellsCube" }` |
| **Max images** | 10 |

`title` defaults to the usual gallery headline. `flairId` defaults to Official HC.

**Native multi-image gallery posts are not in Devvit yet** (`submitPost` `imageUrls` is a single-URL tuple). The endpoint still **accepts** up to 10 picture URLs. One image is posted; more than one returns `501` `{ "ok": false, "error": "reddit_gallery_api_unavailable" }` so Mork can fall back to asyncpraw.

## Feature flags

| Switch | Where | Effect |
|--------|-------|--------|
| `REDDIT_GALLERY_VIA_DEVVIT` | VM `.env` (**default on**) | Hour-4 stages Discord picks on GCS and POSTs to `/external/post-gallery` |
| `REDDIT_GALLERY_VIA_DEVVIT=0` | VM `.env` | Emergency asyncpraw-only rollback |

Requires `DEVVIT_POST_CARD_URL` + `DEVVIT_POST_CARD_SECRET` (base URL is rewritten to `/external/post-gallery`).

## Rollback

```bash
REDDIT_GALLERY_VIA_DEVVIT=0
```

Gallery resumes on Mork via Discord history + asyncpraw only.
