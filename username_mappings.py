import json
import os
from typing import Any

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


def _rows_from_mapping_object(data: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for canonical, aliases in data.items():
        canonical_str = str(canonical).strip()
        if not canonical_str:
            continue
        if isinstance(aliases, str):
            alias_cells = [aliases]
        elif isinstance(aliases, list):
            alias_cells = [str(a) for a in aliases]
        else:
            continue
        rows.append([canonical_str, *alias_cells])
    return rows


def load_username_mappings_from_file(path: str) -> bool:
    """Load alias → canonical map from JSON. Returns True if mappings were applied."""
    if not path or not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        rows = _rows_from_mapping_object(data)
    elif isinstance(data, list):
        rows = data
    else:
        return False
    if not rows:
        return False
    set_username_mappings(rows)
    return True


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
