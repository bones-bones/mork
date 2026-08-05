#!/usr/bin/env python3
"""Benchmark cardNameRequest against the Hellscube database JSON."""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cardNameRequest import cardNameRequest  # noqa: E402

DEFAULT_DB = (
    REPO_ROOT.parent
    / "hellfall"
    / "packages"
    / "shared"
    / "src"
    / "data"
    / "Hellscube-Database.json"
)


def is_token(card: dict) -> bool:
    if card.get("layout") == "token":
        return True
    type_line = card.get("type_line") or ""
    return type_line.startswith("Token ")


def load_names(db_path: Path, *, include_tokens: bool = False) -> list[str]:
    with db_path.open() as f:
        data = json.load(f)
    names = []
    for card in data["data"]:
        if not card.get("name"):
            continue
        if not include_tokens and is_token(card):
            continue
        names.append(card["name"].lower())
    return names


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    import shared_vars

    names = load_names(db_path)
    shared_vars.allCards = {name: None for name in names}
    print(f"Loaded {len(names)} card names (non-token) from {db_path}")

    cases = [
        ("lightning bolt", "lightning bolt, but worse"),
        ("counterspell", None),
        ("black lotus", "black lotus"),
        ("whale visions", "whale visions"),
        ("dark rit", "dark ritual"),
        ("dark ritual", "dark ritual"),
        ("jace the mind", None),
        ("goblin guide", None),
        ("liliana of the", "liliana of the vale"),
        ("wrath of god", None),
        ("force of will", None),
        ("brainstorm", "brainstorm maggot"),
        ("tarmogoyf", "tarmogoyf"),
        ("fish", "fish school"),
    ]

    failures = 0
    for query, expected in cases:
        result = cardNameRequest(query)
        ok = expected is None or result == expected
        if not ok:
            failures += 1
        status = "OK" if ok else "FAIL"
        print(f"[{status}] '{query}' -> '{result}'")
        if expected and not ok:
            print(f"       expected '{expected}'")

    long_name_queries = ["jace the mind", "angry beavers", "the", "of will"]
    for query in long_name_queries:
        result = cardNameRequest(query)
        if len(result) > 200:
            failures += 1
            print(f"[FAIL] '{query}' matched overly long name ({len(result)} chars)")
        else:
            print(f"[OK] '{query}' -> '{result[:60]}'")

    start = time.perf_counter()
    for _ in range(5):
        cardNameRequest("lightning bolt")
    elapsed_ms = (time.perf_counter() - start) / 5 * 1000
    print(f"\nAvg lookup: {elapsed_ms:.0f}ms")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
