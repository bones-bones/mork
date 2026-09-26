from typing import Any, TypeAlias, cast

from database_cache.setHandling import SetCode, allSetsList, getAcceptedOrderSet, getSet, isSetCode

_CacheCard: TypeAlias = dict[str, Any]  # noqa: UP040 until we fix the vm issues


def _set_type_is_not_extra(set_type: str | None):
    return bool(set_type and set_type in ["land", "main", "side"])


def _in_cube(card: _CacheCard):
    curSet = getSet(cast(SetCode, card.get("set")))
    if curSet:
        return _set_type_is_not_extra(curSet.set_type)


typical_frame_list = [
    "1993",
    "1997",
    "2003",
    "2015",
    "token_1997",
    "token_2003",
    "token_2015",
    "token_2020",
]

atypical_effect_list = [
    "colorshifted",
    "inverted",
    "showcase",
    "masterpiece",
    "fullart",
    "etched",
    "slab",
    "shatteredglass",
]


def _part_is_typical(part: _CacheCard):
    if part.get("frame") not in typical_frame_list:
        return False
    effects = part.get("frame_effects")
    if not isinstance(effects, list):
        return True
    return not any(effect in atypical_effect_list for effect in effects)


def _card_is_typical(card: _CacheCard):
    return _part_is_typical(card) and (
        "card_faces" not in card or _part_is_typical(card["card_faces"][0])
    )


def _to_set_number(code: SetCode):
    try:
        return allSetsList.index(code)
    except ValueError:
        return -1


def _get_card_set_number(card: _CacheCard):
    curSet = card.get("set")
    if isinstance(curSet, str) and isSetCode(curSet):
        return _to_set_number(getAcceptedOrderSet(curSet))
    return -1


def _parse_accepted(accepted: str):
    try:
        return int(accepted)
    except ValueError:
        try:
            return int(accepted[:-1])
        except ValueError:
            return 0


def _get_accepted(card: _CacheCard):
    accepted = card.get("accepted_order")
    if accepted:
        return _parse_accepted(accepted)
    return 0


def cacheCompare(value1: _CacheCard, value2: _CacheCard):
    cube1 = bool(_in_cube(value1))
    cube2 = bool(_in_cube(value2))
    if cube1 != cube2:
        return -1 if cube1 else 1
    typic1 = _card_is_typical(value1)
    typic2 = _card_is_typical(value2)
    if typic1 != typic2:
        return -1 if typic1 else 1
    date1 = value1.get("date")
    date2 = value2.get("date")
    if isinstance(date1, str) and isinstance(date2, str) and date1 != date2:
        return -1 if date1 < date2 else 1
    date1 = value1.get("date")
    date2 = value2.get("date")
    if isinstance(date1, str) and isinstance(date2, str) and date1 != date2:
        return -1 if date1 < date2 else 1
    diff = _get_card_set_number(value1) - _get_card_set_number(value2)
    if diff:
        return diff
    return _get_accepted(value1) - _get_accepted(value2)


def shouldSwap(newCard: _CacheCard, oldCard: _CacheCard | None = None):
    if not oldCard:
        return True
    return cacheCompare(newCard, oldCard) < 0
