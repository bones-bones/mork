from typing import cast
from discord import Emoji, Member, Message, Role
import discord
from discord.ext import commands
from discord.utils import get

import hc_constants


async def handleVetoPost(message: Message, bot: commands.Bot):
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
        get(cast(Member, message.author).guild.roles, id=hc_constants.VETO_COUNCIL)
    )
    judgeRole = cast(
        Role,
        get(cast(Member,message.author).guild.roles, id=hc_constants.JUDGES)
    )

    copy_for_discussion = await message.attachments[0].to_file()

    mentions = [role.mention, judgeRole.mention]

    author_s = message.content.split(" by ")[1]
    creator_mentions = author_s.split("; ")

    for ref in creator_mentions:
        tempUser = get(bot.users, name=ref)
        if tempUser:
            mentions.append(f"<@{str(tempUser.id)}>")

    hellpits_channel = bot.get_channel(hc_constants.VETO_HELLPITS)

    hellpit_discussion_thread = await cast(
        discord.TextChannel, hellpits_channel
    ).create_thread(name=message.content[0:99], type=discord.ChannelType.private_thread)

    await hellpit_discussion_thread.send(
        file=copy_for_discussion, content=message.content[0:99]
    )
    await hellpit_discussion_thread.send(", ".join(mentions))

    await veto_poll_thread.send(hellpit_discussion_thread.jump_url)

    await hellpit_discussion_thread.send(message.jump_url)

    await veto_poll_thread.edit(locked=True)
