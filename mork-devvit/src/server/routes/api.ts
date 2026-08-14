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

export const api = new Hono();

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

  const title = body.title?.trim();
  const imageUrl = body.imageUrl?.trim();
  if (!title) {
    return c.json(badRequest('title is required'), 400);
  }
  if (!imageUrl) {
    return c.json(badRequest('imageUrl is required'), 400);
  }
  if (!/^https:\/\//i.test(imageUrl)) {
    return c.json(badRequest('imageUrl must be an https URL'), 400);
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

    const response: PostCardResponse = {
      ok: true,
      postId: post.id,
      permalink: post.permalink,
    };
    return c.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('submitPost failed:', message);
    return c.json(badRequest(message), 502);
  }
});
