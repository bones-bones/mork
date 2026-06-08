import asyncio
import io
from datetime import datetime, timezone, timedelta


from typing import cast

from acceptCard import accept_card


from getters import (
    getSubmissionDiscussionChannel,
    getSubmissionsChannel,
    getVetoChannel,
)
from getCardMessage import parseCardNameAndAuthor
from handleVetoPost import handleVetoPost
import hc_constants
from discord.ext import commands
from discord import File, Guild, Member, Message, TextChannel

from discord.utils import get

from is_admin import is_admin
from is_mork import is_mork


async def checkSubmissions(bot: commands.Bot):
    print("checking submissions")
    subChannel = getSubmissionsChannel(bot)
    vetoChannel = getVetoChannel(bot)
    acceptedChannel = getSubmissionDiscussionChannel(bot)
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
        # Drastic measure: throttle hard to avoid Discord 429 rate limits
        await asyncio.sleep(1)
        messageEntry = cast(Message, messageEntry)

        # This block is to filter out non-card entiers in submissions
        if (
            "@everyone" in messageEntry.content
            or "@here" in messageEntry.content
            or len(messageEntry.attachments) == 0
            or not is_mork(messageEntry.author.id)
        ):
            continue

        upvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)

        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at

            positiveMargin = upCount - downCount
            if positiveMargin >= (
                hc_constants.SUBMISSIONS_THRESHOLD
            ) and messageAge >= timedelta(days=1):
                guild = cast(Guild, messageEntry.guild)
                await asyncio.sleep(1)
                upvoteUsers = [user async for user in upvote.users()]
                # This case here is to stop prevent spamming. If there is a single downvote, do a check to see if an admin has voted
                if downCount == 1:
                    prettyValid = False
                    for user in upvoteUsers:
                        if guild.get_member(user.id) is not None and is_admin(
                            cast(Member, user)
                        ):
                            prettyValid = True
                            break

                    if not prettyValid:
                        await asyncio.sleep(1)
                        user = await bot.fetch_user(
                            hc_constants.LLLLLL
                        )  # If a message would be accepted, but there's only a single downvote, need sixel to add another downvote
                        await asyncio.sleep(1)
                        await user.send("Verify " + messageEntry.jump_url)
                        continue
                attachment = messageEntry.attachments[0]
                attachment_data = await attachment.read()
                attachment_filename = attachment.filename
                if positiveMargin >= hc_constants.SUBMISSIONS_THRESHOLD * 2:
                    acceptContent = messageEntry.content + " has won hellscube!"
                else:
                    acceptContent = messageEntry.content + " was accepted"

                accepted_message_no_mentions = messageEntry.content
                for index, mentionEntry in enumerate(messageEntry.raw_mentions):
                    accepted_message_no_mentions = accepted_message_no_mentions.replace(
                        f"<@{str(mentionEntry)}>", messageEntry.mentions[index].name
                    )

                dbname, card_author = parseCardNameAndAuthor(
                    accepted_message_no_mentions
                )
                resolvedName = dbname if dbname != "" else "Crazy card with no name"
                print(f"Processing submission: {resolvedName}")

                # The spooky block is to determine if cards should automatically go to the graveyard channel
                tombstone = get(messageEntry.reactions, emoji=hc_constants.TOMBSTONE)
                if tombstone:
                    spooky = False
                    await asyncio.sleep(1)
                    async for user in tombstone.users():
                        if guild.get_member(user.id) is not None and (
                            is_admin(cast(Member, user)) or is_mork(user.id)
                        ):
                            spooky = True
                    if spooky:
                        resolvedAuthor = (
                            card_author if card_author != "" else "no author"
                        )
                        cardMessage = f"**{resolvedName}** by **{resolvedAuthor}**"
                        await asyncio.sleep(1)
                        await accept_card(
                            bot=bot,
                            channelIdForCard=hc_constants.GRAVEYARD_CARD_LIST,
                            setId="HCV",
                            file=File(
                                fp=io.BytesIO(attachment_data),
                                filename=attachment_filename,
                            ),
                            cardMessage=cardMessage,
                            authorName=card_author,
                            cardName=dbname,
                            errata=False,
                        )
                        await asyncio.sleep(1)
                        # If this submission was previously marked with a time reminder,
                        # delete the bot's reminder ping message in the submissions channel.
                        time_reacts = get(messageEntry.reactions, emoji="🕛")
                        if time_reacts:
                            await asyncio.sleep(1)
                            async for rem_msg in subChannel.history(limit=200):
                                if rem_msg.author == bot.user and messageEntry.jump_url in rem_msg.content:
                                    try:
                                        await asyncio.sleep(1)
                                        await rem_msg.delete()
                                    except Exception:
                                        pass

                        await messageEntry.delete()
                        continue  # and then stop processing the card

                await asyncio.sleep(1)
                vetoEntry = await vetoChannel.send(
                    content=accepted_message_no_mentions,
                    file=File(
                        fp=io.BytesIO(attachment_data),
                        filename=attachment_filename,
                    ),
                )

                await asyncio.sleep(1)
                await handleVetoPost(message=vetoEntry, bot=bot, veto_council=None)

                logContent = f"{acceptContent}, datetime: {f'<t:{int(messageEntry.created_at.timestamp())}:f>'}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await asyncio.sleep(1)
                await acceptedChannel.send(
                    content=acceptContent,
                    file=File(
                        fp=io.BytesIO(attachment_data),
                        filename=attachment_filename,
                    ),
                )
                await asyncio.sleep(1)
                await logChannel.send(
                    content=logContent,
                    file=File(
                        fp=io.BytesIO(attachment_data),
                        filename=attachment_filename,
                    ),
                )

                yesUsers = "voted yes:\n"
                yesUserArray: list[str] = [user.name for user in upvoteUsers]
                yesUsers += ", ".join(yesUserArray)

                await asyncio.sleep(1)
                await logChannel.send(content=yesUsers[: hc_constants.LITERALLY_1984])

                await asyncio.sleep(1)
                # If this submission was previously marked with a time reminder,
                # delete the bot's reminder ping message in the submissions channel.
                time_reacts = get(messageEntry.reactions, emoji="🕛")
                if time_reacts:
                    await asyncio.sleep(1)
                    async for rem_msg in subChannel.history(limit=200):
                        if rem_msg.author == bot.user and messageEntry.jump_url in rem_msg.content:
                            try:
                                await asyncio.sleep(1)
                                await rem_msg.delete()
                            except Exception:
                                pass

                await messageEntry.delete()
                continue
            elif positiveMargin >= (
                hc_constants.SUBMISSIONS_THRESHOLD - 5
            ) and messageAge >= timedelta(days=5.5):
                has_mork_marked_it = False
                timeReacts = get(messageEntry.reactions, emoji="🕛")
                if timeReacts:
                    await asyncio.sleep(1)
                    async for user in timeReacts.users():
                        if is_mork(user.id):
                            has_mork_marked_it = True
                if not has_mork_marked_it:
                    await asyncio.sleep(1)
                    await subChannel.send(
                        f"## {messageEntry.content} is nearing the end... perhaps it deserves further consideration {messageEntry.jump_url}"
                    )
                    await asyncio.sleep(1)
                    await messageEntry.add_reaction("🕛")

    print("------done checking submissions-----")
