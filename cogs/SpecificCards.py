from datetime import datetime, timezone
import re
from typing import cast
import discord
from discord.ext import commands
import asyncio
import random
import json
import urllib.request
import aiohttp
import io
from operator import itemgetter
import pprint as pp
from discord.utils import get


from cogs.HellscubeDatabase import searchFor
from cogs.get_podcast_output import get_podcast_output
import hc_constants
from printCardImages import send_image_reply


# load json from scryfall
async def getScryfallJson(targetUrl):
    await asyncio.sleep(0.2)
    with urllib.request.urlopen(targetUrl) as url:
        resp = json.loads(url.read().decode())
        return resp


# get card image from scryfall json
async def getImageFromJson(json):
    try:
        image = json["image_uris"]["normal"][:-10]
    except:
        image = json["card_faces"][0]["image_uris"]["normal"][:-10]
    return image


# send card image to channel
async def sendImage(url, ctx: commands.Context):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await ctx.send(
                    "Something went wrong while getting the link. Wait for llllll to fix it."
                )
                await session.close()
                return
            data = io.BytesIO(await resp.read())
            await ctx.send(file=discord.File(data, url))
            await session.close()


async def sendDriveImage(url, ctx: commands.Context):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await ctx.send(
                    "Something went wrong while getting the link. Wait for llllll to fix it."
                )
                await session.close()
                return
            # currently extraFilename looks like inline;filename="                                Skald.png"
            extraFilename = resp.headers.get("Content-Disposition")
            parsedFilename = re.findall('inline;filename="(.*)"', str(extraFilename))[0]
            data = io.BytesIO(await resp.read())
            await ctx.send(file=discord.File(data, parsedFilename))
            await session.close()


class SpecificCardsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # for the card item block
    @commands.command()
    async def item(self, ctx: commands.Context):
        items = ["Food", "Treasure", "Clue", "Katana", "Land-Mine"]
        await ctx.send(random.choice(items))

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
        except:
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
            json = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=mana%3D" + cost
            )
            await sendImage(await getImageFromJson(json), ctx)
        except:
            await ctx.send("Not a valid mana cost.")

    # for the card stormstorm
    @commands.command(aliases=["stormstorm"])
    async def storm(self, ctx: commands.Context, number):
        stormCards = [
            "https://cards.scryfall.io/large/front/2/8/2890c2ee-e989-43e5-ac4b-683c52bd6527.jpg",
            "https://cards.scryfall.io/normal/front/0/3/036ef8c9-72ac-46ce-af07-83b79d736538.jpg",
            "https://cards.scryfall.io/large/front/8/b/8b6723f5-a7a9-425d-b4b0-f380da578ef8.jpg",
        ]
        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        if number < 11:
            for i in range(number):
                await sendImage(stormCards[random.randint(0, len(stormCards) - 1)], ctx)
        else:
            await ctx.send("Please use 10 or lower.")

    # for the card keyword warp
    @commands.command(aliases=["keyword", "warp"])
    async def keywords(self, ctx: commands.Context, number: int):
        possibleKeywords = [
            "Deathtouch",
            "Defender",
            "Double Strike",
            "First Strike",
            "Flash",
            "Flying",
            "Haste",
            "Hexproof",
            "Indestructible",
            "Lifelink",
            "Menace",
            "Prowess",
            "Reach",
            "Trample",
            "Vigilance",
            "Ward 1",
            "Absorb 1",
            "Afflict 1",
            "Afterlife 1",
            "Amplify 1",
            "Annihilator 1",
            "Banding",
            "Battle Cry",
            "Bloodthirst 1",
            "Bushido 1",
            "Cascade",
            "Changeling",
            "Convoke",
            "Delve",
            "Dethrone",
            "Devoid",
            "Evolve",
            "Exalted",
            "Exploit",
            "Extort",
            "Fading 1",
            "Fear",
            "Flanking",
            "Devour 1",
            "Dredge 1",
            "Echo",
            "Frenzy 1",
            "Epic",
            "Graft 1",
            "Plainswalk",
            "Mountainwalk",
            "Forestwalk",
            "Hideaway",
            "Horsemanship",
            "Infect",
            "Ingest",
            "Intimidate",
            "Swampwalk",
            "Islandhome",
            "Islandwalk",
            "Protection from Blue",
            "Protection from White",
            "Protection from Red",
            "Protection from Green",
            "Protection from Black",
            "Mentor",
            "Modular 1",
            "Persist",
            "Phasing",
            "Poisonous 1",
            "Myriad",
            "Provoke",
            "Skulk",
            "Shadow",
            "Shroud",
            "Renown 1",
            "Soulshift 1",
            "Rampage 1",
            "Split Second",
            "Retrace",
            "Ripple 1",
            "Sunburst",
            "Tribute 1",
            "Undying",
            "Unleash",
            "Vanishing 1",
            "Wither",
        ]

        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        if number < 101:
            text = ""
            for i in range(number):
                text += (
                    possibleKeywords[random.randint(0, len(possibleKeywords) - 1)]
                    + ", "
                )
            await ctx.send(text)
        else:
            await ctx.send("Please use 100 or lower.")

    # for the card path to degeneracy
    @commands.command(aliases=["path", "degen", "ptd"])
    async def degeneracy(self, ctx: commands.Context):
        femaleWarWalkers = [
            "https://api.scryfall.com/cards/8d7c88ec-0537-4d94-81d1-e1ba877d2cdb?format=json",
            "https://api.scryfall.com/cards/1f2b1975-183b-4989-aa1f-a653ec732abf?format=json",
            "https://api.scryfall.com/cards/e078151b-74b7-426a-9ee5-d83799ca2b85?format=json",
            "https://api.scryfall.com/cards/ac555b4e-c682-46d2-a99e-1bd1656155d7?format=json",
            "https://api.scryfall.com/cards/4422e69e-a7db-4582-b37d-59519b6871f9?format=json",
            "https://api.scryfall.com/cards/3b129f92-e6c4-4967-bd0c-02ff85f09636?format=json",
            "https://api.scryfall.com/cards/9eac128e-5784-467c-85ed-e46c6ab25547?format=json",
            "https://api.scryfall.com/cards/3f17544a-7bcd-4315-8e14-bea8317ee13a?format=json",
            "https://api.scryfall.com/cards/197c8c75-3b53-49ab-adb5-32937b49e834?format=json",
            "https://api.scryfall.com/cards/e5ad78c6-8af3-4efa-b47a-29a646ea412a?format=json",
            "https://api.scryfall.com/cards/28037c63-67ec-4a57-9a8c-3ba88127a258?format=json",
            "https://api.scryfall.com/cards/bdfd5ff8-0591-4e58-aae1-4f441750518d?format=json",
            "https://api.scryfall.com/cards/c1523eed-d417-44bc-90fc-f67ecb3dc2c4?format=json",
            "https://api.scryfall.com/cards/25d63632-c019-4f34-926a-42f829a4665c?format=json",
            "https://api.scryfall.com/cards/43261927-7655-474b-ac61-dfef9e63f428?format=json",
            "https://api.scryfall.com/cards/981850b2-3013-4f12-ab13-6410431585f2?format=json",
            "https://api.scryfall.com/cards/199e3667-33be-415f-8f10-1c42a78d7637?format=json",
        ]
        degenJson = await getScryfallJson(
            femaleWarWalkers[random.randint(0, len(femaleWarWalkers) - 1)]
        )
        await ctx.send(degenJson["name"])
        await sendImage(await getImageFromJson(degenJson), ctx)
        await ctx.send(degenJson["oracle_text"])

    # for the card a blue card
    @commands.command(aliases=["blue"])
    async def bluecard(self, ctx: commands.Context):
        blueCards = [
            "https://api.scryfall.com/cards/9f7983bf-2a3b-4428-8c01-35285f589da8?format=json",
            "https://api.scryfall.com/cards/9e7fb3c0-5159-4d1f-8490-ce4c9a60f567?format=json",
            "https://api.scryfall.com/cards/8b75bef5-a039-4edf-8e43-56b8d089605e?format=json",
            "https://api.scryfall.com/cards/0e84a9db-8130-489b-9f76-e3ecd35a0fd8?format=json",
            "https://api.scryfall.com/cards/6270b93e-8cd2-4668-982a-f4c4628da9d9?format=json",
            "https://api.scryfall.com/cards/ebc01ab4-d89a-4d25-bf54-6aed33772f4b?format=json",
            "https://api.scryfall.com/cards/fbee1e10-0b8c-44ea-b0e5-44cdd0bfcd76?format=json",
            "https://api.scryfall.com/cards/ca097675-5e82-493d-beab-9fc11efd7492?format=json",
            "https://api.scryfall.com/cards/8de3fdae-cc2c-4a14-b15b-4fe1a983dfbf?format=json",
            "https://api.scryfall.com/cards/eff24f82-afd6-48be-ba99-2f9e8a3d0231?format=json",
            "https://api.scryfall.com/cards/5573470a-7192-4f1e-aafd-517c494875a8?format=json",
            "https://api.scryfall.com/cards/5852a174-eef6-4c06-abcd-fd90f4b8a188?format=json",
            "https://api.scryfall.com/cards/d7a7a247-51bd-4244-81c7-2b406a23cc69?format=json",
            "https://api.scryfall.com/cards/e89f2a37-9e8e-4291-9595-3c20b00444b0?format=json",
            "https://api.scryfall.com/cards/268f6afc-bf16-4ca7-a986-945a95d3bffc?format=json",
            "https://api.scryfall.com/cards/809205f3-acf5-4244-b360-09ce4ba76795?format=json",
            "https://api.scryfall.com/cards/d147eb02-4cfc-49ed-a5aa-dd6b3f3a2e51?format=json",
            "https://api.scryfall.com/cards/4aa8f4c4-8177-4c27-9d19-50ae159039ff?format=json",
            "https://api.scryfall.com/cards/fec6b189-97e7-4627-9785-a9ce2f1ad89f?format=json",
            "https://api.scryfall.com/cards/7e41765e-43fe-461d-baeb-ee30d13d2d93?format=json",
        ]
        bluecardJson = await getScryfallJson(
            blueCards[random.randint(0, len(blueCards) - 1)]
        )
        await sendImage(await getImageFromJson(bluecardJson), ctx)

    # for the card wild magic
    @commands.command()
    async def wild(self, ctx: commands.Context):
        wildMagic = [
            "If you roll this text, roll an additional 5 times on the Wild Magic Surge table and gain all that text instead, ignoring this result on subsequent rolls.",
            "Until the end of your next turn, players cast spells as if they were copies of Wild Magic Surge.",
            "Turn all face down creatures face up and manifest all face up creatures. (These are simultaneous.)",
            "Exile all spells on the stack.",
            "Roll a d6. It becomes an X/X Construct artifact creature token named Modron, where X is the number face up on the die.",
            "You gain flying until the end of your next turn. (You can’t be attacked by creatures without flying.)",
            "Wild Magic Surge deals 4 damage to each creature and yourself.",
            "Create a 3/2 pink Flamingo creature token with flying.",
            "Cast a copy of Magic Missile.",
            "Regenerate all creatures.",
            "Roll a d6. If the result was even, target creature gets +X/+X until end of turn, where X was the roll. If the result was odd, target creature gets -X/-X until end of turn, where X was the roll.",
            "Discard a card, then draw two cards.",
            "Play a random card from your hand without paying its mana cost. (You are forced to play lands as well.)",
            "Draw 7 cards. At the end of your next turn, discard 7 cards.",
            "Gain 5 life. At the beginning of your next upkeep, gain 5 life.",
            "Draw two cards, then discard a card.",
            "Sneeze on two target creatures. (Tap them. If you control a creature with infect, destroy them instead.)",
            "Create two treasure tokens.",
            "Goad all creatures.",
            "Wild Magic Surge becomes a minigame until end of turn. Play one round of two truths and a lie with all opponents, with you telling the truths and lie. If you win, draw two cards.",
            "Treat the next roll target opponent makes as a 1. Roll a d4.",
            "For the rest of the game, nonland permanents and spells you cast are blue. Draw a card.",
            "Feel bad that this card did nothing. (Sucks to be you!)",
            "Look at your opponent’s hand, then scry 1.",
            "Roll 1d3. Put that many +1/+1 counters on target creature.",
            "Until end of turn, you may cast spells as though they had flash.",
            "Add UR. Target opponent gains control of Wild Magic Surge.",
            "If you are playing planechase, activate the chaos ability of the plane you are on, then planeswalk. If you are not, activate the chaos ability of a plane chosen at random.",
            "Set your life total to 1. At the beginning of your next upkeep, gain 19 life.",
            "Prevent all combat damage that would be dealt until the end of your next turn.",
            "Dance until the beginning of your next upkeep. If you do, you may tap up to three target permanents.",
            "Wild Magic Surge deals 4 damage to any target.",
            "Scry 2d4.",
            """Choose one:
            Add Zoomer Blue // Boomer White to your hand
            Add Ok Boomer to your hand""",
            "Each player loses 3 life.",
            "Create 1d4 1/2 Horror creature tokens named Flumph with lifelink, defender and flying.",
            "Create two 1/1 green Frog creature tokens. Target opponent creates a 1/1 green Frog creature token.",
            "Gain 2d6 life.",
            "You get an emblem with “At the beginning of your upkeep, target creature you control gains deathtouch and infect until end of turn.” and an emblem with “At the beginning of your end step, lose 2 life.”",
            "Target player from outside the game controls your next turn. At the beginning of your next upkeep, draw 2 cards.",
            "Return target creature to its owner’s hand.",
            "Destroy two target lands controlled by different players.",
            "Each player may say some weeb shit and sacrifice a permanent. If they don’t, they sacrifice two permanents and their honor instead.",
            "Fateseal 1d4.",
            "Cast a copy of a random instant or sorcery spell with converted mana cost 2. [Link](https://scryfall.com/random?q=%28t%3Ainstant+or+t%3Asorcery%29+mv%3D2&unique=cards)",
            "Create a token copy of Pheldagriff.",
            "You may rename any number of target creatures you control.",
            "All creatures lose their text boxes until end of turn.",
            "Search your library for a basic land card, reveal it and put it onto the battlefield tapped. Shuffle your library.",
            "Each player gives a card in their hand to an opponent of their choice.",
            "Tap or untap each permanent at random. (Flip a coin for each. This does not count as flipping a coin or rolling a dice for the purpose of effects.)",
            "Support 2, then support your opponent. (To support your opponent, pay them a compliment or tell them how much you respect them.)",
            "Add UURR.",
            "Tell a joke. If you do, up to three target creatures laugh uncontrollably. (Tap them. They don’t untap during their controller’s next untap step.)",
            "Manifest Wild Magic Surge as it resolves.",
            "All lands become forests in addition to their other types.",
            "Exile Wild Magic Surge, then cast it from exile without paying its mana cost. Replace its text with “Cascade, cascade”.",
            "Each player gains control of creatures controlled by the player to their left until the end of your next turn. They all gain haste.",
            "Spells cast cost {1} more until end of turn.",
            "Spells cast cost {1} less until end of turn.",
            "Until end of turn, you may play any number of land cards.",
            "Punch target creature. If you do, it’s destroyed.",
            "Note the number of cards in your hand. Shuffle your hand into your library, and draw cards equal to target creature you control’s power. That creature has power equal to the noted number.",
            "Wild Magic Surge deals 6 damage split as you choose amongst any number of target creatures.",
            "Creatures you don’t control gain islandwalk until the end of your next turn. Creatures you don’t control get -1/+0 until the end of your next turn.",
            "Counter target spell. If you do, draw a card.",
            "You become a 3/X Elk creature token with shroud and haste until the end of your next turn, where X is your life total. You’re still a player. (Damage does not fall off player creatures, but is permanent instead.)",
            "Cast a copy of Babymake.",
            "You cannot lose the game and opponents cannot win the game until the end of your next turn.",
            "Create a token copy of a random bear. (A bear is a 2/2 with CMC 2.)[link](https://scryfall.com/random?q=pow%3D2+tou%3D2+mv%3D2&unique=cards)",
            "Until the end of your next turn, if a source would deal damage to you, it deals half that damage, rounded down, instead”",
            "Add a token copy of “Avatar of Me” to your hand.",
            "Put a -1/-1 counter on each creature.",
            "Create a green enchantment token named Rainbow with “Lands tap for any colour of mana.”",
            "Exile the top three cards of your library. You may play them until end of turn.",
            "Cast a copy of Better Than One.",
            "Until end of turn, all cards in your sideboard gain “Need: Discard a card.” Until end of turn, after you Need a card, draw a card.",
            "Create a red enchantment token named Wound with “If a source would deal damage to a permanent or player, it deals double that damage to that permanent or player instead.”",
            "Search your library for a card and put it into your hand. Shuffle your library.",
            "Create a Food token. If you have sacrificed a Food token this game, create two instead.",
            "Untap up to two target lands you control. Draw a card.",
            "Cast a copy of Chaos Warp, targeting a permanent chosen at random.",
            "Lifelink. Wild Magic Surge deals 1 damage to each creature.",
            "Draw a card for each card on the stack.",
            "Deathtouch. Wild Magic Surge deals 1 damage to target creature you don’t control.",
            "Exile all creatures, then return them to the battlefield under their owner’s control.",
            "A creature chosen at random gains flying.",
            "Prevent the next instance of damage that would be dealt to you.",
            "Cast a copy of Teferi’s Protection.",
            "Target creature you control gains Phasing. (It continues to have it in any zone for the remainder of the game.)",
            "Until the end of your next turn, whenever you would roll a die, instead roll three and choose which to use.",
            "Exchange control of all permanents and all cards in your hand with target opponent.",
            "You get an emblem with “Permanents have devoid.”",
            "You get an emblem with “Your devotion to Niv Mizzet is increased by 1.” Create a number of 3/1 red and blue Scientist creature tokens equal to your devotion to Niv Mizzet.",
            "Each player draws the bottom card of their deck.",
            "Return a random instant or sorcery card from your graveyard to your hand.",
            "Wild Magic Surge deals 1d6 damage to target creature.",
            "Draw 1d4 cards.",
            "Untap all lands you control.",
            "Gain 5 life, draw a card, create a 3/3 green Dinosaur creature token, target opponent discards a card and Wild Magic Surge deals 3 damage to any target.",
        ]
        randomNum = random.randint(1, 100)
        await ctx.send(str(randomNum) + ": " + wildMagic[randomNum - 1])

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
        except:
            await ctx.send("Please type a number.")
            return
        if number > 20:
            await ctx.send("Please type a number 20 or lower.")
            return

        output = get_podcast_output(number)

        await ctx.send(output)

    # for the card pyrohyperspasm
    @commands.command()
    async def pyrohyperspasm(
        self, ctx: commands.Context, number, buttPlug=False, *creatures
    ):
        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        if number > 400:
            await ctx.send("Please use 400 or lower.")
            return
        if len(creatures) > 26:
            await ctx.send("Please use 26 or fewer creatures.")
            return
        if buttPlug == "true":
            buttPlug = 1
        else:
            buttPlug = 0
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        State = []
        for i in range(len(creatures)):
            creature = []
            creature.append(int(creatures[i].split("/")[0]))
            creature.append(int(creatures[i].split("/")[1]))
            creature.append(alphabet[i])
            State.append(creature)
        for i in range(number):
            State.extend(
                [
                    [4 + buttPlug, 2 + buttPlug],
                    [2 + buttPlug, 3 + buttPlug],
                    [6 + buttPlug, 1 + buttPlug],
                ]
            )
            randomNum = random.randint(0, len(State) - 1)
            State[randomNum][0] += 1 + buttPlug
            State[randomNum][1] += buttPlug
            randomNum = random.randint(0, len(State) - 1)
            State[randomNum][0] += 3 + buttPlug
            State[randomNum][1] += 2 + buttPlug
            randomNum = random.randint(0, len(State) - 1)
            State[randomNum][0] += 4 + buttPlug
            State[randomNum][1] -= 1 - buttPlug
            for x in State:
                if x[1] == 0:
                    State.remove(x)
        result = ""
        amountLeft = 0
        for i in range(len(creatures)):
            if len(State[i]) == 3:
                result += (
                    State[i][2]
                    + ": "
                    + str(State[i][0])
                    + "/"
                    + str(State[i][1])
                    + "\n"
                )
                amountLeft += 1
        State = State[amountLeft:]
        State = sorted(State, key=itemgetter(1), reverse=True)
        State = sorted(State, key=itemgetter(0), reverse=True)

        for i in State:
            result += str(i[0])
            result += "/"
            result += str(i[1])
            result += ", "
        if len(result) > 4000:
            await ctx.send("Sorry, result string too LARGE.")
        elif len(result) > 2000:
            await ctx.send(result[:2000])
            await ctx.send(result[2001:])
        else:
            await ctx.send(result)
        totalPower = 0
        totalToughness = 0
        for i in State:
            totalPower += i[0]
            totalToughness += i[1]
        await ctx.send(
            "Total (new) stats: (" + str(totalPower) + "/" + str(totalToughness) + ")"
        )

    # for the card puzzle box of yogg-saron
    @commands.command(aliases=["puzzle", "box", "pbox", "yogg", "yoggsaron", "pb"])
    async def puzzlebox(self, ctx: commands.Context):
        for i in range(10):
            json = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=t%3Ainstant+or+t%3Asorcery"
            )
            await sendImage(await getImageFromJson(json), ctx)

    # for the card deathseeker
    @commands.command()
    async def death(self, ctx: commands.Context):
        for i in range(2):
            deathseekerJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=o%3A%22When+~+dies%22+t%3Acreature"
            )
            try:
                await sendImage(await getImageFromJson(deathseekerJson), ctx)
            except:
                pp.pprint(deathseekerJson)

    # mirror of !death because why not
    @commands.command()
    async def life(self, ctx: commands.Context):
        for i in range(2):
            deathseekerJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=o%3A%22When+~+enters%22+t%3Acreature"
            )
            try:
                await sendImage(await getImageFromJson(deathseekerJson), ctx)
            except:
                pp.pprint(deathseekerJson)

    # for the card multiverse broadcasting station
    @commands.command()
    async def broadcast(self, ctx: commands.Context):
        for i in range(2):
            broadcastJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=-type%3Anarset+type%3Aplaneswalker+rarity%3Au"
            )
            try:
                await sendImage(await getImageFromJson(broadcastJson), ctx)
            except:
                pp.pprint(broadcastJson)

    # for the card illusionary GF
    @commands.command(aliases=["gf", "chandra"])
    async def girlfriend(self, ctx: commands.Context):
        GFJson = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=t%3Achandra+t%3Aplaneswalker"
        )
        try:
            await sendImage(await getImageFromJson(GFJson), ctx)
        except:
            pp.pprint(GFJson)

    # for the card ballsjrs ultimate curvetopper
    @commands.command()
    async def topper(self, ctx: commands.Context, amount):
        if int(amount) > 10:
            await ctx.send("max is 10")
            return
        for i in range(int(amount)):
            topperJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=mana%3E%3DX"
            )
            try:
                await sendImage(await getImageFromJson(topperJson), ctx)
            except:
                pp.pprint(topperJson)

    # for the card obscure command
    @commands.command()
    async def obscure(self, ctx: commands.Context):
        modes = [
            "Target player loses 2 life.",
            "Return target creature card with converted mana cost 2 or less from your graveyard to the battlefield.",
            "Target creature gets -2/-2 until end of turn.",
            "Up to 2 target creatures gain fear until end of turn.",
            "Counter target spell.",
            "Return target permanent to its owner’s hand.",
            "Tap all creatures your opponents control.",
            "Draw a card.",
            "Obscure Command deals 4 damage to target player or planeswalker.",
            "Obscure Command deals 2 damage to each creature.",
            "Destroy target nonbasic land.",
            "Each player discards all the cards in their hand, then draws that many cards.",
            "Target player gains 7 life.",
            "Put target noncreature permanent on top of its owner’s library.",
            "Target player shuffles their graveyard into their library.",
            "Search your library for a creature card, reveal it, put it into your hand, then shuffle your library.",
            "Destroy all artifacts.",
            "Destroy all enchantments.",
            "Destroy all creatures with converted mana cost 3 or less.",
            "Destroy all creatures with converted mana cost 4 or greater.",
        ]
        for _ in range(4):
            await ctx.send(random.choice(modes))

    # for the card weird elf
    @commands.command()
    async def weird(self, ctx: commands.Context):
        modes = ["Colorless", "White", "Blue", "Black", "Red", "Green"]
        for _ in range(2):
            await ctx.send(random.choice(modes))

    # for the card absurdly cryptic command
    @commands.command()
    async def cryptic(self, ctx: commands.Context):
        for i in range(4):
            crypticJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=c%21u+t%3Ainstant"
            )
            await sendImage(await getImageFromJson(crypticJson), ctx)

    # for the card we need more white cards
    @commands.command()
    async def whitecards(self, ctx: commands.Context):
        for i in range(3):
            whitecardsJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=c=w"
            )
            await sendImage(await getImageFromJson(whitecardsJson), ctx)

    # for the card hugh man, human
    @commands.command(aliases=["hugh", "human"])
    async def hughman(self, ctx: commands.Context):
        hughmanJson = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=t%3Ahuman"
        )
        await sendImage(await getImageFromJson(hughmanJson), ctx)

    # for the card random growth
    @commands.command()
    async def growth(self, ctx: commands.Context):
        growthJson = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=t%3Aland"
        )
        await sendImage(await getImageFromJson(growthJson), ctx)

    # for the card ultimate ultimatum
    @commands.command()
    async def ultimatum(self, ctx: commands.Context):
        ultimatumJson = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=name%3Dultimatum+-c%3Awug"
        )
        await sendImage(await getImageFromJson(ultimatumJson), ctx)

    # for the card regal karakas
    @commands.command()
    async def karakas(self, ctx: commands.Context):
        karakasJson = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=t%3Dcreature+t%3Dlegendary"
        )
        await sendImage(await getImageFromJson(karakasJson), ctx)

    # for the card pregnant sliver
    @commands.command()
    async def sliver(self, ctx: commands.Context):
        sliverJson = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=t%3Asliver"
        )
        await sendImage(await getImageFromJson(sliverJson), ctx)

    # for the card a black six drop
    @commands.command()
    async def black6(self, ctx: commands.Context):
        black6Json = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=t%3Acreature+c%21b+cmc%3A6"
        )
        await sendImage(await getImageFromJson(black6Json), ctx)

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
        await sendDriveImage(
            "https://lh3.googleusercontent.com/d/1uYdnTLOZw42yNGc3xgO0oxhBGwoReo-c", ctx
        )

    @commands.command()
    async def thisIsntMagic(self, ctx: commands.Context):
        chan = cast(
            discord.TextChannel, self.bot.get_channel(hc_constants.THIS_IS_NOT_MAGIC)
        )
        subStart = datetime.strptime("7/4/2024 2:30 PM", "%m/%d/%Y %I:%M %p")
        timeNow = datetime.now(timezone.utc)
        timeNow = timeNow.replace(tzinfo=None)
        messages = chan.history(after=subStart)  # 07/04/2024 2:00 PM
        messages = [message async for message in messages]
        toNotify = []
        for message in messages:
            hasQuestion = get(message.reactions, emoji="❓")
            veto = get(message.reactions, emoji=hc_constants.DELETE)
            accept = get(message.reactions, emoji=hc_constants.DELETE)
            if hasQuestion and veto == None and accept == None:
                toNotify.append(message.jump_url)
        await ctx.send("these still have some uncertainty")
        await ctx.send("\n".join(toNotify))

    @commands.command()
    async def wickyp(self, ctx: commands.Context):
        stickersheets = [
            "https://lh3.googleusercontent.com/d/1uqW4nKy_r7s9HC1mNXCbR4_JiWhZsTkr",
            "https://lh3.googleusercontent.com/d/15keQ6wbMnw0OZeuVeq9InuGKh7CmTSO1",
            "https://lh3.googleusercontent.com/d/1FEn41lDcyxbBoi37HKyD7EYRRbearlMV",
            "https://lh3.googleusercontent.com/d/1FVfTf_5RH8HvUSzLteUhwoa3yLzZzVur",
            "https://lh3.googleusercontent.com/d/1hBxgoKl5R3iguy2Rt5zpfnt5YRDofA6Z",
            "https://lh3.googleusercontent.com/d/1LUPppUAuUEhPE_AYa0vJsaDGzuJFeQmr",
            "https://lh3.googleusercontent.com/d/1b_bnF9gaqCw8I0IluZSwmKcTh7KUMghY",
            "https://lh3.googleusercontent.com/d/1FAaTqQkUQM5-Hy6hK7_s3rkASHKH1_9D",
            "https://lh3.googleusercontent.com/d/1SlR0f3H520XwtT65Nt-tnx0trQtNmlVn",
            "https://lh3.googleusercontent.com/d/1Vo79t5JiEL_vodhXBj8m4z5M4H2xwgU9",
        ]
        selected = random.sample(stickersheets, k=3)
        for sheet in selected:
            await sendDriveImage(sheet, ctx)

    # for the card ballsjr's druidic vow
    @commands.command()
    async def willsSchemes(self, ctx: commands.Context):
        # https://scryfall.com/random?q=will+type=scheme

        json = await getScryfallJson(
            "https://api.scryfall.com/cards/random?q=will+type=scheme"
        )
        await sendImage(await getImageFromJson(json), ctx)

    @commands.command()
    async def locus(self, ctx: commands.Context):
        locusCards = [
            "https://cards.scryfall.io/large/front/2/f/2f28ecdc-a4f0-4327-a78c-340be41555ee.jpg",
            "https://cards.scryfall.io/large/front/8/b/8b63efb6-249c-4f57-9af1-baffe938520c.jpg",
            "https://cards.scryfall.io/large/front/4/a/4afcabf8-8f84-489d-8496-5bec55b351bd.jpg",
            "https://cards.scryfall.io/large/front/2/8/28603c1c-f9b4-4001-bc56-d1453d5cacf5.jpg",
            "https://cards.scryfall.io/large/front/d/a/da785d1b-6b90-4b65-9efb-d7f329405318.jpg",
            "https://cards.scryfall.io/large/front/c/2/c2536a4f-9e73-482b-8c1b-71974ef8950c.jpg",
            "https://cards.scryfall.io/large/front/e/c/eca23062-6014-4a0e-8210-2e86a6308aab.jpg",
            (
                "https://lh3.googleusercontent.com/d/1EsgQVM7jEAy3Yy_KvaVAUpifaEK_GtQh",
                "Mavren Fein, Dusk post",
            ),
            (
                "https://lh3.googleusercontent.com/d/1rcJhs0VO41VHvTY2Y80TjCQldi_3LYDN",
                "seachrome post",
            ),
            (
                "https://lh3.googleusercontent.com/d/1RCnsxsollhx1xmF58bt35DXVUi9NleAw",
                "shitpost",
            ),
            (
                "https://lh3.googleusercontent.com/d/1Chv8ICvXMQIuRg_eAvXEUQR4_-cQTdxR",
                "Omnath, Locus of the Locus",
            ),
        ]
        rlocus = random.randint(0, len(locusCards) - 1)
        # This is not super future proofed against new black border locus, if one gets printed, add it to the list under the scryfall links and add 1 to the number
        black_border_posts = 7
        if rlocus < black_border_posts:
            await sendImage(locusCards[rlocus], ctx)
        else:
            await send_image_reply(
                url=locusCards[rlocus][0],
                cardname=locusCards[rlocus][1],
                message=ctx.message,
                text=None,
            )

    # And this one is for if they spell the command wrong
    @commands.command()
    async def locust(self, ctx: commands.Context):
        await ctx.send("COMMAND CANCELED!!!!! LOCUST ARMY GO")
        await sendImage(
            "https://www.icpac.net/media/images/ezgif.com-video-to-gif_1.width-800.gif",
            ctx,
        )
        await sendImage(
            "https://www.icpac.net/media/images/ezgif.com-video-to-gif_1.width-800.gif",
            ctx,
        )
        await sendImage(
            "https://www.icpac.net/media/images/ezgif.com-video-to-gif_1.width-800.gif",
            ctx,
        )
        await ctx.send("You probably want !locus")

    # for the card tunak tunak tun
    @commands.command()
    async def tunak(self, ctx: commands.Context):
        tunakTokens = [
            "https://cdn.discordapp.com/attachments/692914661191974912/714795268796579860/Tunak_Tunak_TunW.jpg",
            "https://cdn.discordapp.com/attachments/699985664992739409/711162972248080444/fjmquizxc6y41.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795265197998090/Tunak_Tunak_TunG.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795266758279228/Tunak_Tunak_TunR.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795267756523600/Tunak_Tunak_TunU.jpg",
        ]

        tunakSecretTokens = [
            "https://cdn.discordapp.com/attachments/692431610724745247/717492326653755442/Tunak_Tunak_TunP.jpg",
            "https://cdn.discordapp.com/attachments/692431610724745247/717492325420499005/Tunak_Tunak_Tun_Pink.jpg",
            "https://cdn.discordapp.com/attachments/692431610724745247/717492323675668560/Tunak_Tunak_Tun_Pickle.jpg",
            "https://cdn.discordapp.com/attachments/692431610724745247/717492322253668422/Tunak_Tunak_Tun_Brown.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795268796579860/Tunak_Tunak_TunW.jpg",
            "https://cdn.discordapp.com/attachments/699985664992739409/711162972248080444/fjmquizxc6y41.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795265197998090/Tunak_Tunak_TunG.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795266758279228/Tunak_Tunak_TunR.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795267756523600/Tunak_Tunak_TunU.jpg",
        ]

        if random.randint(0, 100) == 50:
            await sendImage(
                tunakSecretTokens[random.randint(0, len(tunakSecretTokens) - 1)], ctx
            )
        else:
            await sendImage(tunakTokens[random.randint(0, len(tunakTokens) - 1)], ctx)

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
        newKW = keywords
        random.shuffle(newKW)
        msg = ""
        for j in newKW:
            msg += "||" + j + "||,"
        await ctx.send(msg)

    # for the card department of homelands security
    @commands.command()
    async def homelands(self, ctx: commands.Context, cost):
        try:
            homelandsJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=%28type%3Aartifact+OR+type%3Acreature+OR+type%3Aenchantment%29+set%3Ahml+cmc%3D"
                + cost
            )
            await sendImage(await getImageFromJson(homelandsJson), ctx)
        except:
            await ctx.send("Not a valid mana cost.")

    # for the card mythos of hellscube
    @commands.command()
    async def firstPick(self, ctx: commands.Context):
        await sendImage(
            "https://cdn.discordapp.com/attachments/631289553415700492/631292919390928918/md7fop4la1k31.png",
            ctx,
        )

    # https://scryfall.com/random?q=is%3Atoken+type%3Acreature+power%3C%3D2&unique=cards&as=grid&order=name
    # That one guy at your LGS + Hero of High Rollers
    @commands.command()
    async def tokenGuy(self, ctx: commands.Context, count: int = 1):
        for i in range(count):
            token_json = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=is%3Atoken+type%3Acreature+power%3C%3D2&unique=cards&as=grid&order=name"
            )
            await sendImage(await getImageFromJson(token_json), ctx)

    # Obscure Commander
    @commands.command()
    async def obscureCommander(self, ctx: commands.Context):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.scryfall.com/cards/search?as=grid&order=name&q=command+oracle%3A•+%28game%3Apaper%29"
            ) as resp:
                if resp.status != 200:
                    await ctx.send(
                        "Something went wrong while getting the link. Wait for llllll to fix it."
                    )
                    await session.close()
                    return
                response = json.loads(await resp.read())

                mapped = map(lambda x: x["oracle_text"], response["data"])
                joined = "\n".join(list(mapped))
                choiceless = joined.replace("Choose two —\n", "")
                asSplit = choiceless.split("\n")

                results = random.sample(population=asSplit, k=4)
                await ctx.send("Choose two —\n{0}".format("\n".join(results)))
                await session.close()

    # for the card Avatar of BallsJr123
    @commands.command()
    async def avatarOfBalls(self, ctx: commands.Context, cost):
        results = searchFor({"cmc": [(cost, "=")], "types": ["creature"]})
        if results.__len__() == 0:
            await ctx.send("nothing found for that cmc")
        result = random.choice(results)
        print(results.__len__())
        await send_image_reply(
            url=result.img(), cardname=result.name(), text=None, message=ctx.message
        )
        
    # for the card Mystery Inc on Duskmourn
    @commands.command()
    async def randomRoom(self, ctx: commands.Context):
        roomDoors = [
            "https://lh3.googleusercontent.com/d/1vp9mKBQB4R-Jk4cxaZYWm1qz4K43MXt9",
            "https://lh3.googleusercontent.com/d/1CbalIi_IZTg5njwwc2LH7YdwtEdbvhw2",
            "https://lh3.googleusercontent.com/d/1a5mRw_yTxBQBmJQ5Ie0ppdJnPK2vF7Vs",
            "https://lh3.googleusercontent.com/d/1x-JUhJs7i7EzQmU3R-K3zMf4NhXVgzc_",
            "https://lh3.googleusercontent.com/d/1bgNOHggRJFY7l1sVQ1sR132CYc_9Px4y",
            "https://lh3.googleusercontent.com/d/14QmdXxckUwDGqAuRIIRaHn_6pnvT-4va",
            "https://lh3.googleusercontent.com/d/1l8B3MLTS4l_Qf3v6PpDvvvqGZ6ktm4D3",
            "https://lh3.googleusercontent.com/d/1cHfy34p0fQMreBBQuwDozngixvNhdq-y",
            "https://lh3.googleusercontent.com/d/1xtmi50HQ9vG0JjQP8SbB4bOt8DMPj6jw",
            "https://lh3.googleusercontent.com/d/1HzjPQO2tevQxZ1oJURpm-8t6K0EuXiu3",
            "https://lh3.googleusercontent.com/d/1Kf4HSEaaiTtjEBLD53FCG6j-1u0Q1UPx",
            "https://lh3.googleusercontent.com/d/1H_S9zJkltcIzwWcEHfQXSECdqRftAZ20",
            "https://lh3.googleusercontent.com/d/13xhTOvmTb0MKXmmIwyCYD-1btGIb4pHo",
            "https://lh3.googleusercontent.com/d/1ZKJw50o329Xlsn0MJZWwk-ng7RPlbHNL",
            "https://lh3.googleusercontent.com/d/1OQtoB5GNWvSvFZIWQNZoQEB9-TK7GiLj",
            "https://lh3.googleusercontent.com/d/1-LLw8dkyiEe5rGLR4b4Sq2XJnc6w1Qtf",
            "https://lh3.googleusercontent.com/d/17WBoHl2Ddd_STGGOlRGT3cbKt9XeHlFW",
            "https://lh3.googleusercontent.com/d/1heaMz5FPpE9Nw4oUMXoLoJpeTup83Lnd",
            "https://lh3.googleusercontent.com/d/1ikaRaXAhrOIBG9GVxh1v4HhomEJ43PEo",
            "https://lh3.googleusercontent.com/d/1XiCnkhxAF5glf-3fVqi__Ti3mIcH5g8t",
            "https://lh3.googleusercontent.com/d/1eMfd47dCDBD4fjCfXswum8cFlyB1_WG9",
            "https://lh3.googleusercontent.com/d/10ID4g__4FxtXsv26w8aiPHScJ7CWCHAz",
            "https://lh3.googleusercontent.com/d/1knhcoAsq_ks1XIeQ9ULU3TP2qA2zKKJF",
            "https://lh3.googleusercontent.com/d/1nIChCVl4nBSZvQwE__L2BL8dmKL5kkjM",
            "https://lh3.googleusercontent.com/d/1vsNdbHLGsgHRt-UopQGhN2yYJHFmZOKG",
            "https://lh3.googleusercontent.com/d/1Pyuhd7TNTSoqyHUS7STLDyHGIkmtl4XW",
            "https://lh3.googleusercontent.com/d/1sbBscdH-hBCTUhTkMR64vBv9ecgrrmmN",
            "https://lh3.googleusercontent.com/d/1VbdPHeCxfMzoEwSkozuEz-pedEJ8uNTB",
            "https://lh3.googleusercontent.com/d/1qLqNdsVSDNPHiM2c5La5yb9afVePrdZi",
            "https://lh3.googleusercontent.com/d/1h47_N9S9EK1ue0yT0Py1gmw4Mzu4gZUa",
            "https://lh3.googleusercontent.com/d/1WVkYn8JpRAb5xnO58CjRo-BWWebq6iaX",
            "https://lh3.googleusercontent.com/d/1laYXfKUxyBWNOZhcY-Es6cOiuYnAPtI9",
            "https://lh3.googleusercontent.com/d/1Os5oQxk_d6dbNOhe5EobC75-VG_bnqvq",
            "https://lh3.googleusercontent.com/d/1L82lt_S43gMLgnk6ZdBzmd803laeDE8T",
            "https://lh3.googleusercontent.com/d/1WCMAZ4I568oJ01vvc6WsyjnVDAEndbeb",
            "https://lh3.googleusercontent.com/d/1XsF46DRispn1mup2Ev-gKCNIfEbMlOlW",
            "https://lh3.googleusercontent.com/d/1tkdmvBdUACSCoF1rzrrAqu5ZOc7NdrXe",
            "https://lh3.googleusercontent.com/d/1y2SWHu9YmC_zE4eMeok2err4ZbWVJmEG",
            "https://lh3.googleusercontent.com/d/1P9bPds7ZDNVI1epvC84pPsN8C8Tr7eW3",
            "https://lh3.googleusercontent.com/d/1qrFozzJ3UNiEVVTFh0bpAoBQ7FQmWy8t",
            "https://lh3.googleusercontent.com/d/127tPQ5ggauSSfRWE53CUaGo1QOqmX9Ay",
            "https://lh3.googleusercontent.com/d/1_W95bS5JaIbJQjckcMDMRlKjh8iDC13h",
            "https://lh3.googleusercontent.com/d/1_cW7uC4eotBWDNezTUDiLvxtpsFBCKhp",
            "https://lh3.googleusercontent.com/d/1mjgqh5urYC9vP_R0EdYumIRrC_kZDTcY",
            "https://lh3.googleusercontent.com/d/1GvL9xpEQIyxubDysm9i3sxc8-HzJWOU7",
            "https://lh3.googleusercontent.com/d/1oSVCV1NRpCIaRi80qCo90iyfA8CVldlK",
            "https://lh3.googleusercontent.com/d/1PBECum1HzXQygl6Uk7nwbryDsM29oSoy",
            "https://lh3.googleusercontent.com/d/1x1-NDykstTTkrcfrEI1M52i7k4ZQmAPc",
            "https://lh3.googleusercontent.com/d/19IR_1iV2oK83lk3iv8GxemY7FCXDFz5d",
            "https://lh3.googleusercontent.com/d/1E2K3gYHtSr34IB2btFC2QjRevQEyuyBy",
        ]
        rroom = random.randint(0, len(roomDoors) - 1)
        await sendImage(roomDoors[rroom], ctx)
    
    # for the card Hearth Magicbrew (subject to change)
    @commands.command()
    async def history(self, ctx: commands.Context):
        iconicHands = [ #modern jund
            [ "https://cards.scryfall.io/large/front/b/6/b6876d9e-0908-43ac-8542-09c7aa02b5ba.jpg",
             "https://cards.scryfall.io/large/front/9/4/94f7a441-bf2d-46fb-a7b6-9bd6137f86d9.jpg",
             "https://cards.scryfall.io/large/front/a/c/ac506c17-adc8-49c6-9d8d-43db7cb1ec9d.jpg",
             "https://cards.scryfall.io/large/front/3/d/3df8c148-e87d-4043-9d8b-ec72bf8b6d5d.jpg",
             "https://cards.scryfall.io/large/front/7/e/7ef67487-c8e5-49bb-b0f7-e073ff2e31f1.jpg",
             "https://cards.scryfall.io/large/front/f/c/fce07335-cc78-4683-b2f0-9c98a06ea1d8.jpg",
             "https://cards.scryfall.io/large/front/f/2/f281e16f-0fe1-4095-bd63-0a4479f75c11.jpg" ],
            [ #1996 world champ
             "https://cards.scryfall.io/large/front/f/8/f8ac5006-91bd-4803-93da-f87cf196dd2f.jpg",
             "https://cards.scryfall.io/large/front/2/7/2722d7e2-61c6-4934-9c21-875ee78fd06c.jpg",
             "https://cards.scryfall.io/large/front/9/2/92e55b10-375f-4b4f-b676-3b9b8085fdd2.jpg",
             "https://cards.scryfall.io/large/front/f/b/fb4da609-6c08-4a18-b7d9-fb2f9b11bab2.jpg",
             "https://cards.scryfall.io/large/front/e/7/e7880157-7f27-4f1b-9cdc-ab36a6252376.jpg",
             "https://cards.scryfall.io/large/front/b/1/b1623d57-4729-4796-b3f7-f1837a05c6ed.jpg",
             "https://cards.scryfall.io/large/front/b/1/b1623d57-4729-4796-b3f7-f1837a05c6ed.jpg", ],
            [ #caw blade
             "https://cards.scryfall.io/large/front/b/e/beddd409-0154-45a5-a20d-833cf1b5e1f4.jpg",
             "https://cards.scryfall.io/large/front/b/e/beddd409-0154-45a5-a20d-833cf1b5e1f4.jpg",
             "https://cards.scryfall.io/large/front/b/e/beddd409-0154-45a5-a20d-833cf1b5e1f4.jpg",
             "https://cards.scryfall.io/large/front/0/e/0e606072-a3aa-4300-ba90-ec92a721fa76.jpg",
             "https://cards.scryfall.io/large/front/0/3/03cc5caf-b2d7-4211-a1a4-f0ad6e70e3f4.jpg",
             "https://cards.scryfall.io/large/front/9/9/99939b90-e88c-4c2f-ba78-56d455611703.jpg",
             "https://cards.scryfall.io/large/front/4/d/4dc3a90f-23c4-4c54-8825-32cb17977b48.jpg",],
             [ #many rats
             "https://cards.scryfall.io/large/front/1/c/1c9caf97-75c6-4e12-8724-1abe32212bef.jpg",
             "https://cards.scryfall.io/large/front/1/c/1c9caf97-75c6-4e12-8724-1abe32212bef.jpg",
             "https://cards.scryfall.io/large/front/1/c/1c9caf97-75c6-4e12-8724-1abe32212bef.jpg",
             "https://cards.scryfall.io/large/front/1/c/1c9caf97-75c6-4e12-8724-1abe32212bef.jpg",
             "https://cards.scryfall.io/large/front/1/c/1c9caf97-75c6-4e12-8724-1abe32212bef.jpg",
             "https://cards.scryfall.io/large/front/6/b/6bae27d4-9de5-4f95-8c56-79afc6cbeb0c.jpg",
             "https://cards.scryfall.io/large/front/6/b/6bae27d4-9de5-4f95-8c56-79afc6cbeb0c.jpg"],
             [ #eldrazi winter
             "https://cards.scryfall.io/large/front/3/9/3906b61a-3865-4dfd-ae06-a7d2a608851a.jpg",
             "https://cards.scryfall.io/large/front/b/f/bffc360e-db41-48f3-9365-680d55046e04.jpg",
             "https://cards.scryfall.io/large/front/3/1/311a05b1-042d-47e7-9fd7-6e8abe8fc578.jpg",
             "https://cards.scryfall.io/large/front/6/4/64820f4f-1f78-4338-beb8-5ed5a447cfe4.jpg",
             "https://cards.scryfall.io/large/front/5/2/52d4b652-a830-4fd4-94bb-c17c227f2928.jpg",
             "https://cards.scryfall.io/large/front/c/3/c3b21941-1b7d-4fde-8b1d-7edbd5e5b796.jpg",
             "https://cards.scryfall.io/large/front/3/1/315924c9-77e3-405b-9bbf-852ed563c6e3.jpg"],
             [ #early red deck wins
             "https://cards.scryfall.io/large/front/3/7/3707ab74-9aec-4d30-86e0-ffa5f72d5b4f.jpg",
             "https://cards.scryfall.io/large/front/c/a/ca2ecfd4-c874-4468-8601-87aa110d5a00.jpg",
             "https://cards.scryfall.io/large/front/3/1/31415b9b-fb30-4132-a9a3-795b4573a901.jpg",
             "https://cards.scryfall.io/large/front/f/9/f9b2ff2a-6dfe-4635-8da2-22d525e82b94.jpg",
             "https://cards.scryfall.io/large/front/9/9/99ff731b-8399-40c8-b539-ba6ba5783771.jpg",
             "https://cards.scryfall.io/large/front/2/3/23e043bf-a6d7-4778-8460-13bdf38b7d39.jpg",
             "https://cards.scryfall.io/large/front/9/5/9515ced4-b679-48f0-bf62-8b7baef5e1c2.jpg"],
             [ #faeries
             "https://cards.scryfall.io/large/front/4/e/4e5ba4a9-a282-4d4b-b25a-179e05e458f4.jpg",
             "https://cards.scryfall.io/large/front/f/5/f53d8540-fb6d-4d4c-b467-ebfbfa53c880.jpg",
             "https://cards.scryfall.io/large/front/8/1/8145fed6-6b51-420a-84cf-4ea5e0aa1883.jpg",
             "https://cards.scryfall.io/large/front/3/d/3df8c148-e87d-4043-9d8b-ec72bf8b6d5d.jpg",
             "https://cards.scryfall.io/large/front/8/c/8ca3c48b-f104-4292-9a4e-2ce87a65893c.jpg",
             "https://cards.scryfall.io/large/front/9/e/9e4afa65-7933-4a64-b50f-a9a9f832b112.jpg",
             "https://cards.scryfall.io/large/front/9/d/9d91a31c-b70a-45bd-a8dd-48d49b277f24.jpg"],
             [ #tron
             "https://cards.scryfall.io/large/front/7/a/7a235785-b720-483b-bb28-6de440be2129.jpg",
             "https://cards.scryfall.io/large/front/4/4/4499c80b-72af-485c-9106-22967b5252cd.jpg",
             "https://cards.scryfall.io/large/front/8/6/86c6dc88-ef09-4b37-b9e8-c483cccd0e0e.jpg",
             "https://cards.scryfall.io/large/front/f/9/f9287151-95df-4f5a-b32a-4b0aea825452.jpg",
             "https://cards.scryfall.io/large/front/c/5/c55bee97-593f-441f-b96c-a998d5212a55.jpg",
             "https://cards.scryfall.io/large/front/3/3/33672990-4860-4aa6-ac1b-f9da66f5da59.jpg",
             "https://cards.scryfall.io/large/front/1/d/1d7a1357-debd-49b0-9fd5-560d5b3f589e.jpg"],
             [ #UW delver
             "https://cards.scryfall.io/large/front/1/1/11bf83bb-c95b-4b4f-9a56-ce7a1816307a.jpg",
             "https://cards.scryfall.io/large/front/9/e/9e5b279e-4670-4a1e-87d0-3cab7e4f9e58.jpg",
             "https://cards.scryfall.io/large/front/3/5/35b57113-b39a-460b-b4aa-02606b40bbd0.jpg",
             "https://cards.scryfall.io/large/front/7/0/70305148-23bd-41dd-9de5-13cf5ae591ae.jpg",
             "https://cards.scryfall.io/large/front/a/7/a7c7757d-8036-4b33-a1cb-07795d392588.jpg",
             "https://cards.scryfall.io/large/front/b/9/b9d18532-2247-4e33-a760-bc42a727e9f5.jpg",
             "https://cards.scryfall.io/large/front/c/f/cf258641-b73c-4813-8a23-da47cf79eca5.jpg"],
             [ #degenerate urzas saga
             "https://cards.scryfall.io/large/front/6/c/6c877da3-68fa-41d0-8a24-8c79fcd8ecc1.jpg",
             "https://cards.scryfall.io/large/front/0/5/05e9fec4-1e0a-4206-ab2b-cc2543cba667.jpg",
             "https://cards.scryfall.io/large/front/2/8/28028830-83ed-45e2-b495-3b9ad9d3e988.jpg",
             "https://cards.scryfall.io/large/front/a/d/ad7ac9a5-340f-4509-826c-7b9416d47887.jpg",
             "https://cards.scryfall.io/large/front/6/e/6e091dd6-149f-46ea-bae0-224e79e3aacb.jpg",
             "https://cards.scryfall.io/large/front/5/e/5e977755-8ea4-4a8b-90c4-dd175321e05d.jpg",
             "https://cards.scryfall.io/large/front/f/3/f3d62dbd-63db-4ac9-950f-9852627f23f2.jpg"],
             [ #hogaak summer
             "https://cards.scryfall.io/large/front/0/0/0049e68d-0caf-474f-9523-dad343f1250a.jpg",
             "https://cards.scryfall.io/large/front/5/1/51eb9f05-9d5a-4196-9329-626ce4793c42.jpg",
             "https://cards.scryfall.io/large/front/5/2/52c44610-6d4b-4c14-839f-2c085badec90.jpg",
             "https://cards.scryfall.io/large/front/8/1/813104f6-e6e4-4709-8626-12fe4262a11f.jpg",
             "https://cards.scryfall.io/large/front/0/a/0a19da90-880e-4eca-8cf7-6d7baf090d53.jpg",
             "https://cards.scryfall.io/large/front/4/8/48d73cb5-22ac-43df-9c4b-0c860bb80b3e.jpg",
             "https://cards.scryfall.io/large/front/5/f/5faba6c8-3463-47c1-ba01-09eb87fcb2d5.jpg"],
             [ #affinity
             "https://cards.scryfall.io/large/front/9/6/969ebd20-de69-44ba-a0c2-9e2a89480370.jpg",
             "https://cards.scryfall.io/large/front/f/f/ff504dcb-2eb8-4b3c-a8b9-29697739b649.jpg",
             "https://cards.scryfall.io/large/front/e/f/efb965a7-877a-4302-b507-25b0a9e32d9b.jpg",
             "https://cards.scryfall.io/large/front/9/0/90ea95d0-9f95-462b-a080-22a5da7b2e97.jpg",
             "https://cards.scryfall.io/large/front/0/5/056affab-4e2a-4b68-b864-d879becd3c45.jpg",
             "https://cards.scryfall.io/large/front/e/2/e2ab98a1-664c-4775-a3dd-22a15e2f836b.jpg",
             "https://cards.scryfall.io/large/front/7/3/73866487-33f4-4f64-b100-2c4ddadcd74e.jpg"],
             [ #abzan control siege rhino
             "https://cards.scryfall.io/large/front/9/0/9011126a-20bd-4c86-a63b-1691f79ac247.jpg",
             "https://cards.scryfall.io/large/front/8/f/8f7b7598-35b0-4bb5-8347-8c868500f846.jpg",
             "https://cards.scryfall.io/large/front/6/5/65b7275a-5305-42e6-b5c3-8b88568b4e28.jpg",
             "https://cards.scryfall.io/large/front/5/9/596822f6-dbd4-4cc8-aa50-9331ff42544e.jpg",
             "https://cards.scryfall.io/large/front/d/7/d75b4559-8946-45bb-a580-318a13d1e89e.jpg",
             "https://cards.scryfall.io/large/front/2/d/2dd40d90-c939-458a-9a98-27d10da6ff2f.jpg",
             "https://cards.scryfall.io/large/front/0/f/0f14b6b3-5f40-4328-a3be-28fe32dd7cb1.jpg"],
             [ #broko oko
             "https://cards.scryfall.io/large/front/3/4/3462a3d0-5552-49fa-9eb7-100960c55891.jpg",
             "https://cards.scryfall.io/large/front/4/0/4034e5ba-9974-43e3-bde7-8d9b4586c3a4.jpg",
             "https://cards.scryfall.io/large/front/3/0/30377bf0-d9b1-4c14-8dde-f74b1e02d604.jpg",
             "https://cards.scryfall.io/large/front/8/0/801dd9c6-b159-4e1c-af2c-214c1f573633.jpg",
             "https://cards.scryfall.io/large/front/a/a/aa686c34-1c11-469f-93c2-f9891aea521f.jpg",
             "https://cards.scryfall.io/large/front/c/c/cc46739c-290c-4a2d-9301-5ab89727ce37.jpg",
             "https://cards.scryfall.io/large/front/b/b/bb54233c-0844-4965-9cde-e8a4ef3e11b8.jpg"],
             [ #posts
             "https://cards.scryfall.io/large/front/2/f/2f28ecdc-a4f0-4327-a78c-340be41555ee.jpg",
             "https://cards.scryfall.io/large/front/8/b/8b63efb6-249c-4f57-9af1-baffe938520c.jpg",
             "https://cards.scryfall.io/large/front/8/2/82fc9498-7397-4857-87fe-7c9010944ed8.jpg",
             "https://cards.scryfall.io/large/front/6/7/67600383-bbb8-411c-b8e6-2296650bc747.jpg",
             "https://cards.scryfall.io/large/front/e/0/e0b4d4b1-6e25-4c4b-a21a-1b7b1c1d6452.jpg",
             "https://cards.scryfall.io/large/front/f/2/f2e3d197-e978-4ec6-ab69-3c5fd8ac3fc1.jpg",
             "https://cards.scryfall.io/large/front/9/5/95862196-1805-498e-84ee-3c6bbee1a673.jpg"],
             [ # monored aggro standard
             "https://cards.scryfall.io/large/front/4/8/48ace959-66b2-40c8-9bff-fd7ed9c99a82.jpg",
             "https://cards.scryfall.io/large/front/e/e/eef5a0ae-5907-42c9-a097-3f973737e392.jpg",
             "https://cards.scryfall.io/large/front/0/0/0035082e-bb86-4f95-be48-ffc87fe5286d.jpg",
             "https://cards.scryfall.io/large/front/9/2/92c5f0e3-345a-40a8-9cda-565a62156692.jpg",
             "https://cards.scryfall.io/large/front/7/0/7054012b-4f9d-44a0-aaf9-7fd3bddc7b2d.jpg",
             "https://cards.scryfall.io/large/front/0/b/0b384d24-8771-4860-8fc1-1b74217f1c4c.jpg",
             "https://cards.scryfall.io/large/front/0/b/0b384d24-8771-4860-8fc1-1b74217f1c4c.jpg"]
                 ]
        
        #random 1/1001 chance to get channel fireball hand
        selectedHand = random.choice(iconicHands)
        if random.randint(1, 1001) == 1:
            for card in ["https://cards.scryfall.io/large/front/e/a/eace2c85-976c-425e-9800-5a6ccbd91b56.jpg",
                         "https://cards.scryfall.io/large/front/b/0/b0faa7f2-b547-42c4-a810-839da50dadfe.jpg",
                         "https://cards.scryfall.io/large/front/c/1/c1862c47-71cc-45a3-8805-a5ddc62e55ea.jpg",
                         "https://cards.scryfall.io/large/front/b/7/b7623c00-144b-4a8f-9c6c-f5e9e4f65ece.jpg",
                         "https://cards.scryfall.io/large/front/7/8/78a9088f-8755-47cb-aa93-51d992ccab90.jpg",
                         "https://cards.scryfall.io/large/front/7/8/78a9088f-8755-47cb-aa93-51d992ccab90.jpg",
                         "https://cards.scryfall.io/large/front/7/8/78a9088f-8755-47cb-aa93-51d992ccab90.jpg"]:
                await sendImage(card, ctx)
        else:
            for card in selectedHand:
                await sendImage(card, ctx)
 

    # for the card Grunch
    # Original: https://zaxer2.github.io/howtogrunch
    @commands.command()
    async def grunch(self, ctx: commands.Context):
        rules_text_options = [
            (
                "asshole",
                "To Grunch, add a token copy of Grunch to your hand.\n'?' is equal to 3.",
            ),
            (
                "boy",
                "To Grunch, Grunch fights up to one target creature.\n'?' is equal to the number of creatures on the battlefield.",
            ),
            ("chap", "To Grunch, draw a card.\n'?' is equal to four."),
            (
                "dude",
                "To Grunch, create four token copies of Grunch, except they don't have this ability.\n'?' is equal to 1.",
            ),
            (
                "egotist",
                "To Grunch, pay X mana. '?' is equal to 2 to the power of (X+1).",
            ),
            (
                "fella",
                "To Grunch, take an extra turn after this one. Exile grunch.\n'?' is equal to NaN.",
            ),
            (
                "guy",
                "To Grunch, draw two cards.\n'?' is equal to the number of cards in your hand.",
            ),
            (
                "hooligan",
                "To Grunch, do up to seven push-ups in real life.\n'?' is equal to the number of push-ups you did. You are allowed to lie.\nDoing push-ups is a special action and does not use the stack.",
            ),
            (
                "ingrate",
                "To Grunch, attach Grunch to target land you control. Grunch has the abilities of the land he is attached to.\n'?' is equal to the number of lands you control.",
            ),
            (
                "jerk",
                "To Grunch, Put a Grunch counter on Grunch. For as long as Grunch has a Grunch counter, Grunch has 'tap: Grunch.' *(Be sure to revisit tinyurl.com/howtoGRUNCH each time you tap Grunch.)*\n'?' is perpetually equal to one. '?' cannot be changed for the rest of the game.",
            ),
            (
                "killer",
                "To Grunch, destroy up to two target creatures with combined power 5 or less.\n'?' is equal to 2.",
            ),
            (
                "lhurgoyf",
                "To Grunch, mill up to 10 cards.\n'?' is equal to the number of creature types among cards in your graveyard.",
            ),
            (
                "monster",
                "To Grunch, replace target creature's power and toughness numbers with Grunch's power and toughness question marks. *(Use scissors if you have to.)*\n'?' is equal to 0.",
            ),
            (
                "nonce",
                "To Grunch, gain control of up to one target creature with power 3 or less.\n'?' is equal to the number of creatures you control.",
            ),
            (
                "oaf",
                "To Grunch, name a card. Target opponent reveals their hand. If their hand contains the named card, '?' becomes 8. Otherwise, '?' is 4.",
            ),
            (
                "prick",
                "To Grunch, Grunch becomes a token copy of Questing Beast. You may not use a physical token, replacement card, or overlay to represent this. Just use your memory.\n'?' is irrelevant in this instance. Go google the p/t of Questing Beast.",
            ),
            (
                "quack",
                "To Grunch, draw target card in any zone.\n'?' is equal to the number of cards in your hand.",
            ),
            ("ruffian", "To Grunch, create a token copy of Grunch."),
        ]

        flavor_text_options = [
            "'Grunch.' -Grunch",
            "'Grunch?' -Grunch",
            "A grungle saved is a wungle earned.",
            "Grunch? Grunch!! Gruuuuuuunch!!",
            "What the grunch did you just say about me, you little grunch?",
            "I \\*grunch\\* my family!",
            "\\*annoyed grunch\\*",
            "To grunch, or not to grunch?",
            "I am the grunch that is approaching",
            "All signs point to grunch",
            "Grunch again later",
            "A word of advice: grunch.",
            "That'll do, grunch. That'll do.",
            "This one is sentient. If you close the page he will die.",
            "GG stands for Good Grunch. There will be no further questions.",
            "I AM NOT CRAZY.\nI am not crazy! I know he swapped those numbers. I knew it was one. The grunch count starts at \\*one\\*. As if I could ever make such a mistake. Never. Never! I just - I just couldn't prove it. He covered his tracks, he got that idiot on the council to lie for him. You think this is something? You think this is bad? This? This... chicanery? He's done worse. That errata! Are you telling me that a card just happens to change like that? No! \\*He\\* orchestrated it! Grunch! He had no \\*rules text\\*! And we accepted him! We shouldn't have. We took him into our own cube! What was I \\*thinking\\*? He'll never change. He'll \\*never\\* change! Ever since he was drawn, \\*always\\* the same! Couldn't keep himself out of the design contests! But not our Grunch! Couldn't be precious \\*Grunch\\*! Grunching them blind! And \\*HE\\* gets to be a card? What a sick joke! I should've stopped him when I had the chance!\nBut you have to stop him! You-",
            "Ikora's most wanted",
            "(This card is every gender.)",
            "Despite his hostile demeanor, Grunch has his roots deep in the trans community.",
            "Okay, okay. You can have a little grunch. As a treat.",
            "It was Felipe's son, Andre Felipe Felipe, who developed what he called the “Grunching” strategy.",
            "Move your grunch around more.",
            "GG stands for Grunch Grass. There will be no further questions.",
            "Chili dogs?! - Classic Grunch Quote",
            "Blame Gerrit for this one.",
            "Grunch Pro Tip: Hover your mouse over Grunch for his sage words of wisdom.",
            "It's grunchin' time.",
        ]

        default_grunch_image = "https://i.imgur.com/gbFuCzV.png"
        grunch_image_options = [
            "https://i.imgur.com/prDIShY.gif",
            "https://i.imgur.com/xXFJIER.gif",
            "https://i.imgur.com/BaRCH9U.gif",
            "https://i.imgur.com/ZT3ofcu.gif",
            "https://i.imgur.com/7rFA7wX.gif",
            "https://i.imgur.com/K6HXuGT.gif",
        ]

        random_rules_text = random.choice(rules_text_options)
        random_flavor_text = random.choice(flavor_text_options)

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
        message_parts.append(f"-# [original](https://zaxer2.github.io/howtogrunch)")

        await ctx.send("\n".join(message_parts))


async def setup(bot: commands.Bot):
    await bot.add_cog(SpecificCardsCog(bot))
