import os
import sys

from discord.ext import commands
from dotenv import load_dotenv

from shared_vars import intents

# systemd redirects stdout to a file, which makes Python block-buffer it (~8KB),
# so print()-based lifecycle logging never reaches /var/log/my_app.log in real time.
# Force line buffering so each line flushes immediately.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(line_buffering=True)  # type: ignore[union-attr]

load_dotenv()

DISCORD_ACCESS_TOKEN = os.environ["DISCORD_ACCESS_TOKEN"]


class MyBot(commands.Bot):
    async def setup_hook(self):
        print("This is asynchronous!")

        initial_extensions = [
            "cogs.General",
            "cogs.HellscubeDatabase",
            "cogs.Lifecycle",
            "cogs.Quotes",
            "cogs.Roles",
            "cogs.SpecificCards",
            # "cogs.Misc",
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
