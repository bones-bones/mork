import io
import aiohttp
import discord
from cardNameRequest import cardNameRequest
import hc_constants
from image_response_filename import filename_from_image_response

FISH_FROM_GO_FISH_SEARCH = "the fish from go fish"
from shared_vars import allCards
from discord.message import Message


async def post_card_images(message: Message):
    print(message.author)
    message_text = message.content.lower().split("{{")[1:]
    for i in range(len(message_text)):  # TODO: maybe use a .map here
        message_text[i] = message_text[i].split("}}")[0]
    requestedCards = []
    if len(message_text) > 10:
        await message.reply(
            "Don't call more than 10 cards per message, final warning, keep trying and you get blacklisted from the bot."
        )
        return
    for cardName in message_text:
        search_text = cardName
        if (
            message.author.id == hc_constants.LLLLLL
            and cardName.strip() == "fish"
        ):
            search_text = FISH_FROM_GO_FISH_SEARCH
        requestedCards.append(cardNameRequest(search_text))
    for post in requestedCards:
        if post == "":
            await message.reply("No Match Found!", mention_author=False)
        else:
            print(allCards[post].getImg())
            await send_image_reply(
                url=allCards[post].getImg(),
                cardname=allCards[post].getName(),
                message=message,
                text=None,
            )


async def send_image_reply(url: str, cardname: str, text: str | None, message: Message):
    headers = {"User-Agent": hc_constants.USER_AGENT}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await message.reply(
                    "Something went wrong while getting the link for "
                    + cardname
                    + ". Wait for llllll or klunker to fix it."
                )
                await session.close()
                return
            parsedFilename = filename_from_image_response(
                content_disposition=resp.headers.get("Content-Disposition"),
                url=str(resp.url),
                content_type=resp.headers.get("Content-Type"),
                fallback_name=cardname,
            )

            data = io.BytesIO(await resp.read())
            sentMessage = await message.reply(
                content=text,
                file=discord.File(data, parsedFilename),
                mention_author=False,
            )
            await sentMessage.add_reaction(hc_constants.DELETE)
            await session.close()
