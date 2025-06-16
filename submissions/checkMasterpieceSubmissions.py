from datetime import datetime, timezone, timedelta


from typing import cast

from getters import (
    getSubmissionDiscussionChannel,
    getVetoChannel,
)
from handleVetoPost import handleVetoPost
import hc_constants
from discord.ext import commands
from discord import Member, TextChannel

from discord.utils import get

from is_admin import is_admin
from is_mork import is_mork


async def checkMasterpieceSubmissions(bot: commands.Bot):
    subChannel = cast(TextChannel, bot.get_channel(hc_constants.MASTERPIECE_CHANNEL))
    vetoChannel = getVetoChannel(bot)
    acceptedChannel = getSubmissionDiscussionChannel(bot)
    logChannel = cast(
        TextChannel, bot.get_channel(hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL)
    )
    timeNow = datetime.now(timezone.utc)
    oneWeek = timeNow + timedelta(weeks=-2)
    messages = subChannel.history(after=oneWeek, limit=None)
    if messages is None:
        return

    messages = [message async for message in messages]
    for messageEntry in messages:

        if (
            "@everyone" in messageEntry.content
            or "@here" in messageEntry.content
            or len(messageEntry.attachments) == 0
            or not is_mork(messageEntry.author.id)
        ):
            continue  # just ignore these
        upvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at
            # card was voted in
            if (
                upCount - downCount
            ) >= hc_constants.MASTERPIECE_THRESHOLD and messageAge >= timedelta(days=1):

                if downCount == 1:
                    prettyValid = False
                    async for user in upvote.users():
                        if is_admin(cast(Member, user)):
                            prettyValid = True
                    if not prettyValid:
                        user = await bot.fetch_user(
                            hc_constants.LLLLLL
                        )  # If a message would be accepted, but there's only a single downvote, need llllll to add another downvote
                        await user.send("Verify " + messageEntry.jump_url)
                        continue
                file = await messageEntry.attachments[0].to_file()
                acceptContent = messageEntry.content + " was accepted"
                accepted_message_no_mentions = messageEntry.content
                for index, mentionEntry in enumerate(messageEntry.raw_mentions):
                    accepted_message_no_mentions = accepted_message_no_mentions.replace(
                        f"<@{str(mentionEntry)}>", messageEntry.mentions[index].name
                    )

                copy = await messageEntry.attachments[0].to_file()
                vetoEntry = await vetoChannel.send(
                    content="HC7: " + accepted_message_no_mentions, file=copy
                )

                await handleVetoPost(vetoEntry, bot, None)

                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content=acceptContent)
                await acceptedChannel.send(content="", file=file)
                await logChannel.send(content=logContent, file=copy2)
                await messageEntry.delete()
                continue
            elif (upCount - downCount) >= (
                hc_constants.MASTERPIECE_THRESHOLD - 5
            ) and messageAge >= timedelta(days=13):
                hasMork = False
                timeReacts = get(messageEntry.reactions, emoji="🕛")
                if timeReacts:
                    async for user in timeReacts.users():
                        if is_mork(user.id):
                            hasMork = True
                if not hasMork:
                    await acceptedChannel.send(
                        f"{messageEntry.content} is nearing the end... perhaps it deserves further consideration {messageEntry.jump_url}"
                    )
                    await messageEntry.add_reaction("🕛")
    print("------done checking masterpiece submissions-----")
