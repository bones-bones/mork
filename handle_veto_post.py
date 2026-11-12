from typing import cast

import discord
from discord import Emoji, Member, Message, Role
from discord.ext import commands
from discord.utils import get

import hc_constants
from utils import at

portal_time = False

VETO_POLL_UUID_PREFIX = "uuid: "


def _is_discord_channel_url(text: str) -> bool:
    lowered = text.lower()
    return "discord.com/channels/" in lowered or "discordapp.com/channels/" in lowered


def parse_hellfall_uuid_from_veto_poll_messages(contents: list[str]) -> str | None:
    """Find ``uuid: <hellfall print id>`` anywhere in the veto-poll thread messages."""
    for content in contents:
        text = (content or "").strip()
        if not text.lower().startswith("uuid:"):
            continue
        uuid_value = text.split(":", 1)[1].strip()
        if uuid_value:
            return uuid_value
    return None


def parse_hcid_from_veto_poll_messages(contents: list[str]) -> str | None:
    """Legacy: a thread message that is only a numeric hcid."""
    for content in contents:
        text = (content or "").strip()
        if text.isdigit():
            return text
    return None


def parse_hellpit_thread_id_from_veto_poll_messages(contents: list[str]) -> int | None:
    """Find the hellpit Discord jump URL in the veto-poll thread (not fixed index)."""
    for content in contents:
        text = (content or "").strip()
        if not text or not _is_discord_channel_url(text):
            continue
        try:
            return int(text.rstrip("/").split("/").pop())
        except ValueError:
            continue
    return None


async def hcid_from_veto_poll_thread(thread: discord.Thread) -> str | None:
    messages = [message async for message in thread.history(limit=10, oldest_first=True)]
    contents = [message.content for message in messages]
    uuid_value = parse_hellfall_uuid_from_veto_poll_messages(contents)
    if uuid_value:
        from accept_card import hcid_from_unapproved_hellfall_id

        return hcid_from_unapproved_hellfall_id(uuid_value)
    return parse_hcid_from_veto_poll_messages(contents)


async def handle_veto_post(
    message: Message,
    bot: commands.Bot,
    veto_council: int | None,
    submission_thread_url: str | None = None,
    hellfall_uuid: str | None = None,
    vc_mention_user_ids: tuple[int, ...] = (),
):
    if portal_time:
        veto_council = hc_constants.VETO_COUNCIL_PORTAL
    else:
        await message.add_reaction(hc_constants.CLOCK)
        # if veto_council is None:
        #     veto_council = random.choice(
        #         [hc_constants.VETO_COUNCIL, hc_constants.VETO_COUNCIL_2]
        #     )
        # if veto_council == hc_constants.VETO_COUNCIL_PORTAL:
        #     await message.add_reaction(hc_constants.CLOCK)
        # else:
        #     await message.add_reaction(hc_constants.CLOCK)
    veto_council = hc_constants.VETO_COUNCIL
    await message.add_reaction(hc_constants.VOTE_UP)

    # Errata
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.CIRION_SPELLING)))
    await message.add_reaction(hc_constants.VOTE_DOWN)

    # too strong
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.NERF)))

    # too weak
    await message.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.BUFF)))
    await message.add_reaction(hc_constants.BAD)
    await message.add_reaction(hc_constants.UNSURE)

    veto_poll_thread = await message.create_thread(name=message.content[0:99])

    judgeRole = cast(Role, get(cast(Member, message.author).guild.roles, id=hc_constants.JUDGES))

    copy_for_discussion = await message.attachments[0].to_file()

    if vc_mention_user_ids:
        mentions = [f"<@{uid}>" for uid in vc_mention_user_ids]
        mentions.append(judgeRole.mention)
    else:
        role = cast(
            Role,
            get(cast(Member, message.author).guild.roles, id=veto_council),
        )
        mentions = [role.mention, judgeRole.mention]

    splitted = message.content.rsplit(" by ", 1)
    author_s = at(splitted, 1, "NO AUTHOR")
    creator_mentions = author_s.split("; ")

    for ref in creator_mentions:
        tempUser = get(bot.users, name=ref)
        if tempUser:
            mentions.append(f"<@{tempUser.id}>")

    hellpits_channel = bot.get_channel(hc_constants.VETO_HELLPITS)

    hellpit_discussion_thread = await cast(discord.TextChannel, hellpits_channel).create_thread(
        name=message.content[0:99], type=discord.ChannelType.private_thread
    )

    await hellpit_discussion_thread.send(file=copy_for_discussion, content=message.content[0:99])
    await hellpit_discussion_thread.send(", ".join(mentions))

    await veto_poll_thread.send(hellpit_discussion_thread.jump_url)
    if hellfall_uuid:
        await veto_poll_thread.send(f"{VETO_POLL_UUID_PREFIX}{hellfall_uuid}")

    await hellpit_discussion_thread.send(message.jump_url)

    if submission_thread_url:
        await hellpit_discussion_thread.send(submission_thread_url)

    await veto_poll_thread.edit(locked=True)
