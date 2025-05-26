from datetime import datetime, timezone, timedelta
import os
from random import sample
from typing import Dict, List, cast
import discord
from discord.ext import commands

import hc_constants

from reddit_functions import post_gallery_to_reddit


async def post_daily_submissions(bot: commands.Bot):
    subChannel = cast(
        discord.TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL)
    )
    timeNow = datetime.now(timezone.utc)
    oneDay = timeNow + timedelta(days=-1)
    messages = subChannel.history(after=oneDay, limit=None)
    images: List[Dict[str, str]] = []

    messages = [message async for message in messages]

    filteredMessages = list(filter(lambda x: len(x.attachments) > 0, messages))

    toPost = sample(filteredMessages, min(10, filteredMessages.__len__()))
    for messageEntry in toPost:

        file = await messageEntry.attachments[0].to_file()
        file_data = file.fp.read()
        image_path = f"tempImages/{messageEntry.id}{file.filename}"
        images.append({"image_path": image_path})
        with open(image_path, "wb") as out:
            out.write(file_data)
    await post_gallery_to_reddit(
        title=f"Some of Today's Submissions: Have any strong opinions on these cards? Join the discord to share them!",
        images=images,
        flair=hc_constants.OFFICIAL_FLAIR,
    )
    for imageEntry in images:
        os.remove(list(imageEntry.values())[0])
    return
