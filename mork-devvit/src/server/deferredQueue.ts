import { redis } from '@devvit/web/server';
import {
  DEFERRED_ITEMS_KEY,
  DEFERRED_QUEUE_KEY,
  type DeferredDrainRequest,
  type DeferredDrainResponse,
  type DeferredEnqueueRequest,
  type DeferredEnqueueResponse,
  type DeferredErrorResponse,
  type DeferredQueueItem,
  type DeferredStatusResponse,
} from '../shared/deferredQueue.js';
import { badRequest, submitImagePost } from './postCard.js';
import { getOfficialHcRedditFlair } from './appSettings.js';

const MAX_DRAIN = 50;

function newDeferredId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function deferredPendingCount(): Promise<number> {
  return redis.zCard(DEFERRED_QUEUE_KEY);
}

export async function enqueueDeferredItem(
  input: DeferredEnqueueRequest,
): Promise<DeferredEnqueueResponse> {
  const title = input.title?.trim() ?? '';
  const imageUrl = input.imageUrl?.trim() ?? '';
  if (!title) {
    throw new Error('title is required');
  }
  if (!imageUrl) {
    throw new Error('imageUrl is required');
  }
  if (!/^https:\/\//i.test(imageUrl)) {
    throw new Error('imageUrl must be an https URL');
  }

  const id = newDeferredId();
  const enqueuedAt = Date.now();
  const item: DeferredQueueItem = {
    id,
    title,
    imageUrl,
    flairId: input.flairId?.trim() || undefined,
    subredditName: input.subredditName?.trim() || undefined,
    enqueuedAt,
  };

  await redis.hSet(DEFERRED_ITEMS_KEY, { [id]: JSON.stringify(item) });
  await redis.zAdd(DEFERRED_QUEUE_KEY, { member: id, score: enqueuedAt });

  return {
    ok: true,
    id,
    pending: await deferredPendingCount(),
  };
}

export async function drainDeferredQueue(
  count: number,
): Promise<DeferredDrainResponse> {
  const n = Math.max(0, Math.min(Math.floor(count), MAX_DRAIN));
  if (n === 0) {
    return {
      ok: true,
      posted: 0,
      pending: await deferredPendingCount(),
      errors: [],
    };
  }

  const entries = await redis.zRange(DEFERRED_QUEUE_KEY, 0, n - 1);
  let posted = 0;
  const errors: string[] = [];

  for (const entry of entries) {
    const id = entry.member;
    const raw = await redis.hGet(DEFERRED_ITEMS_KEY, id);
    if (!raw) {
      await redis.zRem(DEFERRED_QUEUE_KEY, [id]);
      continue;
    }

    let item: DeferredQueueItem;
    try {
      item = JSON.parse(raw) as DeferredQueueItem;
    } catch {
      await redis.zRem(DEFERRED_QUEUE_KEY, [id]);
      await redis.hDel(DEFERRED_ITEMS_KEY, [id]);
      errors.push(`${id}: invalid queue payload`);
      continue;
    }

    try {
      const flairId =
        item.flairId?.trim() || (await getOfficialHcRedditFlair());
      await submitImagePost({
        title: item.title,
        imageUrl: item.imageUrl,
        flairId,
        subredditName: item.subredditName,
      });
      await redis.zRem(DEFERRED_QUEUE_KEY, [id]);
      await redis.hDel(DEFERRED_ITEMS_KEY, [id]);
      posted += 1;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${item.title}: ${message}`);
    }
  }

  return {
    ok: true,
    posted,
    pending: await deferredPendingCount(),
    errors,
  };
}

export async function handleDeferredEnqueue(body: DeferredEnqueueRequest): Promise<{
  response: DeferredEnqueueResponse | DeferredErrorResponse;
  status: number;
}> {
  try {
    const response = await enqueueDeferredItem(body);
    return { response, status: 200 };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (
      message.includes('required') ||
      message.includes('https URL')
    ) {
      return { response: badRequest(message), status: 400 };
    }
    console.error('deferred enqueue failed:', message);
    return { response: badRequest(message), status: 502 };
  }
}

export async function handleDeferredDrain(body: DeferredDrainRequest): Promise<{
  response: DeferredDrainResponse | DeferredErrorResponse;
  status: number;
}> {
  const count = body?.count;
  if (typeof count !== 'number' || !Number.isFinite(count) || count < 1) {
    return { response: badRequest('count must be a positive number'), status: 400 };
  }
  try {
    const response = await drainDeferredQueue(count);
    return { response, status: 200 };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('deferred drain failed:', message);
    return { response: badRequest(message), status: 502 };
  }
}

export async function handleDeferredStatus(): Promise<{
  response: DeferredStatusResponse | DeferredErrorResponse;
  status: number;
}> {
  try {
    return {
      response: { ok: true, pending: await deferredPendingCount() },
      status: 200,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('deferred status failed:', message);
    return { response: badRequest(message), status: 502 };
  }
}
