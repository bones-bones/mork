import random
from typing import Optional, cast#, Literal
import discord
from discord.ext import commands
from random import randrange

from datetime import datetime, timezone, timedelta
# from CardClasses import Card, Side, CardSearch
# from cardNameRequest import cardNameRequest
import hc_constants
from hellfall_changesets import modifyTagWithServer
from hellfall_fetcher import SearchResponse, getCreators, getExactCard, getInfo, getRandomFromServer, getRulings, getSearchFromServer
# from isRealCard import isRealCard
from post_card_images import send_image_reply


from shared_vars import intents, googleClient#, cardSheet
# from username_mappings import resolve_authors, set_username_mappings, resolve_username

# cardDict: dict[str,CardSearch] = {}
# """ Maps card ids to cards """

# hcidDict: dict[str,str] = {}
# """ Maps hcids to card ids """
databaseSheets = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE)


notMagicCardSheet = databaseSheets.worksheet("NotMagic")

client = discord.Client(intents=intents)

def getUnapprovedCardSheet():
    return googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet(hc_constants.DATABASE_UNAPPROVED)

# keys = [
#     'hcid',
#     'name',
#     'image',
#     'creators',
#     'cardset',
#     'legalities',
#     'related',
#     'rulings',
#     'mana_value',
#     'colors',
#     'mana_cost',
#     'supertypes',
#     'types',
#     'subtypes',
#     'power',
#     'toughness',
#     'loyalty',
#     'oracle_text',
#     'flavor_text',
#     '0image',
#     'artists',
#     'tags',
#     'accepted_order',
#     '1mana_cost',
#     '1supertypes',
#     '1types',
#     '1subtypes',
#     '1power',
#     '1toughness',
#     '1loyalty',
#     '1oracle_text',
#     '1flavor_text',
#     '1image',
#     '2mana_cost',
#     '2supertypes',
#     '2types',
#     '2subtypes',
#     '2power',
#     '2toughness',
#     '2loyalty',
#     '2oracle_text',
#     '2flavor_text',
#     '2image',
#     '3mana_cost',
#     '3supertypes',
#     '3types',
#     '3subtypes',
#     '3power',
#     '3toughness',
#     '3loyalty',
#     '3oracle_text',
#     '3flavor_text',
#     '3image',
#     'uuid',
#     'oracle_id',
# ]
# rootKeys = [
#     'uuid',
#     'oracle_id',
#     'hcid',
#     'name',
#     'cardset',
#     'accepted_order',
#     'image',
#     'mana_value',
#     'colors',
#     'legalities',
#     'creators',
#     'artists',
#     'rulings',
#     'tags',
#     'sides',
#     'related',
# ]
# keyType = Literal[*keys]

# def fixEmptyArray(value:list[str]):
#     if len(value) == 1 and not value[0]:
#         return []
#     return value
# def getManaValue(mv:str) ->int|float:
#     if mv == '∞':
#         return 999999999999999
#     try:
#         return int(mv)
#     except ValueError:
#         try:
#             return float(mv)
#         except ValueError:
#             return 0

# def findLastIndex(lst):
#     for i, value in enumerate(reversed(lst)):
#         if value:
#             return len(lst) - 1 - i
#     return -1

# def colToFaceNum(index:int):
#     for i in range(1,4):
#         if index < keys.index(f'{i}mana_cost'):
#             return i
#     return 4
# do I still need this?
# def build_database():
#     global cardDict
#     cardDict = {}
#     global hcidDict
#     hcidDict = {}

#     usernameMappingSheet = databaseSheets.worksheet("Username Mappings")
#     usernameMappings = usernameMappingSheet.get_all_values()[1:]
#     set_username_mappings(usernameMappings)

#     cardSheetSearch = databaseSheets.worksheet("Database")
#     all_values = cardSheetSearch.get_all_values()
#     cardsDataSearch:List[List[Any]] = all_values
    

#     for entry in cardsDataSearch:
#         def entryAt(key:str)->str:
#             return entry[keys.index(key)]
#         cardObject:dict[str,Any] = {
#             'sides':[],
#         }
#         for key in rootKeys:
#             value = entryAt(key)
#             match key:
#                 case 'creators':
#                     cardObject[key] = fixEmptyArray(resolve_authors(value))
#                 case 'colors' | 'artists' | 'tags' | 'related':
#                     cardObject[key] = fixEmptyArray(value.split(';'))
#                 case 'mana_value':
#                     cardObject[key] = getManaValue(value)
#                 case _:
#                     cardObject[key] = value
#         newSides = []
#         faceNum = colToFaceNum(findLastIndex(entry[:keys.index('uuid')]))
        
#         def addPropToFace(key:str,value:Any,index:int):
#             while len(newSides) <= index:
#                 newSides.append({})
#             newSides[index][key]=value
            
#         for i in range(faceNum):
#             for key in [k[1:] for k in keys if k[0] == str(i)]:
#                 entryList = entryAt(key).split(' // ') if i == 3 else [entryAt(key)]
#                 for index, item in enumerate(entryList):
#                     if (key in ['supertypes', 'types', 'subtypes']):
#                         addPropToFace(key,fixEmptyArray(item.split(';')),i+index)
#                     else:
#                         addPropToFace(key,item,i+index)
#         cardObject['sides'] = newSides
#         try:
#             card = CardSearch(**cardObject)
#             cardDict[card.uuid()]=card
#             hcidDict[card.hcid()]=card.uuid()
#         except Exception as e:
#             print(f"couldn't parse {entry}", e)


class HellscubeDatabaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     # still necessary?
    #     # global log
    #     build_database()

    #     global allCards  # Need to modify shared allCards object
    #     allCards = {uuid: Card(card.uuid(),card.oracleId(),card.hcid(),card.name(),card.image(),card.creators(),card.artists()) for uuid, card in cardDict.items()}

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
        """ Returns a random card from #this-isnt-magic """
        random_card = random.randint(2, len(notMagicCardSheet.col_values(1)))
        print(random_card)
        name = cast(str, notMagicCardSheet.col_values(1)[random_card])
        img = cast(str, notMagicCardSheet.col_values(2)[random_card])
        ruling = cast(str, notMagicCardSheet.col_values(4)[random_card])
        await send_image_reply(url=img, cardname=name, text=ruling, message=ctx.message)

    @commands.command(name="random")
    async def randomCard(self, ctx: commands.Context, query:Optional[str]):
        """
        Returns a random card image from the database.
        Can accept a search query to narrow the search.
        """
        response = await getRandomFromServer(query)
        await send_image_reply(
            url=response.image, cardname=response.name, message=ctx.message, text=None
        )

    @commands.command()
    async def creator(self, channel, *cardName):
        name = " ".join(cardName).lower()
        response = await getCreators(name)
        message = f'{response.name} created by: {', '.join(response.creators)}'
        await channel.send(message)

    # @commands.command()
    # async def syncDb(self, ctx: commands.Context):
    #     if ctx.author.id == hc_constants.LLLLLL:
    #         build_database()
    #         await ctx.send("done")

    @commands.command()
    async def rulings(self, channel, *cardName):
        """
        Returns the rulings for a given card.
        """
        name = " ".join(cardName).lower()
        response = await getRulings(name)
        message = "something went wrong!"
        name = response.name
        rulings = response.rulings
        if not rulings:
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
        response = await getExactCard(cardName)        

        cardSheetUnapproved = getUnapprovedCardSheet()
        cell = cardSheetUnapproved.find(response.hcid,in_column=1)
        if not cell:
            await ctx.send("Unable to find the card... this shouldn't happen")
            return
        cell.row
        currentRuling = cardSheetUnapproved.cell(cell.row, 8)

        newRuling = (
            f"{currentRuling}\n" if currentRuling != "" else ""
        ) + f"{ruling}- {ctx.author.name} {datetime.today().strftime('%Y-%m-%d')}"

        # global cardDict
        # for card in cardDict.values():
        #     # print(card.name())
        #     if card.name().lower() == cardName.lower():
        #         card.setRuling(newRuling)
        #         break

        cardSheetUnapproved.update_cell(
            cell.row,
            8,
            newRuling,
        )

        await ctx.send(f"ruling updated to:\n{newRuling}")

    @commands.command(rest_is_raw=True)
    async def tag(self, ctx: commands.Context, *, args: str):
        """ Adds a tag. Uses the same process as on hellfall. """
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

        message = await modifyTagWithServer(cardName, tag, 'add')

        await ctx.send(message)

    @commands.command(rest_is_raw=True)
    async def removetag(self, ctx: commands.Context, *, args: str):
        """ Removes a tag. Uses the same process as on hellfall. """
        cardName = args.split("\n")[0].strip()
        splitLines = args.split("\n")
        if splitLines.__len__() != 2:
            await ctx.send(
                "seems like you're missing a line break or have an extra one"
            )
            return

        tag = splitLines[1].strip()


        message = await modifyTagWithServer(cardName, tag, 'delete')

        await ctx.send(message)

    @commands.command()
    async def info(self, channel, *cardName):
        name = " ".join(cardName).lower()
        response = await getInfo(cardName=name)
        message = 'something went wrong!'
        if (response.info):
            message = response.info
        await channel.send(message)

    @commands.command()
    async def search(self, ctx: commands.Context, query: str):
        response = await getSearchFromServer(query)

        if response.total_cards > 100:
            await ctx.send(
                f"There were {response.total_cards} results you fucking moron. Go use hellfall or something."
            )
            return
        
        message = formatSearchResults(response)
        # if message == "":
        #     message = "Nothing found"
        n = 2000
        messages = [message[i : i + n] for i in range(0, len(message), n)]
        for msg in messages:
            await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(HellscubeDatabaseCog(bot))

def formatSearchResults(response: SearchResponse):
    returnString = response.details
    if (response.warnings):
        for warning in response.warnings:
            returnString += f'\n{warning}'
    for card in response.data:
        returnString+= f'\n{card.name} ({card.set.replace('_','.')}) {card.collector_number}'
    return returnString