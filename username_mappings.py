username_mappings: dict[str, str]


def set_username_mappings(mappings: list[list[str]]) -> None:
    global username_mappings
    username_mappings = {v.lower(): key for key, value in mappings for v in value.split(";")}


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
