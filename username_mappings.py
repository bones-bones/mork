username_mappings: dict[str, str] = {}


def set_username_mappings(mappings: list[list[str]]) -> None:
    global username_mappings
    result: dict[str, str] = {}
    for row in mappings:
        if len(row) < 2 or not row[0].strip():
            continue
        key = row[0]
        for alias in ";".join(row[1:]).split(";"):
            alias = alias.strip()
            if alias:
                result[alias.lower()] = key
    username_mappings = result


def resolve_username(raw: str) -> str:
    if raw.lower() in username_mappings:
        return username_mappings[raw.lower()]
    return raw


def resolve_authors(raw: str) -> list[str]:
    return [resolve_username(name) for name in raw.split(";")]


def usernames_equivalent(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return resolve_username(a).lower() == resolve_username(b).lower()
