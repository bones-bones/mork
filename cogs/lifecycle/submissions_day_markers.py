"""Post a daily submissions-channel marker and maintain the PREVIOUS WEEK pin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from discord import Message, TextChannel
from discord.ext import commands

import hc_constants
from getters import getSubmissionsChannel
from is_mork import is_mork


def day_marker_content(day: datetime) -> str:
    """Text for a new submissions-day marker (author should be the running bot)."""
    iso = day.strftime("%Y-%m-%d")
    human = day.strftime("%A, %B %d, %Y")
    return f"{hc_constants.SUBMISSIONS_DAY_MARKER_PREFIX}{iso}\n{human}"


def utc_day_start(day: datetime) -> datetime:
    return day.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def has_image_attachment(message: Message) -> bool:
    """True when the first attachment looks like a card image."""
    if not message.attachments:
        return False
    attachment = message.attachments[0]
    if attachment.content_type and attachment.content_type.startswith("image/"):
        return True
    filename = (attachment.filename or "").lower()
    return any(filename.endswith(ext) for ext in IMAGE_EXTENSIONS)


def is_submissions_card(message: Message) -> bool:
    """Mork-posted submission with an image attachment (same filter as checkSubmissions)."""
    if not is_mork(message.author.id):
        return False
    if not has_image_attachment(message):
        return False
    if is_submissions_day_marker(message):
        return False
    if message.content.startswith(hc_constants.PREVIOUS_WEEK_PIN_PREFIX):
        return False
    if "@everyone" in message.content or "@here" in message.content:
        return False
    return True


def is_submissions_day_marker(message: Message) -> bool:
    if not is_mork(message.author.id):
        return False
    return message.content.startswith(hc_constants.SUBMISSIONS_DAY_MARKER_PREFIX)


def day_marker_iso_date(message: Message) -> Optional[str]:
    if not is_submissions_day_marker(message):
        return None
    rest = message.content[len(hc_constants.SUBMISSIONS_DAY_MARKER_PREFIX) :].strip()
    iso = rest.split("\n", 1)[0].strip()
    if len(iso) == 10:
        return iso
    return None


def format_previous_week_body(markers: List[Message]) -> str:
    lines = [hc_constants.PREVIOUS_WEEK_PIN_PREFIX, "", "Last 7 submission days:", ""]
    if not markers:
        lines.append("_No day markers yet._")
        return "\n".join(lines)

    for marker in markers:
        iso = day_marker_iso_date(marker) or "unknown date"
        try:
            human = datetime.strptime(iso, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        except ValueError:
            human = iso
        lines.append(f"**{human}** — {marker.jump_url}")
    return "\n".join(lines)


async def collect_recent_day_markers(
    channel: TextChannel, *, limit: int = 7
) -> List[Message]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=21)
    found: List[Message] = []
    async for message in channel.history(after=cutoff, limit=None):
        if is_submissions_day_marker(message):
            found.append(message)
    found.sort(key=lambda m: m.created_at, reverse=True)
    return found[:limit]


async def find_previous_week_message(channel: TextChannel) -> Optional[Message]:
    for pin in await channel.pins():
        if pin.author.id != hc_constants.MORK_2:
            continue
        if pin.content.startswith(hc_constants.PREVIOUS_WEEK_PIN_PREFIX):
            return pin
    async for message in channel.history(limit=300):
        if message.author.id != hc_constants.MORK_2:
            continue
        if message.content.startswith(hc_constants.PREVIOUS_WEEK_PIN_PREFIX):
            return message
    return None


async def find_most_recent_day_marker(channel: TextChannel) -> Optional[Message]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=21)
    latest: Optional[Message] = None
    async for message in channel.history(after=cutoff, limit=None):
        if not is_submissions_day_marker(message):
            continue
        if latest is None or message.created_at > latest.created_at:
            latest = message
    return latest


async def has_card_submissions_between(
    channel: TextChannel, start: datetime, end: datetime
) -> bool:
    async for message in channel.history(after=start, before=end, limit=None):
        if is_submissions_card(message):
            return True
    return False


def submission_period_start(
    now: datetime, last_marker: Optional[Message]
) -> datetime:
    """Start of the open submission window to check before posting a new day marker."""
    yesterday_start = utc_day_start(now) - timedelta(days=1)
    if last_marker is None:
        return yesterday_start
    return max(last_marker.created_at, yesterday_start)


async def has_day_marker_for_date(channel: TextChannel, iso_date: str) -> bool:
    day_start = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    async for message in channel.history(after=day_start, limit=100):
        if day_marker_iso_date(message) == iso_date:
            return True
    return False


async def update_previous_week_pin(channel: TextChannel) -> None:
    markers = await collect_recent_day_markers(channel)
    body = format_previous_week_body(markers)
    summary = await find_previous_week_message(channel)
    if summary is None:
        summary = await channel.send(body)
        await summary.pin()
        return
    if summary.content != body:
        await summary.edit(content=body)


async def ensure_submissions_day_marker(bot: commands.Bot) -> None:
    """On first lifecycle run each UTC day, post today's marker and refresh the pin."""
    channel = getSubmissionsChannel(bot)
    now = datetime.now(timezone.utc)
    iso_today = now.strftime("%Y-%m-%d")

    if await has_day_marker_for_date(channel, iso_today):
        await update_previous_week_pin(channel)
        return

    today_start = utc_day_start(now)
    if not await has_card_submissions_between(channel, today_start, now):
        return

    await channel.send(day_marker_content(now))
    await update_previous_week_pin(channel)
