from datetime import datetime
from typing import cast
from discord import TextChannel
from discord.ext import commands
import asyncpraw
from datetime import datetime, timezone, timedelta
import hc_constants

from bot_secrets.reddit_secrets import ID, NAME, PASSWORD, SECRET, USER_AGENT


async def check_reddit(bot: commands.Bot):
    print("checking reddit")
    timeNow = datetime.now(timezone.utc)
    oneHour = timeNow + timedelta(hours=-2)
    reddit = asyncpraw.Reddit(
        client_id=ID,
        client_secret=SECRET,
        password=PASSWORD,
        user_agent=USER_AGENT,
        username=NAME,
    )
    hellscubeSubreddit = cast(
        asyncpraw.reddit.Subreddit, await reddit.subreddit("HellsCube")
    )

    redditChannel = cast(TextChannel, bot.get_channel(hc_constants.REDDIT_CHANNEL))
    messagesInLastDay = [mess async for mess in redditChannel.history(after=oneHour)]

    async for submission in hellscubeSubreddit.search('flair:"Card Idea" OR flair:"HellsCube Submission"', time_filter="hour"):  # type: ignore
        #  print(messagesInLastDay.__len__(), submission.permalink)
        alreadyPosted = False
        for discordMessage in messagesInLastDay:
            if submission.permalink in discordMessage.content:
                alreadyPosted = True
                break

        if not alreadyPosted:
            await redditChannel.send(
                content=f"reddit says: https://reddit.com{submission.permalink}"
            )
    await reddit.close()
    return
