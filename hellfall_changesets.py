"""Submit card changes via POST."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

import aiohttp

from hellfall_fetcher import getExactCard, getFuzzyCard
from hellfall_shared import (
    get_api_key,
    get_api_url,
    get_auth_headers,
    get_request_timeout,
    read_response_json,
)


class ChangesetError(Exception):
    """Raised when changeset fails."""


async def modifyTagWithServer(
    cardName: str, tag: str, change_type: Literal["add", "delete"]
) -> str:
    api_url = get_api_url()
    api_key = get_api_key()
    if not api_url or not api_key:
        raise ChangesetError("HELLFALL_API_URL and HELLFALL_POSTCARD_API_KEY are required")

    timeout = get_request_timeout()
    card = await getExactCard(cardName)
    if not card:
        closest = await getFuzzyCard(cardName)
        if not closest:
            return "please include a card name"
        return f"unable to find an exact match for {cardName}. did you mean: {closest.name}"
    uuid = card.id
    payload: dict[str, str] = {
        "tag": tag,
        "change_type": change_type,
    }

    async with (
        aiohttp.ClientSession().post(
            f"{api_url}/api/cards/{quote(uuid)}/tags",
            json=payload,
            headers=get_auth_headers(api_key),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        reason = data.get("reason") if isinstance(data, dict) else None
        return (
            reason.replace("_", " ")
            if isinstance(reason, str)
            else f"successfully {'added' if change_type == 'add' else 'removed'} tag"
        )
