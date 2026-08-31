"""Use various commands via GET /api/mork."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import aiohttp

from database_cache import database as card_database
from database_cache.catalog_cache import (
    DEFAULT_CATALOG_URL,
    DEFAULT_SETS_URL,
    catalog_to_cache,
)
from database_cache.database import (
    SearchCard,
    build_database,
    card_name_exists,
    get_card_by_fuzzy_name,
    get_card_by_id,
    get_card_by_name,
)
from hellfall_shared import (
    get_api_url,
    get_auth_headers,
    get_request_timeout,
    read_response_json,
)


class CommandError(Exception):
    """Raised when hellfall command fails."""


STILL_USING_CACHE = True


def is_card_cache_loaded() -> bool:
    return bool(card_database.idMap)


async def bootstrap_card_cache(*, force: bool = False) -> None:
    """Fetch catalog and build in-memory lookup maps. Call before handling messages."""
    if is_card_cache_loaded() and not force:
        print("[db] card cache already loaded, skipping bootstrap")
        return
    print("[db] bootstrapping card cache")
    cache = await getDatabaseCache()
    build_database(cache)
    print("[db] card cache bootstrap complete")


async def getDataFromServer(payload: dict[str, str] | dict[str, str | list[str]]):
    api_url = get_api_url()
    if not api_url:
        raise CommandError("HELLFALL_API_URL is required")
    timeout = get_request_timeout()

    async with (
        aiohttp.ClientSession().get(
            f"{api_url}/api/mork",
            json=payload,
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        if resp.status != 200:
            reason = data.get("reason") if isinstance(data, dict) else None
            raise CommandError(reason or f"HTTP {resp.status}")
        if not isinstance(data, dict):
            raise CommandError("command_failed")
        return data


async def getDatabaseCache() -> dict[str, dict[str, Any]]:
    timeout = get_request_timeout()
    print(f"[db] fetching catalog from {DEFAULT_CATALOG_URL}")
    print(f"[db] fetching sets from {DEFAULT_SETS_URL}")
    async with (
        aiohttp.ClientSession() as session,
        session.get(DEFAULT_CATALOG_URL, timeout=timeout) as catalog_resp,
        session.get(DEFAULT_SETS_URL, timeout=timeout) as sets_resp,
    ):
        catalog_data = await read_response_json(catalog_resp)
        sets_data = await read_response_json(sets_resp)
        print(f"[db] catalog HTTP {catalog_resp.status}, sets HTTP {sets_resp.status}")
        if catalog_resp.status != 200:
            raise CommandError(f"catalog HTTP {catalog_resp.status}")
        if sets_resp.status != 200:
            raise CommandError(f"sets HTTP {sets_resp.status}")
    if not isinstance(catalog_data, dict):
        print(f"[db] catalog response type: {type(catalog_data).__name__}")
        raise CommandError("catalog_invalid")
    if "nameMap" in catalog_data:
        print(f"[db] using pre-built cache payload ({len(catalog_data.get('idMap', {}))} cards)")
        return catalog_data
    cards = catalog_data.get("data")
    if not isinstance(cards, list):
        print(f"[db] catalog missing data list; keys: {list(catalog_data.keys())[:10]}")
        raise CommandError("catalog_invalid")
    if not isinstance(sets_data, dict):
        print(f"[db] sets response type: {type(sets_data).__name__}")
        raise CommandError("sets_invalid")
    sets = sets_data.get("data")
    if not isinstance(sets, list):
        print(f"[db] sets missing data list; keys: {list(sets_data.keys())[:10]}")
        raise CommandError("sets_invalid")
    print(f"[db] building cache from {len(cards)} cards, {len(sets)} sets")
    cache = catalog_to_cache(cards, sets=sets)
    print(
        "[db] built cache: "
        f"{len(cache.get('idMap', {}))} cards, "
        f"{len(cache.get('nameMap', {}))} names"
    )
    return cache


async def getCardById(uuid: str) -> SearchCard | None:
    if STILL_USING_CACHE:
        return get_card_by_id(uuid)

    payload: dict[str, str] = {
        "command": "uuid",
        "card_name": uuid,
    }
    data = await getDataFromServer(payload)
    return SearchCard(**data)


async def getMultipleCardsByIds(uuids: list[str]) -> list[SearchCard]:
    if STILL_USING_CACHE:
        cards = [get_card_by_id(cardName) for cardName in uuids]
        return [card for card in cards if card]
    try:
        payload: dict[str, str | list[str]] = {
            "command": "multiple_uuid",
            "card_names": uuids,
        }
        data = (await getDataFromServer(payload)).get("data")
        if isinstance(data, list):
            return [SearchCard(**card) for card in data]
    except CommandError:
        return []
    return []


async def getExactCard(cardName: str) -> SearchCard | None:
    if STILL_USING_CACHE:
        return get_card_by_name(cardName)

    payload: dict[str, str] = {
        "command": "exact",
        "card_name": cardName,
    }
    data = await getDataFromServer(payload)
    return SearchCard(**data)


async def getMultipleExactCards(cardNames: list[str]) -> list[SearchCard]:
    if STILL_USING_CACHE:
        cards = [get_card_by_name(cardName) for cardName in cardNames]
        return [card for card in cards if card]
    try:
        payload: dict[str, str | list[str]] = {
            "command": "multiple_exact",
            "card_names": cardNames,
        }
        data = (await getDataFromServer(payload)).get("data")
        if isinstance(data, list):
            return [SearchCard(**card) for card in data]
    except CommandError:
        return []
    return []


async def getFuzzyCard(cardName: str | None) -> SearchCard | None:
    if not cardName:
        return None
    if STILL_USING_CACHE:
        return get_card_by_fuzzy_name(cardName)
    payload: dict[str, str] = {
        "command": "fuzzy",
        "card_name": cardName,
    }
    try:
        data = await getDataFromServer(payload)
        return SearchCard(**data)
    except CommandError:
        return None


async def getMultipleFuzzyCards(cardNames: list[str]) -> list[SearchCard]:
    if STILL_USING_CACHE:
        cards = [get_card_by_fuzzy_name(cardName) for cardName in cardNames]
        return [card for card in cards if card]
    try:
        payload: dict[str, str | list[str]] = {
            "command": "multiple_fuzzy",
            "card_names": cardNames,
        }
        data = (await getDataFromServer(payload)).get("data")
        if isinstance(data, list):
            return [SearchCard(**card) for card in data]
    except CommandError:
        return []
    return []


async def cardExists(cardName: str):
    if STILL_USING_CACHE:
        return card_name_exists(cardName)
    try:
        if await getExactCard(cardName):
            return True
    except CommandError:
        return False
    return False


async def cardsExist(cardNames: list[str]):
    if STILL_USING_CACHE:
        return all(card_name_exists(cardName) for cardName in cardNames)

    api_url = get_api_url()
    if not api_url:
        raise CommandError("HELLFALL_API_URL is required")
    timeout = get_request_timeout()
    payload: dict[str, str | list[str]] = {
        "command": "all_exist",
        "card_names": cardNames,
    }

    async with (
        aiohttp.ClientSession().get(
            f"{api_url}/api/mork",
            json=payload,
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        if resp.status not in [200, 400]:
            reason = data.get("reason") if isinstance(data, dict) else None
            raise CommandError(reason or f"HTTP {resp.status}")
        return resp.status == 200


@dataclass
class SearchResponse:
    object: str
    total_cards: int
    details: str
    warnings: list[str] | None
    data: list[SearchCard]


async def getSearchFromServer(query: str) -> SearchResponse:
    api_url = get_api_url()
    if not api_url:
        raise CommandError("HELLFALL_API_URL is required")
    timeout = get_request_timeout()

    async with (
        aiohttp.ClientSession().get(
            f"{api_url}/api/cards/search/",
            params={"q": query, "format": "json"},
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        if resp.status != 200:
            reason = data.get("reason") if isinstance(data, dict) else None
            raise CommandError(reason or f"HTTP {resp.status}")
        if not isinstance(data, dict) or data.get("object") is None:
            raise CommandError("search_failed")
        object = data.get("object")
        total_cards = data.get("total_cards")
        details = data.get("details")
        warnings = data.get("warnings")
        rawData = data.get("data")
        if object is None or total_cards is None or details is None or rawData is None:
            raise CommandError("search_failed")
        cards = [SearchCard(**card) for card in rawData]
        return SearchResponse(
            object=object,
            total_cards=total_cards,
            details=details,
            warnings=warnings,
            data=cards,
        )


async def getRandomFromServer(query: str | None) -> SearchCard:
    if STILL_USING_CACHE and not query:
        card = get_card_by_id(random.choice(list(card_database.idMap.keys())))
        if not card:
            raise CommandError("random_failed")
        return card
    api_url = get_api_url()
    if not api_url:
        raise CommandError("HELLFALL_API_URL is required")
    timeout = get_request_timeout()

    async with (
        aiohttp.ClientSession().get(
            f"{api_url}/api/cards/random/",
            params={"q": query} if query else None,
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        if resp.status != 200:
            reason = data.get("reason") if isinstance(data, dict) else None
            raise CommandError(reason or f"HTTP {resp.status}")
        if not isinstance(data, dict) or data.get("object") is None:
            raise CommandError("random_failed")
        return SearchCard(**data)


async def getMultipleRandomFromServer(query: str | None, num: int) -> list[SearchCard]:
    if num <= 1:
        return [await getRandomFromServer(query)]
    if STILL_USING_CACHE and not query:
        cards = [
            get_card_by_id(random.choice(list(card_database.idMap.keys()))) for i in range(num)
        ]
        if not cards[0]:
            raise CommandError("random_failed")
        return [card for card in cards if card]
    api_url = get_api_url()
    if not api_url:
        raise CommandError("HELLFALL_API_URL is required")
    timeout = get_request_timeout()

    async with (
        aiohttp.ClientSession().get(
            f"{api_url}/api/cards/random/",
            params={"q": query} if query else None,
            json={"num": num},
            headers=get_auth_headers(),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        if resp.status != 200:
            reason = data.get("reason") if isinstance(data, dict) else None
            raise CommandError(reason or f"HTTP {resp.status}")
        if not isinstance(data, dict) or data.get("object") is None or data.get("data") is None:
            raise CommandError("random_failed")
        cards = data["data"]
        return [SearchCard(**card) for card in cards]
