import random
import re
from typing import cast
import discord
from discord.ext import commands
from random import randrange

from datetime import datetime, timezone, timedelta
from CardClasses import Card, Side, CardSearch
from cardNameRequest import cardNameRequest
import hc_constants
from printCardImages import sendImageReply


from shared_vars import intents, allCards, googleClient, cardSheet

cardList: list[CardSearch] = []

cardSheetSearch = googleClient.open("Hellscube Database").worksheet("Database")

cardsDataSearch = cardSheetSearch.get_all_values()[3:]

client = discord.Client(intents=intents)


# in theory: cost, super, type, sub, power, toughness, loyalty, text box, flavor text
def genSide(stats: list[str]):
    cost = stats[0]
    supertypes = (stats[1] if stats[1] else "").split(";")
    types = stats[2].split(";")
    subtypes = (stats[3] if stats[3] else "").split(";")

    power = 0
    toughness = 0
    loyalty = 0
    if stats[4] != "" and stats[4] != " ":
        newPower = re.sub(r"[^\d]", "", stats[4])
        power = int(newPower if newPower != "" else "0")
    if stats[5] != "" and stats[5] != " ":
        newToughness = re.sub(r"[^\d]", "", stats[5])
        toughness = int(newToughness if newToughness != "" else "0")
    if stats[6] != "" and stats[6] != " ":
        newLoyalty = re.sub(r"[^\d]", "", stats[6])

        loyalty = int(newLoyalty if newLoyalty != "" else "0")
    text = stats[7]
    flavor = stats[8] if stats.__len__() >= 9 else ""
    return Side(
        cost, supertypes, types, subtypes, power, toughness, loyalty, text, flavor
    )


for entry in cardsDataSearch:
    try:
        name = entry[0]
        img = entry[1]
        creator = entry[2]
        cardset = entry[3]
        legality = entry[4]
        rulings = entry[5]
        cmc = entry[6] if entry[6] else 0
        colors = entry[7].split(";")

        # 8
        sides = []
        sides.append(genSide(entry[8:17]))
        if entry[21] != "" and entry[21] != " ":
            sides.append(genSide(entry[18:26]))
        if entry[29] != "" and entry[29] != " ":
            sides.append(genSide(entry[27:35]))
        if entry[38] != "" and entry[38] != " ":
            sides.append(genSide(entry[36:45]))

        cardList.append(
            CardSearch(
                name, img, creator, cmc, colors, sides, cardset, legality, rulings
            )
        )
    except Exception as e:
        print(f"couldn't parse {entry}", e)


class HellscubeDatabaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # global log
        nameList = cast(list[str], cardSheet.col_values(1)[3:])
        imgList = cardSheet.col_values(2)[3:]
        creatorList = cardSheet.col_values(3)[3:]
        global allCards  # Need to modify shared allCards object

        for i in range(len(nameList)):
            allCards[nameList[i].lower()] = Card(
                nameList[i], imgList[i], creatorList[i]
            )

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

    @commands.command(name="random")
    async def randomCard(self, ctx: commands.Context):
        card = allCards[random.choice(list(allCards.keys()))]

        await sendImageReply(
            url=card.getImg(), cardname=card.getName(), message=ctx.message
        )

    @commands.command()
    async def creator(self, channel, *cardName):
        name = cardNameRequest(" ".join(cardName).lower())
        await channel.send(
            allCards[name].getName() + " created by: " + allCards[name].getCreator()
        )

    @commands.command()
    async def rulings(self, channel, *cardName):
        name = cardNameRequest(" ".join(cardName).lower())
        message = "something went wrong!"
        for card in cardList:
            if card.name().lower() == name:
                rulings = card.rulings()
                rulingsList = rulings.split("\\\\\\")
                if len(rulings) == 0:
                    message = "There are no rulings for " + name
                else:
                    message = f"rulings for {name}:"
                    for i in rulingsList:
                        message = message + "\n```" + i + "```"
        await channel.send(message)

    @commands.command(rest_is_raw=True)
    async def judgement(self, ctx: commands.Context, *, args: str):
        if ctx.channel.id != hc_constants.JUDGES_TOWER:
            await ctx.send("Only allowed in the judge's tower")
            return
        cardName = args.split("\n")[0].strip()
        ruling = args.split("\n")[1].strip()

        name = cardNameRequest(cardName.lower())

        print(f"[{name}], [{cardName.lower()}]")
        if name != cardName.lower():
            await ctx.send(
                f"unable to find an exact match for {cardName}. did you mean: {name}"
            )
            return

        cardSheetUnapproved = googleClient.open_by_key(
            hc_constants.HELLSCUBE_DATABASE
        ).worksheet("Database (Unapproved)")

        allCardNames = cardSheetUnapproved.col_values(1)

        rulings = cardSheetUnapproved.col_values(6)
        lowerList = list(map(lambda x: cast(str, x).lower(), allCardNames))
        dbRowIndex = lowerList.index(cardName.lower()) + 1

        currentRuling = (
            rulings[dbRowIndex - 1] if rulings.__len__() >= dbRowIndex else ""
        )

        newRuling = (
            f"{currentRuling}\n" if currentRuling != "" else ""
        ) + f"{ruling}- {ctx.author.name} {datetime.today().strftime('%Y-%m-%d')}"

        cardSheetUnapproved.update_cell(
            dbRowIndex,
            6,
            newRuling,
        )
        await ctx.send("ruling updated to:\n{newRuling}")

    @commands.command(rest_is_raw=True)
    async def tag(self, ctx: commands.Context, *, args: str):

        cardName = args.split("\n")[0].strip()
        tag = args.split("\n")[1].strip()
        if tag.__contains__(" "):
            await ctx.send('no spaces allowed, use "-"')
        print(tag, ctx.author.name)
        name = cardNameRequest(cardName.lower())
        if name != cardName.lower():
            await ctx.send(
                f"unable to find an exact match for {cardName}. did you mean: {name}"
            )
            return

        cardSheetUnapproved = googleClient.open_by_key(
            hc_constants.HELLSCUBE_DATABASE
        ).worksheet("Database (Unapproved)")

        allCardNames = cardSheetUnapproved.col_values(1)
        tags = cardSheetUnapproved.col_values(18)

        dbRowIndex = allCardNames.index(cardName) + 1

        currentTags = tags[dbRowIndex - 1] if tags.__len__() >= dbRowIndex else ""

        cardSheetUnapproved.update_cell(
            dbRowIndex,
            18,
            (f"{currentTags};" if currentTags != "" else "") + f"{tag}",
        )
        await ctx.send("successfully tagged")

    @commands.command()
    async def info(self, channel, *cardName):
        name = cardNameRequest(" ".join(cardName).lower())
        message = "something went wrong!"
        for card in cardList:
            # print(card.name())
            if card.name().lower() == name:
                creator = card.creator()
                cardset = card.cardset()
                legality = card.legality()
                rulings = card.rulings()
                message = f"{card.name()}\ncreator: {creator}\nset: {cardset}\nlegality: {legality}\nrulings:\n{rulings}"
        await channel.send(message)

    @commands.command()
    async def search(self, ctx: commands.Context, *conditions: str):
        restrictions = {}
        for i in conditions:
            if i.lower()[0:2] == "o:":
                if "text" in restrictions.keys():
                    restrictions["text"].append(i[2:])
                else:
                    restrictions["text"] = [i[2:]]
            if i.lower()[0:2] == "f:":
                if "flavor" in restrictions.keys():
                    restrictions["flavor"].append(i[2:])
                else:
                    restrictions["flavor"] = [i[2:]]
            if i.lower()[0:2] == "t:":
                if "types" in restrictions.keys():
                    restrictions["types"].append(i[2:])
                else:
                    restrictions["types"] = [i[2:]]
            if i.lower()[0:5] == "type:":
                if "types" in restrictions.keys():
                    restrictions["types"].append(i[5:])
                else:
                    restrictions["types"] = [i[5:]]
            if i.lower()[0:2] == "n:":
                if "name" in restrictions.keys():
                    restrictions["name"].append(i[2:])
                else:
                    restrictions["name"] = [i[2:]]
            if i.lower()[0:5] == "from:":
                if "creator" in restrictions.keys():
                    restrictions["creator"].append(i[5:])
                else:
                    restrictions["creator"] = [i[5:]]
            if i.lower()[0:2] == "s:":
                if "cardset" in restrictions.keys():
                    restrictions["cardset"].append(i[2:])
                else:
                    restrictions["cardset"] = [i[2:]]
            if i.lower()[0:4] == "set:":
                if "cardset" in restrictions.keys():
                    restrictions["cardset"].append(i[4:])
                else:
                    restrictions["cardset"] = [i[4:]]
            if i.lower()[0:6] == "legal:":
                if "legality" in restrictions.keys():
                    restrictions["legality"].append(i[6:])
                else:
                    restrictions["legality"] = [i[6:]]
            if i.lower()[0:3] == "cmc":
                if "cmc" in restrictions.keys():
                    restrictions["cmc"].append((i[4:], i[3]))
                else:
                    restrictions["cmc"] = [(i[4:], i[3])]
            if i.lower()[0:3] == "pow":
                if "pow" in restrictions.keys():
                    restrictions["pow"].append((i[4:], i[3]))
                else:
                    restrictions["pow"] = [(i[4:], i[3])]
            if i.lower()[0:3] == "tou":
                if "tou" in restrictions.keys():
                    restrictions["tou"].append((i[4:], i[3]))
                else:
                    restrictions["tou"] = [(i[4:], i[3])]
            if i.lower()[0:3] == "loy":
                if "loy" in restrictions.keys():
                    restrictions["loy"].append((i[4:], i[3]))
                else:
                    restrictions["loy"] = [(i[4:], i[3])]
            if i.lower()[0] == "c" and i.lower()[1] in "<=>":
                if "color" in restrictions.keys():
                    restrictions["color"].append((i[2:], i[1]))
                else:
                    restrictions["color"] = [(i[2:], i[1])]

        if restrictions == {}:
            return

        matchingCards = searchFor(restrictions)
        if matchingCards.__len__() > 100:
            await ctx.send(
                f"There were {matchingCards.__len__()} results you fucking moron. Go use hellfall or something."
            )
            return
        message = printCardNames(matchingCards)
        if message == "":
            message = "Nothing found"
        n = 2000
        messages = [message[i : i + n] for i in range(0, len(message), n)]
        for msg in messages:
            await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(HellscubeDatabaseCog(bot))


def searchFor(searchDict: dict):
    for i in ["types", "text", "flavor", "name", "creator", "cardset", "legality"]:
        if not i in searchDict.keys():
            searchDict[i] = None
    for i in ["cmc", "pow", "tou", "loy", "color"]:
        if not i in searchDict.keys():
            searchDict[i] = [(None, None)]
    hits: list[CardSearch] = []
    for i in cardList:
        if (
            checkForString(
                searchDict["types"], list(map(lambda x: x.lower(), i.types()))
            )
            and checkForString(searchDict["text"], i.text().lower())
            and checkForString(searchDict["flavor"], i.flavor().lower())
            and checkForString(searchDict["name"], i.name().lower())
            and checkForString(searchDict["creator"], i.creator().lower())
            and checkForString(searchDict["cardset"], i.cardset().lower())
            and checkForString(searchDict["legality"], i.legality().lower())
        ):
            if (
                checkForInt(searchDict["cmc"], i.cmc())
                and checkForInt(searchDict["tou"], i.toughness())
                and checkForInt(searchDict["pow"], i.power())
                and checkForInt(searchDict["loy"], i.loyalty())
            ):
                if checkForColor(
                    searchDict["color"], list(map(lambda x: x.lower(), i.colors()))
                ):
                    hits.append(i)
    return hits


def checkForString(condition, data):
    if type(condition) is str:
        condition = [condition.lower()]
    if condition:
        for j in condition:
            if not j.lower() in data:
                return False
    return True


def checkForInt(condition, data):
    for i in condition:
        if i[0] != None:
            number = int(i[0])
            operator = i[1]
            if operator == "=":
                if not number in data:
                    return False
            if operator == ">":
                works = False
                for j in data:
                    if j > number:
                        works = True
                if not works:
                    return False
            if operator == "<":
                works = False
                for j in data:
                    if j < number:
                        works = True
                if not works:
                    return False
    return True


colorLetterDict = {
    "w": "white",
    "u": "blue",
    "b": "black",
    "r": "red",
    "g": "green",
    "p": "purple",
    "m": "multicolor",
}


def checkForColor(condition, data):
    if not condition[0][0]:
        return True
    allowed = True
    for requirement in condition:
        allowedColors = [""]
        requiredColors = []
        if requirement[1] == "=":
            for i in requirement[0]:
                if i in colorLetterDict.keys():
                    requiredColors.append(colorLetterDict[i])
                    allowedColors.append(colorLetterDict[i])
        if requirement[1] == ">":
            for i in requirement[0]:
                if i in colorLetterDict.keys():
                    requiredColors.append(colorLetterDict[i])
            for i in colorLetterDict.keys():
                allowedColors.append(colorLetterDict[i])
        if requirement[1] == "<":
            for i in requirement[0]:
                if i in colorLetterDict.keys():
                    allowedColors.append(colorLetterDict[i])
        for i in requiredColors:
            if i == "multicolor":
                if len(data) < 2:
                    allowed = False
            else:
                if not i in data:
                    allowed = False
        for i in data:
            if not "m" in requirement[0]:
                if not i in allowedColors:
                    allowed = False
    return allowed


def printCardNames(cards):
    returnString = "Results: "
    returnString += str(len(cards)) + "\n"
    for i in cards:
        returnString += i.name() + "\n"
    return returnString
