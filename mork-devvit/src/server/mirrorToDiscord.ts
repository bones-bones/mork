import { redis, settings } from '@devvit/web/server';
import type { OnPostSubmitRequest } from '@devvit/web/shared';
import { getAppBooleanSetting } from './appSettings.js';
import {
  buildMirrorMessage,
  DEFAULT_MIRROR_VIA_DEVVIT,
  MIRROR_REDIS_PREFIX,
  shouldMirrorFlair,
} from '../shared/mirrorFlairs.js';

export type MirrorToDiscordResult = {
  mirrored: boolean;
  reason?: string;
  permalink?: string;
};

export async function runMirrorToDiscord(
  input: OnPostSubmitRequest,
): Promise<MirrorToDiscordResult> {
  const viaDevvit = await getAppBooleanSetting(
    'redditMirrorViaDevvit',
    DEFAULT_MIRROR_VIA_DEVVIT,
  );
  if (!viaDevvit) {
    return { mirrored: false, reason: 'devvit_disabled' };
  }

  const webhookUrl = (await settings.get<string>('redditMirrorWebhookUrl'))?.trim();
  if (!webhookUrl) {
    return { mirrored: false, reason: 'webhook_not_configured' };
  }
  if (!/^https:\/\/discord\.com\/api\/webhooks\//i.test(webhookUrl)) {
    throw new Error('redditMirrorWebhookUrl must be a discord.com webhook URL');
  }

  const post = input.post;
  if (!post?.id || !post.permalink) {
    return { mirrored: false, reason: 'missing_post' };
  }

  const flairText = post.linkFlair?.text ?? '';
  if (!shouldMirrorFlair(flairText)) {
    return { mirrored: false, reason: 'flair_not_mirrored' };
  }

  const dedupKey = `${MIRROR_REDIS_PREFIX}${post.id}`;
  const alreadyMirrored = await redis.get(dedupKey);
  if (alreadyMirrored) {
    return {
      mirrored: false,
      reason: 'already_mirrored',
      permalink: post.permalink,
    };
  }

  const content = buildMirrorMessage(flairText, post.permalink);
  const response = await fetch(webhookUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Discord webhook failed (${response.status}): ${body}`);
  }

  await redis.set(dedupKey, '1');
  return { mirrored: true, permalink: post.permalink };
}
