"""Stage-1 Reddit migration: post acceptance cards via Devvit instead of asyncpraw."""

from __future__ import annotations

import os

import aiohttp

DEFAULT_DEVVIT_SUBREDDIT = "HellsCube"
DEVVIT_MANAGED_TOKEN_PREFIX = "devvit_at_"


def reddit_accept_via_devvit_enabled() -> bool:
    return os.environ.get("REDDIT_ACCEPT_VIA_DEVVIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def reddit_cotd_via_devvit_enabled() -> bool:
    """When true, HC6 card-of-the-day is handled by hellscube-bridge scheduler (not Lifecycle)."""
    return os.environ.get("REDDIT_COTD_VIA_DEVVIT", "").strip().lower() in {
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


def validate_devvit_post_card_url(url: str) -> None:
    """Validate DEVVIT_POST_CARD_URL for external-endpoint callers."""
    if "/external/" not in url:
        raise RuntimeError(
            "DEVVIT_POST_CARD_URL must target /external/post-card for GCP callers "
            "(https://developers.reddit.com/docs/capabilities/server/external-endpoints)"
        )
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    if "t5_" in host:
        raise RuntimeError(
            f"DEVVIT_POST_CARD_URL hostname {host!r} must omit the t5_ prefix "
            "(e.g. hellscube-bridge-21otlg-external.devvit.net, not t5_21otlg)"
        )
    if not host.endswith("-external.devvit.net"):
        raise RuntimeError(
            f"DEVVIT_POST_CARD_URL hostname {host!r} does not look like a Devvit "
            "external endpoint host (*-external.devvit.net)"
        )


def validate_devvit_post_card_secret(secret: str) -> None:
    """Validate DEVVIT_POST_CARD_SECRET is a managed App Token."""
    if not secret.startswith(DEVVIT_MANAGED_TOKEN_PREFIX):
        raise RuntimeError(
            "DEVVIT_POST_CARD_SECRET must be a managed App Token from Devvit "
            f"developer settings ({DEVVIT_MANAGED_TOKEN_PREFIX}…), not postCardSecret"
        )


def _devvit_config() -> tuple[str, str]:
    url = os.environ.get("DEVVIT_POST_CARD_URL", "").strip()
    secret = os.environ.get("DEVVIT_POST_CARD_SECRET", "").strip()
    if not url or not secret:
        raise RuntimeError(
            "REDDIT_ACCEPT_VIA_DEVVIT is enabled but DEVVIT_POST_CARD_URL "
            "and DEVVIT_POST_CARD_SECRET must both be set"
        )
    validate_devvit_post_card_url(url)
    validate_devvit_post_card_secret(secret)
    return url, secret


async def post_accept_via_devvit(
    *,
    title: str,
    image_url: str,
    flair_id: str,
    subreddit_name: str = DEFAULT_DEVVIT_SUBREDDIT,
) -> dict:
    """POST an acceptance image to the Devvit /external/post-card endpoint."""
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
        "Accept": "application/json",
    }
    async with (
        aiohttp.ClientSession().post(url, json=payload, headers=headers) as resp,
    ):
        body = await resp.json(content_type=None)
        if resp.status >= 400:
            error = body.get("error") if isinstance(body, dict) else body
            raise RuntimeError(f"Devvit post-card failed ({resp.status}): {error}")
        if not isinstance(body, dict) or not body.get("ok"):
            raise RuntimeError(f"Devvit post-card returned unexpected body: {body}")
        return body
