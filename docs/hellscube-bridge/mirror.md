# hellscube-bridge Reddit → Discord mirror

Devvit [PostSubmit](https://developers.reddit.com/docs/capabilities/server/triggers) trigger replaces the 5-minute `check_reddit.py` flair search poll.

## Behavior

When a new post is submitted to r/HellsCube with one of these link flairs, hellscube-bridge POSTs to a Discord webhook:

| Flair | Discord prefix |
|-------|----------------|
| Card Idea, HellsCube Submission, Brainstorming | `reddit says:` |
| Hellscube Would Love This (Shitpost) | `Reddit thinks Hellscube would love this:` |

Message format: `{prefix} https://reddit.com{permalink}` — same as the legacy bot.

**Dedup:** Redis key `mirror:posted:{postId}` — one mirror per post.

Implementation: `mork-devvit/src/server/mirrorToDiscord.ts`, `src/shared/mirrorFlairs.ts`.

## Feature flag (Devvit vs Lifecycle)

| Switch | Where | Devvit path |
|--------|-------|-------------|
| `REDDIT_MIRROR_VIA_DEVVIT=1` | VM `.env` (Discord bot) | Skips `check_reddit` in the lifecycle loop |
| `redditMirrorViaDevvit` | hellscube-bridge **global** app setting (default `false`) | PostSubmit actually mirrors |
| `redditMirrorWebhookUrl` | **CLI** `devvit settings set` (global) | Discord webhook for `#reddit` |

Pair both flags on at cutover to avoid double posts or zero posts.

### Cutover

```bash
cd mork-devvit
npm run build
npx devvit upload --bump=patch
npx devvit install r/HellsCube

npx devvit settings set redditMirrorWebhookUrl
# paste https://discord.com/api/webhooks/…

npx devvit settings set redditMirrorViaDevvit
# enter true
```

On the VM:

```bash
REDDIT_MIRROR_VIA_DEVVIT=1
```

Redeploy / restart Mork.

### Rollback

```bash
REDDIT_MIRROR_VIA_DEVVIT=0   # or unset
printf 'false\n' | npx devvit settings set redditMirrorViaDevvit
```

**Note:** Until a build with proper boolean parsing is published, the string `"false"` from the CLI is truthy in JavaScript and mirror may still run. **Immediate stop:** delete or regenerate the `#reddit` Discord webhook (Server Settings → Integrations) so the stored URL is invalid.

Full deploy steps: [`deploy-checklist.md`](deploy-checklist.md).

## Limitations

- **Flair at submit time only.** `PostSubmit` fires when the post is created. If flair is added later, the legacy poll would have caught it but Devvit will not (until a `PostFlairUpdate` handler is added).
- **Reply bridge unchanged.** Discord → Reddit replies still use asyncpraw in `Lifecycle.py` (`reddit says:` prefix only).
