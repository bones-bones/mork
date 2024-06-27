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
from shared_vars import googleClient


import asyncpraw


from acceptCard import acceptCard
from cardNameRequest import cardNameRequest
import hc_constants
from is_admin import is_veto
import is_admin
from is_mork import is_mork

from shared_vars import intents, cardSheet, allCards


client = discord.Client(intents=intents)


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     global log
    #     async with aiohttp.ClientSession() as session:
    #         async with session.get("https://api.scryfall.com/cards/search?as=grid&order=name&q=command+oracle%3A•+%28game%3Apaper%29") as resp:
    #             if resp.status != 200:
    #                 #await ctx.send('Something went wrong while getting the link. Wait for @llllll to fix it.')
    #                 return
    #             response = json.loads( await resp.read())

    #             mapped = (map( lambda x: x['oracle_text'], response["data"]))
    #             joined = "\n".join(list(mapped))
    #             choiceless = joined.replace("Choose two —\n", "")
    #             asSplit = choiceless.split('\n')

    #             results = random.choices(population = asSplit, k = 6)
    #             ctx.send("Choose two —\n{0}".format("\n".join(results)))
    #             await session.close()
    # print(f'{self.bot.user.name} has connected to Discord!')
    # print( get(self.bot.users, name="llllll______").id)
    # the_thread = vetoChannel.threads[0]

    # print([message async for message in vetoChannel.threads[0].history(limit = 1, oldest_first = True)])
    # vetoChannel = cast(discord.TextChannel, self.bot.get_channel(hc_constants.BOT_TEST_CHANNEL))
    # print( [message async for message in vetoChannel.history(limit=1)][0].content)
    # # [message async for message in vetoChannel.history(limit=1)][0]
    # print(vetoChannel.threads)

    # @commands.Cog.listener()
    # async def on_raw_reaction_add(self, reaction: discord.RawReactionActionEvent):
    #     guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))
    #     channel = guild.get_channel_or_thread(reaction.channel_id)

    #     print(channel, reaction.message_id, reaction.channel_id)

    # @commands.Cog.listener()
    # async def on_message(self, message:discord.Message):
    #     print('ping')
    #     if message.channel.id == hc_constants.VETO_TEST and not is_mork(message.author.id):
    #         print('second')
    #         guild = cast(discord.Guild, message.guild)
    #         role = get(message.author.guild.roles, id = hc_constants.VETO_COUNCIL)

    #         copyagain = await message.attachments[0].to_file()
    #         channel =  guild.get_channel(hc_constants.VETO_TEST)

    #         if channel:
    #             channelAsText = cast(discord.TextChannel,channel)
    #             secretThread = await channelAsText.create_thread(name="hey", type = discord.ChannelType.private_thread)
    #             await secretThread.send(file = copyagain, content="heyyyyyy")
    #             mentions = [role.mention]

    #             for raw in message.raw_mentions:
    #                 mentions.append(f'<@{str(raw)}>')
    #             await secretThread.send(', '.join(mentions))

    # @commands.command()
    # async def sss(self,ctx:commands.Context):

    #     print(member.get_role(631288945044357141) != None)
    #     guild = client.get_guild()
    #     member = await guild.fetch_member(hc_constants.LLLLLL)
    #     print(member)
    #     if message.channel.id == hc_constants.REDDIT_CHANNEL:
    #             lastTwo = [mess async for mess in message.channel.history(limit = 2)]
    #             if not is_mork(lastTwo[0].author.id) and is_mork(lastTwo[1].author.id) and "reddit says: " in lastTwo[1].content:
    #                 reddit = asyncpraw.Reddit(
    #                     client_id = ID,
    #                     client_secret = SECRET,
    #                     password = PASSWORD,
    #                     user_agent = USER_AGENT,
    #                     username = NAME
    #                 )
    #                 # print(await reddit.user.me())
    #                 reddit_url = lastTwo[1].content.replace("reddit says: ",'')

    #                 #https://www.reddit.com/r/HellsCube/comments/1c2ii4s/sometitle/
    #                 post_id =  re.search("comments/([^/]*)", reddit_url).group(1)
    #                 post = await reddit.submission(post_id)
    #                 await post.reply(f"i'm just a bot that can't see pictures, but if i could, i'd say: {lastTwo[0].content}")

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     # try:
    #     #         subChannel = cast(discord.TextChannel, self.bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))
    #     #         timeNow = datetime.now(timezone.utc)
    #     #         oneDay = timeNow + timedelta(days=-1)
    #     #         messages = subChannel.history(after = oneDay, limit = None)
    #     #         images: List[Dict[str, str]]=[]
    #     #         if messages is None:
    #     #             return

    #     #         messages = [message async for message in messages][:10]
    #     #         for messageEntry in messages:
    #     #             file = await messageEntry.attachments[0].to_file()
    #     #             file_data = file.fp.read()
    #     #             image_path = f'tempImages/{file.filename}'
    #     #             images.append({"image_path": image_path})
    #     #             with open(image_path, 'wb') as out:
    #     #                 out.write(file_data)
    #     #         await postGalleryToReddit(
    #     #             title = f"Today's Submissions: Have any strong opinions on these cards? Join the discord to share them!",
    #     #             images = images,
    #     #             flair = hc_constants.OFFICIAL_FLAIR
    #     #         )
    #     #         for imageEntry in images:
    #     #             os.remove(list(imageEntry.values())[0])
    #     # except Exception as e:
    #     #         print(e)

    #     vetoChannel = cast(discord.TextChannel, self.bot.get_channel(hc_constants.VETO_CHANNEL))
    #     # vetoDiscussionChannel = cast(discord.TextChannel, self.bot.get_channel(hc_constants.VETO_DISCUSSION_CHANNEL))
    #     timeNow = datetime.now(timezone.utc)
    #     fourWeeksAgo = timeNow + timedelta(days=-28)

    #     messages = vetoChannel.history(after = fourWeeksAgo, limit = None)

    #     if messages is None:
    #         return
    #     messages = [message async for message in messages]

    #     for messageEntry in messages:

    #         guild = cast(discord.Guild, messageEntry.guild)
    #         thread = cast(discord.Thread, guild.get_channel_or_thread(messageEntry.id))
    #         if thread:
    #         # new code
    #             threadMessages = thread.history()
    #             threadMessages = [message async for message in threadMessages]
    #             for threadMessage in threadMessages:

    #                 if threadMessage.content == f"<@&{798689768379908106}>":
    #                    if (timeNow - threadMessage.created_at) < timedelta(days = 7):
    #                     # then it was recently acted upon
    #                     print(threadMessage.created_at, messageEntry.content)

    # end new code


# Mork Rasewoter#1393
# mork2#8326

# @commands.Cog.listener()
# async def on_ready(self):


# @commands.command()
# async def modal(self, ctx:commands.Context):
#    print(ctx.interaction)
#    await ctx.interaction.response.send_modal(MorkModal())


# @commands.Cog.listener()
# async def on_ready(self):
#     # print(f'{self.bot.user.name} has connected to Discord!')
#     cardlist = self.bot.get_channel(hc_constants.FOUR_ONE_CARD_LIST_CHANNEL)
#     messages = cardlist.history( limit=10 )
#     messages = [message async for message in messages]
#     for message in messages:
#         #print(message.content)
#         [card,creator]=(message.content.split('** by **'))
#         card = card.replace("**",'')
#        # print(card)


#         creator = creator.replace("**",'')
#       #  print(creator)

#         cardMessage=message.content.replace('**','')


#         file = await message.attachments[0].to_file()
#         print( cardMessage, file, card, creator)
#         await acceptCard(
#             bot=self.bot,
#             cardMessage=cardMessage,
#             file=file,
#             cardName=card,
#             authorName=creator
#         )


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
