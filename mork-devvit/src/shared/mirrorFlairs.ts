/** Inbound flairs mirrored to Discord #reddit (matches `check_reddit.py`). */

export const MIRROR_SHITPOST_FLAIR = 'Hellscube Would Love This (Shitpost)';

export const MIRROR_STANDARD_FLAIRS = new Set([
  'Card Idea',
  'HellsCube Submission',
  'Brainstorming',
]);

export const MIRROR_REDIS_PREFIX = 'mirror:posted:';

export const DEFAULT_MIRROR_VIA_DEVVIT = false;

export function mirrorMessagePrefix(flairText: string): string | null {
  const flair = flairText.trim();
  if (flair === MIRROR_SHITPOST_FLAIR) {
    return 'Reddit thinks Hellscube would love this:';
  }
  if (MIRROR_STANDARD_FLAIRS.has(flair)) {
    return 'reddit says:';
  }
  return null;
}

export function shouldMirrorFlair(flairText: string | undefined): boolean {
  if (!flairText?.trim()) {
    return false;
  }
  return mirrorMessagePrefix(flairText) !== null;
}

export function buildMirrorMessage(flairText: string, permalink: string): string {
  const prefix = mirrorMessagePrefix(flairText);
  if (!prefix) {
    throw new Error(`unsupported flair for mirror: ${flairText}`);
  }
  const url = permalink.startsWith('http')
    ? permalink
    : `https://reddit.com${permalink}`;
  return `${prefix} ${url}`;
}
