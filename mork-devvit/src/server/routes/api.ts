import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { settings } from '@devvit/web/server';
import type {
  PostCardErrorResponse,
  PostCardRequest,
} from '../../shared/postCard.js';
import { badRequest, handlePostCard } from '../postCard.js';

function unauthorized(): PostCardErrorResponse {
  return { ok: false, error: 'unauthorized' };
}

async function authorizeRequest(
  authorizationHeader: string | undefined,
): Promise<boolean> {
  const expected = await settings.get<string>('postCardSecret');
  if (!expected) {
    console.error('postCardSecret is not configured in app settings');
    return false;
  }
  return authorizationHeader === `Bearer ${expected}`;
}

export const api = new Hono();

// Webview-internal route — auth via postCardSecret setting
api.post('/post-card', async (c) => {
  if (!(await authorizeRequest(c.req.header('authorization')))) {
    return c.json(unauthorized(), 401);
  }

  let body: PostCardRequest;
  try {
    body = await c.req.json<PostCardRequest>();
  } catch {
    return c.json(badRequest('invalid JSON body'), 400);
  }

  const { response, status } = await handlePostCard(body);
  return c.json(response, status as ContentfulStatusCode);
});

export const external = new Hono();

// External endpoint (devvit.json server.externalEndpoints.postCard).
// Gateway auth: managed App Token (Authorization: Bearer devvit_at_…).
// See https://developers.reddit.com/docs/capabilities/server/external-endpoints
external.post('/post-card', async (c) => {
  let body: PostCardRequest;
  try {
    body = await c.req.json<PostCardRequest>();
  } catch {
    return c.json(badRequest('invalid JSON body'), 400);
  }

  const { response, status } = await handlePostCard(body);
  return c.json(response, status as ContentfulStatusCode);
});
