import { Hono } from 'hono';
import type { MenuItemRequest, UiResponse } from '@devvit/web/shared';
import { deferredPendingCount, drainDeferredQueue } from '../deferredQueue.js';

export const menu = new Hono();

/** Mod menu: post one deferred card from the Redis queue. */
menu.post('/drain-deferred', async (c) => {
  await c.req.json<MenuItemRequest>().catch(() => undefined);

  const pendingBefore = await deferredPendingCount();
  if (pendingBefore === 0) {
    return c.json<UiResponse>({
      showToast: 'No deferred Reddit posts in the queue',
    });
  }

  const result = await drainDeferredQueue(1);
  if (result.posted === 1) {
    return c.json<UiResponse>({
      showToast: `Posted 1 deferred card (${result.pending} remaining)`,
    });
  }

  const detail = result.errors[0] ?? 'unknown error';
  return c.json<UiResponse>({
    showToast: `Deferred post failed: ${detail}`,
  });
});
