from datetime import datetime, timedelta, timezone
import io
import json
from numbers import Number
import os
import random
import re
from typing import Dict, List, cast
import aiohttp
import discord
from discord.ext import commands
from discord.utils import get
from numpy import number
from cogs.HellscubeDatabase import searchFor
from getters import getBotTest, getSubmissionDiscussionChannel, getVetoChannel
from handleVetoPost import handleVetoPost
from isRealCard import isRealCard
from printCardImages import sendImageReply
from shared_vars import googleClient


from discord import (
    ClientUser,
    Guild,
    Member,
    RawReactionActionEvent,
    Role,
    TextChannel,
    Thread,
)

from acceptCard import acceptCard
from cardNameRequest import cardNameRequest
import hc_constants
from is_admin import is_veto, is_admin

from is_mork import is_mork

from shared_vars import intents, cardSheet, allCards


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # for the card Avatar of BallsJr123
    @commands.command()
    async def avatarOfBalls(self, ctx: commands.Context, cost):
        print("oi")
        results = searchFor({"cmc": [(cost, "=")], "types": ["creature"]})
        if results.__len__() == 0:
            await ctx.send("nothing found for that cmc")
        result = random.choice(results)
        print(results.__len__())
        await sendImageReply(
            url=result.img(), cardname=result.name(), text=None, message=ctx.message
        )

    @commands.command()
    async def attack(self, ctx: commands.Context):
        await ctx.send("Yes master~ :pink_heart:")
    
    @commands.command()
    async def hellpitstatus(self, ctx: commands.Context, days: int = 30):
        if ctx.channel.id != hc_constants.VETO_DISCUSSION_CHANNEL:
            await ctx.send("Veto Council Only")
            return
        guild = cast(Guild, ctx.guild)
        timeNow = datetime.now(timezone.utc)
        epicCatchphrases = [
            "You opened the box...",
            "are you sure about this?",
            "**HIC SUNT DRACONES**",
            "|piss|",
            "i'll do it after u !grunch five times",
            "all glory to *locus dei*",
            "computing devotion to dreadmaw...",
            "no turning back now",
            "he's right behind me, isn't he?",
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

        for messageEntry in errataCardMessages:
            thread = guild.get_channel_or_thread(messageEntry.id)

            needsErrataCards.append(getCardMessage(messageEntry.content))
            await messageEntry.add_reaction(hc_constants.ACCEPT)
            if thread:
                await cast(Thread, thread).edit(archived=True)

        for messageEntry in purgatoryCardMessages:
            messageAge = timeNow - messageEntry.created_at
            if messageAge > timedelta(days=6):
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

    # @commands.Cog.listener()
    # async def on_message(self, message: discord.Message):
    #     if message.channel.id == hc_constants.BOT_TEST_CHANNEL:
    #         wholeMessage = message.content.split("\n")
    #         submissionDiscussion = getSubmissionDiscussionChannel(self.bot)
    #         if wholeMessage.__len__() != 2:

    #             await submissionDiscussion.send(
    #                 content=f"<@{message.author.id}>, make sure to include the name of your token and at least one card it is for on a new line"
    #             )
    #         forCards = re.split(r"; ?", wholeMessage[1])
    #         weGood = True
    #         for card in forCards:
    #             if not await isRealCard(cardName=card, ctx=getBotTest(self.bot)):
    #                 weGood = False

    #         if not weGood:
    #             await message.delete()
    #             await submissionDiscussion.send(
    #                 content=f"<@{message.author.id}>, ^ looks like one of the cards wasn't found, try again"
    #             )
    #             return
    #         await message.add_reaction(hc_constants.VOTE_UP)
    #         await message.add_reaction(hc_constants.VOTE_DOWN)
    #         await message.add_reaction(hc_constants.DELETE)

    # @commands.command(rest_is_raw=True)
    # async def judgement2(self, ctx: commands.Context, *, args: str):

    # @commands.Cog.listener()
    # async def on_ready(self):
    # @commands.Cog.listener()
    # async def on_raw_reaction_add(self, reaction: discord.RawReactionActionEvent):
    #     if is_mork(reaction.user_id):
    #         return
    #     guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))
    #     channel = guild.get_channel_or_thread(reaction.channel_id)

    #     if channel:
    #         channelAsText = cast(discord.TextChannel, channel)
    #         print(str(reaction.emoji) == hc_constants.ACCEPT)
    # if (
    #     cast(discord.Thread, channel).parent
    #     and cast(discord.TextChannel, cast(discord.Thread, channel).parent).id
    #     == hc_constants.VETO_HELLPITS
    # ):
    #     message = await channelAsText.fetch_message(reaction.message_id)
    #     thread_messages = [
    #         message
    #         async for message in message.channel.history(
    #             limit=3, oldest_first=True
    #         )
    #     ]

    #     first_message = thread_messages[0]
    #     link_message = thread_messages[2]
    #     # TODO: I hate that the name comparison is being used here
    #     if reaction.emoji.name == hc_constants.ACCEPT and (
    #         is_admin(cast(discord.Member, reaction.member))
    #         or is_veto(cast(discord.Member, reaction.member))
    #     ):
    #         vetoChall = getVetoChannel(bot=self.bot)
    #         # TODO: compartmentalize this
    #         ogMessage = await vetoChall.fetch_message(
    #             int(link_message.content.split("/").pop())
    #         )

    #         copy = await message.attachments[0].to_file()
    #         if copy:
    #             vetoChannel = getVetoChannel(bot=self.bot)
    #             vetoEntry = await vetoChannel.send(
    #                 content=first_message.content, file=copy
    #             )
    #             await handleVetoPost(message=vetoEntry, bot=self.bot)
    #             await ogMessage.add_reaction(hc_constants.DELETE)


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
