import { settings } from '@devvit/web/server';
import {
  DEFAULT_CATALOG_URL,
  DEFAULT_OFFICIAL_HC_REDDIT_FLAIR,
} from '../shared/constants.js';
import { DEFAULT_SUBMISSIONS_GALLERY_MANIFEST_URL } from '../shared/submissionsGallery.js';

/** Devvit CLI may return boolean settings as strings ("true" / "false"). */
export function parseAppBoolean(
  value: boolean | string | undefined,
  defaultValue: boolean,
): boolean {
  if (value === undefined || value === null) {
    return defaultValue;
  }
  if (typeof value === 'boolean') {
    return value;
  }
  const normalized = String(value).trim().toLowerCase();
  if (normalized === 'true' || normalized === '1') {
    return true;
  }
  if (normalized === 'false' || normalized === '0' || normalized === '') {
    return false;
  }
  return defaultValue;
}

export async function getAppBooleanSetting(
  key: string,
  defaultValue: boolean,
): Promise<boolean> {
  const value = await settings.get<boolean | string>(key);
  return parseAppBoolean(value, defaultValue);
}

/** Devvit CLI may return boolean settings as strings ("true" / "false"). */
export function parseAppBoolean(
  value: boolean | string | undefined,
  defaultValue: boolean,
): boolean {
  if (value === undefined || value === null) {
    return defaultValue;
  }
  if (typeof value === 'boolean') {
    return value;
  }
  const normalized = String(value).trim().toLowerCase();
  if (normalized === 'true' || normalized === '1') {
    return true;
  }
  if (normalized === 'false' || normalized === '0' || normalized === '') {
    return false;
  }
  return defaultValue;
}

export async function getAppBooleanSetting(
  key: string,
  defaultValue: boolean,
): Promise<boolean> {
  const value = await settings.get<boolean | string>(key);
  return parseAppBoolean(value, defaultValue);
}

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

export async function getSubmissionsGalleryManifestUrl(): Promise<string> {
  const value = await settings.get<string>('submissionsGalleryManifestUrl');
  const trimmed = value?.trim();
  return trimmed || DEFAULT_SUBMISSIONS_GALLERY_MANIFEST_URL;
}
