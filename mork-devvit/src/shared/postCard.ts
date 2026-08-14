export type PostCardRequest = {
  title: string;
  imageUrl: string;
  flairId?: string;
  subredditName?: string;
};

export type PostCardResponse = {
  ok: true;
  postId: string;
  permalink: string;
};

export type PostCardErrorResponse = {
  ok: false;
  error: string;
};
