
from datetime import datetime, timedelta, timezone
import re
from typing import cast
import discord
from discord.ext import commands
from discord.utils import get


import asyncpraw


from acceptCard import acceptCard
from cogs.Lifecycle import VetoPollResults, getVetoPollsResults
import hc_constants
from is_mork import is_mork
from secrets.reddit_secrets import ID, NAME, PASSWORD, SECRET, USER_AGENT
from shared_vars import intents,cardSheet,allCards


client = discord.Client(intents=intents)

class MiscCog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot





    # @commands.command()
    # async def sss(self,ctx:commands.Context):
        
    #     print(member.get_role(631288945044357141) != None)
    #     guild = client.get_guild()
    #     member = await guild.fetch_member(hc_constants.LLLLLL)
    #     print(member)

    @commands.Cog.listener()
    async def on_message(self, message:discord.Message):
        if message.channel.id == hc_constants.BOT_TEST_CHANNEL:
            splitString = message.content.split("\n")
            title = splitString[0]
            update = splitString[1]
            reason = splitString[2]
            if not reason or not update or not title:
                await message.channel.send(f"<@{message.author.id}>, Make sure your post is formatted like this:\nClockwolf (name of card)\nMake it cost 5 mana (Suggested change. Write Cut if you want the whole card gone)\nToo strong (Reasoning, as brief or detailed as you want, but remember you need to convince others this change is a good idea)")
                await message.delete()




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
        






    # @commands.Cog.listener()
    # async def on_ready(self):
    #     global log
    #     print(f'{self.bot.user.name} has connected to Discord!')
    #     vetoChannel = self.bot.get_channel(hc_constants.VETO_CHANNEL)

       
    #     messages = vetoChannel.history( limit=4 )
    #     # messages = [message async for message in messages]
    #     # for message in messages:
    #     #     if message.content == "EXACT SUBJECT":
    #     #         print(message.content)
    #     #        # await message.delete()

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
         



async def setup(bot:commands.Bot):
    await bot.add_cog(MiscCog(bot))



