import random
from datetime import UTC, datetime, timedelta
from random import randrange
from typing import Annotated, cast

import discord
from discord.ext import commands

import hc_constants
from database_cache.database import build_database
from hellfall_changesets import modifyTagWithServer
from hellfall_fetcher import (
    STILL_USING_CACHE,
    SearchCard,
    SearchResponse,
    getDatabaseCache,
    getExactCard,
    getFuzzyCard,
    getRandomFromServer,
    getSearchFromServer,
)
from post_card_images import send_single_image_reply
from shared_vars import googleClient, intents

databaseSheets = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)


notMagicCardSheet = databaseSheets.worksheet("NotMagic")

client = discord.Client(intents=intents)


def getUnapprovedCardSheet():
    return googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet(
        hc_constants.DATABASE_UNAPPROVED
    )


cleanText = Annotated[str, commands.clean_content(fix_channel_mentions=True)]


def fixClean(text: str | None):
    return None if text is None else text.lower()


class HellscubeDatabaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if STILL_USING_CACHE:
            build_database(await getDatabaseCache())

    @commands.command(aliases=["synccache"])
    async def syncDb(self, ctx: commands.Context):
        if ctx.author.id == hc_constants.LLLLLL:
            if STILL_USING_CACHE:
                build_database(await getDatabaseCache())
                await ctx.send("done")
            else:
                await ctx.send("cache is currently turned off")

    # okay not technically a DB command
    @commands.command()
    async def randomReject(self, ctx: commands.Context):
        """
        Returns a random card image from #submissions.
        Chooses a random date between the start of submissions and now, then gets history near that date.
        Filters out messages without attachments, then chooses a random message from that history.
        """
        subStart = datetime.strptime("5/13/2021 1:30 PM", "%m/%d/%Y %I:%M %p").astimezone(UTC)
        timeNow = datetime.now(UTC)
        timeNow = timeNow.replace(tzinfo=None)
        delta = timeNow - subStart
        intDelta = (delta.days * 24 * 60 * 60) + delta.seconds
        randomSecond = randrange(intDelta)
        randomDate = subStart + timedelta(seconds=randomSecond)
        subChannel = self.bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL)
        subHistory = cast(discord.TextChannel, subChannel).history(around=randomDate)
        subHistory = [message async for message in subHistory if message.attachments]
        randomNum = randrange(1, len(subHistory)) - 1
        file = await subHistory[randomNum].attachments[0].to_file()
        sentMessage = await ctx.reply(content="", file=file, mention_author=False)
        await sentMessage.add_reaction(hc_constants.DELETE)

    @commands.command()
    async def notMagic(self, ctx: commands.Context):
        """Returns a random card from #this-isnt-magic"""
        random_card = random.randint(2, len(notMagicCardSheet.col_values(1)))
        print(random_card)
        name = cast(str, notMagicCardSheet.col_values(1)[random_card])
        img = cast(str, notMagicCardSheet.col_values(2)[random_card])
        ruling = cast(str, notMagicCardSheet.col_values(4)[random_card])
        await send_single_image_reply(url=img, cardname=name, text=ruling, message=ctx.message)

    @commands.command(name="random")
    async def randomCard(self, ctx: commands.Context, *, query: cleanText | None = None):
        """
        Returns a random card image from the database.
        Can accept a search query to narrow the search.
        """
        response = await getRandomFromServer(query)
        await send_single_image_reply(
            url=response.image, cardname=response.name, message=ctx.message, text=None
        )

    @commands.command(aliases=["creators"])
    async def creator(self, channel: discord.abc.Messageable, *, cardName: cleanText | None = None):
        name = fixClean(cardName)
        card = await getFuzzyCard(name)
        message = "something went wrong!"
        if not card:
            await channel.send(message)
            return
        message = f"{card.name} created by: {', '.join(card.creators)}"
        await channel.send(message)

    @commands.command(aliases=["ruling"])
    async def rulings(self, channel: discord.abc.Messageable, *, cardName: cleanText | None = None):
        """
        Returns the rulings for a given card.
        """
        name = fixClean(cardName)
        card = await getFuzzyCard(name)
        message = "something went wrong!"
        if not card:
            await channel.send(message)
            return
        name = card.name
        rulings = card.rulings
        if not rulings:
            message = f"There are no rulings for {name}"
        else:
            rulingsList = rulings.split("\\\\\\")
            ruling_blocks = "".join(f"\n```{r}```" for r in rulingsList)
            message = f"rulings for {name}:{ruling_blocks}"
        await channel.send(message)

    @commands.command(rest_is_raw=True)
    async def judgement(self, ctx: commands.Context, *, args: str):
        """
        Command for judges to run to add rulings to a card
        """
        if ctx.channel.id != hc_constants.JUDGES_TOWER:
            await ctx.send("Only allowed in the judge's tower")
            return

        ruling = ("\n".join(args.split("\n")[1:])).strip()
        cardName = args.split("\n")[0].strip()
        response = await getExactCard(cardName)
        message = "something went wrong!"
        if not response:
            await ctx.send(message)
            return

        cardSheetUnapproved = getUnapprovedCardSheet()
        cell = cardSheetUnapproved.find(response.hcid, in_column=1)
        if not cell:
            await ctx.send("Unable to find the card... this shouldn't happen")
            return
        currentRuling = cardSheetUnapproved.cell(cell.row, 8)

        prefix = f"{currentRuling}\n" if currentRuling != "" else ""
        newRuling = (
            f"{prefix}{ruling}- {ctx.author.name} {datetime.now(UTC).strftime('%Y-%m-%d')}"
        )
        cardSheetUnapproved.update_cell(
            cell.row,
            8,
            newRuling,
        )

        await ctx.send(f"ruling updated to:\n{newRuling}")

    @commands.command(rest_is_raw=True, aliases=["addtag"])
    async def tag(self, ctx: commands.Context, *, args: cleanText):
        """Adds a tag. Uses the same process as on hellfall."""
        cardName = args.split("\n")[0].strip()
        splitLines = args.split("\n")
        if len(splitLines) != 2:
            await ctx.send("seems like you're missing a line break or have an extra one")
            return

        tag = splitLines[1].strip()

        if " " in tag:
            await ctx.send('no spaces allowed, use "-"')
            return

        message = await modifyTagWithServer(cardName, tag, "add")

        await ctx.send(message)

    @commands.command(rest_is_raw=True)
    async def removetag(self, ctx: commands.Context, *, args: cleanText):
        """Removes a tag. Uses the same process as on hellfall."""
        cardName = args.split("\n")[0].strip()
        splitLines = args.split("\n")
        if len(splitLines) != 2:
            await ctx.send("seems like you're missing a line break or have an extra one")
            return

        tag = splitLines[1].strip()

        message = await modifyTagWithServer(cardName, tag, "delete")

        await ctx.send(message)

    @commands.command()
    async def info(self, channel: discord.abc.Messageable, *, cardName: cleanText):
        name = fixClean(cardName)
        card = await getFuzzyCard(name)
        message = "something went wrong!"
        if not card:
            await channel.send(message)
            return
        message = getInfo(card)
        await channel.send(message)

    @commands.command()
    async def search(self, ctx: commands.Context, *, query: cleanText | None = None):
        if not query:
            await ctx.send("You need to include a query.")
            return
        response = await getSearchFromServer(query)

        if response.total_cards > 100:
            await ctx.send(
                f"There were {response.total_cards} results you fucking moron. Go use hellfall or something."
            )
            return

        message = formatSearchResults(response)
        n = 2000
        messages = [message[i : i + n] for i in range(0, len(message), n)]
        for msg in messages:
            await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(HellscubeDatabaseCog(bot))


def formatSearchResults(response: SearchResponse):
    returnString = response.details
    if response.warnings:
        for warning in response.warnings:
            returnString += f"\n{warning}"
    for card in response.data:
        returnString += f"\n{card.name} ({card.set.replace('_', '.')}) {card.collector_number}"
    return returnString


def getInfo(card: SearchCard):
    if card.oracle_id == "f90c6ef4-a631-49fd-b191-6e004b59a570":
        return "no card found"
    lines: list[str] = [
        f"id: {card.hcid}",
        f"creator{'' if len(card.creators) == 1 else 's'}: {', '.join(card.creators)}",
        f"set: {card.set.replace('_', '.')} #{card.collector_number} (AO: ${card.accepted_order})",
    ]
    for format, legality in card.legalities.items():
        lines.append(f"{format}: {legality}")

    if card.artists:
        lines.append(f"artist{'' if len(card.artists) == 1 else 's'}: {', '.join(card.artists)}")
    if card.base_tags:
        lines.append(f"tags: {', '.join(card.base_tags)}")
    if card.rulings:
        lines.append(f"rulings: \n{card.rulings}")
    return "\n".join(lines)
