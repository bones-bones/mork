"""Post gate open/close announcements in submissions channels."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from discord import TextChannel
from discord.ext import commands

import hc_constants
from cogs.lifecycle.submissions_closed import CLOSED_WEEKDAYS, SUBMISSIONS_TZ

GATES_CLOSED_MESSAGE = "THE GATES OF HELL ARE CLOSED"
GATES_OPENED_MESSAGE = "THE GATES OF HELL HAVE OPENED"
# Day after each closed day (Wed, Sun).
OPENED_WEEKDAYS = {2, 6}
GATES_ANNOUNCEMENT_CHANNEL_IDS = (
    hc_constants.SUBMISSIONS_CHANNEL,
    hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL,
)


def gate_announcement_for(at: datetime) -> str | None:
    """Return announcement text for this US Eastern calendar day, if any."""
    weekday = at.astimezone(SUBMISSIONS_TZ).weekday()
    if weekday in CLOSED_WEEKDAYS:
        return GATES_CLOSED_MESSAGE
    if weekday in OPENED_WEEKDAYS:
        return GATES_OPENED_MESSAGE
    return None


def gate_announcement_key(message: str, iso_date: str) -> str:
    return f"{message}:{iso_date}"


def _load_state() -> dict[str, Any]:
    path = hc_constants.GATES_STATE_FILE
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as file:
        content = file.read().strip()
        if not content:
            return {}
        return json.loads(content)


def _save_state(state: dict[str, Any]) -> None:
    with open(hc_constants.GATES_STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file)


async def ensure_submissions_gates(bot: commands.Bot) -> None:
    """Post today's gate message once per lifecycle day in submissions channels."""
    now = datetime.now(timezone.utc)
    local = now.astimezone(SUBMISSIONS_TZ)
    message = gate_announcement_for(now)
    if message is None:
        return

    iso_today = local.date().isoformat()
    key = gate_announcement_key(message, iso_today)
    state = _load_state()
    if state.get("last_announcement") == key:
        return

    content = f"@here {message}"
    for channel_id in GATES_ANNOUNCEMENT_CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if isinstance(channel, TextChannel):
            await channel.send(content)
    state["last_announcement"] = key
    _save_state(state)
