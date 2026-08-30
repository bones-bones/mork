import { reddit } from '@devvit/web/server';
import type {
  ReplyToPostErrorResponse,
  ReplyToPostRequest,
  ReplyToPostResponse,
} from '../shared/replyToPost.js';
import { badRequest } from './postCard.js';

export function normalizePostId(postId: string): string {
  const trimmed = postId.trim();
  if (!trimmed) {
    throw new Error('postId is required');
  }
  return trimmed.startsWith('t3_') ? trimmed : `t3_${trimmed}`;
}

export async function handleReplyToPost(body: ReplyToPostRequest): Promise<{
  response: ReplyToPostResponse | ReplyToPostErrorResponse;
  status: number;
}> {
  const text = body.text?.trim();
  if (!text) {
    return { response: badRequest('text is required'), status: 400 };
  }

  let postId: string;
  try {
    postId = normalizePostId(body.postId ?? '');
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { response: badRequest(message), status: 400 };
  }

  try {
    const comment = await reddit.submitComment({
      id: postId as `t3_${string}`,
      text,
      runAs: 'APP',
    });

    return {
      response: {
        ok: true,
        commentId: comment.id,
        permalink: comment.permalink,
      },
      status: 200,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('submitComment failed:', message);
    return { response: badRequest(message), status: 502 };
  }
}
