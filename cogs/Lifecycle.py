import asyncio
from datetime import date, datetime
import os
import random
import re
from typing import cast
import aiohttp
from discord import (
    ClientUser,
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


from typing import cast
import asyncpraw

from datetime import datetime, timezone, timedelta

import acceptCard
from cogs.lifecycle.post_daily_submissions import post_daily_submissions
from submissions.checkErrataSubmissions import checkErrataSubmissions
from checkSubmissions import (
    checkSubmissions,
)

from cogs.HellscubeDatabase import searchFor
from cogs.lifecycle.check_reddit import check_reddit
from getCardMessage import getCardMessage
from getVetoPollsResults import VetoPollResults, getVetoPollsResults
from getters import (
    getErrataSubmissionChannel,
    getMorkSubmissionsLoggingChannel,
    getSubmissionDiscussionChannel,
    getVetoChannel,
    getVetoDiscussionChannel,
)
from handleVetoPost import handleVetoPost
import hc_constants
from isRealCard import isRealCard
from is_admin import is_admin, is_veto
from is_mork import is_mork, reasonableCard
from printCardImages import print_card_images
from reddit_functions import post_to_reddit
from bot_secrets.reddit_secrets import ID, NAME, PASSWORD, SECRET, USER_AGENT
from shared_vars import intents, googleClient
from submissions.checkMasterpieceSubmissions import checkMasterpieceSubmissions
from submissions.tokenSubmissions import checkTokenSubmissions

client = discord.Client(intents=intents)
bannedUserIds = []

tokenUnapproved = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet(
    hc_constants.TOKEN_UNAPPROVED
)


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
            f"Hey there! Welcome to HellsCube. Obligatory pointing towards <#{hc_constants.RULES_CHANNEL}>, <#{hc_constants.QUICKSTART_GUIDE}>,and <#{hc_constants.RESOURCES_CHANNEL}>. Especially the explanation for all our channels and bot command to set your pronouns. Enjoy your stay! \n\n We just wrapped up HC6, a commander cube, and have moved to HC7, a cube. BE SURE TO CHECK SLOTS. Each cube has requirements and the current one only allows so many cards of each color."
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: RawReactionActionEvent):
        if is_mork(reaction.user_id):
            return
        guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))
        channel = guild.get_channel_or_thread(reaction.channel_id)

        if channel == None:
            return

        channelAsText = cast(discord.TextChannel, channel)
        message = await channelAsText.fetch_message(reaction.message_id)

        # The "have mork delete my card" react
        if str(reaction.emoji) == hc_constants.DELETE and not is_mork(reaction.user_id):
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
            # and type(channel) == TextChannel
            and hasattr(channel, "parent")  # cast(discord.Thread, channel).parent
            and cast(discord.TextChannel, cast(discord.Thread, channel).parent).id
            == hc_constants.VETO_HELLPITS
        ):
            print("it is a :", type(channel))
            message = await channelAsText.fetch_message(reaction.message_id)
            thread_messages = [
                message
                async for message in message.channel.history(limit=3, oldest_first=True)
            ]

            first_message = thread_messages[0]
            link_message = thread_messages[2]

            if is_admin(cast(discord.Member, reaction.member)) or is_veto(
                cast(discord.Member, reaction.member)
            ):
                veto_channel = getVetoChannel(bot=self.bot)
                # TODO: compartmentalize this
                ogMessage = await veto_channel.fetch_message(
                    int(link_message.content.split("/").pop())
                )
                attachment_reference = message.attachments[0]

                copy_of_file_for_veto_channel = await attachment_reference.to_file()
                copy2 = await attachment_reference.to_file()
                if copy_of_file_for_veto_channel and copy2:
                    vetoChannel = getVetoChannel(bot=self.bot)
                    vetoEntry = await vetoChannel.send(
                        content=first_message.content,
                        file=copy_of_file_for_veto_channel,
                    )

                    veto_council_to_notify = (
                        hc_constants.VETO_COUNCIL
                        if get(ogMessage.reactions, emoji=hc_constants.CLOCK)
                        else (
                            hc_constants.VETO_COUNCIL_2
                            if get(ogMessage.reactions, emoji=hc_constants.WOLF)
                            else None
                        )
                    )
                    await handleVetoPost(
                        message=vetoEntry,
                        bot=self.bot,
                        veto_council=veto_council_to_notify,
                    )
                    await ogMessage.add_reaction(hc_constants.DELETE)
                errata_submissions_channel = getErrataSubmissionChannel(bot=self.bot)
                errata_submission_message = await errata_submissions_channel.send(
                    file=copy2
                )
                await errata_submission_message.add_reaction("☑️")

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

        # Hello single coolest thing about python
        match message.channel.id:
            case (
                hc_constants.HELLS_UNO_CHANNEL
                | hc_constants.DESIGN_HELL_SUBMISSION_CHANNEL
            ):
                await message.add_reaction(hc_constants.VOTE_UP)
                await message.add_reaction(hc_constants.VOTE_DOWN)
            case hc_constants.REDDIT_CHANNEL:
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
                    await reddit.close()

            case hc_constants.TOKEN_SUBMISSIONS:
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

            case hc_constants.VETO_CHANNEL:
                await handleVetoPost(message=message, bot=self.bot, veto_council=None)

            case (
                hc_constants.FOUR_ZERO_ERRATA_SUBMISSIONS_CHANNEL
                | hc_constants.SIX_ERRATA
                | hc_constants.FOUR_ONE_ERRATA_SUBMISSIONS
            ):
                if "@" in message.content:
                    # No ping case
                    user = await self.bot.fetch_user(message.author.id)
                    await user.send(
                        'No "@" are allowed in card title submissions to prevent me from spamming'
                    )
                    return  # no pings allowed
                sentMessage = await message.channel.send(content=message.content)
                await sentMessage.create_thread(name=sentMessage.content[0:99])
                await sentMessage.add_reaction(hc_constants.VOTE_UP)
                await sentMessage.add_reaction(hc_constants.VOTE_DOWN)
                await message.delete()

            case hc_constants.SUBMISSIONS_CHANNEL:
                if len(message.attachments) > 0:
                    if message.content == "":
                        discussionChannel = getSubmissionDiscussionChannel(self.bot)
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
                        acceptedChannel = getSubmissionDiscussionChannel(self.bot)
                        logChannel = getMorkSubmissionsLoggingChannel(self.bot)
                        acceptContent = cardName + " by " + author + " was accepted"
                        accepted_message_no_mentions = acceptContent
                        for index, mentionEntry in enumerate(message.raw_mentions):
                            accepted_message_no_mentions = (
                                accepted_message_no_mentions.replace(
                                    f"<@{str(mentionEntry)}>",
                                    message.mentions[index].name,
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

                        await sentMessage.create_thread(name=cardName[0:99])
                    await message.delete()

            case hc_constants.MASTERPIECE_CHANNEL:
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
                                    f"<@{str(mentionEntry)}>",
                                    message.mentions[index].name,
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

            case _:
                pass

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

            emoji_toSend = (
                hc_constants.CLOCK
                if get(messageEntry.reactions, emoji=hc_constants.CLOCK)
                else hc_constants.WOLF
            )
            if not hasReacted:
                links.append(
                    f"{emoji_toSend} - {messageEntry.content}: {messageEntry.jump_url}"
                )

            is_clock_vc = (
                hc_constants.CLOCK
                if cast(Member, ctx.author).get_role(hc_constants.VETO_COUNCIL) != None
                else hc_constants.WOLF
            )

            links.sort(key=lambda x: not x.__contains__(is_clock_vc))

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

        vetoHellCards: list[str] = []
        mysteryVetoHellCards: list[str] = []
        vetoedCards: list[str] = []
        acceptedCards: list[str] = []

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

            set_to_add_to = "HC7.1"

            channel_to_add_to = hc_constants.SEVEN_CARD_LIST

            await acceptCard.acceptCard(
                bot=self.bot,
                file=file,
                cardMessage=cardMessage,
                cardName=dbname,
                authorName=card_author,
                setId=set_to_add_to,
                channelIdForCard=channel_to_add_to,
            )

            await messageEntry.add_reaction(hc_constants.ACCEPT)
            thread = cast(Thread, guild.get_channel_or_thread(messageEntry.id))
            if thread:
                await thread.edit(archived=True)

        for messageEntry in vetoCardMessages:
            file = await messageEntry.attachments[0].to_file()

            acceptanceMessage = messageEntry.content
            dbname = ""
            card_author = ""
            if (len(acceptanceMessage)) == 0 or "by " not in acceptanceMessage:
                ...
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

            vetoedCards.append(getCardMessage(messageEntry.content))

            await acceptCard.acceptVetoCard(
                bot=self.bot,
                file=file,
                cardMessage=cardMessage,
                cardName=dbname,
                authorName=card_author,
            )

            await messageEntry.add_reaction(hc_constants.ACCEPT)  # see ./README.md

        needsErrataCards: list[str] = []

        for messageEntry in errataCardMessages:
            thread = guild.get_channel_or_thread(messageEntry.id)
            needsErrataCards.append(getCardMessage(messageEntry.content))
            await messageEntry.add_reaction(hc_constants.ACCEPT)
            if thread:
                await cast(Thread, thread).edit(archived=True)

        for messageEntry in purgatoryCardMessages:
            try:
                messageAge = timeNow - messageEntry.created_at
                if messageAge > timedelta(days=6):
                    thread = cast(Thread, guild.get_channel_or_thread(messageEntry.id))

                    if thread:
                        threadMessages = thread.history(oldest_first=True, limit=2)
                        threadMessages = [tm async for tm in threadMessages]
                        hellpit_target = int(threadMessages[1].content.split("/").pop())
                        hellpit_thread = cast(
                            Thread, guild.get_channel_or_thread(hellpit_target)
                        )
                        newest_message = await hellpit_thread.history(
                            limit=1
                        ).__anext__()
                        threadMessageAge = timeNow - newest_message.created_at

                        # then it was recently acted upon
                        recentlyNotified = threadMessageAge < timedelta(days=1)
                        if not recentlyNotified:

                            veto_council_to_notify = (
                                hc_constants.VETO_COUNCIL
                                if get(messageEntry.reactions, emoji=hc_constants.CLOCK)
                                else hc_constants.VETO_COUNCIL_2
                            )

                            role = cast(
                                Role, get(guild.roles, id=veto_council_to_notify)
                            )

                            await thread.send(role.mention)

                        vetoHellCards.append(getCardMessage(messageEntry.content))
                    else:
                        mysteryVetoHellCards.append(
                            getCardMessage(messageEntry.content)
                        )
            except:
                print(f"ERROR: unable to process: {messageEntry.content}")

        vetoDiscussionChannel = getVetoDiscussionChannel(self.bot)

        await vetoDiscussionChannel.send(
            content=f"!! VETO POLLS HAVE BEEN PROCESSED !!"
        )

        # had to use format because python doesn't like \n inside template brackets
        if len(acceptedCards) > 0:
            acceptedMessage = "||​||\nACCEPTED CARDS: \n{0}".format(
                "\n".join(acceptedCards)
            )
            for i in range(0, acceptedMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=acceptedMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(needsErrataCards) > 0:
            errataMessage = "||​||\nNEEDS ERRATA: \n{0}".format(
                "\n".join(needsErrataCards)
            )
            for i in range(0, errataMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=errataMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(vetoedCards) > 0:
            vetoMessage = "||​||\nVETOED: \n{0}".format("\n".join(vetoedCards))
            for i in range(0, vetoMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=vetoMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(vetoHellCards) > 0:
            hellMessage = "||​||\nVETO HELL: \n{0}".format("\n".join(vetoHellCards))
            for i in range(0, hellMessage.__len__(), hc_constants.LITERALLY_1984):
                await vetoDiscussionChannel.send(
                    content=hellMessage[i : i + hc_constants.LITERALLY_1984]
                )
        if len(mysteryVetoHellCards) > 0:
            mysteryHellMessage = "||​||\nMYSTERY VETO HELL (Veto hell but the bot can't see the thread for some reason): \n{0}".format(
                "\n".join(mysteryVetoHellCards)
            )
            for i in range(
                0, mysteryHellMessage.__len__(), hc_constants.LITERALLY_1984
            ):
                await vetoDiscussionChannel.send(
                    content=mysteryHellMessage[i : i + hc_constants.LITERALLY_1984]
                )

    @commands.command()
    async def instaerrata(self, ctx: commands.Context, *, cardMessage: str = ""):
        if not is_admin(cast(Member, ctx.author)):
            return

        if not ctx.message.attachments:
            await ctx.send("Please attach an image file.")
            return

        file = ctx.message.attachments[0]

        if not file.content_type or not file.content_type.startswith("image/"):
            await ctx.send("The attached file must be an image.")
            return

        if (len(cardMessage)) == 0 or "by " not in cardMessage:
            await ctx.send("Please attach a card message.")
            return
        elif cardMessage[0:3] == "by ":
            await ctx.send("Please include a card name")
            return
        else:
            messageChunks = cardMessage.split(" by ")
            firstPart = messageChunks[0]
            secondPart = "".join(messageChunks[1:])

            dbname = str(firstPart)
            card_author = str(secondPart)
            # TODO: do a set lookup
        await acceptCard.acceptCard(
            bot=self.bot,
            file=await file.to_file(),
            cardMessage=cardMessage,
            cardName=dbname,
            authorName=card_author,
            errata=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LifecycleCog(bot))


FIVE_MINUTES = 300


async def status_task(bot: commands.Bot):
    async def post_reddit_card_of_the_day():
        nowtime = datetime.now().date()
        start = date(2024, 3, 13)
        days_since_starting = (nowtime - start).days
        cardOffset = 608 - days_since_starting
        if cardOffset >= 0:
            cards = searchFor({"cardset": "hc4"})
            card = cards[cardOffset]
            name = card.name()
            url = card.img()
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        image_path = f'tempImages/{name.replace("/", "|")}'
                        with open(image_path, "wb") as out:
                            out.write(await resp.read())
                        try:
                            await post_to_reddit(
                                title=f"HC4 Card of the ~day: {name}",
                                image_path=image_path,
                                flair=hc_constants.OFFICIAL_FLAIR,
                            )
                        except:
                            pass
                        os.remove(image_path)
                    await session.close()

    while True:
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
            await check_reddit(bot)
        except Exception as e:
            print(e)
        await bot.change_presence(
            status=discord.Status.online, activity=discord.Game(status)
        )
        now = datetime.now()
        print(f"time is {now}")
        if now.hour == 10 and now.minute <= 4:
            await post_reddit_card_of_the_day()
        if now.hour == 4 and now.minute <= 4:
            try:
                await post_daily_submissions(bot)
            except Exception as e:
                print(e)
        await asyncio.sleep(FIVE_MINUTES)
