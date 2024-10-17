from datetime import datetime, timedelta, timezone
import io
import json
import os
import random
import re
from typing import Dict, List, cast
import aiohttp
import discord
from discord.ext import commands
from discord.utils import get
from CardClasses import Side, CardSearch
from cogs.HellscubeDatabase import searchFor
from getters import getBotTest, getSubmissionDiscussionChannel, getVetoChannel
from handleVetoPost import handleVetoPost
from isRealCard import isRealCard
from printCardImages import sendImageReply
from shared_vars import googleClient


from acceptCard import acceptCard
from cardNameRequest import cardNameRequest
import hc_constants
from is_admin import is_veto, is_admin

from is_mork import is_mork

from shared_vars import intents, cardSheet, allCards


cardList: list[CardSearch] = []


print(cardList)


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
