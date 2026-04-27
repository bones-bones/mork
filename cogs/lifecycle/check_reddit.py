import os
from datetime import datetime, timezone, timedelta
from typing import cast

import asyncpraw
from discord import TextChannel
from discord.ext import commands
from dotenv import load_dotenv

import hc_constants

load_dotenv()

ID = os.environ["REDDIT_ID"]
SECRET = os.environ["REDDIT_SECRET"]
PASSWORD = os.environ["REDDIT_PASSWORD"]
USER_AGENT = os.environ["REDDIT_USER_AGENT"]
NAME = os.environ["REDDIT_NAME"]


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

    async for submission in hellscubeSubreddit.search('flair:"Card Idea" OR flair:"HellsCube Submission" OR flair:"Brainstorming"', time_filter="hour"):  # type: ignore
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
