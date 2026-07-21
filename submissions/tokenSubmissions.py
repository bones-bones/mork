from datetime import datetime, timezone, timedelta


import base64
import os
import re
from typing import cast

from gspread import Cell

from shared_vars import googleClient

from getters import (
    getTokenListChannel,
    getTokenSubmissionChannel,
)
import hc_constants
from discord.ext import commands
from discord import Message

from discord.utils import get

from getCardMessage import parseCardNameAndAuthor
from gcs_card_images import upload_card_image
from is_mork import is_mork
from hellfall_postcard import (
    PostcardSyncError,
    rollback_postcard_write,
    sync_accepted_card,
)

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

    first_line = accepted_message_no_mentions.split("\n")[0]
    cardName, creator = parseCardNameAndAuthor(first_line)
    relatedCards = accepted_message_no_mentions.split("\n")[1]

    file = await message.attachments[0].to_file()
    copy = await message.attachments[0].to_file()

    extension = re.search("\.([^.]*)$", file.filename)
    fileType = (
        extension.group() if extension else ".png"
    )  # just guess that the file is a png
    new_file_name = f'{cardName.replace("/", "|")}{fileType}'

    image_path = f"tempImages/{new_file_name}"

    file_data = file.fp.read()
    image_base64 = base64.b64encode(file_data).decode("ascii")

    allCardNames = tokenUnapproved.col_values(1)

    matching_cards = [
        name
        for name in allCardNames
        if isinstance(name, str) and name.startswith(cardName)
    ]
    max_number = 0
    for card in matching_cards:
        # TODO: Use regex instead
        suffix = card[len(cardName) :]
        if suffix and suffix.isdigit():
            max_number = max(max_number, int(suffix))

    final_card_name = f"{cardName}{max_number + 1}"

    dbRowIndex = allCardNames.__len__() + 1

    postcard_write = None
    imageUrl: str | None = None
    try:
        try:
            postcard_write = await sync_accepted_card(
                name=final_card_name,
                image_base64=image_base64,
                creators=creator,
                set_id="HCT",
                hcid=final_card_name,
                kind="token",
                require_sync=True,
            )
            if postcard_write and postcard_write.image_url:
                imageUrl = postcard_write.image_url
        except PostcardSyncError as err:
            if str(err) != "invalid_body":
                raise
            postcard_write = None

        if not imageUrl:
            with open(image_path, "wb") as out:
                out.write(file_data)
            try:
                gcs_image_url = upload_card_image(
                    image_path, object_name=final_card_name
                )
                postcard_write = await sync_accepted_card(
                    name=final_card_name,
                    image=gcs_image_url,
                    creators=creator,
                    set_id="HCT",
                    hcid=final_card_name,
                    kind="token",
                    require_sync=True,
                )
                imageUrl = (
                    postcard_write.image_url
                    if postcard_write and postcard_write.image_url
                    else gcs_image_url
                )
            finally:
                if os.path.exists(image_path):
                    os.remove(image_path)

        if not imageUrl:
            raise PostcardSyncError("hellfall did not return imageUrl")

        tokenUnapproved.update_cells(
            [
                Cell(row=dbRowIndex, col=1, value=final_card_name),
                Cell(row=dbRowIndex, col=2, value=imageUrl),
                Cell(row=dbRowIndex, col=6, value=relatedCards),
                Cell(row=dbRowIndex, col=8, value=creator),
            ]
        )
        await tokenListChannel.send(
            content=cardName + " by " + creator + "\n" + relatedCards,
            file=copy,
        )
        await message.add_reaction(hc_constants.ACCEPT)

    except Exception:
        if postcard_write is not None:
            await rollback_postcard_write(postcard_write)
        raise
