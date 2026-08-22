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


def reddit_mirror_via_devvit_enabled() -> bool:
    """When true, Reddit → Discord mirroring is handled by hellscube-bridge PostSubmit (not check_reddit)."""
    return os.environ.get("REDDIT_MIRROR_VIA_DEVVIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def reddit_reply_via_devvit_enabled() -> bool:
    """When true, Discord #reddit replies use hellscube-bridge /external/reply-to-post."""
    return os.environ.get("REDDIT_REPLY_VIA_DEVVIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def reddit_gallery_via_devvit_enabled() -> bool:
    """When true, daily gallery is handled by hellscube-bridge scheduler (not Lifecycle)."""
    return os.environ.get("REDDIT_GALLERY_VIA_DEVVIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def devvit_external_url(endpoint: str) -> str:
    """Build a hellscube-bridge external URL from DEVVIT_POST_CARD_URL + endpoint name."""
    base_url = os.environ.get("DEVVIT_POST_CARD_URL", "").strip()
    if not base_url:
        raise RuntimeError("DEVVIT_POST_CARD_URL is not set")
    validate_devvit_post_card_url(base_url)
    if "/external/" not in base_url:
        raise RuntimeError("DEVVIT_POST_CARD_URL must include /external/")
    prefix = base_url.rsplit("/external/", 1)[0] + "/external/"
    return prefix + endpoint.lstrip("/")


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
            "Devvit external calls require DEVVIT_POST_CARD_URL "
            "and DEVVIT_POST_CARD_SECRET to both be set"
        )
    validate_devvit_post_card_url(url)
    validate_devvit_post_card_secret(secret)
    return url, secret


def _devvit_headers(secret: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _post_devvit_external(endpoint: str, payload: dict) -> dict:
    _, secret = _devvit_config()
    url = devvit_external_url(endpoint)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=payload, headers=_devvit_headers(secret)
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status >= 400:
                error = body.get("error") if isinstance(body, dict) else body
                raise RuntimeError(
                    f"Devvit {endpoint} failed ({resp.status}): {error}"
                )
            if not isinstance(body, dict) or not body.get("ok"):
                raise RuntimeError(
                    f"Devvit {endpoint} returned unexpected body: {body}"
                )
            return body


async def post_accept_via_devvit(
    *,
    title: str,
    image_url: str,
    flair_id: str,
    subreddit_name: str = DEFAULT_DEVVIT_SUBREDDIT,
) -> dict:
    """POST an acceptance image to the Devvit /external/post-card endpoint."""
    return await _post_devvit_external(
        "post-card",
        {
            "title": title,
            "imageUrl": image_url,
            "flairId": flair_id,
            "subredditName": subreddit_name,
        },
    )


async def post_reply_via_devvit(*, post_id: str, text: str) -> dict:
    """POST a top-level comment via Devvit /external/reply-to-post."""
    return await _post_devvit_external(
        "reply-to-post",
        {
            "postId": post_id,
            "text": text,
        },
    )
