from datetime import datetime, timezone, timedelta


import os
import re
from typing import cast

from shared_vars import googleClient

from getters import (
    getTokenListChannel,
    getTokenSubmissionChannel,
)
import hc_constants
from discord.ext import commands
from discord import Message

from discord.utils import get

from is_mork import getDriveUrl, is_mork, uploadToDrive

tokenUnapproved = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet(
    hc_constants.TOKEN_UNAPPROVED
)


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
            or "@here" in messageEntry.content
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
