import { Hono } from 'hono';
import { reddit, settings } from '@devvit/web/server';
import type {
  PostCardErrorResponse,
  PostCardRequest,
  PostCardResponse,
} from '../../shared/postCard.js';

const DEFAULT_SUBREDDIT = 'HellsCube';

function unauthorized(): PostCardErrorResponse {
  return { ok: false, error: 'unauthorized' };
}

function badRequest(message: string): PostCardErrorResponse {
  return { ok: false, error: message };
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

async function handlePostCard(body: PostCardRequest): Promise<{
  response: PostCardResponse | PostCardErrorResponse;
  status: number;
}> {
  const title = body.title?.trim();
  const imageUrl = body.imageUrl?.trim();
  if (!title) {
    return { response: badRequest('title is required'), status: 400 };
  }
  if (!imageUrl) {
    return { response: badRequest('imageUrl is required'), status: 400 };
  }
  if (!/^https:\/\//i.test(imageUrl)) {
    return { response: badRequest('imageUrl must be an https URL'), status: 400 };
  }

  const subredditName = (body.subredditName?.trim() || DEFAULT_SUBREDDIT).replace(
    /^r\//,
    '',
  );

  try {
    const post = await reddit.submitPost({
      subredditName,
      title,
      kind: 'image',
      imageUrls: [imageUrl],
      flairId: body.flairId?.trim() || undefined,
      runAs: 'APP',
    });

    return {
      response: { ok: true, postId: post.id, permalink: post.permalink } satisfies PostCardResponse,
      status: 200,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('submitPost failed:', message);
    return { response: badRequest(message), status: 502 };
  }
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
  return c.json(response, status);
});

export const external = new Hono();

// External endpoint — auth handled by Devvit managed token
external.post('/post-card', async (c) => {
  let body: PostCardRequest;
  try {
    body = await c.req.json<PostCardRequest>();
  } catch {
    return c.json(badRequest('invalid JSON body'), 400);
  }

  const { response, status } = await handlePostCard(body);
  return c.json(response, status);
});
