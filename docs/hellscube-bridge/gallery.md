# hellscube-bridge daily submissions gallery

Daily gallery of recent `#submissions` cards posted to r/HellsCube (~04:00 UTC).

## Flow

```mermaid
sequenceDiagram
  participant CH as #submissions
  participant M as Mork VM
  participant GCS as hellcube-images
  participant D as hellscube-bridge
  participant R as r/HellsCube

  CH->>M: Card image at intake
  M->>GCS: Store image + manifest entry
  Note over M: Hour 4 UTC
  M->>M: Pick up to 10 HTTPS URLs
  M->>D: POST /external/post-gallery<br/>{ title, imageUrls }
  D->>R: reddit.submitPost (image; native gallery TBD)
  D-->>M: { ok, postId, permalink }
  Note over M: On Devvit failure, asyncpraw gallery fallback
```

Mork still writes the GCS manifest so it has public HTTPS URLs to send. Devvit does **not** fetch that JSON.

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
| `REDDIT_GALLERY_USE_MANIFEST=1` | VM `.env` (default on) | Gallery reads GCS image URLs, not Discord history |
| `REDDIT_GALLERY_VIA_DEVVIT=1` | VM `.env` (default off) | Hour-4 POSTs to `/external/post-gallery`; asyncpraw fallback on failure |
| *(none on Devvit)* | — | Mork chooses transport |

Requires the same `DEVVIT_POST_CARD_URL` + `DEVVIT_POST_CARD_SECRET` as acceptance posts (base URL is rewritten to `/external/post-gallery`).

## Cutover

```bash
REDDIT_GALLERY_VIA_DEVVIT=1
```

Keep asyncpraw fallback until a native gallery `submitPost` exists (or a single-image smoke test succeeds).

## Rollback

```bash
REDDIT_GALLERY_VIA_DEVVIT=0
```

Gallery resumes on Mork via manifest + asyncpraw only.
