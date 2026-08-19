#!/usr/bin/env python3
"""Benchmark getRoughCard against the live db."""

import time

from hellfall_fetcher import getFuzzyCard


async def main() -> int:
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
        result = await getFuzzyCard(query)
        ok = expected is None or result == expected
        if not ok:
            failures += 1
        status = "OK" if ok else "FAIL"
        print(f"[{status}] '{query}' -> '{result}'")
        if expected and not ok:
            print(f"       expected '{expected}'")

    long_name_queries = ["jace the mind", "angry beavers", "the", "of will"]
    for query in long_name_queries:
        result = await getFuzzyCard(query)
        if len(result.name) > 200:
            failures += 1
            print(f"[FAIL] '{query}' matched overly long name ({len(result.name)} chars)")
        else:
            print(f"[OK] '{query}' -> '{result.name[:60]}'")

    start = time.perf_counter()
    for _ in range(5):
        await getFuzzyCard("lightning bolt")
    elapsed_ms = (time.perf_counter() - start) / 5 * 1000
    print(f"\nAvg lookup: {elapsed_ms:.0f}ms")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
