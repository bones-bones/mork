import { settings } from '@devvit/web/server';
import {
  DEFAULT_CATALOG_URL,
  DEFAULT_OFFICIAL_HC_REDDIT_FLAIR,
} from '../shared/constants.js';

export async function getOfficialHcRedditFlair(): Promise<string> {
  const value = await settings.get<string>('officialHcRedditFlair');
  const trimmed = value?.trim();
  return trimmed || DEFAULT_OFFICIAL_HC_REDDIT_FLAIR;
}

export async function getCatalogUrl(): Promise<string> {
  const value = await settings.get<string>('catalogUrl');
  const trimmed = value?.trim();
  return trimmed || DEFAULT_CATALOG_URL;
}
