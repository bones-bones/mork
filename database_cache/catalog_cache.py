"""Build mork cache maps from the Hellfall GCS catalog."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from database_cache.database_utils import fixName

DEFAULT_CATALOG_URL = (
    "https://storage.googleapis.com/hellfall-489004-hellfall-catalog/catalog.json"
)

_KIND_PRIORITY = {
    "card": 0,
    "front": 1,
    "token": 2,
    "scryfall": 3,
}


def _accepted_order_key(card: dict[str, Any]) -> tuple[int, str]:
    raw = card.get("accepted_order", "")
    try:
        return (int(str(raw)), str(raw))
    except (TypeError, ValueError):
        return (10**9, str(raw))


def _card_sort_key(card: dict[str, Any]) -> tuple[int, int, str]:
    kind = str(card.get("kind", "card"))
    return (
        _KIND_PRIORITY.get(kind, 99),
        _accepted_order_key(card)[0],
        str(card.get("id", "")),
    )


def _preferred_card(cards: list[dict[str, Any]]) -> dict[str, Any]:
    return min(cards, key=_card_sort_key)


def _catalog_card_to_search_card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card["id"],
        "oracle_id": card.get("oracle_id", ""),
        "hcid": str(card.get("hcid", "")),
        "name": card.get("name", ""),
        "set": card.get("set", ""),
        "collector_number": str(card.get("collector_number", "")),
        "accepted_order": str(card.get("accepted_order", "")),
        "image": card.get("image", ""),
        "legalities": card.get("legalities", {}),
        "creators": card.get("creators", []),
        "artists": card.get("artists"),
        "rulings": card.get("rulings", ""),
        "base_tags": card.get("base_tags"),
    }


def catalog_to_cache(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convert Hellfall catalog cards into the get_cache payload shape."""
    id_map: dict[str, dict[str, Any]] = {}
    oracle_map: dict[str, list[str]] = defaultdict(list)
    hcid_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    name_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    alias_map: dict[str, str] = {}

    for card in cards:
        card_id = card.get("id")
        if not card_id:
            continue

        id_map[card_id] = _catalog_card_to_search_card(card)

        oracle_id = card.get("oracle_id")
        if oracle_id:
            oracle_map[str(oracle_id)].append(card_id)

        hcid = card.get("hcid")
        if hcid not in (None, ""):
            hcid_candidates[str(hcid)].append(card)

        name = card.get("name")
        if name:
            name_groups[fixName(name)].append(card)

        flavor_name = card.get("flavor_name")
        if flavor_name and name:
            alias_map[fixName(str(flavor_name))] = fixName(name)

    hcid_map: dict[str, str] = {}
    for hcid, group in hcid_candidates.items():
        hcid_map[fixName(hcid)] = _preferred_card(group)["id"]

    name_map: dict[str, dict[str, Any]] = {}
    for fixed_name, group in name_groups.items():
        preferred = _preferred_card(group)
        set_num_map: dict[str, dict[str, str]] = defaultdict(dict)
        set_map: dict[str, list[str]] = defaultdict(list)

        for card in sorted(group, key=_card_sort_key):
            card_id = card["id"]
            set_code = str(card.get("set", ""))
            collector_number = str(card.get("collector_number", ""))
            if set_code:
                set_map[set_code].append(card_id)
                if collector_number:
                    set_num_map[set_code][collector_number] = card_id

        name_map[fixed_name] = {
            "setNumMap": {code: dict(nums) for code, nums in set_num_map.items()},
            "setMap": dict(set_map),
            "defaultId": preferred["id"],
        }

    return {
        "nameMap": name_map,
        "aliasMap": alias_map,
        "hcidMap": hcid_map,
        "idMap": id_map,
        "oracleMap": dict(oracle_map),
    }
