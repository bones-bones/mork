from discord.ext import commands

from shared_vars import intents
from bot_secrets.discord_token import DISCORD_ACCESS_TOKEN


class MyBot(commands.Bot):
    async def setup_hook(self):
        print("This is asynchronous!")

        initial_extensions = [
            # "cogs.General",
            # "cogs.HellscubeDatabase",
            "cogs.Lifecycle",
            # "cogs.Quotes",
            # "cogs.Roles",
            # "cogs.SpecificCards",
            "cogs.Misc",
        ]
        for i in initial_extensions:
            await self.load_extension(i)


bot = MyBot(command_prefix="!", case_insensitive=True, intents=intents)
bot.remove_command("help")


@bot.command()
async def check_cogs(ctx: commands.Context, cog_name):
    try:
        await bot.load_extension(f"cogs.{cog_name}")
    except commands.ExtensionAlreadyLoaded:
        await ctx.send("Cog is loaded")
    except commands.ExtensionNotFound:
        await ctx.send("Cog not found")
    else:
        await ctx.send("Cog is unloaded")
        await bot.unload_extension(f"cogs.{cog_name}")


bot.run(DISCORD_ACCESS_TOKEN)
