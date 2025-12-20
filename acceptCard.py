import io
import os
import re
from typing import cast
import discord
from gspread import Cell
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
    setId: str = "HCJ",
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
        ...
        # try:
        #     await post_to_reddit(
        #         image_path=image_path,
        #         title=f"{cardMessage.replace('**', '')} was accepted!",
        #         flair=hc_constants.ACCEPTED_FLAIR,
        #     )
        # except Exception as e:
        #     print("tried to post to reddit", e)

    allCards = cardSheetUnapproved.get("A:D")
    index = [
        i
        for i in range(len(allCards))
        if allCards[i][0] == cardName and allCards[i][3] == setId
    ]

    newCard = True
    image_id_to_update = None
    # At least on match was found, and the name isn't blank. There really shouldn't be any nameless cards though cause it breaks
    if cardName != "" and index.__len__() > 0:
        dbRowIndex = index[0] + 1
        newCard = False
        image_id_to_update = allCards[index[0]][1].removeprefix(
            "https://lh3.googleusercontent.com/d/"
        )
    else:
        dbRowIndex = len(allCards) + 1
        if cardName == "":
            cardName = "NO NAME"

    google_drive_file_id = uploadToDrive(image_path, image_id_to_update)

    os.remove(image_path)

    imageUrl = getDriveUrl(google_drive_file_id)

    cardSheetUnapproved.update_cell(dbRowIndex, 2, imageUrl)

    if newCard:
        cardSheetUnapproved.update_cells(
            [
                Cell(row=dbRowIndex, col=1, value=cardName),
                Cell(row=dbRowIndex, col=3, value=authorName),
                Cell(row=dbRowIndex, col=4, value=setId),
            ]
        )


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

    allCards = cardSheetUnapproved.get("A:D")
    index = [
        i
        for i in range(len(allCards))
        if allCards[i][0] == cardName and allCards[i][3] == "HCV"
    ]

    newCard = True
    image_id_to_update = None
    # At least on match was found, and the name isn't blank
    if cardName != "" and index.__len__() > 0:
        dbRowIndex = index[0] + 1
        newCard = False
        image_id_to_update = allCards[index[0]][1].removeprefix(
            "https://lh3.googleusercontent.com/d/"
        )
    else:
        dbRowIndex = len(allCards) + 1
        if cardName == "":
            cardName = "NO NAME"

    google_drive_file_id = uploadToDrive(image_path, image_id_to_update)

    os.remove(image_path)

    imageUrl = getDriveUrl(google_drive_file_id)

    cardSheetUnapproved.update_cells(
        [
            Cell(row=dbRowIndex, col=2, value=imageUrl),
            Cell(row=dbRowIndex, col=4, value="HCV"),
        ]
    )

    if newCard:
        cardSheetUnapproved.update_cells(
            [
                Cell(row=dbRowIndex, col=1, value=cardName),
                Cell(row=dbRowIndex, col=3, value=authorName),
            ]
        )

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
