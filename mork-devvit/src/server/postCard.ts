import { reddit } from '@devvit/web/server';
import { DEFAULT_SUBREDDIT } from '../shared/constants.js';
import type {
  PostCardErrorResponse,
  PostCardRequest,
  PostCardResponse,
} from '../shared/postCard.js';
import { getOfficialHcRedditFlair } from './appSettings.js';

export function badRequest(message: string): PostCardErrorResponse {
  return { ok: false, error: message };
}

export type SubmitImagePostInput = {
  title: string;
  imageUrl: string;
  flairId?: string;
  subredditName?: string;
};

export type SubmitImagePostResult = {
  postId: string;
  permalink: string;
};

export async function submitImagePost(
  input: SubmitImagePostInput,
): Promise<SubmitImagePostResult> {
  const title = input.title.trim();
  const imageUrl = input.imageUrl.trim();
  if (!title) {
    throw new Error('title is required');
  }
  if (!imageUrl) {
    throw new Error('imageUrl is required');
  }
  if (!/^https:\/\//i.test(imageUrl)) {
    throw new Error('imageUrl must be an https URL');
  }

  const subredditName = (input.subredditName?.trim() || DEFAULT_SUBREDDIT).replace(
    /^r\//,
    '',
  );

  const post = await reddit.submitPost({
    subredditName,
    title,
    kind: 'image',
    imageUrls: [imageUrl],
    flairId: input.flairId?.trim() || undefined,
    runAs: 'APP',
  });

  return { postId: post.id, permalink: post.permalink };
}

export async function handlePostCard(body: PostCardRequest): Promise<{
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

  try {
    const flairId = body.flairId?.trim() || (await getOfficialHcRedditFlair());
    const post = await submitImagePost({
      title,
      imageUrl,
      flairId,
      subredditName: body.subredditName,
    });

    return {
      response: {
        ok: true,
        postId: post.postId,
        permalink: post.permalink,
      } satisfies PostCardResponse,
      status: 200,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('submitPost failed:', message);
    return { response: badRequest(message), status: 502 };
  }
}
