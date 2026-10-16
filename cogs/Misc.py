import discord
from discord import RawReactionActionEvent
from discord.ext import commands

from is_mork import is_mork


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: RawReactionActionEvent):
        if is_mork(reaction.user_id):
            return
        # Disabled: sixel untap reaction bypassed veto/compile and accepted straight to HCV.


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
