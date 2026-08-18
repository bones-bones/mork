"""Submit card chages via POST."""

from __future__ import annotations

import json
import os
from typing import Any, Literal

import aiohttp

# from CardClasses import CardSearch
from hellfall_fetcher import getExactCard


class ChangesetError(Exception):
    """Raised when changeset fails."""

def _api_url() -> str:
    return os.environ.get("HELLFALL_API_URL", "").rstrip("/")

def _api_key() -> str:
    return os.environ.get("HELLFALL_POSTCARD_API_KEY", "")

def _auth_headers() -> dict[str, str]:
    return {
        # todo: figure out better way to do this
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }

def _request_timeout() -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=30)

async def _read_response_json(resp: aiohttp.ClientResponse) -> Any:
    body = await resp.text()
    if not body.strip():
        raise ChangesetError(f"empty_response HTTP {resp.status}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        snippet = body[:200]
        raise ChangesetError(
            f"invalid_json HTTP {resp.status}: {snippet!r}"
        ) from exc


async def modifyTagWithServer(cardName:str, tag:str, change_type:Literal['add','delete'])->str:
    api_url = _api_url()
    api_key = _api_key()
    if not api_url or not api_key:
        raise ChangesetError(
            "HELLFALL_API_URL and HELLFALL_POSTCARD_API_KEY are required"
        )

    timeout = _request_timeout()
    uuid = (await getExactCard(cardName)).uuid
    payload: dict[str, str] = {
        "tag": tag,
        "change_type": change_type,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{api_url}/api/cards/{uuid}/tags",
            json=payload,
            headers=_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await _read_response_json(resp)
            reason = data.get("reason") if isinstance(data, dict) else None
            return reason.replace('_', ' ') if isinstance(reason,str) else f'successfully {'added' if change_type == 'add' else 'removed'} tag'
