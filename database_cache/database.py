from dataclasses import dataclass
from typing import Any

from database_cache.database_utils import fixName
from database_cache.get_closest_name import get_closest_name
from database_cache.setHandling import splitCardName


@dataclass
class LookupCard:
    setNumMap: dict[str, dict[str, str]]
    setMap: dict[str, list[str]]
    defaultId: str

    def __init__(self, **kwargs):
        # Only assign fields that exist, since python will throw a fit otherwise
        for field in self.__dataclass_fields__:
            setattr(self, field, kwargs.get(field, ""))

    def get(
        self,
        code: str | None = None,
        collector_number: str | None = None,
        noDefault: bool | None = None,
    ):
        default = None if noDefault else self.defaultId
        if not code:
            return default
        if not collector_number:
            try:
                return self.setMap[code][0]
            except (KeyError, IndexError):
                try:
                    return next(iter(self.setNumMap[code].values()))
                except (KeyError, StopIteration):
                    return default
        try:
            numMap = self.setNumMap[code]
            try:
                return numMap[collector_number]
            except KeyError:
                try:
                    return next(iter(numMap.values()))
                except StopIteration:
                    return default
        except KeyError:
            try:
                return self.setMap[code][0]
            except (KeyError, IndexError):
                return default


@dataclass
class SearchCard:
    id: str
    oracle_id: str
    hcid: str
    name: str
    set: str
    collector_number: str
    accepted_order: str
    image: str
    print_image: str | None
    legalities: dict[str, str]
    creators: list[str]
    artists: list[str] | None
    rulings: str
    base_tags: list[str] | None

    def __init__(self, **kwargs):
        # Only assign fields that exist, since python will throw a fit otherwise
        for field in self.__dataclass_fields__:
            setattr(self, field, kwargs.get(field, ""))


nameMap: dict[str, LookupCard] = {}
""" This maps a name to its individual maps """
aliasMap: dict[str, str] = {}
""" This maps an alias to the name that it is associated with """
hcidMap: dict[str, str] = {}
""" This maps a hcid to the preferred id to use """
idMap: dict[str, SearchCard] = {}
""" Maps card ids to their cards """
oracleMap: dict[str, list[str]] = {}
""" Maps oracle ids to the card ids they are associated with """


def build_database(serverJSON: dict[str, dict[str, Any]]):
    """Builds mork's local database using data from the server."""
    global nameMap, aliasMap, hcidMap, idMap, oracleMap
    print(f"[db] build_database starting; payload keys: {list(serverJSON.keys())}")
    try:
        name_map_data = serverJSON["nameMap"]
        alias_map_data = serverJSON["aliasMap"]
        hcid_map_data = serverJSON["hcidMap"]
        id_map_data = serverJSON["idMap"]
        oracle_map_data = serverJSON["oracleMap"]
    except KeyError as exc:
        print(f"[db] build_database missing key: {exc}")
        raise

    nameMap = {}
    for name, lookup in name_map_data.items():
        nameMap[name] = LookupCard(**lookup)
    aliasMap = alias_map_data
    hcidMap = hcid_map_data
    idMap = {}
    for id, card in id_map_data.items():
        idMap[id] = SearchCard(**card)
    oracleMap = oracle_map_data
    print(
        "[db] build_database complete: "
        f"{len(idMap)} cards, {len(nameMap)} names, "
        f"{len(aliasMap)} aliases, {len(hcidMap)} hcids"
    )


def _get_id_by_set_and_num(
    name: str,
    code: str | None = None,
    collector_number: str | None = None,
    noDefault: bool | None = None,
):
    if not name:
        return
    if not code and name in hcidMap and name not in ["3", "1984"]:
        return hcidMap.get(name)
    try:
        try:
            lookup = nameMap[name]
        except KeyError:
            lookup = nameMap[aliasMap[name]]
        return lookup.get(code, collector_number, noDefault)
    except KeyError:
        return


def yieldAllNames():
    yield from nameMap
    yield from aliasMap
    for hcid in hcidMap:
        if hcid.isdigit():
            yield hcid


def get_id_by_name(text: str):
    return _get_id_by_set_and_num(*splitCardName(fixName(text)))


def get_id_by_fuzzy_name(text: str):
    fixed = fixName(text)
    exact = _get_id_by_set_and_num(*splitCardName(fixed))
    if exact:
        return exact
    return _get_id_by_set_and_num(*splitCardName(get_closest_name(fixed, yieldAllNames())))


def get_id_by_hcid(hcid: str):
    return hcidMap.get(fixName(hcid))


def get_card_by_id(uuid: str):
    return idMap.get(uuid)


def get_card_by_name(name: str):
    uuid = get_id_by_name(name)
    if uuid:
        return get_card_by_id(uuid)


def get_card_by_fuzzy_name(name: str):
    uuid = get_id_by_fuzzy_name(name)
    if uuid:
        return get_card_by_id(uuid)


def card_name_exists(name: str):
    fixed = fixName(name)
    exact = _get_id_by_set_and_num(*splitCardName(fixed))
    return bool(exact)
