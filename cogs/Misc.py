from acceptCard import accept_card
from typing import cast

from discord import RawReactionActionEvent, TextChannel
import discord
from discord.ext import commands

from getCardMessage import parseCardNameAndAuthor

from acceptCard import accept_card
import hc_constants

from is_mork import is_mork




class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: RawReactionActionEvent):
        if is_mork(reaction.user_id):
            return
        guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))
        channel = guild.get_channel_or_thread(reaction.channel_id)

        if channel == None:
            return

        channelAsText = cast(discord.TextChannel, channel)
        message = await channelAsText.fetch_message(reaction.message_id)
        # The sneaky errata case for HC8
        if (
            reaction.emoji.id == hc_constants.SYMBOL_UNTAP
            and reaction.user_id == hc_constants.LLLLLL
        ):
            # <MessageReference message_id=1438689619209097308 channel_id=798690672512335932 guild_id=631288872814247966>
            og_message = message
            reference = message.reference

            if reference != None and reference.message_id != None:
                original_channel = cast(
                    TextChannel,
                    guild.get_channel_or_thread(reference.channel_id),
                )
                message = await original_channel.fetch_message(
                    reference.message_id
                )

            file = await message.attachments[0].to_file()
            acceptanceMessage = message.content

            print(acceptanceMessage)

            dbname, card_author = parseCardNameAndAuthor(acceptanceMessage)
            resolvedName = dbname if dbname != "" else "Crazy card with no name"
            resolvedAuthor = card_author if card_author != "" else "no author"
            cardMessage = f"**{resolvedName}** by **{resolvedAuthor}**"

            set_to_add_to = "HCV"

            channel_to_add_to = hc_constants.VETO_CARD_LIST

            await accept_card(
                bot=self.bot,
                file=file,
                cardMessage=cardMessage,
                cardName=dbname,
                authorName=card_author,
                setId=set_to_add_to,
                channelIdForCard=channel_to_add_to,
            )

            await og_message.delete()



# @commands.command()
# async def test(
#     self,
#     ctx: commands.Context,
# ):
#     if ctx.author.id == hc_constants.LLLLLL:
#         ...
#     else:
#         await ctx.send("no")


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
