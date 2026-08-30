export type ReplyToPostRequest = {
  /** Reddit post id (`t3_…` or bare id from permalink). */
  postId: string;
  text: string;
};

export type ReplyToPostResponse = {
  ok: true;
  commentId: string;
  permalink: string;
};

export type ReplyToPostErrorResponse = {
  ok: false;
  error: string;
};
