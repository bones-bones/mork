import re
from dataclasses import dataclass
from typing import Any, Literal, TypeIs, cast, get_args

type SetCode = Literal[
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
    "HBB_HKL",
    "HCV_HKL",
    "HC9",
    "HC9_0",
    "HBB_9",
    "HCV_9",
    "SCL",
    "SCL_01",
    "SCL_02",
    "SCL_03",
    "HCV_SCL",
    "HDH",
    "HCV_HDH",
    "SCL_04",
    "HBB_SCL",
    "SCL_05",
    "SOH",
    "HCV_SOH",
    "SCL_06",
    "SCL_07",
    "SCL_08",
    "HC9_1",
    "SCL_09",
    "SCL_10",
    "HCV",
    "HCT",
    "HBB",
    "FHCJ",
    "SFT",
    "NRM",
]
allSetsList = get_args(SetCode)


@dataclass
class cardSet:
    id: str
    code: SetCode
    set_type: str
    parent_set_code: SetCode | None
    child_set_codes: list[SetCode] | None
    use_color_order: bool | None

    def __init__(self, **kwargs):
        # Only assign fields that exist, since python will throw a fit otherwise
        for field in self.__dataclass_fields__:
            setattr(self, field, kwargs.get(field, ""))


setMap: dict[SetCode, cardSet] = {}


def loadSets(rawSets: list[dict[str, Any]]):
    """Loads the setMap with sets from the server."""
    global setMap
    setMap = {raw["code"]: cardSet(**raw) for raw in rawSets}


def isSetCode(code: str) -> TypeIs[SetCode]:
    return code in setMap


def isDisplaySetCode(code: str) -> bool:
    return "_" not in code and isSetCode(code.replace(".", "_"))


def fixSetCodeInput(code: str):
    """Fixes valid set code input to actually work"""
    return code.upper().replace(".", "_")


def fixSetCodeInputMaybe(code: str | None):
    """Fixes valid set code input to actually work, accepting `None` as valid"""
    return fixSetCodeInput(code) if code else code


def displayToBackendSetCode(code: str) -> SetCode:
    """Gets the backend version of a set code"""
    return cast(SetCode, code.replace("_", "."))


def backendToDisplaySetCode(code: SetCode) -> str:
    """Gets the display version of a set code"""
    return code.replace(".", "_")


def backendToDisplaySetCodeMaybe(code: SetCode | None):
    """Gets the display version of a set code"""
    return backendToDisplaySetCode(code) if code else code


numRegex = re.compile(r"^\d+$")


def toSetCode(value: str) -> SetCode | None:
    """Converts a value to a set code if possible"""
    code = value.strip()
    if isSetCode(code):
        return code
    if " " in code:
        return
    code = fixSetCodeInput(code)
    if isSetCode(code):
        return code

    splitCode = code.split("_")
    splitCode[0] = splitCode[0].lstrip("0") or "0"
    if len(splitCode[0]) == 1:
        splitCode[0] = "HLC" if splitCode[0] == "1" else f"HC{splitCode[0]}"
    elif splitCode[0] == "HC1":
        splitCode[0] = "HLC"

    start = splitCode[0]
    if not isSetCode(start):
        return
    if len(splitCode) == 1:
        return start
    if start in ["HBB", "HCV"]:
        if splitCode[1].startswith("HC"):
            splitCode[1] = splitCode[1][2:]
        elif splitCode[1] == "HLC":
            splitCode[1] = "1"

    for i in range(len(splitCode)):
        try:
            num = int(splitCode[i])
        except ValueError:
            continue
        splitCode[i] = f"{num:02}" if i == 1 and start == "SCL" else f"{num}"

    joined = "_".join(splitCode)
    return joined if isSetCode(joined) else None


def toDisplaySetCode(value: str):
    return backendToDisplaySetCodeMaybe(toSetCode(value))


def getSet(code: SetCode):
    """Gets the set object given a set code"""
    return setMap.get(code)


def getSetPermissive(code: str):
    """Gets the set object given a set code"""
    toGet = toSetCode(code)
    if toGet:
        return setMap.get(toGet)


def getDirectParentSetCode(code: SetCode):
    """Gets the set code that is the direct parent of another set"""
    curSet = getSet(code)
    if curSet:
        return curSet.parent_set_code


def getDirectParentSet(code: SetCode):
    """Gets the set that is the direct parent of another set"""
    curCode = getDirectParentSetCode(code)
    if curCode:
        return getSet(curCode)


def getParentSet(code: SetCode):
    """Gets the set that is the parent of another set"""
    curSet = getSet(code)
    if not curSet:
        return
    while curSet.parent_set_code:
        curSet = getSet(curSet.parent_set_code)
        if not curSet:
            return
    if curSet.code == code:
        return
    return curSet


def getParentSetCode(code: SetCode):
    """Gets the set code that is the parent of another set"""
    curSet = getParentSet(code)
    if curSet:
        return curSet.code


def _getChildVeto(set: cardSet):
    if set.child_set_codes:
        for child in set.child_set_codes:
            childSet = getSet(child)
            if childSet and childSet.set_type == "veto":
                return childSet


def getVetoSet(code: SetCode):
    """Gets the set that is the veto set for another set"""
    curSet = getSet(code)
    if not curSet or curSet.set_type == "veto":
        return
    veto = _getChildVeto(curSet)
    while not veto and curSet.parent_set_code:
        curSet = getSet(curSet.parent_set_code)
        if not curSet:
            return
        veto = _getChildVeto(curSet)
    return veto


def getVetoSetCode(code: str):
    """Gets the set code that is the veto set code for another set

    Also correctly handles sets that are missing from/not yet added to the db"""
    if isSetCode(code):
        curSet = getVetoSet(code)
        if curSet:
            return curSet.code
    if not getSet(cast(SetCode, code)):
        start = fixSetCodeInput(code).split("_")[0]
        if start.startswith("HCV"):
            return
        if start.startswith("HC"):
            return f"HCV_{start[2:]}"
        return f"HCV_{start}"


def getChildSets(code: SetCode) -> list[SetCode] | None:
    """Gets the sets that are the children of another set"""
    curSet = getSet(code)
    if not curSet or not curSet.child_set_codes:
        return
    codes: list[SetCode] = []
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


def getDirectChildSets(code: SetCode):
    """Gets the sets that are the direct children of another set (i.e. are its children and have the same set type)"""
    childSets = getChildSets(code)
    parent = getParentSet(code)
    if not parent or not childSets:
        return
    parentType = parent.set_type
    directChildren: list[SetCode] = []
    for child in childSets:
        childSet = getSet(child)
        if not childSet:
            continue
        if childSet.set_type == parentType:
            directChildren.append(child)
    if directChildren:
        return directChildren


def getSetAndChildSets(code: SetCode) -> list[SetCode]:
    """Gets the result of {@linkcode getChildSets} except including the set itself"""
    if not isSetCode(code):
        return []
    sets: list[SetCode] = [code]
    children = getChildSets(code)
    if children:
        sets.extend(children)
    return sets


def getSetAndDirectChildSets(code: SetCode) -> list[SetCode]:
    """Gets the result of {@linkcode getDirectChildSets} except including the set itself"""
    if not isSetCode(code):
        return []
    sets: list[SetCode] = [code]
    children = getDirectChildSets(code)
    if children:
        sets.extend(children)
    return sets


def getBlockSets(code: SetCode) -> list[SetCode]:
    """Gets the sets that are in the same block as another set (i.e. are its group and have the same set type)"""
    toGet = getSet(code)
    if not toGet:
        return []
    setType = toGet.set_type
    sets: list[SetCode] = [code]
    children = getDirectChildSets(code)
    if children:
        sets.extend(children)
    for parentCode, parent in setMap.items():
        if parent.set_type != setType:
            continue
        siblings = getDirectChildSets(parentCode)
        if not siblings:
            continue
        if code in siblings:
            sets.extend(siblings)
    return sets


def getGroupSets(code: SetCode) -> list[SetCode]:
    """Gets the sets that are in the same group as another set (i.e. are its children or its parent)"""
    sets: list[SetCode] = [code]
    children = getChildSets(code)
    if children:
        sets.extend(children)
    for parentCode in setMap:
        siblings = getChildSets(parentCode)
        if not siblings:
            continue
        if code in siblings:
            sets.extend(siblings)
    return sets


def getCollectorNumSets(code: SetCode) -> list[SetCode]:
    """Gets the sets that share collector numbers with another set, including that set itself"""
    setItself = getSet(code)
    if not setItself:
        return [code]
    parent = getParentSet(code)
    if (
        setItself.use_color_order
        or (parent and parent.use_color_order)
        or setItself.set_type == "lair"
    ):
        return getBlockSets(code)
    return [code]


def getCollectorOrderSet(code: SetCode) -> SetCode:
    """Gets the set that a set uses for collector number sorting"""
    parent = getParentSet(code)
    if not parent:
        return code
    if parent.use_color_order or parent.set_type == "lair":
        return parent.code
    return code


def getAcceptedOrderSet(code: SetCode) -> SetCode:
    """Gets the set that a set uses for accepted order sorting"""
    parent = getDirectParentSet(code)
    if not parent:
        return code
    if parent.set_type == "lair":
        return parent.code
    if parent.code.startswith("HCV_"):
        [mainset, subset] = code.split("_")[1:]
        acceptedSet = f"{'HLC' if mainset == '1' else f'HC{mainset}_{subset}'}"
        return acceptedSet if isSetCode(acceptedSet) else code
    return code


def isCollectorNum(text: str):
    return bool(re.match(r"^\d+[A-Za-z]?$", text))


masterpieceNumRegex = re.compile(r"^([^:]+):(.*)\|\s*(\d+[A-Za-z]?)$")
masterpieceRegex = re.compile(r"^([^:]+):(.*)$")


def splitMasterpiece(text: str) -> tuple[str, SetCode, str | None] | None:
    match = masterpieceNumRegex.match(text)
    if match:
        (code, name, collector_number) = (
            s.strip() for s in cast(tuple[str, str, str], match.groups())
        )
        code = toSetCode(code)
        if isCollectorNum(collector_number) and code:
            collector_number = collector_number.lower()
            return (name, code, collector_number)
    match = masterpieceRegex.match(text)
    if match:
        (code, name) = (s.strip() for s in cast(tuple[str, str], match.groups()))
        code = toSetCode(code)
        if code:
            return (name, code, None)


setCodeNumRegex = re.compile(
    r"^(.*)(?:\|\s*\(|[(|])\s*([^\s)|]+)\s*(?:\)\s*\||[\s)|])\s*(\d+[A-Za-z]?)$"
)
setCodeRegex = re.compile(r"^(.*)(?:\|\s*\(|[(|])\s*([^\s)|]+)\s*[)|]?$")


def splitSetCode(text: str) -> tuple[str, SetCode, str | None] | None:
    match = setCodeNumRegex.match(text)
    if match:
        (name, code, collector_number) = (
            s.strip() for s in cast(tuple[str, str, str], match.groups())
        )
        code = toSetCode(code)
        if isCollectorNum(collector_number) and code:
            collector_number = collector_number.lower()
            return (name, code, collector_number)
    match = setCodeRegex.match(text)
    if match:
        (name, code) = (s.strip() for s in cast(tuple[str, str], match.groups()))
        code = toSetCode(code)
        if code:
            return (name, code, None)


def splitCardName(text: str) -> tuple[str, SetCode | None, str | None]:
    """Splits a name of a card from input into the card's name, set (if any), and collector num (if any)"""
    match = splitMasterpiece(text)
    if match:
        return match
    match = splitSetCode(text)
    if match:
        return match
    return (text, None, None)
