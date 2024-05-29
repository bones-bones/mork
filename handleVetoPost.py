
from typing import cast
from discord import Emoji, Member, Message, Role
import discord
from discord.ext import commands
from discord.utils import get

import hc_constants


async def handleVetoPost(message:Message, bot:commands.Bot):
    await message.add_reaction(hc_constants.VOTE_UP)
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.CIRION_SPELLING))) # Errata
    await message.add_reaction(hc_constants.VOTE_DOWN)
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.MANA_GREEN))) # too strong
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.MANA_WHITE))) # too weak
    await message.add_reaction(hc_constants.BAD)
    await message.add_reaction(hc_constants.UNSURE)
    thread = await message.create_thread(name = message.content[0:99])

    role = cast(Role, get(cast(Member, message.author).guild.roles, id = hc_constants.VETO_COUNCIL))

    copyforDiscussion = await message.attachments[0].to_file()


    mentions = [role.mention]

    author_s = message.content.split(" by ")[1]
    creator_mentions = author_s.split("; ")

    for ref in creator_mentions:
        tempUser = get(bot.users, name = ref)
        mentions.append(f'<@{str(tempUser.id)}>')

    hellpit_channel = bot.get_channel(hc_constants.VETO_HELLPITS)

    channelAsText = cast(discord.TextChannel,hellpit_channel)
    secretThread = await channelAsText.create_thread(name = message.content[0:99], type = discord.ChannelType.private_thread)
    await secretThread.send(file = copyforDiscussion, content = message.content[0:99])


    await secretThread.send(', '.join(mentions))

    await thread.send(secretThread.jump_url)
    await thread.edit(locked = True)