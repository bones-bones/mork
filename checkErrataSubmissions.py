

import hc_constants
from datetime import datetime, timezone, timedelta
from discord.utils import get
from discord.ext import commands

async def checkErrataSubmissions(bot:commands.Bot):
    subChannel = bot.get_channel(hc_constants.FOUR_ONE_ERRATA_SUBMISSIONS)
    acceptedChannel = bot.get_channel(hc_constants.FOUR_ONE_ERRATA_ACCEPTED)
    timeNow = datetime.now(timezone.utc)
    oneWeek = timeNow + timedelta(weeks = -2)
    messages = subChannel.history(after = oneWeek, limit = None)
    if messages is None:
        return
    messages = [message async for message in messages]
    for i in range(len(messages)):
        if "@everyone" in messages[i].content:
            continue
        if get(messages[i].reactions, emoji = hc_constants.ACCEPT):
            continue
        upvote = get(messages[i].reactions, emoji = hc_constants.VOTE_UP)
        downvote = get(messages[i].reactions, emoji = hc_constants.VOTE_DOWN)

        if upvote and downvote:
            up_count = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messages[i].created_at
            if (up_count - downCount) > 14 and messageAge >= timedelta(days=1):
                acceptContent = messages[i].content
                await acceptedChannel.send(content = acceptContent)
                await messages[i].add_reaction(hc_constants.ACCEPT)
    print("------done checking errata submissions-----")
