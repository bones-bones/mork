import io
import os
import re
from typing import cast
import discord
import hc_constants
from is_mork import getDriveUrl, uploadToDrive
from shared_vars import googleClient
from discord.ext import commands


from reddit_functions import post_to_reddit

cardSheetUnapproved = googleClient.open_by_key(
    hc_constants.HELLSCUBE_DATABASE
).worksheet(hc_constants.DATABASE_UNAPPROVED)


async def acceptCard(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
    channelIdForCard: int = hc_constants.HC_POSSE_CARD_LIST,
    setId: str = "HC7.1",
    errata: bool = False,
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

    cardListChannel = cast(discord.TextChannel, bot.get_channel(channelIdForCard))
    await cardListChannel.send(file=file_copy_for_cardlist, content=cardMessage)

    with open(image_path, "wb") as out:
        out.write(file_data)
    if not errata:
        try:
            await post_to_reddit(
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
    if cardName != "" and cardName in allCardNames:
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
        cardSheetUnapproved.update_cell(dbRowIndex, 4, setId)
    return


async def acceptVetoCard(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
):
    extension = re.search("\\.([^.]*)$", file.filename)
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
    vetoCardListChannel = cast(
        discord.TextChannel, bot.get_channel(hc_constants.VETO_CARD_LIST)
    )

    with open(image_path, "wb") as out:
        out.write(file_data)

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
    cardSheetUnapproved.update_cell(dbRowIndex, 4, "HCV")

    if newCard:
        cardSheetUnapproved.update_cell(dbRowIndex, 1, cardName)
        cardSheetUnapproved.update_cell(dbRowIndex, 3, authorName)

    async for message in vetoCardListChannel.history(limit=None):
        if message.content == cardMessage:
            try:
                await message.delete()  # Delete message if it matches
                print(f"Deleted message: {message.content}")
            except discord.Forbidden:
                print("Bot lacks permissions to delete messages.")
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")

    async for message in cardListChannel.history(limit=None):
        if message.content == cardMessage:
            try:
                await message.delete()  # Delete message if it matches
                print(f"Deleted message: {message.content}")
            except discord.Forbidden:
                print("Bot lacks permissions to delete messages.")
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")

    await vetoCardListChannel.send(file=file_copy_for_cardlist, content=cardMessage)
