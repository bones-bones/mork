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
from post_card_images import send_image_reply

SCRYFALL_API_URL = "https://api.scryfall.com/cards"
HELLFALL_API_URL = "https://hellfall.skeleton.club/api/cards"
SCRYFALL_RANDOM_API_URL = f"{SCRYFALL_API_URL}/random"
HELLFALL_RANDOM_API_URL = f"{HELLFALL_API_URL}/random"


def scryfallApiForCard(id: str):
    return f"{SCRYFALL_API_URL}/{id}"


def hellfallApiForCard(id: str):
    return f"{HELLFALL_API_URL}/{id}"


# load json from scryfall or hellfall
async def get_card_json(targetUrl: str, query: str = "") -> dict[str, Any]:
    """
    Get json of a card from scryfall. it's important to use the header so they know to block us lol.
    """
    headers = {"User-Agent": hc_constants.USER_AGENT}
    async with aiohttp.ClientSession().get(
        targetUrl, params={"q": query} if query else None, headers=headers
    ) as resp:
        return await resp.json()


def _get_image(ob: dict[str, Any], is_hellfall: bool) -> str | None:
    if is_hellfall:
        return ob.get("image")
    uris: dict[str, str] | None = ob.get("image_uris")
    if not uris:
        return
    normal = uris.get("normal")
    if not normal:
        return
    return normal[:-10]


# get card image from scryfall json
async def get_image_from_json(json: dict[str, Any]):
    is_hellfall = "creators" in json
    return _get_image(json, is_hellfall) or _get_image(json["card_faces"][0], is_hellfall)


# send card image to channel
async def send_image(ctx: commands.Context, url: str | None):
    if not url:
        return
    await send_image_reply(url, ctx.message)


async def send_drive_image(ctx: commands.Context, url: str):
    if not url:
        return
    await send_image_reply(url, ctx.message, url.rsplit("/", 1)[-1] or "image")


# helper function for fetching and sending scryfall cards from a URL
async def fetchAndSendCard(ctx: commands.Context, url: str, query: str = ""):
    cardJson = await get_card_json(url, query)
    try:
        await send_image(ctx, await get_image_from_json(cardJson))
    except Exception:
        pp.pprint(cardJson)


# helper function to fetch and send card by query string
async def fetch_random_from_scryfall(ctx: commands.Context, query: str = ""):
    await fetchAndSendCard(ctx, SCRYFALL_RANDOM_API_URL, query)


# helper function to fetch and send card by query string
async def fetch_random_from_hellfall(ctx: commands.Context, query: str = ""):
    await fetchAndSendCard(ctx, HELLFALL_RANDOM_API_URL, query)


# helper function to fetch and send card by card id
async def fetch_scryfall_by_id(ctx: commands.Context, id: str):
    await fetchAndSendCard(ctx, scryfallApiForCard(id))


# helper function to fetch and send card by card id
async def fetch_hellfall_by_id(ctx: commands.Context, id):
    await fetchAndSendCard(ctx, hellfallApiForCard(id))


class SpecificCardsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # for the card item block
    @commands.command()
    async def item(self, ctx: commands.Context):
        await fetch_random_from_hellfall(ctx, '~"item block" unique:cards include:extras')

    # for the card shell game
    @commands.command(aliases=["shellgame", "game"])
    async def shell(self, ctx: commands.Context):
        randomNumber = random.randint(0, 2)
        if randomNumber == 0:
            response = "Plains\nDraw 1 card."
        else:
            response = "Island\nDraw 3 cards."
        await ctx.send(response)

    # for the card big money
    @commands.command(aliases=["big", "money", "bigmoney"])
    async def whammy(self, ctx: commands.Context, number):
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

    # for the card ballsjr's druidic vow
    @commands.command()
    async def vow(self, ctx: commands.Context, cost):
        try:
            await fetch_random_from_scryfall(ctx, f"mana:{cost}")
        except Exception:
            await ctx.send("Not a valid mana cost.")

    # for the card stormstorm
    @commands.command(aliases=["stormstorm"])
    async def storm(self, ctx: commands.Context, number):
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        if number < 11:
            for image in choices(stormCards, k=number):
                await send_image(ctx, image)
        else:
            await ctx.send("Please use 10 or lower.")

    # for the card keyword warp
    @commands.command(aliases=["keyword", "warp"])
    async def keywords(self, ctx: commands.Context, number: int):
        try:
            number = int(number)
        except Exception:
            await ctx.send("Please type a number.")
            return
        if 0 < number < 101:
            await ctx.send(", ".join(choices(possibleKeywords, k=number)))
        else:
            await ctx.send("Please use between 1 and 100, inclusive.")

    # for the card path to degeneracy
    @commands.command(aliases=["path", "degen", "ptd"])
    async def degeneracy(self, ctx: commands.Context):
        await fetch_scryfall_by_id(ctx, choice(femaleWarWalkers))

    # for the card a blue card
    @commands.command(aliases=["blue"])
    async def bluecard(self, ctx: commands.Context):
        await fetch_scryfall_by_id(ctx, choice(blueCards))

    # for the card wild magic
    @commands.command()
    async def wild(self, ctx: commands.Context):
        randomNum = random.randint(1, 100)
        await ctx.send(f"{randomNum}: {wildMagic[randomNum - 1]}")

    # for the card hells triome
    @commands.command()
    async def triome(self, ctx: commands.Context):
        message = ""
        lands = ["Plains", "Mountain", "Forest", "Swamp", "Island"]
        random.shuffle(lands)
        for i in range(3):
            message += lands[i] + ", "
        await ctx.send(message)

    # for the card wrath of pod
    @commands.command()
    async def podcast(self, ctx: commands.Context, number):
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

    # for the card pyrohyperspasm
    @commands.command()
    async def pyrohyperspasm(self, ctx: commands.Context, number):
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

    # for the card puzzle box of yogg-saron
    @commands.command(aliases=["puzzle", "box", "pbox", "yogg", "yoggsaron", "pb"])
    async def puzzlebox(self, ctx: commands.Context):
        for i in range(10):
            await fetch_random_from_scryfall(ctx, "t:instant or t:sorcery game:paper")

    # for the card deathseeker
    @commands.command()
    async def death(self, ctx: commands.Context):
        for _ in range(2):
            await fetch_random_from_scryfall(ctx, 'o:"When ~ dies" t:creature game:paper')

    # mirror of !death because why not
    @commands.command()
    async def life(self, ctx: commands.Context):
        for _ in range(2):
            await fetch_random_from_scryfall(ctx, 'o:"When ~ enters" t:creature game:paper')

    # another one (this time for attack triggers)
    @commands.command()
    async def attack(self, ctx: commands.Context):
        for _ in range(2):
            await fetch_random_from_scryfall(ctx, 'o:"Whenever ~ attacks" t:creature game:paper')

    # for the card multiverse broadcasting station
    @commands.command()
    async def broadcast(self, ctx: commands.Context):
        for i in range(2):
            await fetch_random_from_scryfall(ctx, "-t:narset t:planeswalker r:u")

    # for the card illusionary GF
    @commands.command(aliases=["gf", "chandra"])
    async def girlfriend(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:chandra t:planeswalker")

    # for the card ballsjrs ultimate curvetopper
    @commands.command()
    async def topper(self, ctx: commands.Context, amount):
        if int(amount) > 10:
            await ctx.send("max is 10")
            return
        for i in range(int(amount)):
            await fetch_random_from_scryfall(ctx, "mana>=X")

    # for the card obscure command
    @commands.command()
    async def obscure(self, ctx: commands.Context):
        await ctx.send("\n".join(choices(obscureModes, k=4)))

    # for the card weird elf
    @commands.command()
    async def weird(self, ctx: commands.Context):
        modes = ["Colorless", "White", "Blue", "Black", "Red", "Green"]
        for _ in range(2):
            await ctx.send(random.choice(modes))

    # for the card absurdly cryptic command
    @commands.command()
    async def cryptic(self, ctx: commands.Context):
        for _ in range(4):
            await fetch_random_from_scryfall(ctx, "c=u t:instant")

    # for the card we need more white cards
    @commands.command()
    async def whitecards(self, ctx: commands.Context):
        for _ in range(3):
            await fetch_random_from_scryfall(ctx, "c=w")

    # for the card hugh man, human
    @commands.command(aliases=["hugh", "human"])
    async def hughman(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:human")

    # for the card random growth
    @commands.command()
    async def growth(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:land")

    # for the card ultimate ultimatum
    @commands.command()
    async def ultimatum(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "ultimatum -c:bant c=3")

    # for the card regal karakas
    @commands.command()
    async def karakas(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:creature t:legendary")

    # for the card pregnant sliver
    @commands.command()
    async def sliver(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:sliver")

    # for the card a black six drop
    @commands.command()
    async def black6(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:creature c=b mv=6")

    # for the card kodama's reach but kodama has really long arms
    @commands.command()
    async def reach(self, ctx: commands.Context):
        lands = ["Plains", "Mountain", "Forest", "Swamp", "Island"]
        random.shuffle(lands)
        for i in range(2):
            await ctx.send(lands[i])

    # for the card colossal godmaw
    @commands.command()
    async def dreadmaw(self, ctx: commands.Context):
        await send_drive_image(
            ctx, "https://lh3.googleusercontent.com/d/1uYdnTLOZw42yNGc3xgO0oxhBGwoReo-c"
        )

    @commands.command()
    async def thisIsntMagic(self, ctx: commands.Context):
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
        selected = sample(wicky_sheets, k=3)
        for sheet in selected:
            await send_drive_image(ctx, sheet)

    # for the card will, willful scheme
    @commands.command()
    async def willsSchemes(self, ctx: commands.Context):
        # https://scryfall.com/random?q=will+type=scheme
        await fetch_random_from_scryfall(ctx, "will t:scheme")

    # for the _______ Balls
    @commands.command(aliases=["balls"])
    async def _______Balls(self, ctx: commands.Context):
        selected = random.sample(balls_sheets, k=3)
        for sheet in selected:
            await fetch_scryfall_by_id(ctx, sheet)

    @commands.command()
    async def locus(self, ctx: commands.Context):
        hell_len = len(hell_locus_ids)
        rlocus = random.randint(0, hell_len + len(scry_locus_ids) - 1)
        if rlocus < hell_len:
            await fetch_hellfall_by_id(ctx, hell_locus_ids[rlocus])
        else:
            await fetch_scryfall_by_id(ctx, scry_locus_ids[rlocus - hell_len])

    # And this one is for if they spell the command wrong
    @commands.command()
    async def locust(self, ctx: commands.Context):
        await ctx.send("COMMAND CANCELED!!!!! LOCUST ARMY GO")
        for i in range(3):
            await send_image(
                ctx,
                "https://www.icpac.net/media/images/ezgif.com-video-to-gif_1.width-800.gif",
            )
        await ctx.send("You probably want !locus")

    # for the card tunak tunak tun
    @commands.command()
    async def tunak(self, ctx: commands.Context):
        await fetch_random_from_hellfall(ctx, '~"item block" unique:cards include:extras')

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

    # for cards with crystallize
    @commands.command()
    async def crystallize(self, ctx: commands.Context):
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

    # for the card department of homelands security
    @commands.command()
    async def homelands(self, ctx: commands.Context, cost):
        try:
            await fetch_random_from_scryfall(ctx, f"is:permanent mv={cost}")
        except Exception:
            await ctx.send("Not a valid mana cost.")

    # for the card mythos of hellscube (TODO: decide if this is actually necessary anymore)
    @commands.command()
    async def firstPick(self, ctx: commands.Context):
        await fetch_hellfall_by_id(ctx, "51c353c1-7a29-49dc-91aa-3cfad270ce74")

    # https://scryfall.com/random?is%3Atoken+type%3Acreature+power%3C%3D2&unique=cards&as=grid&order=name
    # That one guy at your LGS + Hero of High Rollers
    @commands.command()
    async def tokenGuy(self, ctx: commands.Context, count: int = 1):
        for i in range(count):
            await fetch_random_from_scryfall(ctx, "t:token t:creature pow<=2")

    # Obscure Commander
    @commands.command()
    async def obscureCommander(self, ctx: commands.Context):
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

    # for the card Avatar of BallsJr123
    @commands.command()
    async def avatarOfBalls(self, ctx: commands.Context, cost):
        await fetch_random_from_hellfall(ctx, f"mv={cost} t:creature")

    # get a random invoker for the card voke enjoyer
    @commands.command()
    async def invoke(self, ctx: commands.Context):
        for i in range(2):
            await fetch_random_from_scryfall(ctx, "invoker unique:cards (o:{7} or o:{8})")

    # roll the planar die
    @commands.command()
    async def planarDie(self, ctx: commands.Context):
        rresult = random.randint(0, 5)
        await ctx.send("You rolled a ")
        if rresult < 4:
            await ctx.send("blank side. No effect.")
        if rresult == 4:
            await ctx.send("Planeswalk!")
        else:
            if rresult == 5:
                await ctx.send("<:chaos:1323372133501505637>")

    # get a random Hero card from Hero's Path
    @commands.command()
    async def therosHero(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "t:hero -t:creature")

    # get three random Dragon card from the set Dragibs of Tarkir, for the card Dragon Age
    @commands.command()
    async def dragonAge(self, ctx: commands.Context):
        for i in range(3):
            await fetch_random_from_scryfall(ctx, "t:dragon set:dtk")

    # get a random card that starts with urza, aka urza's stuff
    @commands.command(aliases=["urzas", "urza's", "urzastuff"])
    async def urza(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "/^urza's/ legal:vintage")

    # get a random sword from the sword of x and y cycle, for Dr. Jankenstein, Swordsmith
    @commands.command()
    async def sword(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "otag:sword-of-x-and-y")

    # get a random legends commander from set:legends, for card League of Legends
    @commands.command(aliases=["league"])
    async def leagueOfLegends(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "set:leg is:commander")

    # get random artifact creatures and/or vehicles for Mechtitan
    @commands.command(aliases=["mechdietan"])
    async def mechtitan(self, ctx: commands.Context):
        for i in range(4):
            await fetch_random_from_scryfall(
                ctx,
                "(t:/artifact creature/ or t:vehicle) game:paper -otag:unsetmechanics unique:cards",
            )

    # get a random card from ARCHMAGE SEPTIMUS ALGENUS's GAME-WINNING SPELLBOOK
    @commands.command(
        aliases=[
            "bigwizardspell",
            "bigfuckingwizardspell",
            "gamewinningspellbook",
            "wizardspell",
        ]
    )
    async def archmage(self, ctx: commands.Context):
        selectedSpells = random.sample(wizardSpells, k=3)
        for spell in selectedSpells:
            await send_image(ctx, spell)

    # get a random vanilla draft signpost, for the card 2 MV 3/3 Vanilla Signpost Uncommon from Ravnica-mancy
    @commands.command()
    async def watchwolf(self, ctx: commands.Context):
        await fetch_random_from_scryfall(ctx, "otag:draft-signpost is:vanilla unique:prints")

    # for the card Mystery Inc on Duskmourn
    @commands.command()
    async def randomRoom(self, ctx: commands.Context):
        await ctx.send(choice(roomDoors))

    # for the card Hearth Magicbrew (subject to change)
    @commands.command()
    async def history(self, ctx: commands.Context):
        # random 1/1001 chance to get channel fireball hand
        selectedHand = random.choice(iconicHands) if random.randint(0, 1000) else channelFireball
        for card in selectedHand:
            await fetch_scryfall_by_id(ctx, card)

    # for the card The Big Bang Theory
    @commands.command()
    async def bigbang(self, ctx: commands.Context, quality: str):
        quality = quality.lower()
        if quality not in quality_queries:
            await ctx.send(
                f"Unknown quality: {quality}. Available qualities: {', '.join(quality_queries.keys())}"
            )
            return

        await fetch_random_from_scryfall(ctx, quality_queries[quality])

    # for the card Grunch
    # Original: https://zaxer2.github.io/howtogrunch
    @commands.command()
    async def grunch(self, ctx: commands.Context):

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
