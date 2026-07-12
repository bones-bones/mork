"""Design Hell admin medal reactions → card acceptance."""

from __future__ import annotations

import re
from typing import Optional

from discord import TextChannel

DESIGN_HELL_SET_PATTERN = re.compile(
    r"Set:\s*(?:\*\*)?\s*([A-Za-z0-9._]+)",
    re.IGNORECASE,
)


def parse_set_id_from_design_hell_prompt(content: str) -> Optional[str]:
    match = DESIGN_HELL_SET_PATTERN.search(content)
    if not match:
        return None
    return match.group(1).strip()


def card_name_and_author_from_design_hell_message(
    content: str, author_name: str
) -> tuple[str, str]:
    card_name = content.strip().split("\n", 1)[0].strip()
    return card_name, author_name.strip()


async def get_current_design_hell_set_id(channel: TextChannel) -> Optional[str]:
    pins = await channel.pins()
    if not pins:
        return None
    return parse_set_id_from_design_hell_prompt(pins[0].content)
