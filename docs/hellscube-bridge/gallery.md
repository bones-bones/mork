# hellscube-bridge daily submissions gallery

Daily gallery of recent `#submissions` cards posted to r/HellsCube (~04:00 UTC).

## Data layer (GCS manifest)

Mork appends to a public JSON manifest when a card lands in `#submissions`:

| | |
|---|---|
| **Object** | `mork/submissions-gallery-manifest.json` on `hellcube-images` |
| **Default URL** | `https://storage.googleapis.com/hellcube-images/mork/submissions-gallery-manifest.json` |
| **Writer** | `submissions_gallery_manifest.append_submission()` from `Lifecycle.py` |
| **Entry shape** | `{ messageId, imageUrl, submittedAt, cardName? }` |

Images are stored under `submissions-gallery/{messageId}.{ext}` on GCS.

## Posting (today)

**Devvit cannot submit native Reddit gallery posts yet** (no multi-image `submitPost`). Until Reddit adds that API:

| Path | Who posts | Transport |
|------|-----------|-----------|
| **Production default** | Mork VM hour-4 job | asyncpraw gallery from GCS manifest |
| **Future** | Devvit scheduler | Blocked at `reddit_gallery_api_unavailable` when >1 image |

### Mork flags

| Switch | Where | Effect |
|--------|-------|--------|
| `REDDIT_GALLERY_USE_MANIFEST=1` | VM `.env` (default on) | Gallery reads GCS manifest, not Discord history |
| `REDDIT_GALLERY_VIA_DEVVIT=0` | VM `.env` (default off) | Mork still posts gallery; skip when Devvit owns it |

### Devvit settings (prep / future)

| Setting | Default | Role |
|---------|---------|------|
| `submissionsGalleryManifestUrl` | GCS default | Manifest fetch URL |
| `dailyGalleryViaDevvit` | `false` | Scheduler runs; multi-image still skipped |
| **Dedup** | Redis `gallery:lastDate` | One gallery attempt per UTC day |

| Task | Cron | Handler |
|------|------|---------|
| `daily-submissions-gallery` | `0 4 * * *` | `/internal/scheduler/daily-submissions-gallery` |

## Cutover checklist (when gallery API exists)

1. Implement `submitGalleryPost()` in `mork-devvit` once Devvit supports it
2. `npx devvit settings set dailyGalleryViaDevvit` → `true`
3. VM: `REDDIT_GALLERY_VIA_DEVVIT=1`
4. Verify hour-4 gallery on Reddit; Mork hour-4 branch skipped

## Rollback

```bash
REDDIT_GALLERY_VIA_DEVVIT=0
npx devvit settings set dailyGalleryViaDevvit   # → false
```

Gallery resumes on Mork via manifest + asyncpraw.
