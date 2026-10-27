"""Intake for #submissions using the currently active submission set config."""

from __future__ import annotations

import io
import os
import traceback
from datetime import UTC, datetime
from typing import cast

import aiofiles
import discord
from discord import Message
from discord.ext import commands

import hc_constants
from accept_card import promote_from_submissions
from cogs.lifecycle.post_daily_submissions import gallery_uses_manifest
from cogs.lifecycle.submissions_closed import is_submissions_closed
from get_card_message import submission_card_name
from getters import (
    getMorkSubmissionsLoggingChannel,
    getSubmissionDiscussionChannel,
)
from is_admin import is_admin
from is_mork import reasonable_card
from set_config import SetConfig, cooldown_wait_message, hours_since_last_submission
from set_configs import active_set_cooldown_blocks


async def intake_submission_post(
    message: Message,
    bot: commands.Bot,
    config: SetConfig,
) -> None:
    if is_submissions_closed() and not is_admin(cast(discord.Member, message.author)):
        author_id = message.author.id
        preview = (message.content or "").strip()
        attachment_count = len(message.attachments)
        await message.delete()
        parts = [
            f"<@{author_id}> tried to post in <#{message.channel.id}> while it was closed."
        ]
        if preview:
            parts.append(preview[:500])
        if attachment_count:
            parts.append(f"({attachment_count} attachment(s))")
        print("\n".join(parts))
        return

    if len(message.attachments) == 0:
        return

    split_string = message.content.split("\n")
    card_name = split_string[0]
    if "@" in card_name:
        user = await bot.fetch_user(message.author.id)
        await user.send('No "@" are allowed in card title submissions to prevent me from spamming')
        return

    if not submission_card_name(message.content):
        discussionChannel = getSubmissionDiscussionChannel(bot)
        file = await message.attachments[0].to_file()
        await discussionChannel.send(
            f"<@{message.author.id}>, make sure to include the name of your card",
            file=file,
        )
        await message.delete()
        return

    author = message.author.mention
    if len(split_string) > 1:
        author = "; ".join([f"<@{raw}>" for raw in message.raw_mentions])

    state_file = hc_constants.SUBMISSIONS_STATE_FILE
    if os.path.exists(state_file):
        async with aiofiles.open(state_file, "r") as file:
            lines = await file.readlines()
            for line in lines:
                if line.startswith(f"{message.author.id}—"):
                    tempDate = datetime.strptime(
                        line.split("—")[1].replace("\n", ""),
                        "%Y-%m-%dT%H:%M:%S%z",
                    )
                    if active_set_cooldown_blocks(tempDate, config) and not is_admin(
                        cast(discord.Member, message.author)
                    ):
                        timeSinceLast = hours_since_last_submission(tempDate, config)
                        discussionChannel = getSubmissionDiscussionChannel(bot)
                        await discussionChannel.send(
                            f"<@{message.author.id}>, {cooldown_wait_message(config, timeSinceLast)}"
                        )
                        await message.delete()
                        return
    async with aiofiles.open(state_file, "a") as file:
        await file.write(
            f"{message.author.id}—{datetime.now(tz=UTC).strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
        )

    file = await message.attachments[0].to_file()
    if reasonable_card():
        acceptedChannel = getSubmissionDiscussionChannel(bot)
        logChannel = getMorkSubmissionsLoggingChannel(bot)
        acceptContent = f"{card_name} by {author} was accepted"
        attachment = message.attachments[0]
        attachment_data = await attachment.read()
        attachment_filename = attachment.filename or "card.png"
        try:
            await promote_from_submissions(
                bot=bot,
                veto_content=f"{card_name} by {message.author.name}",
                file=discord.File(
                    fp=io.BytesIO(attachment_data),
                    filename=attachment_filename,
                ),
                cardName=card_name,
                authorName=author,
                message_set_id=config.set_id,
                vc_mention_user_ids=config.vc_mention_user_ids,
            )
        except Exception as e:
            print(f"reasonable_card promote_from_submissions failed: {e}")
            return
        copy2 = discord.File(
            fp=io.BytesIO(attachment_data),
            filename=attachment_filename,
        )
        logContent = (
            f"{acceptContent}, message id: {message.id}, upvotes: 0, downvotes: 0, magic: true"
        )
        await acceptedChannel.send(content=f"✨✨ {acceptContent} ✨✨")
        await acceptedChannel.send(content="", file=file)
        await logChannel.send(content=logContent, file=copy2)
    else:
        contentMessage = f"{card_name} by {author}"
        sent_message = await message.channel.send(content=contentMessage, file=file)
        await sent_message.add_reaction(hc_constants.VOTE_UP)
        await sent_message.add_reaction(hc_constants.VOTE_DOWN)
        await sent_message.add_reaction(hc_constants.DELETE)

        await sent_message.create_thread(name=card_name[0:99])
        if gallery_uses_manifest() and config.set_id == hc_constants.ACTIVE_CUBE_ID:
            try:
                from submissions_gallery_manifest import append_submission

                attachment = message.attachments[0]
                image_bytes = await attachment.read()
                append_submission(
                    message_id=str(sent_message.id),
                    image_bytes=image_bytes,
                    filename=attachment.filename or "card.png",
                    card_name=card_name,
                )
            except Exception:
                traceback.print_exc()
    await message.delete()
