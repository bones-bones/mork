import os
import random
from datetime import datetime, timedelta, timezone, UTC
from urllib.parse import urlparse

import aiofiles
import aiohttp

import hc_constants
from cogs.lifecycle.submissions_day_markers import is_submissions_card
from reddit_functions import post_gallery_to_reddit
from submissions_gallery_manifest import entries_last_24h, manifest_url

GALLERY_TITLE = (
    "Some of Today's Submissions: Have any strong opinions on these cards? "
    "Join the discord to share them!"
)


def gallery_uses_manifest() -> bool:
    return os.environ.get("REDDIT_GALLERY_USE_MANIFEST", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


async def _download_image_to_temp(image_url: str, message_id: str) -> str:
    parsed = urlparse(image_url)
    ext = os.path.splitext(parsed.path)[1] or ".png"
    os.makedirs("tempImages", exist_ok=True)
    path = f"tempImages/gallery_{message_id}{ext}"
    async with (
        aiohttp.ClientSession() as session,
        session.get(image_url) as resp,
    ):
        resp.raise_for_status()
        data = await resp.read()
    async with aiofiles.open(path, "wb") as out:
        await out.write(data)
    return path


async def _gallery_images_from_manifest() -> list[dict[str, str]]:
    entries = entries_last_24h()
    if not entries:
        return []
    picked = random.sample(entries, min(10, len(entries)))
    images: list[dict[str, str]] = []
    for entry in picked:
        message_id = str(entry.get("messageId", "unknown"))
        image_url = str(entry.get("imageUrl", "")).strip()
        if not image_url:
            continue
        path = await _download_image_to_temp(image_url, message_id)
        images.append({"image_path": path})
    return images


async def _gallery_images_from_discord(bot) -> list[dict[str, str]]:
    from typing import cast

    import discord

    sub_channel = cast(
        discord.TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL)
    )
    time_now = datetime.now(UTC)
    one_day = time_now + timedelta(days=-1)
    messages = [message async for message in sub_channel.history(after=one_day, limit=None)]
    filtered = [m for m in messages if is_submissions_card(m)]
    if not filtered:
        return []

    picked = random.sample(filtered, min(10, len(filtered)))
    images: list[dict[str, str]] = []
    for message_entry in picked:
        file = await message_entry.attachments[0].to_file()
        file_data = file.fp.read()
        os.makedirs("tempImages", exist_ok=True)
        image_path = f"tempImages/{message_entry.id}{file.filename}"
        images.append({"image_path": image_path})
        async with aiofiles.open(image_path, "wb") as out:
            await out.write(file_data)
    return images


async def post_daily_submissions(bot):
    if gallery_uses_manifest():
        images = await _gallery_images_from_manifest()
    else:
        images = await _gallery_images_from_discord(bot)

    if not images:
        print(
            "daily submissions gallery: no images "
            f"(manifest={manifest_url() if gallery_uses_manifest() else 'discord'})"
        )
        return

    await post_gallery_to_reddit(
        title=GALLERY_TITLE,
        images=images,
        flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
    )
    for image_entry in images:
        os.remove(next(iter(image_entry.values())))
