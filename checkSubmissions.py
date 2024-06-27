from datetime import datetime, timezone, timedelta
from typing import cast

import discord
from handleVetoPost import handleVetoPost
import hc_constants
from discord.ext import commands
from discord import Emoji, Guild, Member, Message, Role, TextChannel

from discord.utils import get

from is_admin import is_admin
from is_mork import is_mork


async def checkSubmissions(bot: commands.Bot):
    subChannel = cast(TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))
    vetoChannel = cast(TextChannel, bot.get_channel(hc_constants.VETO_CHANNEL))
    acceptedChannel = cast(
        TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL)
    )
    logChannel = cast(
        TextChannel, bot.get_channel(hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL)
    )
    timeNow = datetime.now(timezone.utc)
    oneWeek = timeNow + timedelta(weeks=-1)
    messages = subChannel.history(after=oneWeek, limit=None)
    if messages is None:
        return

    messages = [message async for message in messages]
    for messageEntry in messages:
        messageEntry = cast(Message, messageEntry)
        if "@everyone" in messageEntry.content:
            continue  # just ignore these
        upvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at

            positiveMargin = upCount - downCount
            if (
                positiveMargin >= 30
                and len(messageEntry.attachments) > 0
                and messageAge >= timedelta(days=1)
                and is_mork(messageEntry.author.id)
            ):
                # This case here is to stop prevent spamming. If there is a single downvote, do a check to see if an admin has voted
                if downCount == 1:
                    guild = cast(Guild, messageEntry.guild)
                    prettyValid = False
                    async for user in upvote.users():
                        if guild.get_member(user.id) is not None and is_admin(
                            cast(Member, user)
                        ):
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
                    content=accepted_message_no_mentions, file=copy
                )

                await handleVetoPost(message=vetoEntry, bot=bot)

                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content=acceptContent)
                await acceptedChannel.send(content="", file=file)
                await logChannel.send(content=logContent, file=copy2)

                await messageEntry.delete()
                continue
            elif (
                positiveMargin >= 25
                and len(messageEntry.attachments) > 0
                and messageAge >= timedelta(days=1)
                and is_mork(messageEntry.author.id)
            ):
                ...

    print("------done checking submissions-----")


async def checkMasterpieceSubmissions(bot: commands.Bot):
    subChannel = cast(TextChannel, bot.get_channel(hc_constants.MASTERPIECE_CHANNEL))
    vetoChannel = cast(TextChannel, bot.get_channel(hc_constants.VETO_CHANNEL))
    acceptedChannel = cast(
        TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL)
    )
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

        if "@everyone" in messageEntry.content:
            continue  # just ignore these
        upvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at
            # card was voted in
            if (
                (upCount - downCount) >= 30
                and len(messageEntry.attachments) > 0
                and messageAge >= timedelta(days=1)
                and is_mork(messageEntry.author.id)
            ):

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
                    content="HC6: " + accepted_message_no_mentions, file=copy
                )

                await handleVetoPost(vetoEntry, bot)

                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content=acceptContent)
                await acceptedChannel.send(content="", file=file)
                await logChannel.send(content=logContent, file=copy2)
                await messageEntry.delete()
                continue
    print("------done checking submissions-----")
