import pprint as pp
from typing import cast
import discord
from discord.ext import commands
from cardNameRequest import cardNameRequest
from shared_vars import drive
import hc_constants
from discord.utils import get

BlueRed = False
log = ""

custom_deliminator = "$%$%$"


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="dumplog")
    async def _dumplog(self, ctx: commands.Context):
        global log
        if ctx.author.id == hc_constants.LLLLLL:
            with open("log.txt", "a", encoding="utf8") as file:
                file.write(log)
                log = ""
                print("log dumped")

    @commands.command()
    async def BlueRed(self, ctx: commands.Context):
        if ctx.author.id == hc_constants.CIRION:
            global BlueRed
            if BlueRed:
                BlueRed = False
                await ctx.send("Turned Off")
            else:
                BlueRed = True
                await ctx.send("Turned On")
        else:
            await ctx.send("cirion Only Command")

    @commands.command()
    async def ai(self, ctx: commands.Context):
        await ctx.send("¡ai caramba!")

    @commands.command()
    async def help(self, ctx: commands.Context):
        await ctx.send(
            "https://discord.com/channels/631288872814247966/803384271766683668/803389199503982632"
        )

    @commands.command()
    async def menu(self, ctx: commands.Context):
        if (
            ctx.channel.id == hc_constants.RESOURCES_CHANNEL
            or hc_constants.BOT_TEST_CHANNEL
        ):
            embed = discord.Embed(
                title="Resources Menu",
                description="[Channel Explanation](https://discord.com/channels/631288872814247966/803384271766683668/803384426360078336)\n[Command List](https://discord.com/channels/631288872814247966/803384271766683668/803389199503982632)\n[Achievements](https://discord.com/channels/631288872814247966/803384271766683668/803389622247882782)\n[Database](https://discord.com/channels/631288872814247966/803384271766683668/803390530145878057)\n[Release Notes](https://discord.com/channels/631288872814247966/803384271766683668/803390718801346610)\n[Cubecobras](https://discord.com/channels/631288872814247966/803384271766683668/803391239294025748)\n[Tabletop Simulator](https://discord.com/channels/631288872814247966/803384271766683668/803391314095636490)",
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def getMessage(self, ctx: commands.Context, id):
        subChannel = cast(
            discord.TextChannel, self.bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL)
        )
        message = await subChannel.fetch_message(id)
        await ctx.send(message.jump_url)

    @commands.command()
    async def macro(self, ctx: commands.Context, thing: str, *args):
        # print(args)
        if thing == "help":
            message = "Macros are:\nJoke [word]\n"
            for name in hc_constants.macroList.keys():
                if type(hc_constants.macroList[name]) is str:
                    message += f"{name}\n"
                else:
                    message += f"{name}\n"
                    for subname in hc_constants.macroList[name]:
                        message += f"                {subname}\n"
            await ctx.send(message)
            return
        lowerThing = thing.lower()
        if lowerThing in hc_constants.macroList.keys():
            if type(hc_constants.macroList[lowerThing]) is str:
                await ctx.send(
                    hc_constants.macroList[lowerThing].replace("@arg", " ".join(args))
                )
            else:
                pp.pprint(hc_constants.macroList[lowerThing])
                await ctx.send(hc_constants.macroList[lowerThing][args[0].lower()])

    # for card-brazil and card-netherlands
    @commands.command()
    async def goodbye(self, ctx: commands.Context):
        if (
            ctx.channel.id == hc_constants.MAYBE_BRAZIL_CHANNEL
            or ctx.channel.id == hc_constants.MAYBE_ONE_WORD_CHANNEL
        ):
            messages = ctx.channel.history(limit=500)
            messages = [message async for message in messages]
            card = ""
            for i in range(1, len(messages)):
                if messages[i].content.lower().startswith("start"):
                    break
                if messages[i].content != "":
                    if messages[i].content[0] != "(":
                        card = messages[i].content + " " + card
            card = card.replace("/n", "\n")
            cubeChannel = cast(
                discord.TextChannel, self.bot.get_channel(hc_constants.CUBE_CHANNEL)
            )
            await cubeChannel.send(card)
            await ctx.channel.send(card)

    @commands.command()
    async def gameNight(self, ctx: commands.Context, mode, game: str):
        if mode not in [
            "create",
            "list",
            "amount",
            "remove",
            "get",
            "lose",
            "tag",
            "who",
            "search",
        ]:
            return
        if mode == "search":
            options = (
                drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                .GetContentString()
                .replace("\r", "")
                .split("\n")
            )
            userGames = []
            for i in options:
                if custom_deliminator in i:
                    try:
                        user = await self.bot.fetch_user(
                            int(i.split(custom_deliminator)[0])
                        )
                        if game.lower() in user.name.lower():
                            userGames.append(i.split(custom_deliminator)[1])
                    except:
                        ...
            result = "User " + game.lower() + " has roles for the following games\n"
            for i in userGames:
                result += i + "\n"
            if len(userGames) > 0:
                await ctx.send(result)
            else:
                await ctx.send("User has no game roles")

        role_file = drive.CreateFile({"id": hc_constants.GAME_NIGHT_ROLES})
        role_file_content = role_file.GetContentString()

        if mode == "list":
            await ctx.send(role_file_content)
            return

        games = role_file_content.replace("\r", "").split("\n")

        if mode == "create":
            if not game.lower() in games:
                role_file_content = role_file_content + game.lower() + "\n"
                role_file.SetContentString(role_file_content)
                role_file.Upload()
                await ctx.send('Created game "' + game.lower() + '"')
            else:
                await ctx.send("This game already exist.")

        if mode == "amount":
            amount = []
            users = (
                drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                .GetContentString()
                .replace("\r", "")
                .split("\n")
            )
            for x in range(len(games)):
                amount.append(0)
                for i in users:
                    if custom_deliminator in i:
                        if i.split(custom_deliminator)[1] == games[x].lower():
                            amount[x] += 1
            result = "Amount of users per game:\n"
            for i in range(len(amount)):
                result += f"{games[i]: {str(amount[i])}}\n"
            await ctx.send(result)
        if mode == "remove":
            role = get(
                cast(discord.Member, ctx.message.author).guild.roles,
                id=int(631288945044357141),
            )
            if role in cast(discord.Member, ctx.author).roles:
                if game.lower() in games:
                    file2 = drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                    gnPeople = file2.GetContentString()
                    options = gnPeople.replace("\r", "").split("\n")
                    for i in options:
                        if custom_deliminator in i:
                            if i.split(custom_deliminator)[1] == game.lower():
                                options.remove(i)
                    update = "\n".join(options)
                    file2.SetContentString(update)
                    file2.Upload()
                    await ctx.send('Removed role "' + game.lower() + '" from everyone')
                    options = games
                    for i in options:
                        if i == game.lower():
                            options.remove(i)
                    update = "\n".join(options)
                    role_file.SetContentString(update)
                    role_file.Upload()
                    await ctx.send('Removed role "' + game.lower() + '" from existence')
                else:
                    await ctx.send("This game doesn't exist.")
            else:
                await ctx.send(
                    "Removing games is only available to mods, probably tag one of them if you need the game removed."
                )
        if mode == "get":
            if game.lower() in games:
                file = drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                gnPeople = file.GetContentString()
                gnPeople = (
                    gnPeople
                    + str(ctx.author.id)
                    + custom_deliminator
                    + game.lower()
                    + "\n"
                )
                file.SetContentString(gnPeople)
                file.Upload()
                await ctx.send('Gave you game role for game "' + game.lower() + '"')
            else:
                await ctx.send("This game doesn't exist.")
        if mode == "lose":
            if game.lower() in games:
                file = drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                gnPeople = file.GetContentString()
                options = gnPeople.replace("\r", "").split("\n")
                for i in options:
                    if custom_deliminator in i:
                        if (
                            i.split(custom_deliminator)[1] == game.lower()
                            and int(i.split(custom_deliminator)[0]) == ctx.author.id
                        ):
                            options.remove(i)
                            update = "\n".join(options)
                            file.SetContentString(update)
                            file.Upload()
                            await ctx.send(
                                'Removed role "' + game.lower() + '" from you'
                            )
            else:
                await ctx.send("This game doesn't exist.")
        if mode == "tag":
            if game.lower() in games:
                options = (
                    drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                    .GetContentString()
                    .replace("\r", "")
                    .split("\n")
                )
                userIds = []
                for i in options:
                    if custom_deliminator in i:
                        if i.split(custom_deliminator)[1] == game.lower():
                            userIds.append(i.split(custom_deliminator)[0])
                result = "Wanna play a game of " + game.lower() + "\n"
                for i in userIds:
                    result += "<@" + i + ">\n"
                await ctx.send(result)
            else:
                await ctx.send("This game doesn't exist.")
        if mode == "who":
            if game.lower() in games:
                options = (
                    drive.CreateFile({"id": hc_constants.GAME_NIGHT_PEOPLE})
                    .GetContentString()
                    .replace("\r", "")
                    .split("\n")
                )
                userIds = []
                for i in options:
                    if custom_deliminator in i:
                        if i.split(custom_deliminator)[1] == game.lower():
                            userIds.append(i.split(custom_deliminator)[0])
                result = "All people who play " + game.lower() + " are:\n"
                for i in userIds:
                    try:
                        g = await self.bot.fetch_user(i)
                        result += g.name + "\n"
                    except:
                        ...
                await ctx.send(result)
            else:
                await ctx.send("This game doesn't exist.")


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
