import re
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
async def sendImage(url, ctx):
    async with aiohttp.ClientSession() as session:
      async with session.get(url) as resp:
        if resp.status != 200:
          await ctx.send('Something went wrong while getting the link. Wait for @llllll to fix it.')
          return
        data = io.BytesIO(await resp.read())
        await ctx.send(file=discord.File(data, url))
        await session.close()

async def sendDriveImage(url,ctx):
    async with aiohttp.ClientSession() as session:
      async with session.get(url) as resp:
        if resp.status != 200:
          await ctx.send('Something went wrong while getting the link. Wait for @llllll to fix it.')
          return
         # currently extraFilename looks like inline;filename="                                Skald.png"
        extraFilename = resp.headers.get("Content-Disposition")  
        parsedFilename = re.findall('inline;filename="(.*)"', str(extraFilename))[0]
        data = io.BytesIO(await resp.read())
        await ctx.send(file = discord.File(data, parsedFilename))
        await session.close()


class SpecificCardsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # for the card item block
    @commands.command()
    async def item(self, ctx):
        items = ["Food", "Treasure", "Clue", "Katana", "Land-Mine"]
        await ctx.send(random.choice(items))

    # for the card shell game
    @commands.command(aliases=['shellgame', 'game'])
    async def shell(self, ctx):
        randomNumber = random.randint(0, 2)
        if randomNumber == 0:
            response = "Plains\nDraw 1 card."
        else:
            response = "Island\nDraw 3 cards."
        await ctx.send(response)

    # for the card big money
    @commands.command(aliases=['big', 'money', 'bigmoney'])
    async def whammy(self, ctx:commands.Context, number):
        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        ### heres some fun stuff if user inputs a negative number
        if number < 0:
            deck = ["Garfield of the Dead", "Swamp (the AB Dual)", "Swamp (the basic)", "[[SwAmp]]", "Tropical 2", "Clockwolf", "Force of Hill", "a Grunch creature token", "Plains"]
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
    async def vow(self, ctx:commands.Context, cost):
        try:
            json = await getScryfallJson("https://api.scryfall.com/cards/random?q=mana%3D" + cost)
            await sendImage(await getImageFromJson(json), ctx)
        except:
            await ctx.send("Not a valid mana cost.")

    # for the card stormstorm
    @commands.command(aliases=['stormstorm'])
    async def storm(self, ctx:commands.Context, number):
        stormCards = [
            "https://img.scryfall.com/cards/normal/front/f/f/ff301010-c9c9-4abb-9bf2-78d123cff292.jpg",
            "https://img.scryfall.com/cards/normal/front/f/f/ff301010-c9c9-4abb-9bf2-78d123cff292.jpg",
            "https://img.scryfall.com/cards/normal/front/f/f/ff301010-c9c9-4abb-9bf2-78d123cff292.jpg",
            "https://img.scryfall.com/cards/normal/front/f/f/ff301010-c9c9-4abb-9bf2-78d123cff292.jpg",
            "https://img.scryfall.com/cards/normal/front/2/e/2ea8d5cb-cf7e-4194-8019-812b3f56cf20.jpg",
            "https://img.scryfall.com/cards/normal/front/3/c/3cd19bdf-64f1-4c59-920b-1165f3551928.jpg",
            "https://img.scryfall.com/cards/normal/front/8/d/8d42d7aa-7f53-4cfc-842a-086aab2448d1.jpg",
            "https://img.scryfall.com/cards/normal/front/b/e/beb755c1-9221-480e-bef9-73f1f13a3345.jpg",
            "https://img.scryfall.com/cards/normal/front/a/2/a2d4ea78-16f1-46ac-8a60-db20c37aad5e.jpg",
            "https://img.scryfall.com/cards/normal/front/d/f/dfe87b59-b456-4532-a695-0dea3110d878.jpg",
            "https://img.scryfall.com/cards/normal/front/2/9/2955a257-302c-48df-9eec-8561cbc8374c.jpg",
            "https://img.scryfall.com/cards/normal/front/7/e/7e573308-40d0-43ce-be04-dbab6bc1ed35.jpg",
        ]
        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        if number < 11:
            for i in range(number):
                await sendImage(stormCards[random.randint(0,len(stormCards)-1)], ctx)
        else:
            await ctx.send("Please use 10 or lower.")

    # for the card keyword warp
    @commands.command(aliases=['keyword', 'warp'])
    async def keywords(self, ctx:commands.Context, number):
        possibleKeywords = ["Deathtouch", "Defender", "Double Strike", "First Strike", "Flash", "Flying", "Haste",
                            "Hexproof", "Indestructible", "Lifelink", "Menace", "Prowess", "Reach", "Trample",
                            "Vigilance", "Ward 1", "Absorb 1", "Afflict 1", "Afterlife 1", "Amplify 1", "Annihilator 1",
                            "Banding", "Battle Cry", "Bloodthirst 1", "Bushido 1", "Cascade", "Changeling", "Convoke",
                            "Delve", "Dethrone", "Devoid", "Evolve", "Exalted", "Exploit", "Extort", "Fading 1", "Fear",
                            "Flanking", "Devour 1", "Dredge 1", "Echo", "Frenzy 1", "Epic", "Graft 1", "Plainswalk",
                            "Mountainwalk", "Forestwalk", "Hideaway", "Horsemanship", "Infect", "Ingest", "Intimidate",
                            "Swampwalk", "Islandhome", "Islandwalk", "Protection from Blue", "Protection from White",
                            "Protection from Red", "Protection from Green", "Protection from Black", "Mentor",
                            "Modular 1", "Persist", "Phasing", "Poisonous 1", "Myriad", "Provoke", "Skulk", "Shadow",
                            "Shroud", "Renown 1", "Soulshift 1", "Rampage 1", "Split Second", "Retrace", "Ripple 1",
                            "Sunburst", "Tribute 1", "Undying", "Unleash", "Vanishing 1", "Wither"]

        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        if number < 101:
            text = ""
            for i in range(number):
                text += possibleKeywords[random.randint(0, len(possibleKeywords) - 1)] + ", "
            await ctx.send(text)
        else:
            await ctx.send("Please use 100 or lower.")

    # for the card path to degeneracy
    @commands.command(aliases=['path', 'degen', 'ptd'])
    async def degeneracy(self, ctx):
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
        degenJson = await getScryfallJson(femaleWarWalkers[random.randint(0, len(femaleWarWalkers) - 1)])
        await ctx.send(degenJson["name"])
        await sendImage(await getImageFromJson(degenJson), ctx)
        await ctx.send(degenJson["oracle_text"])

    # for the card a blue card
    @commands.command(aliases=['blue'])
    async def bluecard(self, ctx):
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
        bluecardJson = await getScryfallJson(blueCards[random.randint(0,len(blueCards)-1)])
        await sendImage(await getImageFromJson(bluecardJson), ctx)

    # for the card wild magic
    @commands.command()
    async def wild(self, ctx):
        wildMagic = [
            "If you roll this text, roll an additional 5 times on the Wild Magic Surge table and gain all that text instead, ignoring this result on subsequent rolls.",
            "Until the end of your next turn, players cast spells as if they were copies of Wild Magic Surge.",
            "Turn all face down creatures face up and manifest all face up creatures. (These are simultaneous.)",
            "Exile all spells on the stack.",
            "Roll a d6. It becomes an X/X Construct artifact creature token named Modron, where X is the number face up on the die.",
            "You gain flying until the end of your next turn. (You can’t be attacked by creatures without flying.)",
            "Wild Magic Surge deals 4 damage to each creature and yourself.",
            "You get an emblem with “Gotcha - Whenever an opponent mentions a real animal (especially pink flamingos, but any will do), they discard a card.”",
            "Cast a copy of Magic Missile.",
            "Regenerate all creatures.",
            "Roll a d6. If the result was even, target creature gets +X/+X until end of turn, where X was the roll. If the result was odd, target creature gets -X/-X until end of turn, where X was the roll.",
            "Discard a card, then draw two cards.",
            "Play a random card from your hand without paying its mana cost. (You are forced to play lands as well.)",
            "Draw 7 cards. At the end of your next turn, discard 7 cards.",
            "Gain 5 life. At the beginning of your next upkeep, gain 5 life.",
            "Draw two cards, then discard a card.",
            "You get an emblem with “Whenever you sneeze, target creature gains flying until end of turn.” (Faking it is boring.)",
            "Create two treasure tokens.",
            "Goad all creatures.",
            "Wild Magic Surge becomes a minigame until end of turn. Play one round of two truths and a lie with all opponents, with you telling the truths and lie. If you win, draw two cards.",
            "Treat the next roll target opponent makes as a 1. Roll a d4.",
            "Take off an item of clothing for the rest of the game. Put it on the battlefield as a 3/2 Clothing artifact creature token.",
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
            "Draw cards equal to your age divided by 10, rounding down.",
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
            "Cast a copy of a random instant or sorcery spell with converted mana cost 2.",
            "Create a token copy of Pheldagriff.",
            "Target opponent renames you. You get an emblem with “Gotcha - Whenever an opponent refers to you by anything but your new name, scry 1, then draw a card.”",
            "Creatures lose all their text boxes until end of turn.",
            "Search your library for a basic land card, reveal it and put it onto the battlefield tapped. Shuffle your library.",
            "Each player gives a card in their hand to an opponent of their choice.",
            "Tap or untap each permanent at random. (Flip a coin for each. This does not count as flipping a coin or rolling a dice for the purpose of effects.)",
            "Support 2, then support your opponent. (To support your opponent, pay them a compliment or tell them how much you respect them.)",
            "Add UURR.",
            "You get an emblem with “Gotcha - Whenever you make an opponent laugh, they sacrifice a creature. If they can’t, they discard a card.”",
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
            "Until the end of your next turn, if a source would deal damage to you, it deals half that damage, rounded down, instead”",
            "Put into your hand a token copy of the Magic: the Gathering card you feel best represents you. (You should prepare this in advance.)",
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
        await ctx.send(str(randomNum) + ": " + wildMagic[randomNum-1])

    # for the card hells triome
    @commands.command()
    async def triome(self, ctx):
        message = ""
        lands = ["Plains", "Mountain", "Forest", "Swamp", "Island"]
        random.shuffle(lands)
        for i in range(3):
            message += lands[i] + ", "
        await ctx.send(message)

    # for the card wrath of pod
    @commands.command()
    async def podcast(self, ctx:commands.Context, number):
        podSentence = ["When @p said @c had good flavor, I lost all respect for them",
                       "The next big mechanic is Devotion to @k.", "@p 2024",
                       "@p is a @s shill! Why do you think they gave @o a good grade?",
                       "i would buy @o if @p hadn't told me it was the worst thing for @f since @c",
                       "@0 - now with 50% less @m! I'm so exited.",
                       "To this day, no one knows why @c was errata'd to give 10 Devotion to Dreadmaw.",
                       "In five years, the only two people still playing @f will be @p and @p",
                       "@c should be a basic, change my mind.", "I heard wizards is trying to make @f a @c exclusive",
                       "Did you see @p's new @c cosplay, it's so hot.",
                       "What's better @k or @es. They're pretty similar.",
                       "@c's next character arc: gain @m to be more like @p", "WOTC stole the idea for @c from @r",
                       "@p is actually a bot programmed by @p", "It was @p with @c in @f.",
                       "Petition to add @es to @c.", "Legend say @b was actually programmed by @p",
                       "@b is now hosted on a server sponsored by @s", "@b is just @b but with more jank",
                       "Move over @c, @c’s the most expensive card in @f now",
                       "Did you hear the latest gossip, @p and @p are having an affair",
                       "@p invited me over for dinner yesterday and all he gave me to eat was @c",
                       "@p has petitioned WotC to name the next function reprint of @c \"@p\"",
                       "There’s this new @m card I keep hearing about called @c, could be good in @f",
                       "Just trust me, @k is totally in @m’s pie", "In my opinion @f is just a worse version of @f.",
                       "I feel @c should be banned in @f.", "Wizards should really make @c but @m.",
                       "@m's part of the color pie is just @c repeated 100 times.",
                       "@c is a good budget replacement for @c.", "I feel @m is too good in @f",
                       "I recently built a new @f deck around @c.",
                       "Why would you ever play @c when you could just be playing @c.",
                       "Would it be too much to ask for @c to have @k.", "@k is the best keyword change my mind.",
                       "i want to see a card thats a combination of @c and @c, maybe even in @m",
                       "If you ever see @c in draft you should insta first pick it.",
                       "I'm building a mono @m cube, with the one exception being @c because it's soo good.",
                       "I can't believe @a is now LGBTQ+ in canon",
                       "At my local game store I met @p, he owned me with his @c deck.",
                       "Did you know @c is supposed to represent @p.",
                       "Did you know that @a is going to be the main character for the next block.", "I stan @a.",
                       "The @f meta is getting overrun with @c.",
                       "I just saw @p's latest stream, I can't believe he said @a wasn't hot.",
                       "I think @c is actually secretly @a.",
                       "I can't believe my opponent countered my @c, I see what @p meant now.",
                       "I feel @c is overrated in @f.", "I feel @c is underrated in @f.",
                       "I heard @p got banned for playing 5 copies of @c in a tournament.",
                       "@r is way too obsessed with @c", "@r is just a more retarded version of @r",
                       "@a should be the mascot of @r", "This podcast has been brought to you by @s",
                       "The next @f tournament will be sponsored by @s", "I can't believe @c is getting banned in @f.",
                       "Did you see the new Arena exclusive card, it's @c but it costs 1 less.",
                       "Did you see the latest cantrip it's a 2 mana @m spell with @es and draw a card.",
                       "Our preview card, it's a @m mythic with @es, @es, @es, @es, @es.",
                       "New planeswalker, +1: @es, -1: @es, @es, -6: @es, @es, @es, @es.",
                       "I'm going to make a @f deck around @c.",
                       "I can't believe @c is getting new promo art on @i but not on @i.",
                       "New card out on @i, robo-@a.", "Why is there so much porn of @a.",
                       "The price of @c spiked after @p made a deck around it.",
                       "@s sent me a booster box of @o and I got @c out of it!",
                       "I can't believe wizards is rereleasing @o as the summer expension.",
                       "I want a fanfiction between @a and @a"]
        podCards = ["Lightning Bolt", "The Unspeakable", "Elder Gargaroth", "Once Upon a Time", "Oko", "Primeval Titan",
                    "Storm Crow", "Force of Will", "Snapcaster Mage", "Black Lotus", "Blood Moon", "Back to Basics",
                    "Timetwister", "Thoughtseize", "Bloodbraid Elf", "Dryad of the Ilysian Grove", "Tarmogoyf",
                    "Sol Ring", "7 Mana Karn", "Thassa's Oricle", "Dig Through Time", "Opt", "Brainstorm", "Fatal Push",
                    "Teferi, Time Raveler", "Walking Ballista", "Uro", "Island", "Leyline of the Void", "Swords",
                    "Lotus Petal", "Delver", "Thalia", "Wasteland", "Strip Mine", "Mox Sapphire", "Pyroblast",
                    "Deathrite Shaman", "Stonecoil Serpent", "Hollow One", "Stinkweed Imp", "Fetch Lands",
                    "Mishra's Workshop", "Mulldrifter", "Dreadmaw", "Healing Salve", "Gut Shot", "One with Nothing",
                    "Siege Rhino", "Winter Orb", "Contract from Below", "AAAAAAAAAAAAAAA", "Mana Tithe", "Goblin Game",
                    "Dark Ritual", "Shock", "Counterspell", "Nekusar, the Mindrazer", "Harmonize",
                    "Borrowing 100.000 Arrows", "Prophet of Kruphix", "Rystic Study", "Teysa Karlov", "Boros Charm",
                    "Grizzly Bear", "Uzra", "Infinity Elemental", "Llanowar Tribe", "Maro's Gone Nuts", "Birds",
                    "Uncle Istvan", "Shahrazad", "Time Walk", "Seasons Beatings", "Thopter Pie Network", "Crow Storm",
                    "Library of Leng", "Alexander Clamilton", "Moat", "Ragnaros the Firelord", "Predator Ooze",
                    "Whale Visions", "Mistform Ultimus", "Lord of Tresserhorn"]
        podKey = ["flying", "horsemanship", "shadow", "epic", "haste", "flash", "phasing", "trample", "annihilator 2",
                  "affinity for artifacts", "cycling 1", "embalm 1W", "exalted", "persist", "infect", "provoke",
                  "prowess", "mentor", "rebound", "undying", "slivercycling", "storm", "gravestorm", "fear"]
        podProduct = ["From the vault: Dreadmaw", "From the vault: Annihilation", "Secret Lair: Fetch lands",
                      "Signiture Spellbook: @a", "a Homelands booster box", "a vintage masters booster box",
                      "p3k starter kit", "@p's global deck", "Dragons Maze fat pack", "War of the Spark mythic edition",
                      "kamigawa block pauper tiny leaders challenger decks", "brawl precons", "@o VIP Edition"]
        podFormat = ["hellscube sealed", "modern", "legacy", "pauper", "pioneer", "frontier",
                     "kamigawa block pauper tiny leaders", "commander", "cEDH", "standard", "big deck", "judge's tower",
                     "chaos draft", "brawl", "oathbreaker", "vintage", "five-headed giant", "momir basic",
                     "three card vintage", "tiny leaders", "emperor", "usurper", "horde", "prismatic"]
        podColor = ["white", "black", "green", "red", "blue"]
        podPerson = ["EpicNessBrian", "MaRo", "Trump", "Exalted", "Ballsjr123", "Putin", "LSV", "Desolator Magic",
                     "Pleasant Kenobi", "Rystic Studies", "Spice8Rack", "Josh Lee Kwai", "The Proffesor",
                     "Saffron Olive", "Jon Finkle", "Kibler", "RoboRosewater"]
        podCharacter = ["Urza", "Nicol Bolas", "Ugin", "Teferi", "Chandra", "Jace", "Nissa", "Niv Mizzet", "Rakdos",
                        "Kaya", "Fblthp", "Yargle", "K'rrik", "Alexander Clamilton", "Uncle Istvan", "Emrakul",
                        "Ulamog", "Kozilek", "Darigaaz", "Stangg Twin", "Rakdos", "Vivian", "Azusa", "Doran",
                        "Grandmother Sengir", "Angus Mackenzie", "Joven", "Oko", "The Elk Form of Kenrith",
                        "the amalgam between Will and Rowan Kenrith", "Mklthd", "Bresela", "Frankie Peanuts",
                        "Ihsan's Shade"]
        podReddit = ["r/Hellscube", "r/custommagic", "r/MagicTheCircleJerking", "r/MTGLardFetcher", "r/MagicTCG",
                     "r/ShittyJudgeQuestions", "r/MTGpauper", "r/EDH", "r/unbantwin", "r/MagicArena",
                     "r/MagicDeckBuilding", "r/spikes", "r/mtgfinance", "r/mtgporn", "r/ModernMagic",
                     "r/CompetitiveEDH", "r/MtgJudge", "r/MTGVintage", "r/Pauper", "r/freemagic", "r/MTGLegacy",
                     "r/MakingMagic"]
        podSponsor = ["Audible", "Raid Shadow Legends", "WOTC", "Dollar Shave Club", "the @r moderators",
                      "@p's youtube channel", "Lords Mobile", "Generic Mobile Game #263"]
        podSmallEffect = ["Deal 2 damage to any target", "Draw a card", "Search you library for a card named @c.",
                          "Gain 2 life.", "Target player discards a card", "Exile target card from a graveyard",
                          "Create a 2/2 zombie token", "counter target spell unless it's controller pays 1",
                          "Target creature gets +3/+3 until and of turn", "Look at target players hand",
                          "Mill target player for 3", "scry 2", "Creatures you control get lifelink until end of turn",
                          "Permanents enter the battlefield tapped this turn",
                          "You may play an additional land this turn", "Tap target creature", "Draw 3 cards",
                          "Discard 2 cards", "Destroy target permanent",
                          "Return up to one target land card from your graveyard to your hand",
                          "Target player sacrifices a creature",
                          "creature a 4/4 blue Elemental Bird creature token with flying", "Create 2 food tokens",
                          "Until your next turn, you may cast spells as though they had flash", "Add RR",
                          "Create 2 1/1 white Human Soldier tokens.", "Freeze the stack until your next turn",
                          "target opponent antes a card from their hand",
                          "Target creature gains haste, haste and haste"]
        podClient = ["paper", "moto", "arena", "duals of the planeswalkers 2015", "puzzlequest", "shandelar",
                     "the magic origens client", "cockatrice", "battlenet", ]
        podBulk = ["Eon Storm", "Arashin Sovereign"]
        podBot = ["Scryfall", "FatesealRise", "ExploreAside", "SurvielStill", "RippleApproach"]

        podEncoding = [("@f", podFormat), ("@c", podCards), ("@m", podColor), ("@k", podKey), ("@o", podProduct),
                       ("@p", podPerson), ("@es", podSmallEffect), ("@i", podClient), ("@a", podCharacter),
                       ("@r", podReddit), ("@s", podSponsor), ("@b", podBot)]

        try:
            number = int(number)
        except:
            await ctx.send("Please type a number.")
            return
        if number > 20:
            await ctx.send("Please type a number 20 or lower.")
            return
        output = ""
        for i in range(number):
            output += podSentence[random.randint(0, len(podSentence) - 1)]
            while "@" in output:
                for key in podEncoding:
                    output = output.replace(key[0], key[1][random.randint(0, len(key[1]) - 1)], 1)
            output += "\n"
        await ctx.send(output)

    # for the card pyrohyperspasm
    @commands.command()
    async def pyrohyperspasm(self, ctx:commands.Context, number, buttPlug=False, *creatures):
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
            State.extend([[4 + buttPlug, 2 + buttPlug], [2 + buttPlug, 3 + buttPlug], [6 + buttPlug, 1 + buttPlug], ])
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
                result += State[i][2] + ": " + str(State[i][0]) + "/" + str(State[i][1]) + "\n"
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
        await ctx.send("Total (new) stats: (" + str(totalPower) + "/" + str(totalToughness) + ")")

    # for the card puzzle box of yogg-saron
    @commands.command(aliases=['puzzle', 'box', 'pbox', 'yogg', 'yoggsaron', 'pb'])
    async def puzzlebox(self, ctx):
        for i in range(10):
            json = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Ainstant+or+t%3Asorcery")
            await sendImage(await getImageFromJson(json), ctx)

    # for the card deathseeker
    @commands.command()
    async def death(self, ctx):
        for i in range(2):
            deathseekerJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=o%3A%22When+~+dies%22+t%3Acreature")
            try:
                await sendImage(await getImageFromJson(deathseekerJson), ctx)
            except:
                pp.pprint(deathseekerJson)

    # for the card multiverse broadcasting station
    @commands.command()
    async def broadcast(self, ctx):
        for i in range(2):
            broadcastJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=-type%3Anarset+type%3Aplaneswalker+rarity%3Au")
            try:
                await sendImage(await getImageFromJson(broadcastJson), ctx)
            except:
                pp.pprint(broadcastJson)

    # for the card illusionary GF
    @commands.command(aliases=['gf', 'chandra'])
    async def girlfriend(self, ctx):
        GFJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Achandra+t%3Aplaneswalker")
        try:
            await sendImage(await getImageFromJson(GFJson), ctx)
        except:
            pp.pprint(GFJson)

    # for the card ballsjrs ultimate curvetopper
    @commands.command()
    async def topper(self, ctx:commands.Context, amount):
        if int(amount) > 10:
            await ctx.send("max is 10")
            return
        for i in range(int(amount)):
            topperJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=mana%3E%3DX")
            try:
                await sendImage(await getImageFromJson(topperJson), ctx)
            except:
                pp.pprint(topperJson)

    # for the card obscure command
    @commands.command()
    async def obscure(self, ctx):
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
    async def weird(self, ctx):
        modes = ["Colorless", "White", "Blue", "Black", "Red", "Green"]
        for _ in range(2):
            await ctx.send(random.choice(modes))

    # for the card absurdly cryptic command
    @commands.command()
    async def cryptic(self, ctx):
        for i in range(4):
            crypticJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=c%21u+t%3Ainstant")
            await sendImage(await getImageFromJson(crypticJson), ctx)

    # for the card we need more white cards
    @commands.command()
    async def whitecards(self, ctx):
        for i in range(3):
            whitecardsJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=c=w")
            await sendImage(await getImageFromJson(whitecardsJson), ctx)

    # for the card hugh man, human
    @commands.command(aliases=['hugh', 'human'])
    async def hughman(self, ctx):
        hughmanJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Ahuman")
        await sendImage(await getImageFromJson(hughmanJson), ctx)

    # for the card random growth
    @commands.command()
    async def growth(self, ctx):
        growthJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Aland")
        await sendImage(await getImageFromJson(growthJson), ctx)

    # for the card ultimate ultimatum
    @commands.command()
    async def ultimatum(self, ctx):
        ultimatumJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=name%3Dultimatum+-c%3Awug")
        await sendImage(await getImageFromJson(ultimatumJson), ctx)

    # for the card regal karakas
    @commands.command()
    async def karakas(self, ctx):
        karakasJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Dcreature+t%3Dlegendary")
        await sendImage(await getImageFromJson(karakasJson), ctx)

    # for the card pregnant sliver
    @commands.command()
    async def sliver(self, ctx):
        sliverJson = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Asliver")
        await sendImage(await getImageFromJson(sliverJson), ctx)

    # for the card a black six drop
    @commands.command()
    async def black6(self, ctx):
        black6Json = await getScryfallJson("https://api.scryfall.com/cards/random?q=t%3Acreature+c%21b+cmc%3A6")
        await sendImage(await getImageFromJson(black6Json), ctx)

    # for the card kodama's reach but kodama has really long arms
    @commands.command()
    async def reach(self, ctx):
        lands = ["Plains", "Mountain", "Forest", "Swamp", "Island"]
        random.shuffle(lands)
        for i in range(2):
            await ctx.send(lands[i])

    # for the card colossal godmaw
    @commands.command()
    async def dreadmaw(self, ctx): 
        await sendDriveImage(
            "https://lh3.googleusercontent.com/d/1uYdnTLOZw42yNGc3xgO0oxhBGwoReo-c",
            ctx)

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
           "https://lh3.googleusercontent.com/d/1Vo79t5JiEL_vodhXBj8m4z5M4H2xwgU9"]
       selected = random.sample(stickersheets, k=3)
       for sheet in selected:
           await sendDriveImage(sheet, ctx)

    # for the card tunak tunak tun
    @commands.command()
    async def tunak(self, ctx):
        tunakTokens = [
            "https://cdn.discordapp.com/attachments/692914661191974912/714795268796579860/Tunak_Tunak_TunW.jpg",
            "https://cdn.discordapp.com/attachments/699985664992739409/711162972248080444/fjmquizxc6y41.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795265197998090/Tunak_Tunak_TunG.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795266758279228/Tunak_Tunak_TunR.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795267756523600/Tunak_Tunak_TunU.jpg"]

        tunakSecretTokens = [
            "https://cdn.discordapp.com/attachments/692431610724745247/717492326653755442/Tunak_Tunak_TunP.jpg",
            "https://cdn.discordapp.com/attachments/692431610724745247/717492325420499005/Tunak_Tunak_Tun_Pink.jpg",
            "https://cdn.discordapp.com/attachments/692431610724745247/717492323675668560/Tunak_Tunak_Tun_Pickle.jpg",
            "https://cdn.discordapp.com/attachments/692431610724745247/717492322253668422/Tunak_Tunak_Tun_Brown.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795268796579860/Tunak_Tunak_TunW.jpg",
            "https://cdn.discordapp.com/attachments/699985664992739409/711162972248080444/fjmquizxc6y41.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795265197998090/Tunak_Tunak_TunG.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795266758279228/Tunak_Tunak_TunR.jpg",
            "https://cdn.discordapp.com/attachments/692914661191974912/714795267756523600/Tunak_Tunak_TunU.jpg"]

        if random.randint(0, 100) == 50:
            await sendImage(tunakSecretTokens[random.randint(0, len(tunakSecretTokens) - 1)], ctx)
        else:
            await sendImage(tunakTokens[random.randint(0, len(tunakTokens) - 1)], ctx)

    # for cards with crystallize
    @commands.command()
    async def crystallize(self, ctx):
        keywords = ["flying", "first strike", "deathtouch", "hexproof", "lifelink", "menace", "reach", "trample",
                    "vigilance", "+1/+1"]
        newKW = keywords
        random.shuffle(newKW)
        msg = ""
        for j in newKW:
            msg += ("||" + j + "||,")
        await ctx.send(msg)

    # for the card department of homelands security
    @commands.command()
    async def homelands(self, ctx:commands.Context, cost):
        try:
            homelandsJson = await getScryfallJson(
                "https://api.scryfall.com/cards/random?q=%28type%3Aartifact+OR+type%3Acreature+OR+type%3Aenchantment%29+set%3Ahml+cmc%3D" + cost)
            await sendImage(await getImageFromJson(homelandsJson), ctx)
        except:
            await ctx.send("Not a valid mana cost.")

    # for the card mythos of hellscube
    @commands.command()
    async def firstPick(self, ctx):
        await sendImage(
            "https://cdn.discordapp.com/attachments/631289553415700492/631292919390928918/md7fop4la1k31.png", ctx)
    
async def setup(bot:commands.Bot):
    await bot.add_cog(SpecificCardsCog(bot))
