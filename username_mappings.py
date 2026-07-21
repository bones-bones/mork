username_mappings: list[list[str]] = []


def set_username_mappings(mappings: list[list[str]]) -> None:
    global username_mappings
    username_mappings = mappings


def resolve_username(raw: str) -> str:
    if not raw:
        return raw
    row = next((m for m in username_mappings if raw in m[1]), None)
    return row[0] if row else raw


def resolve_authors(raw: str) -> str:
    if "; " in raw:
        return "; ".join(resolve_username(part.strip()) for part in raw.split("; "))
    return resolve_username(raw)


def usernames_equivalent(a: str, b: str) -> bool:
    return resolve_username(a).lower() == resolve_username(b).lower()
