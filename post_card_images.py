import io
import re
from collections.abc import Sequence

import aiohttp
import discord
from discord.message import Message

import hc_constants
from database_cache.database import SearchCard
from hellfall_fetcher import getMultipleFuzzyCards
from image_response_filename import filename_from_image_response

FISH_FROM_GO_FISH_SEARCH = "the fish from go fish"

nameRegex = re.compile(r"{{([^}]+)}}")


async def send_single_image_reply(
    message: Message, url: str, cardname: str | None = None, text: str | None = None
):
    """Sends an images in a reply."""
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


async def send_multiple_image_reply(
    message: Message, image_data: Sequence[str | tuple[str, str]], text: str | None = None
):
    """Sends multiple images in a reply. `image_data` should be a list of urls or url, cardname tuples."""
    headers = {"User-Agent": hc_constants.USER_AGENT}
    files: list[discord.File] = []
    for i, image in enumerate(image_data):
        url = image if isinstance(image, str) else image[0]
        cardname = None if isinstance(image, str) else image[1]
        async with (
            aiohttp.ClientSession(headers=headers) as session,
            session.get(url) as resp,
        ):
            if resp.status != 200:
                continue
            data_bytes = await resp.read()
            parsedFilename = filename_from_image_response(
                content_disposition=resp.headers.get("Content-Disposition"),
                url=str(resp.url),
                content_type=resp.headers.get("Content-Type"),
                fallback_name=cardname or f"image-{i}",
                body=data_bytes,
            )

            data = io.BytesIO(data_bytes)
            files.append(discord.File(data, parsedFilename))
            await session.close()
    if not files:
        await message.reply(
            "Something went wrong while getting all files. Wait for llllll or klunker to fix it."
        )
        return
    sentMessage = await message.reply(
        content=text,
        files=files,
        mention_author=False,
    )
    await sentMessage.add_reaction(hc_constants.DELETE)


async def send_single_card_reply(message: Message, card: SearchCard):
    await send_single_image_reply(message, card.image, card.name)


async def send_multiple_card_reply(message: Message, cards: list[SearchCard]):
    await send_multiple_image_reply(message, [(card.image, card.name) for card in cards])


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
    if not requestedCards:
        await message.reply("No Matches Found!", mention_author=False)
    await send_multiple_card_reply(message, requestedCards)
