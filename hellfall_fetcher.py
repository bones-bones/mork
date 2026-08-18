"""Use various commands via GET /api/mork."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import aiohttp

# from CardClasses import CardSearch


class CommandError(Exception):
    """Raised when hellfall command fails."""

def _api_url() -> str:
    return os.environ.get("HELLFALL_API_URL", "").rstrip("/")

def _auth_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
    }

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
            if not isinstance(data, dict):
                raise CommandError("command_failed")
            return data
@dataclass
class SearchCard:
    name: str
    image:str
    collector_number:str
    set:str
    uuid: str
    hcid: str
    def __init__(self, **kwargs):
        # Only assign fields that exist in this dataclass
        for field in self.__dataclass_fields__:
            setattr(self, field, kwargs.get(field, ''))



async def getExactCard(cardName: str)->SearchCard:
    payload: dict[str, str] = {
        "command": 'exact',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    return SearchCard(**data)


async def cardExists(cardName: str):
    try:
        card = await getExactCard(cardName)
        return True
    except:
        return False

async def cardsExist(cardNames:list[str]):
    api_url = _api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = _request_timeout()
    payload: dict[str, str|list[str]] = {
        "command": 'exist',
        "card_names": cardNames,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/mork",
            json=payload,
            headers=_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await _read_response_json(resp)
            if resp.status not in [200, 400]:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            return resp.status == 200

@dataclass
class CreatorResponse:
    uuid: str
    name: str
    creators: list[str]

async def getCreators(cardName: str,) -> CreatorResponse:
    payload: dict[str, str] = {
        "command": 'creators',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    uuid = data.get('uuid')
    name=data.get('name')
    creators = data.get('creators')
    if not uuid or name is None or creators is None:
        raise CommandError("command_failed")
    return CreatorResponse(uuid=uuid,name=name,creators=creators)

@dataclass
class RulingsResponse:
    uuid: str
    name: str
    rulings: str

async def getRulings(cardName: str,) -> RulingsResponse:
    payload: dict[str, str] = {
        "command": 'rulings',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    uuid = data.get('uuid')
    name=data.get('name')
    rulings = data.get('rulings')
    if not uuid or name is None or rulings is None:
        raise CommandError("command_failed")
    return RulingsResponse(uuid=uuid,name=name,rulings=rulings)

@dataclass
class InfoResponse:
    uuid: str
    info: str

async def getInfo(cardName: str,) -> InfoResponse:
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
    data: list[SearchCard]

async def getSearchFromServer(query:str)->SearchResponse:
    api_url = _api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = _request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/cards/search/",
            params={'q':query, 'format':'json'},
            headers=_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await _read_response_json(resp)
            if resp.status != 200:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            if not isinstance(data, dict) or data.get('object') is None:
                raise CommandError("search_failed")
            object=data.get('object')
            total_cards=data.get('total_cards')
            details=data.get('details')
            warnings=data.get('warnings')
            rawData = data.get('data')
            if object is None or total_cards is None or details is None or rawData is None:
                raise CommandError("search_failed")
            cards=[SearchCard(**card) for card in rawData]
            return SearchResponse(object=object,total_cards=total_cards,details=details,warnings=warnings,data=cards)

@dataclass
class ErrataDataResponse:
    uuid: str
    hcid: str
    name: str
    image:str
    creators: list[str]

async def getErrataData(cardName: str,) -> ErrataDataResponse:
    payload: dict[str, str] = {
        "command": 'errata_data',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    uuid = data.get('uuid')
    name=data.get('name')
    hcid = data.get('hcid')
    creators = data.get('creators')
    image = data.get('image')
    if not uuid or name is None or creators is None or hcid is None or image is None:
        raise CommandError("command_failed")
    return ErrataDataResponse(uuid=uuid,name=name,creators=creators, hcid=hcid, image=image)

@dataclass
class RandomResponse:
    name:str
    image:str

async def getRandomFromServer(query:str|None)->RandomResponse:
    api_url = _api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = _request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/cards/random/",
            params={'q':query} if query else {},
            headers=_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await _read_response_json(resp)
            if resp.status != 200:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            if not isinstance(data, dict) or data.get('object') is None:
                raise CommandError("search_failed")
            image = data.get('image')
            name = data.get('name')
            if image is None or name is None:
                raise CommandError("random_failed")
            return RandomResponse(image=image, name=name)

