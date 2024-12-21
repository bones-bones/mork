from typing import Optional, cast
from discord import Emoji, Member, Message, Role, Thread
import discord
from discord.abc import Messageable
from discord.ext import commands
from discord.utils import get

import hc_constants


async def handleVetoPost(message: Message, bot: commands.Bot, old_thread: Thread | None = None) -> Thread:
    await message.add_reaction(hc_constants.VOTE_UP)
    await message.add_reaction(
        cast(Emoji, bot.get_emoji(hc_constants.CIRION_SPELLING))
    )  # Errata
    await message.add_reaction(hc_constants.VOTE_DOWN)

    await message.add_reaction(
        cast(Emoji, bot.get_emoji(hc_constants.MANA_GREEN))
    )  # too strong
    await message.add_reaction(
        cast(Emoji, bot.get_emoji(hc_constants.MANA_WHITE))
    )  # too weak
    await message.add_reaction(hc_constants.BAD)
    await message.add_reaction(hc_constants.UNSURE)

    veto_poll_thread = await message.create_thread(name=message.content[0:99])


    role = cast(
        Role,
        get(cast(Member, message.author).guild.roles, id=hc_constants.VETO_COUNCIL),
    )
    judgeRole = cast(
        Role, get(cast(Member, message.author).guild.roles, id=hc_constants.JUDGES)
    )

    copy_for_discussion = await message.attachments[0].to_file()

    authors_to_message_mention = []

    author_s = message.content.split(" by ")[1]
    creator_mentions = author_s.split("; ")

    for ref in creator_mentions:
        tempUser = get(bot.users, name=ref)
        if tempUser:
            authors_to_message_mention.append(f"<@{str(tempUser.id)}>")

    mentions = [role.mention, judgeRole.mention]
    mentions.extend(authors_to_message_mention)    

    hellpits_channel = bot.get_channel(hc_constants.VETO_HELLPITS)

    hellpit_discussion_thread = await cast(
        discord.TextChannel, hellpits_channel
    ).create_thread(name=message.content[0:99], type=discord.ChannelType.private_thread)

    await hellpit_discussion_thread.send(
        file=copy_for_discussion, content=message.content[0:99]
    )

    if old_thread:
        old_thread_link = await hellpit_discussion_thread.send(f"Old thread: {old_thread.jump_url}")
        await old_thread_link.pin()

    await hellpit_discussion_thread.send(f"Veto polls: {message.jump_url}")
    await hellpit_discussion_thread.send(", ".join(mentions))

    if not old_thread:
         await hellpit_discussion_thread.send(f"{", ".join(authors_to_message_mention)}, the Veto Council will deliberate on the card and discuss their thoughts here, and say if any changes are required.")

    await veto_poll_thread.edit(locked=True)
    await veto_poll_thread.send(hellpit_discussion_thread.jump_url)

    return hellpit_discussion_thread
