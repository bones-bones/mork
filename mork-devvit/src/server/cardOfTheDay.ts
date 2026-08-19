import { redis, settings } from '@devvit/web/server';
import type { CatalogCard, CatalogRoot } from '../shared/catalog.js';
import {
  COTD_START_DATE,
  COTD_START_INDEX,
  DEFAULT_SUBREDDIT,
} from '../shared/constants.js';
import { getCatalogUrl, getOfficialHcRedditFlair } from './appSettings.js';
import { submitImagePost } from './postCard.js';

const LAST_RUN_KEY = 'cotd:lastDate';

export type CardOfTheDayResult = {
  skipped: boolean;
  reason?: string;
  cardName?: string;
  postId?: string;
  permalink?: string;
};

function utcDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysSinceStart(startDate: string): number {
  const [year, month, day] = startDate.split('-').map(Number);
  const now = new Date();
  const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const startUtc = Date.UTC(year, month - 1, day);
  return Math.floor((todayUtc - startUtc) / (24 * 60 * 60 * 1000));
}

function isHc6Card(card: CatalogCard): boolean {
  return /^HC6/i.test(card.set?.trim() ?? '');
}

export async function fetchHc6CatalogCards(catalogUrl: string): Promise<CatalogCard[]> {
  const response = await fetch(catalogUrl);
  if (!response.ok) {
    throw new Error(`catalog fetch failed: ${response.status} (${catalogUrl})`);
  }

  const body = (await response.json()) as CatalogRoot;
  if (!Array.isArray(body.data)) {
    throw new Error('catalog missing data array');
  }

  return body.data.filter(isHc6Card);
}

export function pickCardOfTheDay(cards: CatalogCard[]): CatalogCard | null {
  const offset = COTD_START_INDEX - daysSinceStart(COTD_START_DATE);
  if (offset < 0 || offset >= cards.length) {
    return null;
  }
  return cards[offset];
}

export async function runCardOfTheDay(): Promise<CardOfTheDayResult> {
  const viaDevvit = await settings.get<boolean>('cardOfTheDayViaDevvit');
  if (!viaDevvit) {
    return { skipped: true, reason: 'devvit_disabled' };
  }

  const today = utcDateString();
  const lastRun = await redis.get(LAST_RUN_KEY);
  if (lastRun === today) {
    return { skipped: true, reason: 'already_ran_today' };
  }

  const catalogUrl = await getCatalogUrl();
  const flairId = await getOfficialHcRedditFlair();
  const hc6Cards = await fetchHc6CatalogCards(catalogUrl);
  const card = pickCardOfTheDay(hc6Cards);
  if (!card) {
    return { skipped: true, reason: 'no_card_for_today' };
  }

  const name = card.name?.trim();
  const imageUrl = card.image?.trim();
  if (!name || !imageUrl || !/^https:\/\//i.test(imageUrl)) {
    throw new Error(
      `invalid catalog card: name=${name ?? ''}, image=${imageUrl ?? ''}`,
    );
  }

  const post = await submitImagePost({
    title: `HC6 Card of the day: ${name}`,
    imageUrl,
    flairId,
    subredditName: DEFAULT_SUBREDDIT,
  });

  await redis.set(LAST_RUN_KEY, today);

  return {
    skipped: false,
    cardName: name,
    postId: post.postId,
    permalink: post.permalink,
  };
}
