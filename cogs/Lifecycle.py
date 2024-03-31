import asyncio
from datetime import date, datetime
import os
import random
from typing import cast
import aiohttp
from discord import  ClientUser, Emoji, Guild, Member, RawReactionActionEvent, Role, TextChannel, Thread
import discord
from discord.ext import commands
from discord.message import Message
from discord.utils import get
import random
from acceptCard import acceptCard
from typing import cast
from discord.utils import get

from datetime import datetime, timezone, timedelta


from checkErrataSubmissions import checkErrataSubmissions
from checkSubmissions import checkSubmissions

from cogs.HellscubeDatabase import searchFor
from getCardMessage import getCardMessage
import hc_constants
from is_mork import is_mork, reasonableCard
from printCardImages import print_card_images
from reddit_functions import postToReddit
from shared_vars import intents

ONE_HOUR = 3600


client = discord.Client(intents=intents)
bannedUserIds = []

class LifecycleCog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # global log
        print(f'{cast(ClientUser,self.bot.user).name} has connected to Discord!')
        self.bot.loop.create_task(status_task(self.bot))
        while True:
            await asyncio.sleep(ONE_HOUR)
            # with open("log.txt", 'a', encoding='utf8') as file:
            #     file.write(log)
            #     log = ""
        
    # @commands.Cog.listener()
    # async def on_raw_reaction_remove(self, payload:RawReactionActionEvent):
    #     # global log
    #     if payload.channel_id == hc_constants.SUBMISSIONS_CHANNEL:
    #         serv = self.bot.get_guild(hc_constants.SERVER_ID)
           # user = serv.get_member(payload.user_id)
            # log += f"{payload.message_id}: Removed {payload.emoji.name} from {payload.user_id} ({user.name}|{user.nick}) at {datetime.now()}\n"

    @commands.Cog.listener()
    async def on_member_join(self,member:Member):
        await member.send(f"Hey there! Welcome to HellsCube. Obligatory pointing towards <#{hc_constants.RULES_CHANNEL}>, <#{hc_constants.FAQ_CHANNEL}> and <#{hc_constants.RESOURCES_CHANNEL}>. Especially the explanation for all our channels and bot command to set your pronouns. Enjoy your stay!")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction:RawReactionActionEvent):
        if str(reaction.emoji) == hc_constants.DELETE and not is_mork(reaction.user_id):
            guild = cast(Guild, self.bot.get_guild(cast(int,reaction.guild_id)))
            channel = cast(TextChannel, guild.get_channel(reaction.channel_id))
            message = await channel.fetch_message(reaction.message_id)
            if not is_mork(message.author.id):
                return
            if reaction.member in message.mentions:
                await message.delete()
                return
            if message.reference:
                messageReference = await channel.fetch_message(cast(int, message.reference.message_id))
                if reaction.member == messageReference.author:
                    await message.delete()
                    return

    @commands.Cog.listener()
    async def on_thread_create(self, thread:Thread):
        try:
           await thread.join()
        except:
            print("Can't join that thread.")

    @commands.Cog.listener()
    async def on_message(self,message:Message):
        if (message.author == client.user
            or message.author.bot
            or message.author.id in bannedUserIds):
            return
        if "{{" in message.content:
            await print_card_images(message)
        if message.channel.id == hc_constants.HELLS_UNO_CHANNEL:
            await message.add_reaction(hc_constants.VOTE_UP)
            await message.add_reaction(hc_constants.VOTE_DOWN)
        if message.channel.id == hc_constants.VETO_CHANNEL:
            await message.add_reaction(hc_constants.VOTE_UP)
            await message.add_reaction(cast(Emoji, self.bot.get_emoji(hc_constants.CIRION_SPELLING))) # Eratta
            await message.add_reaction(hc_constants.VOTE_DOWN)
            await message.add_reaction(cast(Emoji, self.bot.get_emoji(hc_constants.MANA_GREEN))) # too strong
            await message.add_reaction(cast(Emoji, self.bot.get_emoji(hc_constants.MANA_WHITE))) # too weak
            await message.add_reaction("🤮")
            await message.add_reaction("🤔")
            thread = await message.create_thread(name = message.content[0:99])
            role = cast(Role, get(cast(Member, message.author).guild.roles, id = hc_constants.VETO_COUNCIL))
            await thread.send(role.mention)
        if message.channel.id == hc_constants.FOUR_ZERO_ERRATA_SUBMISSIONS_CHANNEL:
            if "@" in message.content:
                # No ping case
                user = await self.bot.fetch_user(message.author.id)
                await user.send('No "@" are allowed in card title submissions to prevent me from spamming')
                return # no pings allowed
            sentMessage = await message.channel.send(content = message.content)
            await sentMessage.add_reaction(hc_constants.VOTE_UP)
            await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
            await message.delete()
        if message.channel.id == hc_constants.SUBMISSIONS_CHANNEL and len(message.attachments) > 0:
            if "@" in message.content:
                # No ping case
                user = await self.bot.fetch_user(message.author.id)
                await user.send('No "@" are allowed in card title submissions to prevent me from spamming')
                return # no pings allowed
            file = await message.attachments[0].to_file()
            if reasonableCard():
                vetoChannel = cast(TextChannel, self.bot.get_channel(hc_constants.VETO_CHANNEL))
                acceptedChannel = cast(TextChannel, self.bot.get_channel(hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL))
                logChannel = cast(TextChannel, self.bot.get_channel(hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL))
                acceptContent = message.content + " was accepted"
                mention = f'<@{str(message.raw_mentions[0])}>'
                accepted_message_no_mentions = message.content.replace(mention, message.mentions[0].name)
                copy = await message.attachments[0].to_file()
                await vetoChannel.send(content = accepted_message_no_mentions, file = copy)
                copy2 = await message.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {message.id}, upvotes: 0, downvotes: 0, magic: true"
                await acceptedChannel.send(content = "✨✨ {acceptContent} ✨✨")
                await acceptedChannel.send(content = "", file = file)
                await logChannel.send(content = logContent, file = copy2)
            else:
                sentMessage = await message.channel.send(content = f"{message.content} by {message.author.mention}" , file = file)
                await sentMessage.add_reaction(hc_constants.VOTE_UP)
                await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
                await sentMessage.add_reaction(hc_constants.DELETE)
            await message.delete()



    @commands.Cog.listener()
    async def compileveto(self, ctx: commands.Context):
        if ctx.channel.id != hc_constants.VETO_DISCUSSION_CHANNEL:
            await ctx.send("Veto Council Only")
            return

        vetoChannel = cast(TextChannel, self.bot.get_channel(hc_constants.VETO_CHANNEL))
        vetoDiscussionChannel = cast(TextChannel, self.bot.get_channel(hc_constants.VETO_DISCUSSION_CHANNEL))
        timeNow = datetime.now(timezone.utc)        
        fourWeeksAgo = timeNow + timedelta(days=-28)
        epicCatchphrases = ["If processing lasts more than 5 minutes, consult your doctor.", "on it, yo.", "ya ya gimme a sec", "processing...", "You're not the boss of me", "ok, 'DAD'", "but what of the children?", "?", "workin' on it!", "on it!", "can do, cap'n!", "raseworter pro tip: run it back, but with less 'tude next time.", "who? oh yeah sure thing b0ss", "how about no for a change?", "CAAAAAAAAAAAAAAN DO!", "i'm afraid i can't let you do that.", "i mean like, if you say so, man", "WOOOOOOOOOOOOOOOOOOOOOOOOOOOO", "*nuzzles u*"]
        
        await ctx.send(random.choice(epicCatchphrases))
        
        
        messages = vetoChannel.history(after = fourWeeksAgo, limit = None)
    
        if messages is None:
            return
        messages = [message async for message in messages]
        acceptedCards:list[str] = []
        needsErrataCards:list[str] = []
        vetoedCards:list[str] = []
        vetoHellCards:list[str] = []
        for messageEntry in messages:
            if (len(messageEntry.attachments) == 0):
                continue
            up = get(messageEntry.reactions, emoji = hc_constants.VOTE_UP)
            upvote = up.count if up else -1

            down = get(messageEntry.reactions, emoji = hc_constants.VOTE_DOWN)
            downvote = down.count if down else -1

            erratas = get(messageEntry.reactions, emoji = self.bot.get_emoji(hc_constants.CIRION_SPELLING))
            errata = erratas.count if erratas else -1
        
            messageAge = timeNow - messageEntry.created_at

            if (
                get(messageEntry.reactions, emoji = hc_constants.ACCEPT)
                or get(messageEntry.reactions, emoji = hc_constants.DELETE)
                or messageAge < timedelta(days=1)
            ):
                continue # Skip cards that have been marked, or are only a day old
            # Errata needed case
            
            guild = cast(Guild, messageEntry.guild)
            
            if (
                errata > 4
                and errata >= upvote
                and errata >= downvote
            ):
                needsErrataCards.append(getCardMessage(messageEntry.content))

                await messageEntry.add_reaction(hc_constants.ACCEPT)
                thread = guild.get_channel_or_thread(messageEntry.id)
                if thread:
                    await cast(Thread, thread).edit(archived = True)

            # Accepted case
            elif (
                upvote > 4
                and upvote >= downvote
                and upvote >= errata
            ):
                thread = cast(Thread, guild.get_channel_or_thread(messageEntry.id))
                if thread:
                    await thread.edit(archived = True)

                file = await messageEntry.attachments[0].to_file()
                
                acceptanceMessage = messageEntry.content
                # consider putting most of this into acceptCard
                # this is pretty much the same as getCardMessage but teasing out the db logic too was gonna suck
                dbname = ""
                card_author = ""
                if (len(acceptanceMessage)) == 0 or "by " not in acceptanceMessage:
                    ... # This is really the case of setting both to "", but due to scoping i got lazy
                elif (acceptanceMessage[0:3] == "by "):
                    card_author = str((acceptanceMessage.split("by "))[1])
                else:
                    [firstPart, secondPart] = acceptanceMessage.split(" by ")
                    dbname = str(firstPart)
                    card_author = str(secondPart)
                resolvedName = dbname if dbname !="" else "Crazy card with no name"
                resolvedAuthor = card_author if card_author != "" else "no author"
                cardMessage = f"**{resolvedName}** by **{resolvedAuthor}**"
                acceptedCards.append(cardMessage)
                await acceptCard(
                    bot = self.bot,
                    file = file,
                    cardMessage = cardMessage,
                    cardName = dbname,
                    authorName = card_author
                )
                await messageEntry.add_reaction(hc_constants.ACCEPT)


            # Veto case
            elif (
                downvote > 4
                and downvote >= upvote
                and downvote >= errata
            ):
                vetoedCards.append(getCardMessage(messageEntry.content))
                await messageEntry.add_reaction(hc_constants.ACCEPT) # see ./README.md 

            # Veto Hell
            elif (messageAge > timedelta(days = 7)):
                thread = cast(Thread, guild.get_channel_or_thread(messageEntry.id))
                recentlyNotified = False
                # new code
                threadMessages = thread.history()
                threadMessages = [message async for message in threadMessages]

                for threadMessage in threadMessages:
                    if threadMessage.content == f"<@&{798689768379908106}>":
                       threadMessageAge = timeNow - threadMessage.created_at
                       if threadMessageAge < timedelta(days = 7):
                        # then it was recently acted upon
                        recentlyNotified = True
                        break

                if not recentlyNotified:
                    role = cast(Role, get(guild.roles, id = hc_constants.VETO_COUNCIL))
                    await thread.send(role.mention)
                    vetoHellCards.append(getCardMessage(messageEntry.content))


        await vetoDiscussionChannel.send(content= f"!! VETO POLLS HAVE BEEN PROCESSED !!")

        # had to use format because python doesn't like \n inside template brackets
        if(len(acceptedCards) > 0):
            vetoMessage = ("\n\nACCEPTED CARDS: \n{0}".format("\n".join(acceptedCards)))
            await vetoDiscussionChannel.send(content = vetoMessage)
        if(len(needsErrataCards) > 0):
            errataMessage = ("\n\nNEEDS ERRATA: \n{0}".format("\n".join(needsErrataCards)))
            await vetoDiscussionChannel.send(content = errataMessage)
        if(len(vetoedCards) > 0):
            vetoMessage = ("\n\nVETOED: \n{0}".format("\n".join(vetoedCards)))
            await vetoDiscussionChannel.send(content = vetoMessage)
        if(len(vetoHellCards) > 0):
            hellMessage = ("\n\nVETO HELL: \n{0}".format("\n".join(vetoHellCards)))
            await vetoDiscussionChannel.send(content = hellMessage)




async def setup(bot:commands.Bot):
    await bot.add_cog(LifecycleCog(bot))



FIVE_MINUTES = 300

async def status_task(bot: commands.Bot):
    while True:
        # creator = random.choice(cardSheet.col_values(3)[4:])
        status = random.choice(hc_constants.statusList)
        # print(status)
        await checkSubmissions(bot)
        await checkErrataSubmissions(bot)
        await bot.change_presence(status = discord.Status.online, activity = discord.Game(status))
        now = datetime.now()
        print(f"time is {now}")
        if now.hour == 4 and now.minute <= 4:
            nowtime = now.date()
            start = date(2024, 3, 13)  # more or less the start date to post to reddit
            days_since_starting = (nowtime - start).days
            cardOffset = 608 - days_since_starting # 608 is how many cards there were in hc4 at the time
            if cardOffset >= 0:
                cards = searchFor({"cardset": "hc4"})
                card = cards[cardOffset]
                name = card.name()
                url = card.img()
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            print(resp)                       
                            image_path = f'tempImages/{name.replace("/", "|")}'
                            with open(image_path, 'wb') as out: ## Open temporary file as bytes
                                out.write(await resp.read())  ## Read bytes into file
                            try:
                                await  postToReddit(
                                    title = f"HC4 Card of the ~day: {name}",
                                    image_path = image_path,
                                    flair = "5778f0e4-52c0-11eb-9a1d-0ebf18b4acab"
                                )
                            except:
                                ...
                            os.remove(image_path)
        await asyncio.sleep(FIVE_MINUTES)
