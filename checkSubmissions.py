from datetime import datetime, timezone, timedelta


import os
import re
from typing import cast

from acceptCard import acceptCard
from shared_vars import googleClient

from getters import (
    getGraveyardChannel,
    getSubmissionDiscussionChannel,
    getSubmissionsChannel,
    getTokenListChannel,
    getTokenSubmissionChannel,
    getVetoChannel,
)
from handleVetoPost import handleVetoPost
import hc_constants
from discord.ext import commands
from discord import Guild, Member, Message, TextChannel

from discord.utils import get

from is_admin import is_admin
from is_mork import getDriveUrl, is_mork, uploadToDrive

tokenUnapproved = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet(
    hc_constants.TOKEN_UNAPPROVED
)


async def checkSubmissions(bot: commands.Bot):
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
                        )
                        await messageEntry.delete()
                        continue  # and then stop processing the card

                vetoEntry = await vetoChannel.send(
                    content=accepted_message_no_mentions, file=copy
                )

                await handleVetoPost(message=vetoEntry, bot=bot)

                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content=acceptContent, file=file)
                await logChannel.send(content=logContent, file=copy2)

                yesUsers = "voted yes:\n"
                async for user in upvote.users():
                    yesUsers += ", " + user.name

                for i in range(0, yesUsers.__len__(), hc_constants.LITERALLY_1984):
                    await logChannel.send(
                        content=yesUsers[i : i + hc_constants.LITERALLY_1984]
                    )

                await messageEntry.delete()
                continue
            elif positiveMargin >= (
                hc_constants.SUBMISSIONS_THRESHOLD - 5
            ) and messageAge >= timedelta(days=6):
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

    print("------done checking submissions-----")


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
            if (upCount - downCount) >= 30 and messageAge >= timedelta(days=1):

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
            elif (upCount - downCount) >= 25 and messageAge >= timedelta(days=13):
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
    print("------done checking submissions-----")


async def checkTokenSubmissions(bot: commands.Bot):
    print("checking token submissions")
    subChannel = getTokenSubmissionChannel(bot)

    timeNow = datetime.now(timezone.utc)
    fourWeek = timeNow + timedelta(weeks=-2)
    messages = subChannel.history(after=fourWeek, limit=None)
    if messages is None:
        return

    messages = [message async for message in messages]
    for messageEntry in messages:
        messageEntry = cast(Message, messageEntry)
        if (
            "@everyone" in messageEntry.content
            or len(messageEntry.attachments) == 0
            or not is_mork(messageEntry.author.id)
        ):
            continue  # just ignore these
        acceptReact = get(messageEntry.reactions, emoji=hc_constants.ACCEPT)
        if acceptReact and acceptReact.count > 0:  # TODO: does this do anything?
            prettyValid = True
            async for user in acceptReact.users():
                if is_mork(user.id):
                    prettyValid = False
                    break
            if not prettyValid:
                continue

        upvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at

            positiveMargin = upCount - downCount
            if positiveMargin >= 5 and messageAge >= timedelta(days=1):
                await acceptTokenSubmission(bot=bot, message=messageEntry)

    print("------done checking submissions-----")


async def acceptTokenSubmission(bot: commands.Bot, message: Message):
    tokenListChannel = getTokenListChannel(bot)
    accepted_message_no_mentions = message.content

    for index, mentionEntry in enumerate(message.raw_mentions):
        accepted_message_no_mentions = accepted_message_no_mentions.replace(
            f"<@{str(mentionEntry)}>", message.mentions[index].name
        )

    cardName = accepted_message_no_mentions.split("\n")[0].split(" by ")[0]
    creator = accepted_message_no_mentions.split("\n")[0].split(" by ")[1]
    relatedCards = accepted_message_no_mentions.split("\n")[1]

    await message.add_reaction(hc_constants.ACCEPT)

    file = await message.attachments[0].to_file()
    copy = await message.attachments[0].to_file()

    await tokenListChannel.send(
        content=cardName + " by " + creator + "\n" + relatedCards,
        file=copy,
    )

    extension = re.search("\.([^.]*)$", file.filename)
    fileType = (
        extension.group() if extension else ".png"
    )  # just guess that the file is a png
    new_file_name = f'{cardName.replace("/", "|")}{fileType}'
    image_path = f"tempImages/{new_file_name}"

    file_data = file.fp.read()

    with open(image_path, "wb") as out:
        out.write(file_data)

    google_drive_file_id = uploadToDrive(image_path)

    os.remove(image_path)

    imageUrl = getDriveUrl(google_drive_file_id)

    allCardNames = tokenUnapproved.col_values(1)

    dbRowIndex = allCardNames.__len__() + 1

    tokenUnapproved.update_cell(dbRowIndex, 2, imageUrl)
    tokenUnapproved.update_cell(dbRowIndex, 8, creator)
    tokenUnapproved.update_cell(dbRowIndex, 1, cardName)
    tokenUnapproved.update_cell(dbRowIndex, 6, relatedCards)
