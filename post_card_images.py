import io
import re

import aiohttp
import discord
from discord.message import Message

import hc_constants
from hellfall_fetcher import getMultipleFuzzyCards
from image_response_filename import filename_from_image_response

FISH_FROM_GO_FISH_SEARCH = "the fish from go fish"

nameRegex = re.compile(r"{{([^}]+)}}")


async def post_card_images(message: Message):
    print(message.author)
    message_text: list[str] = nameRegex.findall(message.content)
    if len(message_text) > 10:
        await message.reply(
            "Don't call more than 10 cards per message, final warning, keep trying and you get blacklisted from the bot."
        )
        return
    if message.author.id == hc_constants.LLLLLL:
        for i, name in enumerate(message_text):
            if name.strip() == "fish":
                message_text[i] = FISH_FROM_GO_FISH_SEARCH
    requestedCards = await getMultipleFuzzyCards(message_text)
    for post in requestedCards:
        if post == "":
            await message.reply("No Match Found!", mention_author=False)
        else:
            print(post.image)
            await send_image_reply(
                url=post.image,
                cardname=post.name,
                message=message,
                text=None,
            )


async def send_image_reply(
    url: str, message: Message, cardname: str | None = None, text: str | None = None
):
    headers = {"User-Agent": hc_constants.USER_AGENT}
    async with (
        aiohttp.ClientSession(headers=headers) as session,
        session.get(url) as resp,
    ):
        if resp.status != 200:
            await message.reply(
                f"Something went wrong while getting the link for {cardname or 'the card'}. Wait for llllll or klunker to fix it."
            )
            await session.close()
            return
        data_bytes = await resp.read()
        parsedFilename = filename_from_image_response(
            content_disposition=resp.headers.get("Content-Disposition"),
            url=str(resp.url),
            content_type=resp.headers.get("Content-Type"),
            fallback_name=cardname or "image",
            body=data_bytes,
        )

        data = io.BytesIO(data_bytes)
        sentMessage = await message.reply(
            content=text,
            file=discord.File(data, parsedFilename),
            mention_author=False,
        )
        await sentMessage.add_reaction(hc_constants.DELETE)
        await session.close()
