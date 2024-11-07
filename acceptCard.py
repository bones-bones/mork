import io
import os
import re
from typing import cast
import discord
import hc_constants
from is_mork import getDriveUrl, uploadToDrive
from shared_vars import googleClient
from discord.ext import commands


from reddit_functions import postToReddit

cardSheetUnapproved = googleClient.open_by_key(
    hc_constants.HELLSCUBE_DATABASE
).worksheet("Database (Unapproved)")


async def acceptCard(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
    errata: bool = False
):
    extension = re.search("\.([^.]*)$", file.filename)
    fileType = (
        extension.group() if extension else ".png"
    )  # just guess that the file is a png
    new_file_name = f'{cardName.replace("/", "|")}{fileType}'
    image_path = f"tempImages/{new_file_name}"

    file_data = file.fp.read()
    file_copy_for_cardlist = discord.File(
        fp=io.BytesIO(file_data), filename=new_file_name
    )

    cardListChannel = cast(
        discord.TextChannel, bot.get_channel(hc_constants.SIX_ONE_CARD_LIST)
    )
    await cardListChannel.send(file=file_copy_for_cardlist, content=cardMessage)

    with open(image_path, "wb") as out:
        out.write(file_data)
    if not errata:
        try:
            await postToReddit(
                image_path=image_path,
                title=f"{cardMessage.replace('**', '')} was accepted!",
                flair=hc_constants.ACCEPTED_FLAIR,
            )
        except Exception as e:
            print("tried to post to reddit", e)

    google_drive_file_id = uploadToDrive(image_path)

    os.remove(image_path)

    imageUrl = getDriveUrl(google_drive_file_id)

    allCardNames = cardSheetUnapproved.col_values(1)

    newCard = True
    if cardName in allCardNames and cardName != "":
        dbRowIndex = allCardNames.index(cardName) + 1
        newCard = False
    else:
        dbRowIndex = len(allCardNames) + 1
        if cardName == "":
            cardName = "NO NAME"

    cardSheetUnapproved.update_cell(dbRowIndex, 2, imageUrl)

    if newCard:
        cardSheetUnapproved.update_cell(dbRowIndex, 1, cardName)
        cardSheetUnapproved.update_cell(dbRowIndex, 3, authorName)
