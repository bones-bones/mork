from datetime import datetime, timezone, timedelta


from typing import cast

from acceptCard import acceptCard


from getters import (
    getSubmissionDiscussionChannel,
    getSubmissionsChannel,
    getVetoChannel,
)
from handleVetoPost import handleVetoPost
import hc_constants
from discord.ext import commands
from discord import Guild, Member, Message, TextChannel

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
        messageEntry = cast(Message, messageEntry)
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

            positiveMargin = upCount - downCount
            if positiveMargin >= (
                hc_constants.SUBMISSIONS_THRESHOLD
            ) and messageAge >= timedelta(days=1):
                guild = cast(Guild, messageEntry.guild)
                # This case here is to stop prevent spamming. If there is a single downvote, do a check to see if an admin has voted
                if downCount == 1:
                    prettyValid = False
                    async for user in upvote.users():
                        if guild.get_member(user.id) is not None and is_admin(
                            cast(Member, user)
                        ):
                            prettyValid = True

                    if not prettyValid:
                        user = await bot.fetch_user(
                            hc_constants.LLLLLL
                        )  # If a message would be accepted, but there's only a single downvote, need sixel to add another downvote
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

                # The spooky block is to determine if cards should automatically go to the graveyard channel
                tombstone = get(messageEntry.reactions, emoji=hc_constants.TOMBSTONE)
                if tombstone:
                    spooky = False
                    async for user in tombstone.users():
                        if guild.get_member(user.id) is not None and (
                            is_admin(cast(Member, user)) or is_mork(user.id)
                        ):
                            spooky = True
                    if spooky:
                        dbname = ""
                        card_author = ""
                        if (
                            len(accepted_message_no_mentions)
                        ) == 0 or "by " not in accepted_message_no_mentions:
                            ...  # This is really the case of setting both to "", but due to scoping i got lazy
                        elif accepted_message_no_mentions[0:3] == "by ":
                            card_author = str(
                                (accepted_message_no_mentions.split("by "))[1]
                            )
                        else:
                            messageChunks = accepted_message_no_mentions.split(" by ")
                            firstPart = messageChunks[0]
                            secondPart = "".join(messageChunks[1:])

                            dbname = str(firstPart)
                            card_author = str(secondPart)
                        resolvedName = (
                            dbname if dbname != "" else "Crazy card with no name"
                        )
                        resolvedAuthor = (
                            card_author if card_author != "" else "no author"
                        )
                        cardMessage = f"**{resolvedName}** by **{resolvedAuthor}**"
                        copy2 = await messageEntry.attachments[0].to_file()
                        await acceptCard(
                            bot=bot,
                            channelIdForCard=hc_constants.GRAVEYARD_CARD_LIST,
                            setId="HCV",
                            file=copy2,
                            cardMessage=cardMessage,
                            authorName=card_author,
                            cardName=dbname,
                            errata=False,
                        )
                        await messageEntry.delete()
                        continue  # and then stop processing the card

                vetoEntry = await vetoChannel.send(
                    content=accepted_message_no_mentions, file=copy
                )

                await handleVetoPost(message=vetoEntry, bot=bot, veto_council=None)

                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, datetime: {f'<t:{int(messageEntry.created_at.timestamp())}:f>'}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content=acceptContent, file=file)
                await logChannel.send(content=logContent, file=copy2)

                yesUsers = "voted yes:\n"
                yesUserArray: list[str] = []
                async for user in upvote.users():
                    yesUserArray.append(user.name)
                yesUsers += ", ".join(yesUserArray)

                for i in range(0, yesUsers.__len__(), hc_constants.LITERALLY_1984):
                    await logChannel.send(
                        content=yesUsers[i : i + hc_constants.LITERALLY_1984]
                    )

                await messageEntry.delete()
                continue
            elif positiveMargin >= (
                hc_constants.SUBMISSIONS_THRESHOLD - 5
            ) and messageAge >= timedelta(days=6):
                has_mork_marked_it = False
                timeReacts = get(messageEntry.reactions, emoji="🕛")
                if timeReacts:
                    async for user in timeReacts.users():
                        if is_mork(user.id):
                            has_mork_marked_it = True
                if not has_mork_marked_it:
                    await acceptedChannel.send(
                        f"{messageEntry.content} is nearing the end... perhaps it deserves further consideration {messageEntry.jump_url}"
                    )
                    await messageEntry.add_reaction("🕛")

    print("------done checking submissions-----")
