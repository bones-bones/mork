import io
from typing import cast

import discord
from discord import RawReactionActionEvent, TextChannel
from discord.ext import commands

import hc_constants
from accept_card import promote_from_submissions
from get_card_message import parseCardNameAndAuthor
from getters import getMorkSubmissionsLoggingChannel, getSubmissionDiscussionChannel
from is_mork import is_mork


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: RawReactionActionEvent):
        if is_mork(reaction.user_id):
            return
        if (
            reaction.emoji.id != hc_constants.SYMBOL_UNTAP
            or reaction.user_id != hc_constants.LLLLLL
        ):
            return
        print(f"reaction: {reaction.emoji}")
        guild = cast(discord.Guild, self.bot.get_guild(cast(int, reaction.guild_id)))
        channel = guild.get_channel_or_thread(reaction.channel_id)
        if channel is None:
            return

        channel_as_text = cast(TextChannel, channel)
        message = await channel_as_text.fetch_message(reaction.message_id)
        og_message = message

        reference = message.reference
        if reference is not None and reference.message_id is not None:
            original_channel = cast(
                TextChannel,
                guild.get_channel_or_thread(reference.channel_id),
            )
            message = await original_channel.fetch_message(reference.message_id)

        if not message.attachments:
            return

        dbname, card_author = parseCardNameAndAuthor(message.content)
        if not dbname:
            return

        resolved_author = card_author if card_author.strip() else "no author"
        veto_content = f"{dbname} by {resolved_author}"

        attachment = message.attachments[0]
        attachment_data = await attachment.read()
        attachment_filename = attachment.filename or "card.png"

        submission_thread = guild.get_channel_or_thread(message.id)
        submission_thread_url = submission_thread.jump_url if submission_thread else None

        try:
            await promote_from_submissions(
                bot=self.bot,
                veto_content=veto_content,
                file=discord.File(
                    fp=io.BytesIO(attachment_data),
                    filename=attachment_filename,
                ),
                cardName=dbname,
                authorName=resolved_author,
                submission_thread_url=submission_thread_url,
            )
        except Exception as e:
            print(f"untap promote_from_submissions failed: {e}")
            return

        accept_content = f"{veto_content} was accepted"
        discussion = getSubmissionDiscussionChannel(self.bot)
        log_channel = getMorkSubmissionsLoggingChannel(self.bot)
        await discussion.send(content=f"✨✨ {accept_content} ✨✨ (untap)")
        await discussion.send(
            content="",
            file=discord.File(
                fp=io.BytesIO(attachment_data),
                filename=attachment_filename,
            ),
        )
        await log_channel.send(
            content=f"{accept_content}, message id: {message.id}, untap: true",
            file=discord.File(
                fp=io.BytesIO(attachment_data),
                filename=attachment_filename,
            ),
        )

        try:
            await og_message.delete()
        except discord.HTTPException as e:
            print(f"untap cleanup delete failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
