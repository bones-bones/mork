# hellscube-bridge scheduler

Devvit [Scheduler](https://developers.reddit.com/docs/capabilities/server/scheduler) jobs for r/HellsCube.

## Card of the day

| | |
|---|---|
| **Task** | `card-of-the-day` in `devvit.json` |
| **Cron** | `0 10 * * *` (10:00 UTC daily) |
| **Handler** | `POST /internal/scheduler/card-of-the-day` |
| **Catalog** | Subreddit setting `catalogUrl` (default: Hellfall GCS `catalog.json`) |
| **Flair** | Global app setting `officialHcRedditFlair` |
| **Card pick** | HC6 cards (`set` matches `HC6_*`), catalog order, index `726 - days_since(2025-11-26)` |
| **Dedup** | Redis key `cotd:lastDate` (UTC `YYYY-MM-DD`) |
| **Post** | Title `HC6 Card of the day: {name}`, Official HC flair, `reddit.submitPost` image |

Implementation: `mork-devvit/src/server/cardOfTheDay.ts`.

## Feature flag (Devvit vs Lifecycle)

| Switch | Where | Devvit path |
|--------|-------|-------------|
| `REDDIT_COTD_VIA_DEVVIT=1` | VM `.env` (Discord bot) | Skips `Lifecycle.py` hour-10 job |
| `cardOfTheDayViaDevvit` | hellscube-bridge **global** app setting (default `true`) | Scheduler actually posts |
| `catalogUrl` | **CLI** `devvit settings set` (global) | Catalog JSON URL |
| `officialHcRedditFlair` | **CLI** `devvit settings set` (global) | Official HC flair UUID |

**Legacy path** (Google Sheets + asyncpraw): leave flags off/default.

### Global settings (CLI)

`devvit settings set` only supports **global** app settings. It prompts interactively for the value — there is no `--subreddit` flag.

```bash
cd mork-devvit
npx devvit settings set catalogUrl
npx devvit settings set officialHcRedditFlair
```

`devvit.json` `defaultValue` does **not** populate `settings.get()` until the key is set in developer settings. The scheduler code defaults to `true` when unset; to set explicitly:

```bash
printf 'true\n' | npx devvit settings set cardOfTheDayViaDevvit
```

**Upload first:** new keys only exist on Reddit after `devvit upload --bump=patch`. If `settings set` says “Unable to lookup the setting key”, upload then retry.

### `cardOfTheDayViaDevvit`

Global boolean. To disable: `printf 'false\n' | npx devvit settings set cardOfTheDayViaDevvit`.

Pair with on the VM:

```bash
REDDIT_COTD_VIA_DEVVIT=1
```

Full deploy steps: [`deploy-checklist.md`](deploy-checklist.md).

Legacy path:

```bash
REDDIT_COTD_VIA_DEVVIT=0   # or unset
npx devvit settings set cardOfTheDayViaDevvit   # → false
```

### Deploy checklist

1. `npm run deploy` / publish updated app
2. App installed on r/HellsCube
3. HTTP fetch domains approved: `storage.googleapis.com`, `storage.cloud.google.com`, `lh3.googleusercontent.com`
4. Set flags per tables above before the next 10:00 UTC window
