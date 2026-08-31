"""Build mork cache maps from the Hellfall GCS catalog."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from database_cache.card_names import get_all_names
from database_cache.database_utils import fixName
from database_cache.setHandling import getCollectorNumSets, getGroupSets, loadSets

DEFAULT_CATALOG_URL = (
    "https://storage.googleapis.com/hellfall-489004-hellfall-catalog/catalog.json"
)
DEFAULT_SETS_URL = (
    "https://raw.githubusercontent.com/bones-bones/hellfall/main/"
    "packages/shared/src/data/sets.json"
)


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


class _CardLookupObject:
    def __init__(self, card: dict[str, Any]) -> None:
        self.set_num_map: dict[str, dict[str, str]] = defaultdict(dict)
        self.set_map: dict[str, list[str]] = defaultdict(list)
        self.default_id = card["id"]
        self.add_card(card)

    def add_card(self, card: dict[str, Any]) -> None:
        card_id = card["id"]
        collector_number = str(card.get("collector_number", "")).lower()
        for set_code in getCollectorNumSets(card["set"]):
            if collector_number:
                self.set_num_map[set_code][collector_number] = card_id
        for set_code in getGroupSets(card["set"]):
            if card_id not in self.set_map[set_code]:
                self.set_map[set_code].append(card_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "setNumMap": {code: dict(nums) for code, nums in self.set_num_map.items()},
            "setMap": dict(self.set_map),
            "defaultId": self.default_id,
        }


class _CardLookupMap:
    def __init__(self) -> None:
        self.name_map: dict[str, _CardLookupObject] = {}
        self.alias_map: dict[str, str] = {}
        self.hcid_map: dict[str, str] = {}

    def add_card(self, card: dict[str, Any]) -> None:
        name = fixName(card["name"])
        hcid = fixName(str(card.get("hcid", "")))
        if hcid:
            self.hcid_map[hcid] = card["id"]

        existing = self.name_map.get(name)
        if existing:
            existing.add_card(card)
        else:
            self.name_map[name] = _CardLookupObject(card)
            self.alias_map.pop(name, None)

        for alias in get_all_names(card):
            if alias in self.name_map or alias in self.alias_map or alias in self.hcid_map:
                continue
            self.alias_map[alias] = name

    def to_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "nameMap": {name: lookup.to_dict() for name, lookup in self.name_map.items()},
            "aliasMap": dict(self.alias_map),
            "hcidMap": dict(self.hcid_map),
        }


def catalog_to_cache(
    cards: list[dict[str, Any]],
    *,
    sets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Convert Hellfall catalog cards into the get_cache payload shape."""
    print(f"[db] catalog_to_cache: {len(cards)} cards")
    if sets is not None:
        print(f"[db] catalog_to_cache: loading {len(sets)} sets")
        loadSets(sets)

    id_map: dict[str, dict[str, Any]] = {}
    oracle_map: dict[str, list[str]] = defaultdict(list)
    lookup = _CardLookupMap()

    for card in cards:
        card_id = card.get("id")
        if not card_id:
            continue

        id_map[card_id] = _catalog_card_to_search_card(card)

        oracle_id = card.get("oracle_id")
        if oracle_id and card_id not in oracle_map[str(oracle_id)]:
            oracle_map[str(oracle_id)].append(card_id)

        lookup.add_card(card)

    cache = lookup.to_dict()
    cache["idMap"] = id_map
    cache["oracleMap"] = dict(oracle_map)
    skipped = len(cards) - len(id_map)
    if skipped:
        print(f"[db] catalog_to_cache: skipped {skipped} cards without id")
    return cache
