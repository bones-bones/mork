import re
from dataclasses import dataclass
from typing import Any, cast


@dataclass
class cardSet:
    id: str
    code: str
    set_type: str
    parent_set_code: str | None
    child_set_codes: list[str] | None
    use_color_order: bool | None

    def __init__(self, **kwargs):
        # Only assign fields that exist, since python will throw a fit otherwise
        for field in self.__dataclass_fields__:
            setattr(self, field, kwargs.get(field, ""))


setMap: dict[str, cardSet] = {}
allSetsList = [
    "HLC",
    "HLC_0",
    "HCV_1_0",
    "HLC_1",
    "HCV_1_1",
    "HLC_2",
    "HCV_1",
    "HC2",
    "HC2_0",
    "HCV_2_0",
    "HC2_1",
    "HCV_2_1",
    "HCV_2",
    "HC3",
    "HC3_0",
    "HCV_3_0",
    "HC3_1",
    "HCV_3_1",
    "HCV_3",
    "HBB_0",
    "HC4",
    "HC4_0",
    "HCV_4_0",
    "HC4_1",
    "HCV_4_1",
    "HBB_4",
    "HCV_4",
    "HC5",
    "HC6",
    "HC6_0",
    "HC6_1",
    "HCC",
    "HCV_6",
    "HWN",
    "HCP",
    "HCV_P",
    "HC7",
    "HC7_0",
    "HC7_1",
    "HBB_7",
    "HCV_7",
    "CDC",
    "HCK",
    "HCV_K",
    "HC8",
    "HC8_0",
    "HCJ",
    "HCV_J",
    "HC8_1",
    "HCV_8",
    "HKL",
    "HBB_L",
    "HCV_HKL",
    "HC9",
    "HC9_0",
    "HBB_9",
    "HCV_9",
    "SCL",
    "SCL_1",
    "SCL_2",
    "SCL_3",
    "HCV_SCL",
    "HDH",
    "HCV_HDH",
    "SCL_4",
    "HBB_S",
    "SCL_5",
    "SOH",
    "HCV_SOH",
    "SCL_6",
    "SCL_7",
    "HCV",
    "HCT",
    "HBB",
    "FHCJ",
    "SFT",
    "NRM",
]


def loadSets(rawSets: list[dict[str, Any]]):
    """Loads the setMap with sets from the server."""
    global setMap
    setMap = {raw["code"]: cardSet(**raw) for raw in rawSets}


def fixSetCode(code: str):
    """Fixes valid set code input to actually work"""
    return code.upper().replace(".", "_")


def isSetCode(code: str):
    return fixSetCode(code) in setMap


def displaySetCode(code: str):
    """Gets the display version of a set code"""
    return code.upper().replace("_", ".")


def fixSetCodeMaybe(code: str | None):
    """Fixes valid set code input to actually work, accepting `None` as valid"""
    return fixSetCode(code) if code else code


def getSet(code: str):
    """Gets the set object given a set code"""
    return setMap.get(fixSetCode(code))


def getDirectParentSetCode(code: str):
    """Gets the set code that is the direct parent of another set"""
    curSet = getSet(code)
    if curSet:
        return curSet.parent_set_code


def getDirectParentSet(code: str):
    """Gets the set that is the direct parent of another set"""
    curCode = getDirectParentSetCode(code)
    if curCode:
        return getSet(curCode)


def getParentSet(code: str):
    """Gets the set that is the parent of another set"""
    curSet = getSet(code)
    if not curSet:
        return
    while curSet.parent_set_code:
        curSet = getSet(curSet.parent_set_code)
        if not curSet:
            return
    if curSet.code == fixSetCode(code):
        return
    return curSet


def getParentSetCode(code: str):
    """Gets the set code that is the parent of another set"""
    curSet = getParentSet(code)
    if curSet:
        return curSet.code


def getChildSets(code: str) -> list[str] | None:
    """Gets the sets that are the children of another set"""
    curSet = getSet(code)
    if not curSet or not curSet.child_set_codes:
        return
    codes: list[str] = []
    for childCode in curSet.child_set_codes:
        codes.append(childCode)
        child = getSet(childCode)
        if not child or not child.child_set_codes:
            continue
        subChildren = getChildSets(childCode)
        if subChildren:
            codes.extend(subChildren)
    if codes:
        return codes


def getDirectChildSets(code: str):
    """Gets the sets that are the direct children of another set (i.e. are its children and have the same set type)"""
    childSets = getChildSets(code)
    parent = getParentSet(code)
    if not parent or not childSets:
        return
    parentType = parent.set_type
    directChildren: list[str] = []
    for child in childSets:
        childSet = getSet(child)
        if not childSet:
            continue
        if childSet.set_type == parentType:
            directChildren.append(child)
    if directChildren:
        return directChildren


def getSetAndChildSets(code: str) -> list[str]:
    """Gets the result of {@linkcode getChildSets} except including the set itself"""
    if not isSetCode(code):
        return []
    sets = [fixSetCode(code)]
    children = getChildSets(code)
    if children:
        sets.extend(children)
    return sets


def getSetAndDirectChildSets(code: str) -> list[str]:
    """Gets the result of {@linkcode getDirectChildSets} except including the set itself"""
    if not isSetCode(code):
        return []
    sets = [fixSetCode(code)]
    children = getDirectChildSets(code)
    if children:
        sets.extend(children)
    return sets


def getBlockSets(code: str) -> list[str]:
    """Gets the sets that are in the same block as another set (i.e. are its group and have the same set type)"""
    toGet = getSet(code)
    if not toGet:
        return []
    setType = toGet.set_type
    fixed = fixSetCode(code)
    sets = [fixed]
    children = getDirectChildSets(code)
    if children:
        sets.extend(children)
    for parentCode, parent in setMap.items():
        if parent.set_type != setType:
            continue
        siblings = getDirectChildSets(parentCode)
        if not siblings:
            continue
        if fixed in siblings:
            sets.extend(siblings)
    return sets


def getGroupSets(code: str) -> list[str]:
    """Gets the sets that are in the same group as another set (i.e. are its children or its parent)"""
    fixed = fixSetCode(code)
    sets = [fixed]
    children = getChildSets(code)
    if children:
        sets.extend(children)
    for parentCode in setMap:
        siblings = getChildSets(parentCode)
        if not siblings:
            continue
        if fixed in siblings:
            sets.extend(siblings)
    return sets


def getCollectorNumSets(code: str) -> list[str]:
    """Gets the sets that share collector numbers with another set, including that set itself"""
    setItself = getSet(code)
    fixed = fixSetCode(code)
    if not setItself:
        return [fixed]
    parent = getParentSet(code)
    if (
        setItself.use_color_order
        or (parent and parent.use_color_order)
        or setItself.set_type == "lair"
    ):
        return getBlockSets(code)
    return [fixed]


def getCollectorOrderSet(code: str) -> str:
    """Gets the set that a set uses for collector number sorting"""
    parent = getParentSet(code)
    fixed = fixSetCode(code)
    if not parent:
        return fixed
    if parent.use_color_order or parent.set_type == "lair":
        return parent.code
    return fixed


def getAcceptedOrderSet(code: str) -> str:
    """Gets the set that a set uses for accepted order sorting"""
    parent = getDirectParentSet(code)
    fixed = fixSetCode(code)
    if not parent:
        return fixed
    if parent.set_type == "lair":
        return parent.code
    if parent.code.startswith("HCV_"):
        [mainset, subset] = fixed.split("_")[1:]
        acceptedSet = f"{'HLC' if mainset == '1' else f'HC{mainset}_{subset}'}"
        return acceptedSet if isSetCode(acceptedSet) else fixed
    return fixed


def isCollectorNum(text: str):
    return bool(re.match(r"^\d+[A-Za-z]?$", text))


masterpieceNumRegex = re.compile(r"^([^:]+):(.*)\|\s*(\d+[A-Za-z]?)$")
masterpieceRegex = re.compile(r"^([^:]+):(.*)$")


def splitMasterpiece(text: str) -> tuple[str, str, str | None] | None:
    match = masterpieceNumRegex.match(text)
    if match:
        (code, name, collector_number) = (
            s.strip() for s in cast(tuple[str, str, str], match.groups())
        )
        if isCollectorNum(collector_number) and isSetCode(code):
            code = fixSetCode(code)
            collector_number = collector_number.lower()
            return (name, code, collector_number)
        code = fixSetCode(code)
    match = masterpieceRegex.match(text)
    if match:
        (code, name) = (s.strip() for s in cast(tuple[str, str], match.groups()))
        if isSetCode(code):
            code = fixSetCode(code)
            return (name, code, None)


setCodeNumRegex = re.compile(
    r"^(.*)(?:\|\s*\(|[(|])\s*([^\s)|]+)\s*(?:\)\s*\||[\s)|])\s*(\d+[A-Za-z]?)$"
)
setCodeRegex = re.compile(r"^(.*)(?:\|\s*\(|[(|])\s*([^\s)|]+)\s*[)|]?$")


def splitSetCode(text: str) -> tuple[str, str, str | None] | None:
    match = setCodeNumRegex.match(text)
    if match:
        (name, code, collector_number) = (
            s.strip() for s in cast(tuple[str, str, str], match.groups())
        )
        if isCollectorNum(collector_number) and isSetCode(code):
            code = fixSetCode(code)
            collector_number = collector_number.lower()
            return (name, code, collector_number)
        code = fixSetCode(code)
    match = setCodeRegex.match(text)
    if match:
        (name, code) = (s.strip() for s in cast(tuple[str, str], match.groups()))
        if isSetCode(code):
            code = fixSetCode(code)
            return (name, code, None)


def splitCardName(text: str) -> tuple[str, str | None, str | None]:
    """Splits a name of a card from input into the card's name, set (if any), and collector num (if any)"""
    match = splitMasterpiece(text)
    if match:
        return match
    match = splitSetCode(text)
    if match:
        return match
    return (text, None, None)
