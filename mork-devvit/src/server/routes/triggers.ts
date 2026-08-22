import { Hono } from 'hono';
import type { OnPostSubmitRequest, TriggerResponse } from '@devvit/web/shared';
import { runMirrorToDiscord } from '../mirrorToDiscord.js';

export const triggers = new Hono();

triggers.post('/on-post-submit', async (c) => {
  try {
    const input = await c.req.json<OnPostSubmitRequest>();
    const result = await runMirrorToDiscord(input);
    console.log('mirror-to-discord:', JSON.stringify(result));
    return c.json<TriggerResponse>({ status: 'ok' }, 200);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('mirror-to-discord failed:', message);
    return c.json({ status: 'error', message }, 500);
  }
});
