/** GCS JSON manifest written by Mork at #submissions intake. */

export type SubmissionsGalleryEntry = {
  messageId: string;
  imageUrl: string;
  submittedAt: string;
  cardName?: string;
};

export type SubmissionsGalleryManifest = {
  updatedAt: string;
  entries: SubmissionsGalleryEntry[];
};

export const DEFAULT_SUBMISSIONS_GALLERY_MANIFEST_URL =
  'https://storage.googleapis.com/hellcube-images/mork/submissions-gallery-manifest.json';

export const GALLERY_TITLE =
  "Some of Today's Submissions: Have any strong opinions on these cards? Join the discord to share them!";

export const GALLERY_LOOKBACK_MS = 24 * 60 * 60 * 1000;
export const GALLERY_MAX_IMAGES = 10;

export function pickGalleryEntries(
  entries: SubmissionsGalleryEntry[],
  nowMs: number = Date.now(),
): SubmissionsGalleryEntry[] {
  const cutoff = nowMs - GALLERY_LOOKBACK_MS;
  const recent = entries.filter((entry) => {
    const ts = Date.parse(entry.submittedAt);
    return Number.isFinite(ts) && ts >= cutoff && entry.imageUrl?.trim();
  });
  if (recent.length === 0) {
    return [];
  }
  const shuffled = [...recent];
  for (let i = shuffled.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, Math.min(GALLERY_MAX_IMAGES, shuffled.length));
}
