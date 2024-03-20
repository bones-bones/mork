import os
import discord
import hc_constants
from is_mork import getDriveUrl, uploadToDrive
from shared_vars import googleClient
from discord.ext import commands


from reddit_functions import postToReddit

cardSheetUnapproved = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet("Kopie van Database")


async def acceptCard(bot:commands.Bot, cardMessage:str, file:discord.File, cardName:str, authorName:str):
    cardListChannel = bot.get_channel(hc_constants.FOUR_ONE_CARD_LIST_CHANNEL)
    await cardListChannel.send(content=cardMessage, file=file)

    image_path = f'tempImages/{file.filename}'

    with open(image_path, 'wb') as out: ## Open temporary file as bytes
        out.write(file.fp.read())  ## Read bytes into file

    try:
        await  postToReddit(
            title = f"{cardMessage} was accepted!",
            flair = hc_constants.ACCEPTED_FLAIR,
            image_path=image_path
        )
    except:
        ...

    google_drive_file_id = uploadToDrive(image_path)
    imageUrl = getDriveUrl(google_drive_file_id)
    os.remove(image_path)

    allCardNames = cardSheetUnapproved.col_values(1)

    newCard = True
    if cardName in allCardNames and cardName != "":
        dbRowIndex = allCardNames.index(cardName) + 1
        newCard = False
    else:
        dbRowIndex = len(allCardNames) + 1
        if cardName == "":
            cardName = "NO NAME"
    cardSheetUnapproved.update_cell(dbRowIndex, 4, imageUrl)
    if newCard:
        cardSheetUnapproved.update_cell(dbRowIndex, 1, cardName)
        cardSheetUnapproved.update_cell(dbRowIndex, 6, authorName)