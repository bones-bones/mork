import random
import re
from typing import Any, List, Literal, cast
import discord
from discord.ext import commands
from random import randrange

from datetime import datetime, timezone, timedelta
from CardClasses import Card, Side, CardSearch
# from cardNameRequest import cardNameRequest
import hc_constants
from hellfall_fetcher import SearchResponse, getCreators, getInfo, getRulings, getSearchFromServer
from isRealCard import isRealCard
from post_card_images import send_image_reply


from shared_vars import intents, allCards, googleClient, cardSheet
from username_mappings import resolve_authors, set_username_mappings, resolve_username

cardDict: dict[str,CardSearch] = {}
""" Maps card ids to cards """

hcidDict: dict[str,str] = {}
""" Maps hcids to card ids """
databaseSheets = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)


notMagicCardSheet = databaseSheets.worksheet("NotMagic")

client = discord.Client(intents=intents)


keys = [
    'hcid',
    'name',
    'image',
    'creators',
    'cardset',
    'legalities',
    'related',
    'rulings',
    'mana_value',
    'colors',
    'mana_cost',
    'supertypes',
    'types',
    'subtypes',
    'power',
    'toughness',
    'loyalty',
    'oracle_text',
    'flavor_text',
    '0image',
    'artists',
    'tags',
    'accepted_order',
    '1mana_cost',
    '1supertypes',
    '1types',
    '1subtypes',
    '1power',
    '1toughness',
    '1loyalty',
    '1oracle_text',
    '1flavor_text',
    '1image',
    '2mana_cost',
    '2supertypes',
    '2types',
    '2subtypes',
    '2power',
    '2toughness',
    '2loyalty',
    '2oracle_text',
    '2flavor_text',
    '2image',
    '3mana_cost',
    '3supertypes',
    '3types',
    '3subtypes',
    '3power',
    '3toughness',
    '3loyalty',
    '3oracle_text',
    '3flavor_text',
    '3image',
    'uuid',
    'oracle_id',
]
rootKeys = [
    'uuid',
    'oracle_id',
    'hcid',
    'name',
    'cardset',
    'accepted_order',
    'image',
    'mana_value',
    'colors',
    'legalities',
    'creators',
    'artists',
    'rulings',
    'tags',
    'sides',
    'related',
]
keyType = Literal[*keys]

def fixEmptyArray(value:list[str]):
    if len(value) == 1 and not value[0]:
        return []
    return value
def getManaValue(mv:str) ->int|float:
    if mv == '∞':
        return 999999999999999
    try:
        return int(mv)
    except ValueError:
        try:
            return float(mv)
        except ValueError:
            return 0

def findLastIndex(lst):
    for i, value in enumerate(reversed(lst)):
        if value:
            return len(lst) - 1 - i
    return -1

def colToFaceNum(index:int):
    for i in range(1,4):
        if index < keys.index(f'{i}mana_cost'):
            return i
    return 4

def build_database():
    global cardDict
    cardDict = {}
    global hcidDict
    hcidDict = {}

    usernameMappingSheet = databaseSheets.worksheet("Username Mappings")
    usernameMappings = usernameMappingSheet.get_all_values()[1:]
    set_username_mappings(usernameMappings)

    cardSheetSearch = databaseSheets.worksheet("Database")
    all_values = cardSheetSearch.get_all_values()
    cardsDataSearch:List[List[Any]] = all_values
    

    for entry in cardsDataSearch:
        def entryAt(key:str)->str:
            return entry[keys.index(key)]
        cardObject:dict[str,Any] = {
            'sides':[],
        }
        for key in rootKeys:
            value = entryAt(key)
            match key:
                case 'creators':
                    cardObject[key] = fixEmptyArray(resolve_authors(value))
                case 'colors' | 'artists' | 'tags' | 'related':
                    cardObject[key] = fixEmptyArray(value.split(';'))
                case 'mana_value':
                    cardObject[key] = getManaValue(value)
                case _:
                    cardObject[key] = value
        newSides = []
        faceNum = colToFaceNum(findLastIndex(entry[:keys.index('uuid')]))
        
        def addPropToFace(key:str,value:Any,index:int):
            while len(newSides) <= index:
                newSides.append({})
            newSides[index][key]=value
            
        for i in range(faceNum):
            for key in [k[1:] for k in keys if k[0] == str(i)]:
                entryList = entryAt(key).split(' // ') if i == 3 else [entryAt(key)]
                for index, item in enumerate(entryList):
                    if (key in ['supertypes', 'types', 'subtypes']):
                        addPropToFace(key,fixEmptyArray(item.split(';')),i+index)
                    else:
                        addPropToFace(key,item,i+index)
        cardObject['sides'] = newSides
        try:
            card = CardSearch(**cardObject)
            cardDict[card.uuid()]=card
            hcidDict[card.hcid()]=card.uuid()
        except Exception as e:
            print(f"couldn't parse {entry}", e)


class HellscubeDatabaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # global log
        build_database()

        global allCards  # Need to modify shared allCards object
        allCards = {uuid: Card(card.uuid(),card.oracleId(),card.hcid(),card.name(),card.image(),card.creators(),card.artists()) for uuid, card in cardDict.items()}

    # okay not technically a DB command
    @commands.command()
    async def randomReject(self, channel, num=0):
        """
        Returns a random card image from #submissions.
        Chooses a random date between the start of submissions and now, then gets history near that date.
        Chooses a random message from that history. If chosen message has no image, calls itself up to 9 more times.
        """
        if num > 9:
            await channel.send("Sorry, no cards were found.")
            return
        subStart = datetime.strptime("5/13/2021 1:30 PM", "%m/%d/%Y %I:%M %p")
        timeNow = datetime.now(timezone.utc)
        timeNow = timeNow.replace(tzinfo=None)
        delta = timeNow - subStart
        intDelta = (delta.days * 24 * 60 * 60) + delta.seconds
        randomSecond = randrange(intDelta)
        randomDate = subStart + timedelta(seconds=randomSecond)
        subChannel = self.bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL)
        subHistory = cast(discord.TextChannel, subChannel).history(around=randomDate)
        subHistory = [message async for message in subHistory]
        randomNum = randrange(1, len(subHistory)) - 1
        if len(subHistory[randomNum].attachments) > 0:
            file = await subHistory[randomNum].attachments[0].to_file()
            await channel.send(content="", file=file)
        else:
            num += 1
            command = self.bot.get_command("randomReject")
            await channel.invoke(command, num)

    @commands.command()
    async def notMagic(self, ctx: commands.Context):
        random_card = random.randint(2, len(notMagicCardSheet.col_values(1)))
        print(random_card)
        name = cast(str, notMagicCardSheet.col_values(1)[random_card])
        img = cast(str, notMagicCardSheet.col_values(2)[random_card])
        ruling = cast(str, notMagicCardSheet.col_values(4)[random_card])
        await send_image_reply(url=img, cardname=name, text=ruling, message=ctx.message)

    @commands.command(name="random")
    async def randomCard(self, ctx: commands.Context):
        """
        Returns a random card image from the database.
        """
        card = allCards[random.choice(list(allCards.keys()))]
        print(card)
        await send_image_reply(
            url=card.getImage(), cardname=card.getName(), message=ctx.message, text=None
        )

    @commands.command()
    async def creator(self, channel, *cardName):
        name = " ".join(cardName).lower()
        response = await getCreators(cardName=name)
        message = 'something went wrong!'
        card = allCards.get(response.uuid)
        name = card.getName() if card else response.name
        creators = card.getCreators() if card else response.creators
        if name is None or creators is None:
            await channel.send(message)
            return
        message = f'{name} created by: {', '.join(creators)}'
        await channel.send(message)

    @commands.command()
    async def syncDb(self, ctx: commands.Context):
        if ctx.author.id == hc_constants.LLLLLL:
            build_database()
            await ctx.send("done")

    @commands.command()
    async def rulings(self, channel, *cardName):
        """
        Returns the rulings for a given card.
        """
        name = " ".join(cardName).lower()
        response = await getRulings(cardName=name)
        message = "something went wrong!"
        card = cardDict.get(response.uuid)
        name = card.name() if card else response.name
        rulings = card.rulings() if card else response.rulings
        if name is None or rulings is None:
            await channel.send(message)
            return
        if not len(rulings):
            message = f'There are no rulings for {name}'
        else:
            rulingsList = rulings.split("\\\\\\")
            message = f'rulings for {name}:{''.join([f'\n```{r}```' for r in rulingsList])}'
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

        if not (await isRealCard(cardName=cardName, ctx=ctx)):
            return

        cardSheetUnapproved = googleClient.open_by_key(
            hc_constants.HELLSCUBE_DATABASE
        ).worksheet(hc_constants.DATABASE_UNAPPROVED)

        allCardNames = cardSheetUnapproved.col_values(2)

        rulings = cardSheetUnapproved.col_values(8)
        lowerList = list(map(lambda x: cast(str, x).lower(), allCardNames))
        if not cardName.lower() in lowerList:
            await ctx.send("Unable to find the card... this shouldn't happen")
            return
        dbRowIndex = lowerList.index(cardName.lower()) + 1

        currentRuling = (
            rulings[dbRowIndex - 1] if rulings.__len__() >= dbRowIndex else ""
        )

        newRuling = (
            f"{currentRuling}\n" if currentRuling != "" else ""
        ) + f"{ruling}- {ctx.author.name} {datetime.today().strftime('%Y-%m-%d')}"

        global cardDict
        for card in cardDict.values():
            # print(card.name())
            if card.name().lower() == cardName.lower():
                card.setRuling(newRuling)
                break

        cardSheetUnapproved.update_cell(
            dbRowIndex,
            8,
            newRuling,
        )

        await ctx.send(f"ruling updated to:\n{newRuling}")

    @commands.command(rest_is_raw=True)
    async def tag(self, ctx: commands.Context, *, args: str):

        card_name = args.split("\n")[0].strip()
        splitLines = args.split("\n")
        if splitLines.__len__() != 2:
            await ctx.send(
                "seems like you're missing a line break or have an extra one"
            )
            return

        tag = splitLines[1].strip()

        if tag.__contains__(" "):
            await ctx.send('no spaces allowed, use "-"')

        if not (await isRealCard(cardName=card_name, ctx=ctx)):
            return

        cardSheetUnapproved = googleClient.open_by_key(
            hc_constants.HELLSCUBE_DATABASE
        ).worksheet(hc_constants.DATABASE_UNAPPROVED)

        allCardNames = cardSheetUnapproved.col_values(2)

        lowerList = list(map(lambda x: cast(str, x).lower(), allCardNames))
        dbRowIndex = lowerList.index(card_name.lower()) + 1

        tags = cardSheetUnapproved.col_values(22)

        currentTags = tags[dbRowIndex - 1] if tags.__len__() >= dbRowIndex else ""

        if tag in str(currentTags).split(";"):
            await ctx.send("card already has that tag")
            return

        cardSheetUnapproved.update_cell(
            dbRowIndex,
            22,
            (f"{currentTags};" if currentTags != "" else "") + f"{tag}",
        )

        global cardDict
        for card in cardDict.values():
            if card.name().lower() == card_name.lower():
                card.addTag(tag=tag)
                break

        await ctx.send("successfully tagged")

    @commands.command(rest_is_raw=True)
    async def removetag(self, ctx: commands.Context, *, args: str):
        cardName = args.split("\n")[0].strip()
        splitLines = args.split("\n")
        if splitLines.__len__() != 2:
            await ctx.send(
                "seems like you're missing a line break or have an extra one"
            )
            return

        tag = splitLines[1].strip()

        if tag.__contains__(" "):
            await ctx.send('no spaces allowed, use "-"')
            return

        if not (await isRealCard(cardName=cardName, ctx=ctx)):
            return

        cardSheetUnapproved = googleClient.open_by_key(
            hc_constants.HELLSCUBE_DATABASE
        ).worksheet(hc_constants.DATABASE_UNAPPROVED)

        allCardNames = cardSheetUnapproved.col_values(2)
        lowerList = list(map(lambda x: cast(str, x).lower(), allCardNames))

        if cardName.lower() not in lowerList:
            await ctx.send("Unable to find the card... this shouldn't happen")
            return

        dbRowIndex = lowerList.index(cardName.lower()) + 1

        tags = cardSheetUnapproved.col_values(22)
        currentTags = tags[dbRowIndex - 1] if tags.__len__() >= dbRowIndex else ""

        currentTagList = [t for t in str(currentTags).split(";") if t != ""]

        if tag not in currentTagList:
            await ctx.send("card does not have that tag")
            return

        newTagList = [t for t in currentTagList if t != tag]
        newTags = ";".join(newTagList)

        cardSheetUnapproved.update_cell(
            dbRowIndex,
            22,
            newTags,
        )

        global cardDict
        for card in cardDict.values():
            if card.name().lower() == cardName.lower():
                card._tags = newTagList
                break

        await ctx.send("successfully removed tag")

    @commands.command()
    async def info(self, channel, *cardName):
        name = " ".join(cardName).lower()
        response = await getInfo(cardName=name)
        message = 'something went wrong!'
        card = allCards.get(response.uuid)
        if (response.info):
            message = response.info
        await channel.send(message)

    @commands.command()
    async def search(self, ctx: commands.Context, query: str):
        print("searching")


        # for i in conditions:
        #     if i.lower()[0:2] == "o:":
        #         if "text" in restrictions.keys():
        #             restrictions["text"].append(i[2:])
        #         else:
        #             restrictions["text"] = [i[2:]]
        #     if i.lower()[0:2] == "f:":
        #         if "flavor" in restrictions.keys():
        #             restrictions["flavor"].append(i[2:])
        #         else:
        #             restrictions["flavor"] = [i[2:]]
        #     if i.lower()[0:2] == "t:":
        #         if "types" in restrictions.keys():
        #             restrictions["types"].append(i[2:])
        #         else:
        #             restrictions["types"] = [i[2:]]
        #     if i.lower()[0:5] == "type:":
        #         if "types" in restrictions.keys():
        #             restrictions["types"].append(i[5:])
        #         else:
        #             restrictions["types"] = [i[5:]]
        #     if i.lower()[0:4] == "tag:":
        #         if "tag" in restrictions.keys():
        #             restrictions["tag"].append(i[4:])
        #         else:
        #             restrictions["tag"] = [i[4:]]
        #     if i.lower()[0:2] == "n:":
        #         if "name" in restrictions.keys():
        #             restrictions["name"].append(i[2:])
        #         else:
        #             restrictions["name"] = [i[2:]]
        #     if i.lower()[0:5] == "from:":
        #         if "creator" in restrictions.keys():
        #             restrictions["creator"].append(i[5:])
        #         else:
        #             restrictions["creator"] = [i[5:]]
        #     if i.lower()[0:2] == "s:":
        #         if "cardset" in restrictions.keys():
        #             restrictions["cardset"].append(i[2:])
        #         else:
        #             restrictions["cardset"] = [i[2:]]
        #     if i.lower()[0:4] == "set:":
        #         if "cardset" in restrictions.keys():
        #             restrictions["cardset"].append(i[4:])
        #         else:
        #             restrictions["cardset"] = [i[4:]]
        #     if i.lower()[0:6] == "legal:":
        #         if "legality" in restrictions.keys():
        #             restrictions["legality"].append(i[6:])
        #         else:
        #             restrictions["legality"] = [i[6:]]
        #     if i.lower()[0:3] == "cmc":
        #         if "cmc" in restrictions.keys():
        #             restrictions["cmc"].append((i[4:], i[3]))
        #         else:
        #             restrictions["cmc"] = [(i[4:], i[3])]
        #     if i.lower()[0:3] == "pow" and i.lower()[3] in "<=>":
        #         if "pow" in restrictions.keys():
        #             restrictions["pow"].append((i[4:], i[3]))
        #         else:
        #             restrictions["pow"] = [(i[4:], i[3])]
        #     if i.lower()[0:5] == "power":
        #         if "pow" in restrictions.keys():
        #             restrictions["pow"].append((i[6:], i[5]))
        #         else:
        #             restrictions["pow"] = [(i[6:], i[5])]
        #     if i.lower()[0:3] == "tou" and i.lower()[3] in ["<", "=", ">"]:
        #         if "tou" in restrictions.keys():
        #             restrictions["tou"].append((i[4:], i[3]))
        #         else:
        #             restrictions["tou"] = [(i[4:], i[3])]
        #     if i.lower()[0:9] == "toughness":
        #         if "tou" in restrictions.keys():
        #             restrictions["tou"].append((i[10:], i[9]))
        #         else:
        #             restrictions["tou"] = [(i[10:], i[9])]
        #     if i.lower()[0:3] == "loy" and i.lower()[3] in "<=>":
        #         if "loy" in restrictions.keys():
        #             restrictions["loy"].append((i[4:], i[3]))
        #         else:
        #             restrictions["loy"] = [(i[4:], i[3])]
        #     if i.lower()[0:7] == "loyalty":
        #         if "loy" in restrictions.keys():
        #             restrictions["loy"].append((i[8:], i[7]))
        #         else:
        #             restrictions["loy"] = [(i[8:], i[7])]
        #     if i.lower()[0] == "c" and i.lower()[1] in "<=>":
        #         if "color" in restrictions.keys():
        #             restrictions["color"].append((i[2:], i[1]))
        #         else:
        #             restrictions["color"] = [(i[2:], i[1])]

        # if restrictions == {}:
        #     return
        # print(restrictions)
        response = await getSearchFromServer(query)

        if response.total_cards > 100:
            await ctx.send(
                f"There were {response.total_cards} results you fucking moron. Go use hellfall or something."
            )
            return
        
        message = printSearchResults(response)
        # if message == "":
        #     message = "Nothing found"
        n = 2000
        messages = [message[i : i + n] for i in range(0, len(message), n)]
        for msg in messages:
            await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(HellscubeDatabaseCog(bot))


# def get_card_by_id(card_id: str) -> CardSearch | None:
#     """Return the CardSearch for the given card ID, or None if not found."""
#     for c in cardList:
#         if str(c.id()) == str(card_id):
#             return c
#     return None


# HCIDs that resolve to "not found" on purpose
# _INFO_JOKE_MISSING_HCIDS = frozenset({"2142", "2972"})


# def format_card_info(card: CardSearch) -> str:
#     hcid = card.hcid()
#     creators = card.creators()
#     cardset = card.cardset()
#     legality = card.legalities()
#     rulings = card.rulings()
#     tags = card.tags()
#     artists = card.artists()
#     to_send = [
#         card.name(),
#         f"id: {hcid}",
#         f"creators: {', '.join(creators)}",
#         f"set: {cardset}",
#         f"legality: {legality}",
#     ]
#     if card.acceptedOrder():
#         to_send.append(f"collector #: {card.acceptedOrder()}")
#     if artists.__len__() > 0:
#         to_send.append(f"artists: {", ".join(artists)}")
#     if tags.__len__() > 0:
#         to_send.append(f"tags: {", ".join(tags)}")
#     if rulings and rulings.__len__() > 0:
#         to_send.append("rulings: \n" + rulings)
#     return "\n".join(to_send)


# def get_card_by_name(card_name: str) -> CardSearch | None:
#     """Return the CardSearch for the given card name, or None if not found."""
#     name_lower = card_name.strip().lower()
#     for c in cardList:
#         if c.name().lower() == name_lower:
#             return c
#     return None


# def searchFor(searchDict: dict):
#     if searchDict.get("creator"):
#         creators = searchDict["creator"]
#         if isinstance(creators, str):
#             creators = [creators]
#         searchDict["creator"] = [resolve_username(c) for c in creators]

#     for i in [
#         "types",
#         "text",
#         "flavor",
#         "name",
#         "creator",
#         "cardset",
#         "legality",
#         "tag",
#     ]:
#         if not i in searchDict.keys():
#             searchDict[i] = None
#     for i in ["cmc", "pow", "tou", "loy", "color"]:
#         if not i in searchDict.keys():
#             searchDict[i] = [(None, None)]
#     hits: list[CardSearch] = []
#     for i in cardList:
#         if "no-fetch" in [t.lower() for t in i.tags()]:
#             continue
#         if (
#             checkForString(
#                 searchDict["types"], list(map(lambda x: x.lower(), i.types()))
#             )
#             and checkForString(
#                 searchDict["tag"], list(map(lambda x: x.lower(), i.tags()))
#             )
#             and checkForString(searchDict["text"], i.oracleText().lower())
#             and checkForString(searchDict["flavor"], i.flavorText().lower())
#             and checkForString(searchDict["name"], i.name().lower())
#             and checkForString(searchDict["creator"], i.creators().lower())
#             and checkForString(searchDict["cardset"], i.cardset().lower())
#             and checkForString(searchDict["legality"], i.legalities().lower())
#         ):
#             if (
#                 checkForInt(searchDict["cmc"], i.manaValue())
#                 and checkForInt(searchDict["tou"], i.toughness())
#                 and checkForInt(searchDict["pow"], i.power())
#                 and checkForInt(searchDict["loy"], i.loyalty())
#             ):
#                 if checkForColor(
#                     searchDict["color"], list(map(lambda x: x.lower(), i.colors()))
#                 ):
#                     hits.append(i)
#     return hits


# def checkForString(condition, data):
#     if type(condition) is str:
#         condition = [condition.lower()]
#     if condition:
#         for j in condition:
#             if not j.lower() in data:
#                 return False
#     return True


# def checkForInt(condition, data):
#     for i in condition:
#         if i[0] != None:
#             number = int(i[0])
#             operator = i[1]
#             if operator == "=":
#                 if not number in list(map(lambda x: int(x), data)):
#                     return False
#             if operator == ">":
#                 works = False
#                 for j in data:
#                     if int(j) > (number):
#                         works = True
#                 if not works:
#                     return False
#             if operator == "<":
#                 works = False
#                 for j in data:
#                     if int(j) < (number):
#                         works = True
#                 if not works:
#                     return False
#     return True


# colorLetterDict = {
#     "w": "white",
#     "u": "blue",
#     "b": "black",
#     "r": "red",
#     "g": "green",
#     "p": "purple",
#     "m": "multicolor",
# }


# def checkForColor(condition, data):
#     if not condition[0][0]:
#         return True
#     allowed = True
#     for requirement in condition:
#         allowedColors = [""]
#         requiredColors = []
#         if requirement[1] == "=":
#             for i in requirement[0]:
#                 if i in colorLetterDict.keys():
#                     requiredColors.append(colorLetterDict[i])
#                     allowedColors.append(colorLetterDict[i])
#         if requirement[1] == ">":
#             for i in requirement[0]:
#                 if i in colorLetterDict.keys():
#                     requiredColors.append(colorLetterDict[i])
#             for i in colorLetterDict.keys():
#                 allowedColors.append(colorLetterDict[i])
#         if requirement[1] == "<":
#             for i in requirement[0]:
#                 if i in colorLetterDict.keys():
#                     allowedColors.append(colorLetterDict[i])
#         for i in requiredColors:
#             if i == "multicolor":
#                 if len(data) < 2:
#                     allowed = False
#             else:
#                 if not i in data:
#                     allowed = False
#         for i in data:
#             if not "m" in requirement[0]:
#                 if not i in allowedColors:
#                     allowed = False
#     return allowed


def printSearchResults(response: SearchResponse):

    returnString = response.details
    if (response.warnings):
        for warning in response.warnings:
            returnString += f'\n{warning}'
    for card in response.data:
        returnString+= f'\n{card.name} ({card.set.replace('_','.')}) {card.collector_number}'    
    return returnString