import asyncio
import json
import pprint as pp
import random
from datetime import UTC, datetime, timezone
from operator import itemgetter
from random import choice, choices, sample
from typing import Any, cast

import aiohttp
import discord
from discord.ext import commands
from discord.utils import get
from get_podcast_output import get_podcast_output
from specific_output import (
    balls_sheets,
    blueCards,
    channelFireball,
    femaleWarWalkers,
    grunch_flavor_text_options,
    grunch_rules_text_options,
    hell_locus_ids,
    iconicHands,
    obscureModes,
    possibleKeywords,
    quality_queries,
    roomDoors,
    scry_locus_ids,
    stormCards,
    wicky_sheets,
    wildMagic,
    wizardSpells,
)

import hc_constants
from hellfall_fetcher import getCardById, getMultipleCardsByIds, getMultipleRandomFromServer
from post_card_images import (
    send_multiple_card_reply,
    send_multiple_image_reply,
    send_single_card_reply,
    send_single_image_reply,
)

SCRYFALL_API_URL = "https://api.scryfall.com/cards"
# HELLFALL_API_URL = "https://hellfall.skeleton.club/api/cards"
SCRYFALL_RANDOM_API_URL = f"{SCRYFALL_API_URL}/random"
# HELLFALL_RANDOM_API_URL = f"{HELLFALL_API_URL}/random"


def scryfallApiForCard(id: str):
    return f"{SCRYFALL_API_URL}/{id}"


# def hellfallApiForCard(id: str):
#     return f"{HELLFALL_API_URL}/{id}"


# load json from scryfall
async def get_card_json(targetUrl: str, query: str = "") -> dict[str, Any]:
    """
    Get json of a card from scryfall. it's important to use the header so they know to block us lol.
    """
    headers = {"User-Agent": hc_constants.USER_AGENT}
    async with aiohttp.ClientSession().get(
        targetUrl, params={"q": query} if query else None, headers=headers
    ) as resp:
        return await resp.json()


def _get_scryfall_image(ob: dict[str, Any]) -> str | None:
    uris: dict[str, str] | None = ob.get("image_uris")
    if not uris:
        return
    normal = uris.get("normal")
    if not normal:
        return
    return normal[:-10]


async def get_image_from_json(json: dict[str, Any]):
    """get card image from scryfall json"""
    return _get_scryfall_image(json) or (
        _get_scryfall_image(json["card_faces"][0] if "card_faces" in json else {})
    )


async def send_image(ctx: commands.Context, url: str | None):
    """send card image to channel"""
    if not url:
        return
    await send_single_image_reply(ctx.message, url)


async def send_images(ctx: commands.Context, urls: list[str] | None):
    """send card images to channel"""
    if not urls:
        return
    await send_multiple_image_reply(ctx.message, urls)


async def send_drive_image(ctx: commands.Context, url: str):
    """send image from drive to channel"""
    if not url:
        return
    await send_single_image_reply(ctx.message, url, url.rsplit("/", 1)[-1] or "image")


async def fetchAndSendScryfallCard(ctx: commands.Context, url: str, query: str = ""):
    """helper function for fetching and sending scryfall cards from a URL"""
    cardJson = await get_card_json(url, query)
    try:
        await send_image(ctx, await get_image_from_json(cardJson))
    except Exception:
        pp.pprint(cardJson)


async def fetch_random_from_scryfall(ctx: commands.Context, query: str = "", num: int = 1):
    """helper function to fetch and send random card(s) from scryfall by query string"""
    cardJsons = [await get_card_json(SCRYFALL_RANDOM_API_URL, query) for i in range(num)]
    try:
        urls = [await get_image_from_json(cardJson) for cardJson in cardJsons]
        await send_images(ctx, [url for url in urls if url])
    except Exception:
        pp.pprint(cardJsons)


async def fetch_random_from_hellfall(ctx: commands.Context, query: str = "", num: int = 1):
    """helper function to fetch and send random card(s) from hellfall by query string"""
    response = await getMultipleRandomFromServer(query, num)
    await send_multiple_card_reply(ctx.message, response)


async def fetch_scryfall_by_id(ctx: commands.Context, id: str):
    """helper function to fetch and send card from scryfall by card id"""
    await fetchAndSendScryfallCard(ctx, scryfallApiForCard(id))


async def fetch_multiple_scryfall_by_id(ctx: commands.Context, ids: list[str]):
    """helper function to fetch and send multiple cards from hellfall by their ids"""
    cardJsons = [await get_card_json(scryfallApiForCard(uuid)) for uuid in ids]
    try:
        urls = [await get_image_from_json(cardJson) for cardJson in cardJsons]
        await send_images(ctx, [url for url in urls if url])
    except Exception:
        pp.pprint(cardJsons)


async def fetch_hellfall_by_id(ctx: commands.Context, id: str):
    """helper function to fetch and send card from hellfall by card id"""
    card = await getCardById(id)
    if card:
        await send_single_card_reply(ctx.message, card)


async def fetch_multiple_hellfall_by_id(ctx: commands.Context, ids: list[str]):
    """helper function to fetch and send multiple cards from hellfall by their ids"""
    cards = await getMultipleCardsByIds(ids)
    if cards:
        await send_multiple_card_reply(ctx.message, cards)


class SpecificCardsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def item(self, ctx: commands.Context):
        """for the card "Item Block" """
        await fetch_random_from_hellfall(ctx, '~"item block" unique:cards include:extras')

    @commands.command(aliases=["shellgame", "game"])
    async def shell(self, ctx: commands.Context):
        """for the card "Shell Game" """
        randomNumber = random.randint(0, 2)
        if randomNumber == 0:
            response = "Plains\nDraw 1 card."
        else:
            response = "Island\nDraw 3 cards."
        await ctx.send(response)

    @commands.command(aliases=["big", "money", "bigmoney"])
    async def whammy(self, ctx: commands.Context, number):
        """for the card "Big Money" """
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        ### heres some fun stuff if user inputs a negative number
        if number < 0:
            deck = [
                "Garfield of the Dead",
                "Swamp (the AB Dual)",
                "Swamp (the basic)",
                "[[SwAmp]]",
                "Tropical 2",
                "Clockwolf",
                "Force of Hill",
                "a Grunch creature token",
                "Plains",
            ]
            await ctx.send("Your hits:")
            whammy = False
            random.shuffle(deck)
            for i in range(0 - number):
                await ctx.send(deck[i % len(deck)])
                if deck[i] == "Plains":
                    whammy = True
                    break
                random.shuffle(deck)
            if not whammy:
                await ctx.send("You get " + str(number - 1) + " treasures!")
            else:
                await ctx.send("You get 1 treasure.")
        elif number < 6:
            deck = ["Mountain", "Forest", "Island", "Swamp", "Plains"]
            await ctx.send("Your hits:")
            whammy = False
            random.shuffle(deck)
            for i in range(number):
                await ctx.send(deck[i])
                if deck[i] == "Plains":
                    whammy = True
            if not whammy:
                await ctx.send("You get " + str(number + 1) + " treasures!")
            else:
                await ctx.send("You get 1 treasure.")
        else:
            await ctx.send("Please use a number under 6.")

    @commands.command()
    async def vow(self, ctx: commands.Context, cost):
        """for the card "BallsJr123's Druidic Vow" """
        try:
            await fetch_random_from_scryfall(ctx, f"mana:{cost}")
        except Exception:
            await ctx.send("Not a valid mana cost.")

    @commands.command(aliases=["stormstorm"])
    async def storm(self, ctx: commands.Context, number):
        """for the card "Stormstorm" """
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        if number < 11:
            await send_multiple_image_reply(ctx.message, choices(stormCards, k=number))
        else:
            await ctx.send("Please use 10 or lower.")

    @commands.command(aliases=["keyword", "warp"])
    async def keywords(self, ctx: commands.Context, number: int):
        """for the card "Keyword Warp" """
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        if 0 < number < 101:
            await ctx.send(", ".join(choices(possibleKeywords, k=number)))
        else:
            await ctx.send("Please use between 1 and 100, inclusive.")

    @commands.command(aliases=["path", "degen", "ptd"])
    async def degeneracy(self, ctx: commands.Context):
        """for the card "Path Towards Degeneracy" """
        await fetch_scryfall_by_id(ctx, choice(femaleWarWalkers))

    @commands.command(aliases=["blue"])
    async def bluecard(self, ctx: commands.Context):
        """for the card "A Blue Card" """
        await fetch_scryfall_by_id(ctx, choice(blueCards))

    @commands.command()
    async def wild(self, ctx: commands.Context):
        """for the card "Wild Magic <HC>" """
        randomNum = random.randint(1, 100)
        await ctx.send(f"{randomNum}: {wildMagic[randomNum - 1]}")

    @commands.command()
    async def triome(self, ctx: commands.Context):
        """for the card "Hell's Triome" """
        message = ""
        lands = ["Plains", "Mountain", "Forest", "Swamp", "Island"]
        random.shuffle(lands)
        for i in range(3):
            message += lands[i] + ", "
        await ctx.send(message)

    @commands.command()
    async def podcast(self, ctx: commands.Context, number):
        """for the card "Wrath of Pod" """
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        if number > 20:
            await ctx.send("Please type a number 20 or lower.")
            return

        output = await asyncio.to_thread(get_podcast_output, number)

        await ctx.send(output)

    @commands.command()
    async def pyrohyperspasm(self, ctx: commands.Context, number):
        """for the card "Pyrohyperspasm" """
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        if number > 400:
            await ctx.send("Please use 400 or lower.")
            return
        creatures: list[tuple[int, int]] = []
        counters = [(1, 0), (3, 2), (4, -1)]
        # repeat this whole thing `number` times
        for i in range(number):
            newCreatures = [(4, 2), (2, 3), (6, 1)]
            creatures.extend(newCreatures)  # add the new creatures
            to_kill = -1
            for counter in counters:
                i = random.randint(0, len(creatures) - 1)
                creatures[i] = (creatures[i][0] + counter[0], creatures[i][1] + counter[1])
                if counter[1] == -1:
                    to_kill = i
            # only check toughness after all counters placed and only for the one that got +4/-1
            if creatures[to_kill][1] < 1:
                creatures.pop(to_kill)
        creatures.sort(key=itemgetter(1), reverse=True)
        creatures.sort(key=itemgetter(0), reverse=True)
        result = ", ".join([f"{c[0]}/{c[1]}" for c in creatures])
        if len(result) > 4000:
            await ctx.send("Sorry, result string too LARGE.")
        elif len(result) > 2000:
            await ctx.send(result[:2000])
            await ctx.send(result[2001:])
        else:
            await ctx.send(result)
        totalPower = 0
        totalToughness = 0

        for p, t in creatures:
            totalPower += p
            totalToughness += t
        await ctx.send("Total (new) stats: (" + str(totalPower) + "/" + str(totalToughness) + ")")

    @commands.command(aliases=["puzzle", "box", "pbox", "yogg", "yoggsaron", "pb"])
    async def puzzlebox(self, ctx: commands.Context):
        """for the card "Puzzle Box of Yogg-Saron" """
        await fetch_random_from_scryfall(ctx, "t:instant or t:sorcery game:paper", 10)

    @commands.command()
    async def death(self, ctx: commands.Context):
        """for the card "Deathseeker" """
        await fetch_random_from_scryfall(ctx, 'o:"When ~ dies" t:creature game:paper', 2)

    @commands.command()
    async def life(self, ctx: commands.Context):
        """mirror of !death because why not"""
        await fetch_random_from_scryfall(ctx, 'o:"When ~ enters" t:creature game:paper', 2)

    @commands.command()
    async def attack(self, ctx: commands.Context):
        """another one (this time for attack triggers)"""
        await fetch_random_from_scryfall(ctx, 'o:"Whenever ~ attacks" t:creature game:paper', 2)

    @commands.command()
    async def broadcast(self, ctx: commands.Context):
        """for the card "Multiverse Broadcasting Station" """
        await fetch_random_from_scryfall(ctx, "-t:narset t:planeswalker r:u", 2)

    @commands.command(aliases=["gf", "chandra"])
    async def girlfriend(self, ctx: commands.Context):
        """for the card "Illusionary GF" """
        await fetch_random_from_scryfall(ctx, "t:chandra t:planeswalker")

    @commands.command()
    async def topper(self, ctx: commands.Context, amount):
        """for the card "Ballsjr's Ultimate Curvetopper" """
        if int(amount) > 10:
            await ctx.send("max is 10")
            return
        await fetch_random_from_scryfall(ctx, "mana>=X", int(amount))

    @commands.command()
    async def obscure(self, ctx: commands.Context):
        """for the card "Obscure Command" """
        await ctx.send("\n".join(choices(obscureModes, k=4)))

    @commands.command()
    async def weird(self, ctx: commands.Context):
        """for the card "Weird Elf" """
        modes = ["Colorless", "White", "Blue", "Black", "Red", "Green"]
        for _ in range(2):
            await ctx.send(random.choice(modes))

    @commands.command()
    async def cryptic(self, ctx: commands.Context):
        """for the card "Absurdly Cryptic Command" """
        await fetch_random_from_scryfall(ctx, "c=u t:instant", 4)

    @commands.command()
    async def whitecards(self, ctx: commands.Context):
        """for the card "We Need More White Cards" """
        await fetch_random_from_scryfall(ctx, "c=w", 3)

    @commands.command(aliases=["hugh", "human"])
    async def hughman(self, ctx: commands.Context):
        """for the card "Hugh Man, Human" """
        await fetch_random_from_scryfall(ctx, "t:human")

    @commands.command()
    async def growth(self, ctx: commands.Context):
        """for the card "Random Growth" """
        await fetch_random_from_scryfall(ctx, "t:land")

    @commands.command()
    async def ultimatum(self, ctx: commands.Context):
        """for the card "Ultimate Ultimatum" """
        await fetch_random_from_scryfall(ctx, "ultimatum -c:bant c=3")

    @commands.command()
    async def karakas(self, ctx: commands.Context):
        """for the card "Regal Karakas" """
        await fetch_random_from_scryfall(ctx, "t:creature t:legendary")

    @commands.command()
    async def sliver(self, ctx: commands.Context):
        """for the card "Pregnant Sliver" """
        await fetch_random_from_scryfall(ctx, "t:sliver")

    @commands.command()
    async def black6(self, ctx: commands.Context):
        """for the card "A Black 6 Drop Creature" """
        await fetch_random_from_scryfall(ctx, "t:creature c=b mv=6")

    @commands.command()
    async def reach(self, ctx: commands.Context):
        """for the card "Kodama's Reach but Kodama has Long Arms" """
        lands = ["Plains", "Mountain", "Forest", "Swamp", "Island"]
        random.shuffle(lands)
        for i in range(2):
            await ctx.send(lands[i])

    @commands.command()
    async def dreadmaw(self, ctx: commands.Context):
        """for devotion to dreadmaw"""
        await send_drive_image(
            ctx, "https://lh3.googleusercontent.com/d/1uYdnTLOZw42yNGc3xgO0oxhBGwoReo-c"
        )

    @commands.command()
    async def thisIsntMagic(self, ctx: commands.Context):
        """get a random card from #this-isnt-magic"""
        chan = cast(discord.TextChannel, self.bot.get_channel(hc_constants.THIS_IS_NOT_MAGIC))
        subStart = datetime.strptime("7/4/2024 2:30 PM", "%m/%d/%Y %I:%M %p").astimezone(UTC)
        timeNow = datetime.now(timezone.utc)
        timeNow = timeNow.replace(tzinfo=None)
        messages = chan.history(after=subStart)  # 07/04/2024 2:00 PM
        messages = [message async for message in messages]
        toNotify = []
        for message in messages:
            hasQuestion = get(message.reactions, emoji="❓")
            veto = get(message.reactions, emoji=hc_constants.DELETE)
            accept = get(message.reactions, emoji=hc_constants.DELETE)
            if hasQuestion and veto is None and accept is None:
                toNotify.append(message.jump_url)
        await ctx.send("these still have some uncertainty")
        await ctx.send("\n".join(toNotify))

    @commands.command()
    async def wickyp(self, ctx: commands.Context):
        """for the card Wicky P, Vintage Banworthy" """
        await send_images(ctx, sample(wicky_sheets, k=3))
        selected = sample(wicky_sheets, k=3)
        for sheet in selected:
            await send_drive_image(ctx, sheet)

    @commands.command()
    async def willsSchemes(self, ctx: commands.Context):
        """for the card "Will, Willful Schemer" """
        # https://scryfall.com/random?q=will+type=scheme
        await fetch_random_from_scryfall(ctx, "will t:scheme")

    @commands.command(aliases=["balls"])
    async def _______Balls(self, ctx: commands.Context):
        """for the card "_______ Balls" """
        await fetch_multiple_scryfall_by_id(ctx, sample(balls_sheets, k=3))

    @commands.command()
    async def locus(self, ctx: commands.Context):
        """for the card "Omnath, Locus of the Locus" """
        hell_len = len(hell_locus_ids)
        rlocus = random.randint(0, hell_len + len(scry_locus_ids) - 1)
        if rlocus < hell_len:
            await fetch_hellfall_by_id(ctx, hell_locus_ids[rlocus])
        else:
            await fetch_scryfall_by_id(ctx, scry_locus_ids[rlocus - hell_len])

    @commands.command()
    async def locust(self, ctx: commands.Context):
        """And this one is for if they spell the command wrong"""
        await ctx.send("COMMAND CANCELED!!!!! LOCUST ARMY GO")
        for i in range(
            3
        ):  # Not grouping this one into one message since that would defeat the joke
            await send_image(
                ctx,
                "https://www.icpac.net/media/images/ezgif.com-video-to-gif_1.width-800.gif",
            )
        await ctx.send("You probably want !locus")

    @commands.command()
    async def tunak(self, ctx: commands.Context):
        """for the card "Tunak Tunak Tun" """
        await fetch_random_from_hellfall(ctx, '"tunak tunak tun" unique:cards include:extras')

        # tunakSecretTokens = [
        #     "https://cdn.discordapp.com/attachments/692431610724745247/717492326653755442/Tunak_Tunak_TunP.jpg",
        #     "https://cdn.discordapp.com/attachments/692431610724745247/717492325420499005/Tunak_Tunak_Tun_Pink.jpg",
        #     "https://cdn.discordapp.com/attachments/692431610724745247/717492323675668560/Tunak_Tunak_Tun_Pickle.jpg",
        #     "https://cdn.discordapp.com/attachments/692431610724745247/717492322253668422/Tunak_Tunak_Tun_Brown.jpg",
        #     "https://cdn.discordapp.com/attachments/692914661191974912/714795268796579860/Tunak_Tunak_TunW.jpg",
        #     "https://cdn.discordapp.com/attachments/699985664992739409/711162972248080444/fjmquizxc6y41.jpg",
        #     "https://cdn.discordapp.com/attachments/692914661191974912/714795265197998090/Tunak_Tunak_TunG.jpg",
        #     "https://cdn.discordapp.com/attachments/692914661191974912/714795266758279228/Tunak_Tunak_TunR.jpg",
        #     "https://cdn.discordapp.com/attachments/692914661191974912/714795267756523600/Tunak_Tunak_TunU.jpg",
        # ]

        # if random.randint(0, 100) == 50:
        #     await send_image(tunakSecretTokens[random.randint(0, len(tunakSecretTokens) - 1)], ctx)
        # else:
        #     await send_image(tunak_tokens[random.randint(0, len(tunak_tokens) - 1)], ctx)

    @commands.command()
    async def crystallize(self, ctx: commands.Context):
        """for cards with crystallize"""
        keywords = [
            "flying",
            "first strike",
            "deathtouch",
            "hexproof",
            "lifelink",
            "menace",
            "reach",
            "trample",
            "vigilance",
            "+1/+1",
        ]
        random.shuffle(keywords)
        await ctx.send(", ".join([f"||{kw}||" for kw in keywords]))

    @commands.command()
    async def homelands(self, ctx: commands.Context, cost):
        """for the card "Department of Homelands Security" """
        try:
            await fetch_random_from_scryfall(ctx, f"is:permanent mv={cost}")
        except Exception:
            await ctx.send("Not a valid mana cost.")

    @commands.command()
    async def firstPick(self, ctx: commands.Context):
        """for the card "Mythos of Hellscube" (TODO: remove when resources documentation is updated)"""
        await fetch_hellfall_by_id(ctx, "51c353c1-7a29-49dc-91aa-3cfad270ce74")

    @commands.command()
    async def tokenGuy(self, ctx: commands.Context, count: int = 1):
        """for the cards "That One Guy at Your LGS" and "Hero of High Rollers" """
        if count < 11:
            await fetch_random_from_scryfall(ctx, "t:token t:creature pow<=2", count)
        else:
            await ctx.send("Please use 10 or lower.")

    @commands.command()
    async def obscureCommander(self, ctx: commands.Context):
        """for the card "Obscure Commander" """
        headers = {"User-Agent": hc_constants.USER_AGENT}
        async with (
            aiohttp.ClientSession(headers=headers) as session,
            session.get(
                "https://api.scryfall.com/cards/search",
                params={"q": 'command otag:command game:paper o:"choose two —" unique:cards'},
            ) as resp,
        ):
            if resp.status != 200:
                await ctx.send(
                    "Something went wrong while getting the link. Wait for llllll to fix it."
                )
                await session.close()
                return
            response = json.loads(await resp.read())
            mapped = [x["oracle_text"] for x in response["data"]]
            modes = [line for lines in mapped for line in lines.split("\n")[1:]]
            results = random.sample(population=modes, k=4)
            await ctx.send(f"Choose two —\n{'\n'.join(results)}")
            await session.close()

    @commands.command()
    async def avatarOfBalls(self, ctx: commands.Context, cost):
        """for the card "Avatar of BallsJr123" """
        await fetch_random_from_hellfall(ctx, f"mv={cost} t:creature")

    @commands.command()
    async def invoke(self, ctx: commands.Context):
        """get a random invoker"""
        await fetch_random_from_scryfall(ctx, "invoker unique:cards (o:{7} or o:{8})", 2)

    @commands.command()
    async def planarDie(self, ctx: commands.Context):
        """roll the planar die"""
        rresult = random.randint(0, 5)
        await ctx.send("You rolled a ")
        if rresult < 4:
            await ctx.send("blank side. No effect.")
        if rresult == 4:
            await ctx.send("Planeswalk!")
        else:
            if rresult == 5:
                await ctx.send("<:chaos:1323372133501505637>")

    @commands.command()
    async def therosHero(self, ctx: commands.Context):
        """get a random Hero card from Hero's Path"""
        await fetch_random_from_scryfall(ctx, "t:hero -t:creature")

    @commands.command()
    async def dragonAge(self, ctx: commands.Context):
        """get three random Dragon cards from the set Dragons of Tarkir, for the card "Dragon Age" """
        await fetch_random_from_scryfall(ctx, "t:dragon set:dtk", 3)

    @commands.command(aliases=["urzas", "urza's", "urzastuff"])
    async def urza(self, ctx: commands.Context):
        """get a random card that starts with urza, aka urza's stuff"""
        await fetch_random_from_scryfall(ctx, "/^urza's/ legal:vintage")

    @commands.command()
    async def sword(self, ctx: commands.Context):
        """get a random sword from the sword of x and y cycle"""
        await fetch_random_from_scryfall(ctx, "otag:sword-of-x-and-y")

    @commands.command(aliases=["league"])
    async def leagueOfLegends(self, ctx: commands.Context):
        """get a random legends commander from `set:leg`, for the card "League of Legends" """
        await fetch_random_from_scryfall(ctx, "set:leg is:commander")

    @commands.command(aliases=["mechdietan"])
    async def mechtitan(self, ctx: commands.Context):
        """get random artifact creatures and/or vehicles for the card "Mechtitan" """
        await fetch_random_from_scryfall(
            ctx,
            "(t:/artifact creature/ or t:vehicle) game:paper -otag:unsetmechanics unique:cards",
            4,
        )

    @commands.command(
        aliases=[
            "bigwizardspell",
            "bigfuckingwizardspell",
            "gamewinningspellbook",
            "wizardspell",
        ]
    )
    async def archmage(self, ctx: commands.Context):
        """get a random card from ARCHMAGE SEPTIMUS ALGENUS's GAME-WINNING SPELLBOOK"""
        await send_multiple_image_reply(ctx.message, sample(wizardSpells, k=3))

    @commands.command()
    async def watchwolf(self, ctx: commands.Context):
        """get a random vanilla draft signpost, for the card "2 MV 3/3 Vanilla Signpost Uncommon from Ravnica-mancy" """
        await fetch_random_from_scryfall(ctx, "otag:draft-signpost is:vanilla unique:prints")

    @commands.command()
    async def randomRoom(self, ctx: commands.Context):
        """for the card "Mystery Inc on Duskmourn" """
        await ctx.send(choice(roomDoors))

    @commands.command()
    async def history(self, ctx: commands.Context):
        """for the card "Hearth Magicbrew" (subject to change)"""
        # random 1/1001 chance to get channel fireball hand
        selectedHand = random.choice(iconicHands) if random.randint(0, 1000) else channelFireball
        await fetch_multiple_scryfall_by_id(ctx, selectedHand)

    @commands.command()
    async def bigbang(self, ctx: commands.Context, quality: str):
        """for the card "The Big Bang Theory" """
        quality = quality.lower()
        if quality not in quality_queries:
            await ctx.send(
                f"Unknown quality: {quality}. Available qualities: {', '.join(quality_queries.keys())}"
            )
            return

        await fetch_random_from_scryfall(ctx, quality_queries[quality])

    @commands.command()
    async def grunch(self, ctx: commands.Context):
        """for cards that grunch"""
        # Original: https://zaxer2.github.io/howtogrunch

        default_grunch_image = "https://i.imgur.com/gbFuCzV.png"
        grunch_image_options = [
            "https://i.imgur.com/prDIShY.gif",
            "https://i.imgur.com/xXFJIER.gif",
            "https://i.imgur.com/BaRCH9U.gif",
            "https://i.imgur.com/ZT3ofcu.gif",
            "https://i.imgur.com/7rFA7wX.gif",
            "https://i.imgur.com/K6HXuGT.gif",
        ]

        random_rules_text = random.choice(grunch_rules_text_options)
        random_flavor_text = random.choice(grunch_flavor_text_options)

        chosen_image = default_grunch_image
        random_image_chance = random.random()

        if random_image_chance >= 0.3:
            chosen_image = random.choice(grunch_image_options)

        message_parts = [
            f"# [How to Grunch]({chosen_image} \"Secret Grunch rules text: '?' is not a number until it can be determined, either by the static CDA text on this website or the triggered Grunch ability. If '?' remains undefined, it is not zero. A Grunch with no P/T cannot die to damage or as a result of having 'zero toughness'. If '?' changes after it has been determined to be a number, it changes globally for all creatures with a '?' in their P/T box.\")",
            f"So you want to learn how to deal with this wacky little {random_rules_text[0]}? Well here's how!",
        ]

        message_parts.extend(f"## {line}" for line in random_rules_text[1].split("\n"))
        message_parts.extend(f"### *{line}*" for line in random_flavor_text.split("\n"))
        message_parts.append("-# [original](https://zaxer2.github.io/howtogrunch)")

        await ctx.send("\n".join(message_parts))


async def setup(bot: commands.Bot):
    await bot.add_cog(SpecificCardsCog(bot))
