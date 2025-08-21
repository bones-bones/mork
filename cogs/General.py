import pprint as pp
from typing import cast
import discord
from discord.ext import commands
from cardNameRequest import cardNameRequest
from shared_vars import drive
import hc_constants
from discord.utils import get
import random
from datetime import date, datetime, timezone

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

    @commands.command()
    async def wait(self, ctx: commands.Context):
        # From https://www.resiliencelab.us/thought-lab/self-care-ideas
        possibleActivities = ["start a gratitude journal and write down three things you’re thankful for every day.",
        "practice deep breathing exercises to calm your mind.",
        "schedule a therapy session to work through emotions and challenges.",
        "set boundaries by saying no to things that overwhelm you.",
        "try a guided meditation app for relaxation.",
        "watch or listen to a mental health podcast or documentary.",
        "write a letter to your future self about your goals and dreams.",
        "take a break from social media for a day—or a week.",
        "learn about mindfulness and practice being present in the moment.",
        "create a vision board to inspire you throughout the year.",
        "read a book about personal growth or mental health.",
        "identify one habit that isn’t serving you and make a plan to change it.",
        "practice self-compassion when you make a mistake.",
        "write affirmations and repeat them to yourself each morning.",
        "identify and track your emotional triggers to understand them better.",
        "use a mood-tracking app to recognize patterns in your emotions.",
        "schedule regular 'me time' to do something that makes you happy.",
        "let yourself cry—it’s okay to release emotions.",
        "watch a funny movie or show to lift your spirits.",
        "celebrate small wins and milestones in your life.",
        "practice active listening during conversations to build stronger connections.",
        "join an online support group for shared experiences and encouragement.",
        "spend time with a pet, or volunteer at an animal shelter.",
        "write out your worries and then tear up or shred the paper as a symbolic release.",
        "create a list of your strengths and revisit it whenever you’re feeling down.",
        "take a 20-minute walk in your neighborhood or a nearby park.",
        "create a bedtime routine to improve your sleep quality.",
        "drink a glass of water first thing in the morning to stay hydrated.",
        "try a beginner yoga class online or in person.",
        "experiment with a new healthy recipe for dinner.",
        "set a daily step goal and track it with a fitness app or pedometer.",
        "do a 5-minute stretch routine in the morning to wake up your body.",
        "take a relaxing bath with Epsom salts or essential oils.",
        "book a massage to ease tension in your muscles.",
        "swap out sugary drinks for herbal tea or infused water.",
        "spend a few minutes dancing to your favorite songs.",
        "schedule a doctor or dentist appointment you’ve been postponing.",
        "try a new fitness activity, like Pilates, cycling, or swimming.",
        "near sunscreen daily to protect your skin.",
        "declutter your closet and donate items you no longer need.",
        "keep healthy snacks, like fruit or nuts, on hand for busy days.",
        "take a screen break every hour to rest your eyes and move around.",
        "go for a bike ride and explore a new trail or area.",
        "treat yourself to a haircut or self-care grooming session.",
        "practice good posture while sitting or standing.",
        "spend time gardening or caring for indoor plants.",
        "try aromatherapy with calming scents like lavender or eucalyptus.",
        "do a short workout or stretch session during your lunch break.",
        "plan a day to relax and unplug from technology completely.",
        "make a playlist of energizing music to listen to during your workouts.",
        "call or video chat with a friend you haven’t spoken to in a while.",
        "plan a coffee or lunch date with someone whose company you enjoy.",
        "write a heartfelt thank-you note or message to someone who has supported you.",
        "join a book club or interest group to connect with like-minded people.",
        "set boundaries with people or commitments that leave you feeling drained.",
        "volunteer your time for a cause or organization you care about.",
        "host a small gathering or game night with close friends.",
        "spend time with family members who uplift and support you.",
        "take a class or workshop to meet new people while learning something fun.",
        "find an online community where you can share your hobbies or interests.",
        "give someone a genuine compliment to brighten their day.",
        "reconnect with an old friend by reaching out with a simple text or email.",
        "practice active listening during conversations to strengthen your relationships.",
        "attend a local event or activity, like a concert, farmers’ market, or art show.",
        "schedule regular quality time with the people who matter most to you.",
        "spend time outdoors and appreciate the beauty of nature.",
        "reflect on your personal values and how they guide your decisions.",
        "practice gratitude by listing three things you’re thankful for each day.",
        "meditate or engage in quiet reflection to connect with your inner self.",
        "read books or articles that inspire spiritual growth or self-awareness.",
        "attend a spiritual or religious gathering that resonates with you.",
        "light a candle and spend a few moments in peaceful silence.",
        "create a personal ritual, like journaling at sunrise or saying affirmations before bed.",
        "explore creative outlets, like writing, painting, or music, as a way to express yourself spiritually.",
        "write down your hopes or intentions for the year ahead and revisit them regularly.",
        "start a new art project, like drawing, painting, or pottery.",
        "try writing a short story, poem, or song.",
        "cook or bake something new, like a recipe you’ve always wanted to try.",
        "begin a photo journal to document your favorite moments.",
        "plan a day trip to a nearby town or nature spot you’ve never explored.",
        "play a musical instrument or take a beginner’s class to learn one.",
        "create a scrapbook of happy memories or milestones.",
        "host a DIY crafting night with friends or family.",
        "watch a movie or TV show in a genre you don’t typically explore.",
        "make a playlist of your favorite songs to listen to when you need a pick-me-up.",
        "write letters to your future self and seal them for later.",
        "try gardening or planting flowers, herbs, or vegetables.",
        "experiment with a new creative medium, like digital art or embroidery.",
        "decorate or rearrange a room in your home to give it a fresh look.",
        "spend time playing games—whether they’re board games, puzzles, or video games.",
        "declutter a small area of your home, like a drawer or countertop.",
        "take a long, relaxing bath or shower with your favorite products.",
        "light a candle or diffuse calming essential oils in your space.",
        "spend 10 minutes sitting in silence, focusing on your breathing.",
        "enjoy a cup of your favorite tea or coffee without any distractions.",
        "take a few minutes to stretch or do gentle yoga before bed.",
        "step outside for fresh air, even if it’s just for a few minutes.",
        "write down one thing you did well today and give yourself credit for it.",
        "give yourself permission to rest when you feel tired."]
        
        with open("../mork-state", "r") as file:
            lines = file.readlines()
            for line in lines:
                if line.startswith(f"{ctx.author.id}-"):
                    tempDate = datetime.strptime(
                        line.split("-")[1].replace("\n", ""),
                        "%Y-%m-%dT%H:%M:%S%z",
                    )

                    timeSinceLast = (
                        (
                            datetime.now(tz=timezone.utc) - tempDate
                        ).total_seconds()
                    ) / (60 * 60)

                    text = ""
                    if timeSinceLast < 22:
                        text += (
                            f"<@{ctx.author.id}>, you've submitted a card within the past {timeSinceLast} hours. You need to wait 22 hours before submitting cards. While you wait, why don't you "
                        )
                        randomNum = random.randint(0, len(possibleActivities) - 1)
                        text += possibleActivities[randomNum]
                    else:
                        text += (
                            f"<@{ctx.author.id}>, you've submitted a card within the past {timeSinceLast} hours. It has been over 22 hours, so you may submit another card"
                        )
                        return
                    await ctx.send(text)
                    return
        await ctx.send(
            f"<@{ctx.author.id}>, you have no pending cards. You may submit a card"
        )
        return

async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
