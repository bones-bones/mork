# hellscube-bridge deploy checklist

Current production target: **COTD via Devvit ON**, **acceptance postcard via Devvit OFF**, **mirror via Devvit OFF** (enable after webhook configured).

## 1. Devvit (`mork-devvit`)

```bash
cd mork-devvit
# Node ≥ 22 required
npm run test:types && npm run build
npm run launch      # devvit publish — required for r/HellsCube (>200 subs)
npx devvit install r/HellsCube hellscube-bridge@latest
```

`npm run deploy` (`devvit upload`) is for private/playtest subs only.

**App settings (global, CLI):**

| Setting | Target | CLI |
|---------|--------|-----|
| `cardOfTheDayViaDevvit` | `true` | `printf 'true\n' \| npx devvit settings set cardOfTheDayViaDevvit` (code also defaults `true` when unset) |
| `catalogUrl` | Hellfall catalog | `npx devvit settings set catalogUrl` (optional) |
| `officialHcRedditFlair` | Official HC UUID | `npx devvit settings set officialHcRedditFlair` (optional) |
| `redditMirrorWebhookUrl` | Discord webhook | `npx devvit settings set redditMirrorWebhookUrl` (required for mirror) |
| `redditMirrorViaDevvit` | `false` until cutover | `npx devvit settings set redditMirrorViaDevvit` → `true` when ready |

To force COTD off later: `npx devvit settings set cardOfTheDayViaDevvit` → enter `false` (after key is registered on upload).

**Acceptance posts** are not gated by a Devvit setting — Mork chooses Devvit vs asyncpraw via VM env below.

## 2. Mork VM `.env`

```bash
# Postcard / acceptance — OFF (asyncpraw)
# Do not set REDDIT_ACCEPT_VIA_DEVVIT, or explicitly:
REDDIT_ACCEPT_VIA_DEVVIT=0

# Card of the day — ON (Devvit scheduler)
REDDIT_COTD_VIA_DEVVIT=1

# Reddit → Discord mirror — OFF until webhook + app setting enabled
# REDDIT_MIRROR_VIA_DEVVIT=1
```

Redeploy / restart Mork after editing `.env`.

## 3. Verify

- Acceptance card → still uses asyncpraw (`reddit_functions.py`)
- Hour 10 UTC → Devvit scheduler (not `Lifecycle.py` COTD)
- No double COTD posts (both `REDDIT_COTD_VIA_DEVVIT=1` and Devvit flag on)
- Mirror: after cutover, new inbound-flair posts appear in `#reddit` without `check_reddit` running
