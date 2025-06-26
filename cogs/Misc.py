from datetime import datetime, timedelta, timezone

from typing import Dict, List, cast

from discord import TextChannel
from discord.ext import commands
from discord.utils import get
from cogs.HellscubeDatabase import searchFor

authorSplit = "$#$#$"
QUOTE_SPLIT = ";%;%;"
from cogs.lifecycle import post_daily_submissions
from getters import getBotTest, getSubmissionDiscussionChannel, getVetoChannel
from handleVetoPost import handleVetoPost
from isRealCard import isRealCard
from printCardImages import send_image_reply
from shared_vars import googleClient
from shared_vars import drive

from acceptCard import acceptCard
from cardNameRequest import cardNameRequest
import hc_constants
from is_admin import is_veto, is_admin

from is_mork import is_mork

from shared_vars import intents, cardSheet, allCards

from cogs.lifecycle.post_daily_submissions import post_daily_submissions


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


#     @commands.Cog.listener()
#     async def on_ready(self):
#         rulesChannel = cast(TextChannel, self.bot.get_channel(631289262519615499))
#         await rulesChannel.send(
#             f"""1) Don't harass people, especially other server members.
# 2) No excessively NSFW comment, especially non-cube related. Anything relating to minors is grounds for instant ban.
# 3) No spamming.
# 4) Keep discussion in its respective channel.
# 5) Racism, homophobia, and other forms of bigotry will not be tolerated.
# 6) When an urgent situation arises, ping <@&631288945044357141>.
# 8) Usage of an alt for the purpose of ban evasion will result in a ban, regardless of standing or circumstance of the new account.
# 9) Don’t overdo it with threads and avoid creating threads in channels which are meant to be read only. Mainly channels like <#631289278479073303>, all the card list channels and basically every other channel in this category.
# """
#         )

# @commands.command()
# async def test(
#     self,
#     ctx: commands.Context,
# ):
#     if ctx.author.id == hc_constants.LLLLLL:
#         ...
#     else:
#         await ctx.send("no")

# @commands.Cog.listener()
# async def on_raw_reaction_add(self, reaction: discord.RawReactionActionEvent):
#     guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))

#     channel = guild.get_channel_or_thread(reaction.channel_id)

#     print(type(channel), type(channel) == discord.TextChannel)

#     print(
#         f"{cast(discord.ClientUser,self.bot.user).name} has connected to Discord!"
#     )
#     subChannel = getVetoChannel(self.bot)
#     message = await subChannel.fetch_message(1338647514940833935)
#     guild = cast(discord.Guild, self.bot.get_guild(hc_constants.SERVER_ID))
#     thread = cast(discord.Thread, guild.get_channel_or_thread(message.id))
#     if thread:
#         threadMessages = thread.history(oldest_first=True, limit=2)
#         threadMessages = [tm async for tm in threadMessages]
#         hellpit_target = int(threadMessages[1].content.split("/").pop())
#         hellpit_thread = cast(
#             discord.Thread, guild.get_channel_or_thread(hellpit_target)
#         )
#         newest_message = await hellpit_thread.history(limit=1).__anext__()
#         print(newest_message)

# for the card Avatar of BallsJr123
# @commands.command()
# async def avatarOfBalls(self, ctx: commands.Context, cost):
#     print("oi")
#     results = searchFor({"cmc": [(cost, "=")], "types": ["creature"]})
#     if results.__len__() == 0:
#         await ctx.send("nothing found for that cmc")
#     result = random.choice(results)
#     print(results.__len__())
#     await send_image_reply(
#         url=result.img(), cardname=result.name(), text=None, message=ctx.message
#     )

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
