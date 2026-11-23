import os
import random
import traceback
from datetime import UTC, datetime, timedelta
from typing import cast

import aiofiles
import discord

import hc_constants
from cogs.lifecycle.submissions_day_markers import is_submissions_card
from reddit_devvit import post_gallery_via_devvit, reddit_gallery_via_devvit_enabled
from reddit_functions import post_gallery_to_reddit

GALLERY_TITLE = (
    "Some of Today's Submissions: Have any strong opinions on these cards? "
    "Join the discord to share them!"
)


async def _recent_submission_cards(bot) -> list[discord.Message]:
    sub_channel = cast(discord.TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))
    one_day = datetime.now(UTC) - timedelta(days=1)
    messages = [message async for message in sub_channel.history(after=one_day, limit=None)]
    filtered = [m for m in messages if is_submissions_card(m)]
    if not filtered:
        return []
    return random.sample(filtered, min(10, len(filtered)))


async def _download_discord_images(messages: list[discord.Message]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for message_entry in messages:
        file = await message_entry.attachments[0].to_file()
        file_data = file.fp.read()
        os.makedirs("tempImages", exist_ok=True)
        image_path = f"tempImages/{message_entry.id}{file.filename}"
        images.append({"image_path": image_path})
        async with aiofiles.open(image_path, "wb") as out:
            await out.write(file_data)
    return images


def _discord_attachment_urls(messages: list[discord.Message]) -> list[str]:
    urls: list[str] = []
    for message_entry in messages:
        url = str(message_entry.attachments[0].url or "").strip()
        if url:
            urls.append(url)
    return urls


async def post_daily_submissions(bot):
    """Pick recent #submissions polls from Discord, then post via Devvit or asyncpraw."""
    picked = await _recent_submission_cards(bot)
    if not picked:
        print("daily submissions gallery: no images (discord)")
        return

    if reddit_gallery_via_devvit_enabled():
        urls = _discord_attachment_urls(picked)
        if urls:
            try:
                await post_gallery_via_devvit(
                    title=GALLERY_TITLE,
                    image_urls=urls,
                    flair_id=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
                )
                return
            except Exception:
                traceback.print_exc()
                print("daily submissions gallery: Devvit failed; falling back to asyncpraw")

    images = await _download_discord_images(picked)
    if not images:
        print("daily submissions gallery: no images (discord)")
        return

    await post_gallery_to_reddit(
        title=GALLERY_TITLE,
        images=images,
        flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
    )
    for image_entry in images:
        os.remove(next(iter(image_entry.values())))
