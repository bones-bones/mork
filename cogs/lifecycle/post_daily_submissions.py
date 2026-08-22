import os
from datetime import datetime, timedelta, timezone
from random import sample
from typing import cast

import aiofiles
import discord
from discord.ext import commands

import hc_constants
from cogs.lifecycle.submissions_day_markers import is_submissions_card
from reddit_functions import post_gallery_to_reddit


async def post_daily_submissions(bot: commands.Bot):
    subChannel = cast(discord.TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))
    timeNow = datetime.now(timezone.utc)
    oneDay = timeNow + timedelta(days=-1)
    messages = subChannel.history(after=oneDay, limit=None)
    images: list[dict[str, str]] = []

    messages = [message async for message in messages]

    filteredMessages = [m for m in messages if is_submissions_card(m)]
    if not filteredMessages:
        return

    toPost = sample(filteredMessages, min(10, len(filteredMessages)))
    for messageEntry in toPost:
        file = await messageEntry.attachments[0].to_file()
        file_data = file.fp.read()
        os.makedirs("tempImages", exist_ok=True)
        image_path = f"tempImages/{messageEntry.id}{file.filename}"
        images.append({"image_path": image_path})
        async with aiofiles.open(image_path, "wb") as out:
            await out.write(file_data)
    await post_gallery_to_reddit(
        title="Some of Today's Submissions: Have any strong opinions on these cards? Join the discord to share them!",
        images=images,
        flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
    )
    for imageEntry in images:
        os.remove(next(iter(imageEntry.values())))
    return
