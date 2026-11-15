/** Redis-backed deferred acceptance/veto image posts (replaces Mork `deferred_reddit/`). */

export const DEFERRED_QUEUE_KEY = 'deferred:queue';
export const DEFERRED_ITEMS_KEY = 'deferred:items';

export type DeferredQueueItem = {
  id: string;
  title: string;
  imageUrl: string;
  flairId?: string;
  subredditName?: string;
  enqueuedAt: number;
};

export type DeferredEnqueueRequest = {
  title: string;
  imageUrl: string;
  flairId?: string;
  subredditName?: string;
};

export type DeferredEnqueueResponse = {
  ok: true;
  id: string;
  pending: number;
};

export type DeferredDrainRequest = {
  count: number;
};

export type DeferredDrainResponse = {
  ok: true;
  posted: number;
  pending: number;
  errors: string[];
};

export type DeferredStatusResponse = {
  ok: true;
  pending: number;
};

export type DeferredErrorResponse = {
  ok: false;
  error: string;
};
