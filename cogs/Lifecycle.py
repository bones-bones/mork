import asyncio
from datetime import date, datetime
import os
import random
import re
from typing import Dict, List, cast
import aiohttp
from discord import (
    ClientUser,
    Emoji,
    Guild,
    Member,
    RawReactionActionEvent,
    Role,
    TextChannel,
    Thread,
)
import discord
from discord.ext import commands
from discord.message import Message
from discord.utils import get
import random

from typing import cast
import asyncpraw

from datetime import datetime, timezone, timedelta

import acceptCard
from checkErrataSubmissions import checkErrataSubmissions
from checkSubmissions import (
    acceptTokenSubmission,
    checkMasterpieceSubmissions,
    checkSubmissions,
    checkTokenSubmissions,
)

from cogs.HellscubeDatabase import searchFor
from getCardMessage import getCardMessage
from getVetoPollsResults import VetoPollResults, getVetoPollsResults
from getters import (
    getErrataSubmissionChannel,
    getSubmissionDiscussionChannel,
    getVetoChannel,
)
from handleVetoPost import handleVetoPost
import hc_constants
from isRealCard import isRealCard
from is_admin import is_admin, is_veto
from is_mork import is_mork, reasonableCard
from printCardImages import print_card_images
from reddit_functions import postGalleryToReddit, postToReddit
from bot_secrets.reddit_secrets import ID, NAME, PASSWORD, SECRET, USER_AGENT
from shared_vars import intents

ONE_HOUR = 3600


client = discord.Client(intents=intents)
bannedUserIds = []


class LifecycleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{cast(ClientUser,self.bot.user).name} has connected to Discord!")
        self.bot.loop.create_task(status_task(self.bot))

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        await member.send(
            f"Hey there! Welcome to HellsCube. Obligatory pointing towards <#{hc_constants.RULES_CHANNEL}>, <#{hc_constants.QUICKSTART_GUIDE}>,and <#{hc_constants.RESOURCES_CHANNEL}>. Especially the explanation for all our channels and bot command to set your pronouns. Enjoy your stay! \n\n We just wrapped up HC4, a vintage cube, and have moved to HC6, a commander cube. BE SURE TO CHECK SLOTS. Each cube has requirements and the current one only allows so many cards of each color and no non-legendary multicolor cards."
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: RawReactionActionEvent):
        if is_mork(reaction.user_id):
            return
        guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))
        channel = guild.get_channel_or_thread(reaction.channel_id)

        if channel:
            channelAsText = cast(discord.TextChannel, channel)
            message = await channelAsText.fetch_message(reaction.message_id)

            # The "have mork delete my card" react
            if str(reaction.emoji) == hc_constants.DELETE and not is_mork(
                reaction.user_id
            ):
                if not is_mork(message.author.id):
                    return
                if reaction.member in message.mentions:
                    await message.delete()
                    return
                if message.reference:
                    messageReference = await channelAsText.fetch_message(
                        cast(int, message.reference.message_id)
                    )
                    if reaction.member == messageReference.author:
                        await message.delete()
                        return
            # The hellpit resubmit case
            if (
                str(reaction.emoji) == hc_constants.ACCEPT
                and cast(discord.Thread, channel).parent
                and cast(discord.TextChannel, cast(discord.Thread, channel).parent).id
                == hc_constants.VETO_HELLPITS
            ):
                message = await channelAsText.fetch_message(reaction.message_id)
                thread_messages = [
                    message
                    async for message in message.channel.history(
                        limit=3, oldest_first=True
                    )
                ]

                first_message = thread_messages[0]
                link_message = thread_messages[2]

                if is_admin(cast(discord.Member, reaction.member)) or is_veto(
                    cast(discord.Member, reaction.member)
                ):
                    vetoChall = getVetoChannel(bot=self.bot)
                    # TODO: compartmentalize this
                    ogMessage = await vetoChall.fetch_message(
                        int(link_message.content.split("/").pop())
                    )

                    copy = await message.attachments[0].to_file()
                    copy2 = await message.attachments[0].to_file()
                    if copy and copy2:
                        vetoChannel = getVetoChannel(bot=self.bot)
                        vetoEntry = await vetoChannel.send(
                            content=first_message.content, file=copy
                        )
                        await handleVetoPost(message=vetoEntry, bot=self.bot)
                        await ogMessage.add_reaction(hc_constants.DELETE)
                    errata_submissions_channel = getErrataSubmissionChannel(
                        bot=self.bot
                    )
                    esubMessage = await errata_submissions_channel.send(file=copy2)
                    await esubMessage.add_reaction("☑️")

            if (
                str(reaction.emoji) == "☑️"
                and reaction.member
                and hc_constants.LLLLLL == reaction.member.id
            ):
                await acceptTokenSubmission(bot=self.bot, message=message)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: Thread):
        try:
            await thread.join()
        except:
            print("Can't join that thread.")

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if (
            message.author == client.user
            or message.author.bot
            or message.author.id in bannedUserIds
        ):
            return
        if "{{" in message.content:
            await print_card_images(message)
        if (
            message.channel.id == hc_constants.HELLS_UNO_CHANNEL
            or message.channel.id == hc_constants.DESIGN_HELL_SUBMISSION_CHANNEL
        ):
            await message.add_reaction(hc_constants.VOTE_UP)
            await message.add_reaction(hc_constants.VOTE_DOWN)
        if message.channel.id == hc_constants.REDDIT_CHANNEL:
            lastTwo = [mess async for mess in message.channel.history(limit=2)]
            if (
                not is_mork(lastTwo[0].author.id)
                and is_mork(lastTwo[1].author.id)
                and "reddit says: " in lastTwo[1].content
            ):
                reddit = asyncpraw.Reddit(
                    client_id=ID,
                    client_secret=SECRET,
                    password=PASSWORD,
                    user_agent=USER_AGENT,
                    username=NAME,
                )
                reddit_url = lastTwo[1].content.replace("reddit says: ", "")

                # https://www.reddit.com/r/HellsCube/comments/1c2ii4s/sometitle/
                source_result = re.search("comments/([^/]*)", reddit_url)
                if source_result:
                    post_id = source_result.group(1)
                    post = await reddit.submission(post_id)
                    await post.reply(
                        f"i'm just a bot that can't see pictures, but if i could, i'd say: {lastTwo[0].content}"
                    )
        if message.channel.id == hc_constants.TOKEN_SUBMISSIONS:
            wholeMessage = message.content.split("\n")
            submissionDiscussion = getSubmissionDiscussionChannel(self.bot)
            if wholeMessage.__len__() != 2:
                await submissionDiscussion.send(
                    content=f"<@{message.author.id}>, make sure to include the name of your token and at least one card it is for on a new line"
                )
            forCards = re.split(r"; ?", wholeMessage[1])
            weGood = True
            for card in forCards:
                if not (await isRealCard(cardName=card, ctx=submissionDiscussion)):
                    weGood = False

            if not weGood:
                await submissionDiscussion.send(
                    content=f"<@{message.author.id}>, ^ looks like one of the cards wasn't found, try again"
                )
                await message.delete()
                return
            theFile = await message.attachments[0].to_file()
            morkMessage = await message.channel.send(
                file=theFile,
                content=f"{wholeMessage[0]} by <@{message.author.id}>\n"
                + "; ".join(forCards),
            )

            await morkMessage.add_reaction(hc_constants.VOTE_UP)
            await morkMessage.add_reaction(hc_constants.VOTE_DOWN)
            await morkMessage.add_reaction(hc_constants.DELETE)
            await message.delete()

        if message.channel.id == hc_constants.VETO_CHANNEL:
            await handleVetoPost(message=message, bot=self.bot)
        if message.channel.id == hc_constants.FOUR_ZERO_ERRATA_SUBMISSIONS_CHANNEL:
            if "@" in message.content:
                # No ping case
                user = await self.bot.fetch_user(message.author.id)
                await user.send(
                    'No "@" are allowed in card title submissions to prevent me from spamming'
                )
                return  # no pings allowed
            sentMessage = await message.channel.send(content=message.content)
            await sentMessage.add_reaction(hc_constants.VOTE_UP)
            await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
            await message.delete()
        if message.channel.id == hc_constants.FOUR_ONE_ERRATA_SUBMISSIONS:
            if "@" in message.content:
                # No ping case
                user = await self.bot.fetch_user(message.author.id)
                await user.send(
                    'No "@" are allowed in card title submissions to prevent me from spamming'
                )
                await message.delete()
                return  # no pings allowed
            sentMessage = await message.channel.send(content=message.content)
            await sentMessage.create_thread(name=sentMessage.content[0:99])
            await sentMessage.add_reaction(hc_constants.VOTE_UP)
            await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
            await message.delete()
        if message.channel.id == hc_constants.SUBMISSIONS_CHANNEL:
            if len(message.attachments) > 0:
                if message.content == "":
                    discussionChannel = cast(
                        TextChannel,
                        self.bot.get_channel(
                            hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL
                        ),
                    )
                    await discussionChannel.send(
                        f"<@{message.author.id}>, make sure to include the name of your card"
                    )
                    await message.delete()
                    return
                splitString = message.content.split("\n")
                cardName = splitString[0]
                if "@" in cardName:
                    # No ping case
                    user = await self.bot.fetch_user(message.author.id)
                    await user.send(
                        'No "@" are allowed in card title submissions to prevent me from spamming'
                    )
                    return  # no pings allowed
                author = message.author.mention
                print(f"{cardName} submitted by {message.author.mention}")

                if splitString.__len__() > 1:
                    author = "; ".join(
                        [f"<@{str(raw)}>" for raw in message.raw_mentions]
                    )

                file = await message.attachments[0].to_file()
                if reasonableCard():
                    vetoChannel = getVetoChannel(bot=self.bot)
                    acceptedChannel = cast(
                        TextChannel,
                        self.bot.get_channel(
                            hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL
                        ),
                    )
                    logChannel = cast(
                        TextChannel,
                        self.bot.get_channel(
                            hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL
                        ),
                    )
                    acceptContent = cardName + " by " + author + " was accepted"
                    accepted_message_no_mentions = acceptContent
                    for index, mentionEntry in enumerate(message.raw_mentions):
                        accepted_message_no_mentions = (
                            accepted_message_no_mentions.replace(
                                f"<@{str(mentionEntry)}>", message.mentions[index].name
                            )
                        )
                    copy = await message.attachments[0].to_file()
                    await vetoChannel.send(
                        content=cardName + " by " + message.author.name, file=copy
                    )
                    copy2 = await message.attachments[0].to_file()
                    logContent = f"{acceptContent}, message id: {message.id}, upvotes: 0, downvotes: 0, magic: true"
                    await acceptedChannel.send(content=f"✨✨ {acceptContent} ✨✨")
                    await acceptedChannel.send(content="", file=file)
                    await logChannel.send(content=logContent, file=copy2)
                else:
                    contentMessage = f"{cardName} by {author}"
                    sentMessage = await message.channel.send(
                        content=contentMessage, file=file
                    )
                    await sentMessage.add_reaction(hc_constants.VOTE_UP)
                    await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
                    await sentMessage.add_reaction(hc_constants.DELETE)
                    # await sentMessage.add_reaction(
                    #     cast(Emoji, self.bot.get_emoji(hc_constants.JIMMY))
                    # )
                    # await sentMessage.add_reaction(
                    #     cast(Emoji, self.bot.get_emoji(hc_constants.WALL))
                    # )

                    await sentMessage.create_thread(name=cardName[0:99])
                await message.delete()
        if message.channel.id == hc_constants.MASTERPIECE_CHANNEL:
            if len(message.attachments) > 0:
                if message.content == "":
                    discussionChannel = cast(
                        TextChannel,
                        self.bot.get_channel(
                            hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL
                        ),
                    )
                    await discussionChannel.send(
                        f"<@{message.author.id}>, make sure to include the name of your card"
                    )
                    await message.delete()
                    return
                splitString = message.content.split("\n")
                cardName = splitString[0]
                if "@" in cardName:
                    # No ping case
                    user = await self.bot.fetch_user(message.author.id)
                    await user.send(
                        'No "@" are allowed in card title submissions to prevent me from spamming'
                    )
                    return  # no pings allowed
                author = message.author.mention
                print(f"{cardName} submitted by {message.author.mention}")
                if splitString.__len__() > 1:
                    author = "; ".join(
                        [f"<@{str(raw)}>" for raw in message.raw_mentions]
                    )

                splitString = message.content.split("\n")
                cardName = splitString[0]
                author = message.author.mention
                file = await message.attachments[0].to_file()
                if reasonableCard():
                    vetoChannel = getVetoChannel(self.bot)
                    acceptedChannel = cast(
                        TextChannel,
                        self.bot.get_channel(
                            hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL
                        ),
                    )
                    logChannel = cast(
                        TextChannel,
                        self.bot.get_channel(
                            hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL
                        ),
                    )
                    acceptContent = cardName + " by " + author + " was accepted"
                    accepted_message_no_mentions = acceptContent
                    for index, mentionEntry in enumerate(message.raw_mentions):
                        accepted_message_no_mentions = (
                            accepted_message_no_mentions.replace(
                                f"<@{str(mentionEntry)}>", message.mentions[index].name
                            )
                        )
                    copy = await message.attachments[0].to_file()
                    await vetoChannel.send(
                        content=cardName + " by " + message.author.name, file=copy
                    )
                    copy2 = await message.attachments[0].to_file()
                    logContent = f"{acceptContent}, message id: {message.id}, upvotes: 0, downvotes: 0, magic: true"
                    await acceptedChannel.send(content=f"✨✨ {acceptContent} ✨✨")
                    await acceptedChannel.send(content="", file=file)
                    await logChannel.send(content=logContent, file=copy2)
                else:
                    contentMessage = f"{cardName} by {author}"
                    sentMessage = await message.channel.send(
                        content=contentMessage, file=file
                    )
                    await sentMessage.add_reaction(hc_constants.VOTE_UP)
                    await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
                    await sentMessage.add_reaction(hc_constants.DELETE)
                    await sentMessage.create_thread(name=message.content[0:99])
                await message.delete()

    @commands.command()
    async def personalhell(self, ctx: commands.Context):
        if ctx.channel.id != hc_constants.VETO_DISCUSSION_CHANNEL:
            await ctx.send("Veto Council Only")
            return
        responseObject = cast(
            VetoPollResults, await getVetoPollsResults(bot=self.bot, ctx=ctx)
        )

        purgatoryCardMessages = responseObject.purgatoryCardMessages

        links: list[str] = []

        for messageEntry in purgatoryCardMessages:
            hasReacted = False
            # messageEntry.reactions[0].users
            up = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
            errata = get(
                messageEntry.reactions,
                emoji=self.bot.get_emoji(hc_constants.CIRION_SPELLING),
            )
            down = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
            think = get(messageEntry.reactions, emoji="🤔")

            if up:
                async for user in up.users():
                    if user.id == ctx.author.id:
                        hasReacted = True
            if errata and not hasReacted:
                async for user in errata.users():
                    if user.id == ctx.author.id:
                        hasReacted = True
            if down and not hasReacted:
                async for user in down.users():
                    if user.id == ctx.author.id:
                        hasReacted = True
            if think:
                async for user in think.users():
                    if user.id == ctx.author.id:
                        hasReacted = False

            if not hasReacted:
                links.append(f"{messageEntry.content}: {messageEntry.jump_url}")

        if len(links) > 0:

            await ctx.send(content="got some work to do:")
            textToSend = "\n".join(links)
            for i in range(0, textToSend.__len__(), hc_constants.LITERALLY_1984):
                await ctx.send(content=textToSend[i : i + hc_constants.LITERALLY_1984])
        else:
            await ctx.send(content="all caught up!")

    @commands.command()
    async def compileveto(self, ctx: commands.Context):
        if ctx.channel.id != hc_constants.VETO_DISCUSSION_CHANNEL:
            await ctx.send("Veto Council Only")
            return
        guild = cast(Guild, ctx.guild)
        timeNow = datetime.now(timezone.utc)
        epicCatchphrases = [
            "it begins",
            "and on this day, it started",
            "woe be unto the world as the gears of fate begin to spin",
        ]

        await ctx.send(random.choice(epicCatchphrases))

        responseObject = cast(
            VetoPollResults, await getVetoPollsResults(bot=self.bot, ctx=ctx)
        )
        errataCardMessages = responseObject.errataCardMessages
        acceptedCardMessages = responseObject.acceptedCardMessages
        vetoCardMessages = responseObject.vetoCardMessages
        purgatoryCardMessages = responseObject.purgatoryCardMessages

        # actual processing
        vetoHellCards: list[str] = []
        mysteryVetoHellCards: list[str] = []
        vetoedCards: list[str] = []
        acceptedCards: list[str] = []
        needsErrataCards: list[str] = []

        for messageEntry in acceptedCardMessages:
            file = await messageEntry.attachments[0].to_file()

            acceptanceMessage = messageEntry.content
            # consider putting most of this into acceptCard
            # this is pretty much the same as getCardMessage but teasing out the db logic too was gonna suck
            dbname = ""
            card_author = ""
            if (len(acceptanceMessage)) == 0 or "by " not in acceptanceMessage:
                ...  # This is really the case of setting both to "", but due to scoping i got lazy
            elif acceptanceMessage[0:3] == "by ":
                card_author = str((acceptanceMessage.split("by "))[1])
            else:
                messageChunks = acceptanceMessage.split(" by ")
                firstPart = messageChunks[0]
                secondPart = "".join(messageChunks[1:])

                dbname = str(firstPart)
                card_author = str(secondPart)
            resolvedName = dbname if dbname != "" else "Crazy card with no name"
            resolvedAuthor = card_author if card_author != "" else "no author"
            cardMessage = f"**{resolvedName}** by **{resolvedAuthor}**"

            acceptedCards.append(cardMessage)

            await acceptCard.acceptCard(
                bot=self.bot,
                file=file,
                cardMessage=cardMessage,
                cardName=dbname,
                authorName=card_author,
            )

            await messageEntry.add_reaction(hc_constants.ACCEPT)
            thread = cast(Thread, guild.get_channel_or_thread(messageEntry.id))
            if thread:
                await thread.edit(archived=True)

        for messageEntry in vetoCardMessages:
            vetoedCards.append(getCardMessage(messageEntry.content))
            await messageEntry.add_reaction(hc_constants.ACCEPT)  # see ./README.md

        for messageEntry in errataCardMessages:
            thread = guild.get_channel_or_thread(messageEntry.id)

            needsErrataCards.append(getCardMessage(messageEntry.content))
            await messageEntry.add_reaction(hc_constants.ACCEPT)
            if thread:
                await cast(Thread, thread).edit(archived=True)

        for messageEntry in purgatoryCardMessages:
            messageAge = timeNow - messageEntry.created_at
            if messageAge > timedelta(days=3):
                thread = cast(Thread, guild.get_channel_or_thread(messageEntry.id))
                recentlyNotified = False

                if thread:
                    threadMessages = thread.history()
                    threadMessages = [tm async for tm in threadMessages]

                    for threadMessage in threadMessages:
                        if (
                            threadMessage.content
                            == f"<@&{hc_constants.VETO_COUNCIL}>, <@&{hc_constants.JUDGES}>"
                        ):
                            threadMessageAge = timeNow - threadMessage.created_at
                            if threadMessageAge < timedelta(days=1):
                                # then it was recently acted upon
                                recentlyNotified = True
                                break

                    if not recentlyNotified:
                        role = cast(
                            Role, get(guild.roles, id=hc_constants.VETO_COUNCIL)
                        )

                        # TODO get the pit thread and include it here. Will require reading up the thread
                        await thread.send(role.mention)

                    vetoHellCards.append(getCardMessage(messageEntry.content))
                else:
                    mysteryVetoHellCards.append(getCardMessage(messageEntry.content))

        vetoDiscussionChannel = cast(
            TextChannel, self.bot.get_channel(hc_constants.VETO_DISCUSSION_CHANNEL)
        )

        await vetoDiscussionChannel.send(
            content=f"!! VETO POLLS HAVE BEEN PROCESSED !!"
        )

        # had to use format because python doesn't like \n inside template brackets
        if len(acceptedCards) > 0:
            vetoMessage = "\n\nACCEPTED CARDS: \n{0}".format("\n".join(acceptedCards))
            for i in range(0, vetoMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=vetoMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(needsErrataCards) > 0:
            errataMessage = "\n\nNEEDS ERRATA: \n{0}".format(
                "\n".join(needsErrataCards)
            )
            for i in range(0, errataMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=errataMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(vetoedCards) > 0:
            vetoMessage = "\n\nVETOED: \n{0}".format("\n".join(vetoedCards))
            for i in range(0, vetoMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=vetoMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(vetoHellCards) > 0:
            hellMessage = "\n\nVETO HELL: \n{0}".format("\n".join(vetoHellCards))
            for i in range(0, hellMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=hellMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(mysteryVetoHellCards) > 0:
            mysteryHellMessage = "\n\nMYSTERY VETO HELL (Veto hell but the bot can't see the thread for some reason): \n{0}".format(
                "\n".join(mysteryVetoHellCards)
            )
            for i in range(
                0, mysteryHellMessage.__len__(), hc_constants.LITERALLY_1984
            ):
                await vetoDiscussionChannel.send(
                    content=mysteryHellMessage[i : i + hc_constants.LITERALLY_1984]
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(LifecycleCog(bot))


FIVE_MINUTES = 300


async def status_task(bot: commands.Bot):
    while True:
        # creator = random.choice(cardSheet.col_values(3)[4:])
        status = random.choice(hc_constants.statusList)
        await checkSubmissions(bot)
        try:
            await checkMasterpieceSubmissions(bot)
        except Exception as e:
            print(e)
        try:
            await checkErrataSubmissions(bot)
        except Exception as e:
            print(e)
        try:
            await checkTokenSubmissions(bot)
        except Exception as e:
            print(e)
        try:
            await checkReddit(bot)
        except Exception as e:
            print(e)
        await bot.change_presence(
            status=discord.Status.online, activity=discord.Game(status)
        )
        now = datetime.now()
        print(f"time is {now}")
        if now.hour == 10 and now.minute <= 4:
            nowtime = now.date()
            start = date(2024, 3, 13)  # more or less the start date to post to reddit
            days_since_starting = (nowtime - start).days
            cardOffset = (
                608 - days_since_starting
            )  # 608 is how many cards there were in hc4 at the time
            if cardOffset >= 0:
                cards = searchFor({"cardset": "hc4"})
                card = cards[cardOffset]
                name = card.name()
                url = card.img()
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            image_path = f'tempImages/{name.replace("/", "|")}'
                            with open(
                                image_path, "wb"
                            ) as out:  ## Open temporary file as bytes
                                out.write(await resp.read())  ## Read bytes into file
                            try:
                                await postToReddit(
                                    title=f"HC4 Card of the ~day: {name}",
                                    image_path=image_path,
                                    flair=hc_constants.OFFICIAL_FLAIR,
                                )
                            except:
                                ...
                            os.remove(image_path)
                        await session.close()

        if now.hour == 4 and now.minute <= 4:
            # Get all the messages, download the images, post them to reddit
            try:
                subChannel = cast(
                    discord.TextChannel,
                    bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL),
                )
                timeNow = datetime.now(timezone.utc)
                oneDay = timeNow + timedelta(days=-1)
                messages = subChannel.history(after=oneDay, limit=None)
                images: List[Dict[str, str]] = []
                if messages is None:
                    return

                messages = [message async for message in messages][:10]
                for messageEntry in messages:
                    if len(messageEntry.attachments) > 0:
                        file = await messageEntry.attachments[0].to_file()
                        file_data = file.fp.read()
                        image_path = f"tempImages/{messageEntry.id}{file.filename}"
                        images.append({"image_path": image_path})
                        with open(image_path, "wb") as out:
                            out.write(file_data)
                await postGalleryToReddit(
                    title=f"Some of Today's Submissions: Have any strong opinions on these cards? Join the discord to share them!",
                    images=images,
                    flair=hc_constants.OFFICIAL_FLAIR,
                )
                for imageEntry in images:
                    os.remove(list(imageEntry.values())[0])
            except Exception as e:
                print(e)

        await asyncio.sleep(FIVE_MINUTES)


async def checkReddit(bot: commands.Bot):
    timeNow = datetime.now(timezone.utc)
    oneDay = timeNow + timedelta(days=-2)
    reddit = asyncpraw.Reddit(
        client_id=ID,
        client_secret=SECRET,
        password=PASSWORD,
        user_agent=USER_AGENT,
        username=NAME,
    )
    hellscubeSubreddit = cast(
        asyncpraw.reddit.Subreddit, await reddit.subreddit("HellsCube")
    )

    redditChannel = cast(TextChannel, bot.get_channel(hc_constants.REDDIT_CHANNEL))
    messagesInLastDay = [mess async for mess in redditChannel.history(after=oneDay)]

    async for submission in hellscubeSubreddit.search('flair:"Card Idea" OR flair:"HellsCube Submission"', time_filter="day"):  # type: ignore
        alreadyPosted = False
        for discordMessage in messagesInLastDay:
            if submission.permalink in discordMessage.content:
                alreadyPosted = True
                break

        if not alreadyPosted:
            await redditChannel.send(
                content=f"reddit says: https://reddit.com{submission.permalink}"
            )
