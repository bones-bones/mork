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
from shared_vars import googleClient


import asyncpraw


from acceptCard import acceptCard
from cardNameRequest import cardNameRequest
import hc_constants
from is_admin import is_veto
import is_admin
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


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
