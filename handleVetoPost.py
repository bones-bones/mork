import random
from typing import cast
from discord import Emoji, Member, Message, Role
import discord
from discord.ext import commands
from discord.utils import get

import hc_constants

portal_time = True


async def handleVetoPost(
    message: Message,
    bot: commands.Bot,
    veto_council: int | None,
):
    if portal_time:
        veto_council = hc_constants.VETO_COUNCIL_PORTAL
    else:
        if veto_council == None:
            veto_council = random.choice(
                [hc_constants.VETO_COUNCIL, hc_constants.VETO_COUNCIL_2]
            )
        if veto_council == hc_constants.VETO_COUNCIL:
            await message.add_reaction(hc_constants.CLOCK)
        else:
            await message.add_reaction(hc_constants.WOLF)

    await message.add_reaction(hc_constants.VOTE_UP)

    # Errata
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.CIRION_SPELLING)))
    await message.add_reaction(hc_constants.VOTE_DOWN)

    # too strong
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.MANA_GREEN)))

    # too weak
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.MANA_WHITE)))
    await message.add_reaction(hc_constants.BAD)
    await message.add_reaction(hc_constants.UNSURE)

    veto_poll_thread = await message.create_thread(name=message.content[0:99])

    role = cast(
        Role,
        get(cast(Member, message.author).guild.roles, id=veto_council),
    )
    judgeRole = cast(
        Role, get(cast(Member, message.author).guild.roles, id=hc_constants.JUDGES)
    )

    copy_for_discussion = await message.attachments[0].to_file()

    mentions = [role.mention, judgeRole.mention]
    splitted = message.content.split(" by ")
    author_s = splitted[1] if splitted.__len__() > 1 else "NO AUTHOR"
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
    return
