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
from getters import getVetoChannel
from handleVetoPost import handleVetoPost
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
