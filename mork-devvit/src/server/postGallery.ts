import {
  GALLERY_API_UNAVAILABLE,
  GALLERY_MAX_IMAGES,
  GALLERY_TITLE,
  galleryImageUrlError,
  normalizeGalleryImageUrls,
  type PostGalleryErrorResponse,
  type PostGalleryRequest,
  type PostGalleryResponse,
} from '../shared/submissionsGallery.js';
import { getOfficialHcRedditFlair } from './appSettings.js';
import { badRequest, submitImagePost } from './postCard.js';

export async function handlePostGallery(body: PostGalleryRequest): Promise<{
  response: PostGalleryResponse | PostGalleryErrorResponse;
  status: number;
}> {
  const title = body.title?.trim() || GALLERY_TITLE;
  const imageUrls = normalizeGalleryImageUrls(body.imageUrls);
  if (imageUrls.length === 0) {
    return { response: badRequest('imageUrls is required'), status: 400 };
  }
  if (imageUrls.length > GALLERY_MAX_IMAGES) {
    return {
      response: badRequest(`imageUrls must have at most ${GALLERY_MAX_IMAGES} entries`),
      status: 400,
    };
  }
  for (const url of imageUrls) {
    const urlError = galleryImageUrlError(url);
    if (urlError) {
      return { response: badRequest(urlError), status: 400 };
    }
  }

  // Devvit submitPost imageUrls is a single-URL tuple; native galleries are not
  // available yet. Accept the pictures on the wire so Mork can cut over without
  // a contract change once Reddit adds a gallery submit API.
  if (imageUrls.length > 1) {
    return { response: badRequest(GALLERY_API_UNAVAILABLE), status: 501 };
  }

  try {
    const imageUrl = imageUrls[0];
    if (!imageUrl) {
      return { response: badRequest('imageUrls is required'), status: 400 };
    }
    const flairId = body.flairId?.trim() || (await getOfficialHcRedditFlair());
    const post = await submitImagePost({
      title,
      imageUrl,
      flairId,
      subredditName: body.subredditName,
    });

    return {
      response: {
        ok: true,
        postId: post.postId,
        permalink: post.permalink,
      } satisfies PostGalleryResponse,
      status: 200,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('submit gallery post failed:', message);
    return { response: badRequest(message), status: 502 };
  }
}
