"""Stage-1 Reddit migration: post acceptance cards via Devvit instead of asyncpraw."""

from __future__ import annotations

import os

import aiohttp

DEFAULT_DEVVIT_SUBREDDIT = "HellsCube"


def reddit_accept_via_devvit_enabled() -> bool:
    return os.environ.get("REDDIT_ACCEPT_VIA_DEVVIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def reddit_title_for_acceptance(
    card_message: str,
    set_id: str,
    *,
    was_vetoed: bool = False,
) -> str:
    verb = "was vetoed from" if was_vetoed else "was accepted into"
    return f"{card_message.replace('**', '')} {verb} {set_id}"


def _devvit_config() -> tuple[str, str]:
    url = os.environ.get("DEVVIT_POST_CARD_URL", "").strip()
    secret = os.environ.get("DEVVIT_POST_CARD_SECRET", "").strip()
    if not url or not secret:
        raise RuntimeError(
            "REDDIT_ACCEPT_VIA_DEVVIT is enabled but DEVVIT_POST_CARD_URL "
            "and DEVVIT_POST_CARD_SECRET must both be set"
        )
    return url, secret


async def post_accept_via_devvit(
    *,
    title: str,
    image_url: str,
    flair_id: str,
    subreddit_name: str = DEFAULT_DEVVIT_SUBREDDIT,
) -> dict:
    """POST an acceptance image to the Devvit /api/post-card endpoint."""
    url, secret = _devvit_config()
    payload = {
        "title": title,
        "imageUrl": image_url,
        "flairId": flair_id,
        "subredditName": subreddit_name,
    }
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                error = body.get("error") if isinstance(body, dict) else body
                raise RuntimeError(
                    f"Devvit post-card failed ({resp.status}): {error}"
                )
            if not isinstance(body, dict) or not body.get("ok"):
                raise RuntimeError(f"Devvit post-card returned unexpected body: {body}")
            return body
