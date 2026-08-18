"""Use various commands via GET /api/mork."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import aiohttp

class CommandError(Exception):
    """Raised when hellfall command fails."""


from hellfall_shared import get_api_url, get_auth_headers, read_response_json, get_request_timeout

async def getDataFromServer(payload:dict[str,str]|dict[str,str|list[str]]):
    api_url = get_api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = get_request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/mork",
            json=payload,
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await read_response_json(resp)
            if resp.status != 200:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            if not isinstance(data, dict):
                raise CommandError("command_failed")
            return data
@dataclass
class SearchCard:
    id: str
    oracle_id:str
    hcid: str
    name: str
    set:str
    collector_number:str
    accepted_order:str
    image:str
    legalities:dict[str,str]
    creators: list[str]
    artists: list[str]|None
    rulings: str
    base_tags: list[str]|None
    def __init__(self, **kwargs):
        # Only assign fields that exist, since python will throw a fit otherwise
        for field in self.__dataclass_fields__:
            setattr(self, field, kwargs.get(field, ''))

async def getExactCard(cardName: str)->SearchCard:
    payload: dict[str, str] = {
        "command": 'exact',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    return SearchCard(**data)

async def getRoughCard(cardName: str)->SearchCard:
    payload: dict[str, str] = {
        "command": 'rough',
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    return SearchCard(**data)

async def getMultipleRoughCards(cardNames: list[str])->list[SearchCard]:
    payload: dict[str, str|list[str]] = {
        "command": 'multiple_rough',
        "card_names": cardNames,
    }
    data = (await getDataFromServer(payload)).get('data')
    if isinstance(data,list):
        return [SearchCard(**card) for card in data]
    return []


async def cardExists(cardName: str):
    try:
        card = await getExactCard(cardName)
        return True
    except:
        return False

async def cardsExist(cardNames:list[str]):
    api_url = get_api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = get_request_timeout()
    payload: dict[str, str|list[str]] = {
        "command": 'exist',
        "card_names": cardNames,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/mork",
            json=payload,
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await read_response_json(resp)
            if resp.status not in [200, 400]:
                reason = data.get("reason") if isinstance(data, dict) else None
                raise CommandError(reason or f"HTTP {resp.status}")
            return resp.status == 200

@dataclass
class SearchResponse:
    object:str
    total_cards:int
    details:str
    warnings:list[str]|None
    data: list[SearchCard]

async def getSearchFromServer(query:str)->SearchResponse:
    api_url = get_api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = get_request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/cards/search/",
            params={'q':query, 'format':'json'},
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await read_response_json(resp)
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
class RandomResponse:
    name:str
    image:str

async def getRandomFromServer(query:str|None)->RandomResponse:
    api_url = get_api_url()
    if not api_url:
        raise CommandError(
            "HELLFALL_API_URL is required"
        )
    timeout = get_request_timeout()

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{api_url}/api/cards/random/",
            params={'q':query} if query else {},
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp:
            data = await read_response_json(resp)
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

