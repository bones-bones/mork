/** Daily submissions gallery posted via POST /external/post-gallery. */

export const GALLERY_TITLE =
  "Some of Today's Submissions: Have any strong opinions on these cards? Join the discord to share them!";

export const GALLERY_MAX_IMAGES = 10;

export const GALLERY_API_UNAVAILABLE = 'reddit_gallery_api_unavailable';

export type PostGalleryRequest = {
  title?: string;
  imageUrls: string[];
  flairId?: string;
  subredditName?: string;
};

export type PostGalleryResponse = {
  ok: true;
  postId: string;
  permalink: string;
};

export type PostGalleryErrorResponse = {
  ok: false;
  error: string;
};

export function normalizeGalleryImageUrls(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const urls: string[] = [];
  for (const item of raw) {
    if (typeof item !== 'string') {
      continue;
    }
    const trimmed = item.trim();
    if (trimmed) {
      urls.push(trimmed);
    }
  }
  return urls;
}

export function galleryImageUrlError(url: string): string | undefined {
  if (!/^https:\/\//i.test(url)) {
    return 'imageUrls must be https URLs';
  }
  return undefined;
}
