import { redis } from '@devvit/web/server';
import {
  DEFAULT_SUBMISSIONS_GALLERY_MANIFEST_URL,
  GALLERY_TITLE,
  pickGalleryEntries,
  type SubmissionsGalleryManifest,
} from '../shared/submissionsGallery.js';
import { submitImagePost } from './postCard.js';
import { getAppBooleanSetting, getOfficialHcRedditFlair } from './appSettings.js';
import { DEFAULT_SUBREDDIT } from '../shared/constants.js';

const DEFAULT_DAILY_GALLERY_VIA_DEVVIT = false;
const LAST_RUN_KEY = 'gallery:lastDate';

function utcDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

export type DailyGalleryResult = {
  skipped: boolean;
  reason?: string;
  pickedCount?: number;
  postId?: string;
  permalink?: string;
};

export async function getSubmissionsGalleryManifestUrl(): Promise<string> {
  const value = await settings.get<string>('submissionsGalleryManifestUrl');
  const trimmed = value?.trim();
  return trimmed || DEFAULT_SUBMISSIONS_GALLERY_MANIFEST_URL;
}

export async function fetchSubmissionsGalleryManifest(
  manifestUrl: string,
): Promise<SubmissionsGalleryManifest> {
  const response = await fetch(manifestUrl);
  if (!response.ok) {
    throw new Error(`manifest fetch failed: ${response.status} (${manifestUrl})`);
  }
  const body = (await response.json()) as SubmissionsGalleryManifest;
  if (!Array.isArray(body.entries)) {
    throw new Error('manifest missing entries array');
  }
  return body;
}

export async function runDailyGallery(): Promise<DailyGalleryResult> {
  const viaDevvit = await getAppBooleanSetting(
    'dailyGalleryViaDevvit',
    DEFAULT_DAILY_GALLERY_VIA_DEVVIT,
  );
  if (!viaDevvit) {
    return { skipped: true, reason: 'devvit_disabled' };
  }

  const today = utcDateString();
  const lastRun = await redis.get(LAST_RUN_KEY);
  if (lastRun === today) {
    return { skipped: true, reason: 'already_ran_today' };
  }

  const manifestUrl = await getSubmissionsGalleryManifestUrl();
  const manifest = await fetchSubmissionsGalleryManifest(manifestUrl);
  const picked = pickGalleryEntries(manifest.entries);
  if (picked.length === 0) {
    return { skipped: true, reason: 'no_recent_submissions', pickedCount: 0 };
  }

  if (picked.length > 1) {
    return {
      skipped: true,
      reason: 'reddit_gallery_api_unavailable',
      pickedCount: picked.length,
    };
  }

  const flairId = await getOfficialHcRedditFlair();
  const post = await submitImagePost({
    title: GALLERY_TITLE,
    imageUrl: picked[0].imageUrl,
    flairId,
    subredditName: DEFAULT_SUBREDDIT,
  });

  await redis.set(LAST_RUN_KEY, today);

  return {
    skipped: false,
    pickedCount: 1,
    postId: post.postId,
    permalink: post.permalink,
  };
}
