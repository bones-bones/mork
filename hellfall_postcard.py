"""Post accepted cards to hellfall via POST /api/cards/postcard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal, Optional

import aiohttp


class PostcardSyncError(Exception):
    """Raised when hellfall postcard sync fails."""


@dataclass
class PostcardWrite:
    doc_id: str
    was_create: bool
    previous: dict[str, Any] | None
    image_url: str | None = None


def postcard_sync_enabled() -> bool:
    return os.environ.get("MORK_POSTCARD_SYNC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _api_url() -> str:
    return os.environ.get("HELLFALL_API_URL", "").rstrip("/")


def _api_key() -> str:
    return os.environ.get("HELLFALL_POSTCARD_API_KEY", "")


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


async def sync_accepted_card(
    *,
    name: str,
    creators: str,
    set_id: str,
    image: Optional[str] = None,
    image_base64: Optional[str] = None,
    hcid: Optional[str] = None,
    kind: Literal["card", "token"] = "card",
    require_sync: bool = False,
) -> Optional[PostcardWrite]:
    if not require_sync and not postcard_sync_enabled():
        return None

    api_url = _api_url()
    api_key = _api_key()
    if not api_url or not api_key:
        raise PostcardSyncError(
            "HELLFALL_API_URL and HELLFALL_POSTCARD_API_KEY are required"
        )

    if not image and not image_base64:
        raise PostcardSyncError("image or image_base64 is required")

    payload: dict[str, str] = {
        "name": name,
        "creators": creators,
        "set": set_id,
        "kind": kind,
    }
    if image_base64:
        payload["imageBase64"] = image_base64
    elif image:
        payload["image"] = image
    if hcid:
        payload["hcid"] = hcid

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{api_url}/api/cards/postcard",
            json=payload,
            headers=_auth_headers(),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise PostcardSyncError(reason or f"HTTP {resp.status}")
            if not isinstance(data, dict) or not data.get("ok"):
                raise PostcardSyncError("postcard_failed")

            previous = data.get("previous")
            image_url = data.get("imageUrl")
            return PostcardWrite(
                doc_id=str(data["docId"]),
                was_create=bool(data["wasCreate"]),
                previous=previous if isinstance(previous, dict) else None,
                image_url=str(image_url) if image_url else None,
            )


async def rollback_postcard_write(write: PostcardWrite) -> None:
    api_url = _api_url()
    api_key = _api_key()
    if not api_url or not api_key:
        return

    payload: dict[str, Any] = {
        "docId": write.doc_id,
        "wasCreate": write.was_create,
    }
    if write.previous is not None:
        payload["previous"] = write.previous

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{api_url}/api/cards/postcard/rollback",
            json=payload,
            headers=_auth_headers(),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                data = await resp.json(content_type=None)
                reason = data.get("reason") if isinstance(data, dict) else None
                raise PostcardSyncError(reason or f"rollback HTTP {resp.status}")
