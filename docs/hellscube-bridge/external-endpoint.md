# hellscube-bridge — external endpoint

Documentation for moderators evaluating this Devvit app. See also [Reddit’s external endpoints guide](https://developers.reddit.com/docs/capabilities/server/external-endpoints).

## Purpose

Allows an **authorized backend** (HellsCube Discord bot on GCP) to request a Reddit image post when the veto council accepts or vetoes a card. The app runs on Reddit’s platform and posts via the Reddit API as the installed app account.

## Endpoint

|                |                                                                                          |
| -------------- | ---------------------------------------------------------------------------------------- |
| **Method**     | `POST`                                                                                   |
| **Path**       | `/external/post-card`                                                                    |
| **Public URL** | `https://hellscube-bridge-{subreddit-id}-external.devvit.net/external/post-card`         |
| **Auth**       | Managed App Token in `Authorization: Bearer devvit_at_…` (created in developer settings) |
| **Rate limit** | 5 req/s (Reddit platform default)                                                        |
| **Body limit** | 10 MB                                                                                    |

Use the subreddit **t5 id without the `t5_` prefix** in the hostname (r/HellsCube → `21otlg`).

## Request body

```json
{
  "title": "Card Name by Author was accepted into SET",
  "imageUrl": "https://storage.googleapis.com/.../card.png",
  "flairId": "optional-flair-uuid",
  "subredditName": "HellsCube"
}
```

## Response

Success (`200`):

```json
{
  "ok": true,
  "postId": "t3_…",
  "permalink": "/r/HellsCube/comments/…"
}
```

Error (`4xx`/`5xx`):

```json
{
  "ok": false,
  "error": "description"
}
```

## Reply endpoint (`/external/reply-to-post`)

|                |                                                                                      |
| -------------- | ------------------------------------------------------------------------------------ |
| **Method**     | `POST`                                                                               |
| **Path**       | `/external/reply-to-post`                                                            |
| **Public URL** | `https://hellscube-bridge-{subreddit-id}-external.devvit.net/external/reply-to-post` |
| **Auth**       | Managed App Token in `Authorization: Bearer devvit_at_…`                             |

**Request body:**

```json
{
  "postId": "abc123",
  "text": "i'm just a bot that can't see pictures, but if i could, i'd say: …"
}
```

`postId` may include or omit the `t3_` prefix.

**Success response:**

```json
{
  "ok": true,
  "commentId": "t1_…",
  "permalink": "/r/HellsCube/comments/…"
}
```

Mork enables this path with `REDDIT_REPLY_VIA_DEVVIT=1` (default off). See [`reply.md`](reply.md).

## Data handling

- **Inbound:** title, image URL, flair id, target subreddit — from the authorized backend only.
- **Outbound HTTP:** fetches the provided `imageUrl` from allow-listed hosts (`storage.googleapis.com`, `lh3.googleusercontent.com`) to submit the Reddit post.
- **No** end-user signup, ads, or sale of data.

## Permissions required

- Reddit API (moderator scope) — submit posts with flair
- HTTP fetch — retrieve card images from GCS
