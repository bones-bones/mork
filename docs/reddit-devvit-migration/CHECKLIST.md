# Reddit → Devvit migration checklist

Living tracker for cutover state. Ops steps: [`deploy-checklist.md`](../hellscube-bridge/deploy-checklist.md).

**Last updated:** 2026-08-29

## Platform

| Item                               | Status | Notes                                                     |
| ---------------------------------- | ------ | --------------------------------------------------------- |
| `hellscube-bridge` app scaffolded  | ✅     | `mork-devvit/`                                            |
| Published on Devvit                | ✅     | Required for r/HellsCube (>200 subs)                      |
| Installed on r/HellsCube           | ✅     |                                                           |
| External endpoints access approved | ⏳     | **Current blocker** — GCP → Devvit POST not allowed yet   |
| Managed App Token on VM            | ⏳     | `devvit_at_…` in `DEVVIT_POST_CARD_SECRET` after approval |
| Developer Funds application        | ⬜     | Optional                                                  |

## Code (implemented)

| Item                                                         | Status                   |
| ------------------------------------------------------------ | ------------------------ | --------------------------------------------- |
| `/external/post-card` (acceptance/veto)                      | ✅                       |
| `/external/reply-to-post` (Discord → Reddit)                 | ✅                       |
| `PostSubmit` mirror → Discord webhook                        | ✅                       |
| Card-of-the-day scheduler (10:00 UTC)                        | ✅                       |
| Daily gallery scheduler prep (04:00 UTC)                     | ✅ (multi-image blocked) |
| Mork feature flags + asyncpraw fallback (`reddit_devvit.py`) | ✅                       |
| Deferred queue on Devvit KV                                  | ⬜                       | Still `deferred_reddit.py` + `!redditcatchup` |
| `scripts/verify_devvit_connectivity.py`                      | 🔄                       | In progress (scripts branch)                  |

## Production cutover

| Feature                     | Transport today          | Devvit ready | VM flag                    | App setting                   |
| --------------------------- | ------------------------ | ------------ | -------------------------- | ----------------------------- |
| **Card of the day**         | Devvit scheduler         | ✅           | `REDDIT_COTD_VIA_DEVVIT=1` | `cardOfTheDayViaDevvit=true`  |
| **Acceptance posts**        | asyncpraw                | ✅           | off                        | n/a                           |
| **Reddit → Discord mirror** | `check_reddit.py` poll   | ✅           | off                        | `redditMirrorViaDevvit=false` |
| **Discord → Reddit reply**  | asyncpraw                | ✅           | off                        | n/a                           |
| **Daily gallery**           | asyncpraw + GCS manifest | partial      | off                        | `dailyGalleryViaDevvit=false` |

Legend: ✅ done · ⏳ waiting on external dependency · ⬜ not started · 🔄 in progress

## Devvit app settings (r/HellsCube)

| Setting                         | Target                    | Done                           |
| ------------------------------- | ------------------------- | ------------------------------ |
| `cardOfTheDayViaDevvit`         | `true`                    | ✅                             |
| `catalogUrl`                    | Hellfall catalog          | ⬜ optional                    |
| `officialHcRedditFlair`         | Official HC UUID          | ⬜ optional                    |
| `redditMirrorWebhookUrl`        | Discord `#reddit` webhook | ⬜ required for mirror cutover |
| `redditMirrorViaDevvit`         | `false` until verified    | ⬜                             |
| `dailyGalleryViaDevvit`         | `false`                   | ⬜ blocked on gallery API      |
| `submissionsGalleryManifestUrl` | GCS manifest              | ⬜ optional                    |

## VM `.env` (lil-mork)

```bash
REDDIT_ACCEPT_VIA_DEVVIT=0          # or unset
REDDIT_COTD_VIA_DEVVIT=1
# REDDIT_MIRROR_VIA_DEVVIT=1
REDDIT_GALLERY_USE_MANIFEST=1
# REDDIT_GALLERY_VIA_DEVVIT=1
# REDDIT_REPLY_VIA_DEVVIT=1
# DEVVIT_POST_CARD_URL=...
# DEVVIT_POST_CARD_SECRET=devvit_at_…
```

## Cutover order (when unblocked)

1. **Mirror** — no external endpoints needed; set webhook + flip both mirror flags
2. **Acceptance** — after external endpoints approved; set token + `REDDIT_ACCEPT_VIA_DEVVIT=1`; smoke via `verify_devvit_connectivity.py --post-smoke`
3. **Reply** — same token; `REDDIT_REPLY_VIA_DEVVIT=1`
4. **Gallery** — wait for Devvit multi-image API, or keep asyncpraw
5. **Deferred queue** — port to Devvit KV + mod menu

## Verify after each flip

- [ ] No double posts (old path disabled before new path enabled)
- [ ] COTD: only Devvit scheduler at 10:00 UTC (Mork skips when flag on)
- [ ] Mirror: `#reddit` gets new flair posts without `check_reddit` running
- [ ] Reply: `#reddit` reply reaches Reddit comment (mork-bridge webhook author recognized)
- [ ] Acceptance: veto council accept/veto creates r/HellsCube image post
