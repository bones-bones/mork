"""Use various commands via GET /api/mork."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal, Optional

import aiohttp

from CardClasses import CardSearch


class CommandError(Exception):
    """Raised when hellfall commmand fails."""


# @dataclass
# class CommandRequest:
#     command: str
#     name:str
#     # was_create: bool
#     # previous: dict[str, Any] | None
#     # image_url: str | None = None
#     # # Hellfall card UUID from response ``id`` (sheet BB / token L). Not always
#     # # equal to ``doc_id`` on updates — use this for sheet UUID columns.
#     # hellfall_id: str | None = None
#     # # Oracle card UUID from response ``oracle_id`` (sheet BC / token M).
#     # oracle_id: str | None = None




def _api_url() -> str:
    return os.environ.get("HELLFALL_API_URL", "").rstrip("/")



def _auth_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
    }


def _payload_summary(payload: dict[str, str]) -> str:
    summary = {key: value for key, value in payload.items() if key != "imageBase64"}
    if "imageBase64" in payload:
        summary["imageBase64"] = f"<{len(payload['imageBase64'])} chars>"
    return repr(summary)


def _request_timeout() -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=30)


async def _read_response_json(resp: aiohttp.ClientResponse) -> Any:
    body = await resp.text()
    if not body.strip():
        raise CommandError(f"empty_response HTTP {resp.status}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        snippet = body[:200]
        raise CommandError(
            f"invalid_json HTTP {resp.status}: {snippet!r}"
        ) from exc



async def getDataFromServer(payload:dict[str,str]):
    api_url = _api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = _request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/mork",
            json=payload,
            headers=_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await _read_response_json(resp)
            if resp.status != 200:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            if not isinstance(data, dict) or not data.get("ok"):
                raise CommandError("command_failed")
            return data

@dataclass
class CreatorResponse:
    uuid: str
    name: str|None
    creators: list[str]|None

async def getCreators(
    *,
    cardName: str,
) -> CreatorResponse:
    payload: dict[str, str] = {
        "command": 'creators',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    uuid = data.get('uuid')
    if not uuid:
        raise CommandError("command_failed")
    name=data.get('name')
    creators = data.get('creators')
    return CreatorResponse(uuid=uuid,name=name,creators=creators)

@dataclass
class RulingsResponse:
    uuid: str
    name: str|None
    rulings: str|None

async def getRulings(
    *,
    cardName: str,
) -> RulingsResponse:
    payload: dict[str, str] = {
        "command": 'rulings',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    uuid = data.get('uuid')
    if not uuid:
        raise CommandError("command_failed")
    name=data.get('name')
    rulings = data.get('rulings')
    return RulingsResponse(uuid=uuid,name=name,rulings=rulings)

@dataclass
class InfoResponse:
    uuid: str
    info: str

async def getInfo(
    *,
    cardName: str,
) -> InfoResponse:
    payload: dict[str, str] = {
        "command": 'info',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    uuid = data.get('uuid')
    if not uuid:
        raise CommandError("command_failed")
    info=data.get('info')
    if not info:
        raise CommandError("command_failed")
    return InfoResponse(uuid=uuid,info=info)

@dataclass
class SearchResponse:
    object:str
    total_cards:int
    details:str
    warnings:list[str]|None
    data: list[Any]

async def getSearchFromServer(query:str)->SearchResponse:
    api_url = _api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = _request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/cards/search/?q={query}",
            headers=_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await _read_response_json(resp)
            if resp.status != 200:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            if not isinstance(data, dict) or not data.get("ok") or data.get('object') is None:
                raise CommandError("search_failed")
            object=data.get('object')
            total_cards=data.get('total_cards')
            details=data.get('details')
            warnings=data.get('warnings')
            cardData=data.get('data')
            if object is None or total_cards is None or details is None or cardData is None:
                raise CommandError("search_failed")
            return SearchResponse(object=object,total_cards=total_cards,details=details,warnings=warnings,data=cardData)
