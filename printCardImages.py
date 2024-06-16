import io
import re
import aiohttp
import discord
from cardNameRequest import cardNameRequest
import hc_constants
from shared_vars import allCards
from discord.message import Message


async def print_card_images(message: Message):
    message_text = message.content.lower().split("{{")[1:]
    for i in range(len(message_text)):  # TODO: maybe use a .map here
        message_text[i] = message_text[i].split("}}")[0]
    requestedCards = []
    if len(message_text) > 10 and message.author.id != hc_constants.CIRION:
        await message.reply(
            "Don't call more than 10 cards per message, final warning, keep trying and you get blacklisted from the bot. Blame dRafter for this if you're actually trying to use the bot."
        )
        return
    for cardName in message_text:
        requestedCards.append(cardNameRequest(cardName))
    for post in requestedCards:
        if post == "":
            await message.reply("No Match Found!", mention_author=False)
        else:
            await sendImageReply(
                allCards[post].getImg(), allCards[post].getName(), message
            )


async def sendImageReply(url: str, cardname: str, message: Message):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await message.reply(
                    "Something went wrong while getting the link for "
                    + cardname
                    + ". Wait for @llllll to fix it."
                )
                return
            # currently extraFilename looks like inline;filename="                                Skald.png"
            extraFilename = resp.headers.get("Content-Disposition")
            parsedFilename = re.findall('inline;filename="(.*)"', str(extraFilename))[0]
            data = io.BytesIO(await resp.read())
            sentMessage = await message.reply(
                file=discord.File(data, parsedFilename), mention_author=False
            )
            await sentMessage.add_reaction(hc_constants.DELETE)
            await session.close()
