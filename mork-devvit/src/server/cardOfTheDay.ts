import { redis } from '@devvit/web/server';
import type { CatalogCard } from '../shared/catalog.js';
import {
  COTD_HC6_SEARCH_QUERY,
  COTD_START_DATE,
  COTD_START_INDEX,
  DEFAULT_CARD_OF_THE_DAY_VIA_DEVVIT,
  DEFAULT_SUBREDDIT,
} from '../shared/constants.js';
import {
  getAppBooleanSetting,
  getHellfallApiUrl,
  getOfficialHcRedditFlair,
} from './appSettings.js';
import { submitImagePost } from './postCard.js';

const LAST_RUN_KEY = 'cotd:lastDate';

export type CardOfTheDayResult = {
  skipped: boolean;
  reason?: string;
  cardName?: string;
  postId?: string;
  permalink?: string;
};

type HellfallSearchResponse = {
  object?: string;
  total_cards?: number;
  data?: CatalogCard[];
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

/** Build search URL matching Lifecycle.py `getSearchFromServer("set:HC6 unique:prints")`. */
export function hellfallHc6SearchUrl(apiBase: string): string {
  const base = apiBase.replace(/\/$/, '');
  const params = new URLSearchParams({
    q: COTD_HC6_SEARCH_QUERY,
    format: 'json',
  });
  return `${base}/api/cards/search?${params.toString()}`;
}

export async function fetchHc6SearchCards(apiBase: string): Promise<CatalogCard[]> {
  const url = hellfallHc6SearchUrl(apiBase);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`hellfall search failed: ${response.status} (${url})`);
  }

  const body = (await response.json()) as HellfallSearchResponse;
  if (!Array.isArray(body.data)) {
    throw new Error('hellfall search missing data array');
  }
  return body.data;
}

export function pickCardOfTheDay(cards: CatalogCard[]): CatalogCard | null {
  const offset = COTD_START_INDEX - daysSinceStart(COTD_START_DATE);
  if (offset < 0 || offset >= cards.length) {
    return null;
  }
  return cards[offset];
}

export async function runCardOfTheDay(): Promise<CardOfTheDayResult> {
  const viaDevvit = await getAppBooleanSetting(
    'cardOfTheDayViaDevvit',
    DEFAULT_CARD_OF_THE_DAY_VIA_DEVVIT,
  );
  if (!viaDevvit) {
    return { skipped: true, reason: 'devvit_disabled' };
  }

  const today = utcDateString();
  const lastRun = await redis.get(LAST_RUN_KEY);
  if (lastRun === today) {
    return { skipped: true, reason: 'already_ran_today' };
  }

  const hellfallApiUrl = await getHellfallApiUrl();
  const flairId = await getOfficialHcRedditFlair();
  const hc6Cards = await fetchHc6SearchCards(hellfallApiUrl);
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
