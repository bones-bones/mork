

from datetime import datetime, timezone, timedelta
from typing import cast
import hc_constants
from discord.ext import commands
from discord import Emoji, Member, Role, TextChannel

from discord.utils import get

from is_admin import is_admin
from is_mork import is_mork



async def checkSubmissions(bot:commands.Bot):
    subChannel = cast(TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))
    vetoChannel = cast(TextChannel, bot.get_channel(hc_constants.VETO_CHANNEL))
    acceptedChannel = cast(TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL))
    logChannel = cast(TextChannel, bot.get_channel(hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL))
    timeNow = datetime.now(timezone.utc)
    oneWeek = timeNow + timedelta(weeks=-1)
    messages = subChannel.history(after = oneWeek, limit = None)
    if messages is None:
        return

    messages = [message async for message in messages]
    for messageEntry in messages:
   
        if "@everyone" in messageEntry.content:
            continue # just ignore these
        upvote = get(messageEntry.reactions, emoji = hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji = hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at
            # card was voted in
            if ((upCount - downCount) > 24
                and len(messageEntry.attachments) > 0
                and messageAge >= timedelta(days = 1)
                and is_mork(messageEntry.author.id)):
                prettyValid = False
                async for user in upvote.users():
                   if is_admin(cast(Member, user)):
                       prettyValid = True
                
                if downCount == 1 and not prettyValid:
                    user = await bot.fetch_user(hc_constants.LLLLLL) # If a message would be accepted, but there's only a single downvote, need llllll to add another downvote
                    await user.send("Verify " + messageEntry.jump_url)
                    continue
                file = await messageEntry.attachments[0].to_file()
                acceptContent = messageEntry.content + " was accepted"
                mention = f'<@{str(messageEntry.raw_mentions[0])}>'
                accepted_message_no_mentions = messageEntry.content.replace(mention, messageEntry.mentions[0].name)
                copy = await messageEntry.attachments[0].to_file()
                vetoEntry = await vetoChannel.send(content=accepted_message_no_mentions, file=copy)


                await vetoEntry.add_reaction(hc_constants.VOTE_UP)
                await vetoEntry.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.CIRION_SPELLING)))
                await vetoEntry.add_reaction(hc_constants.VOTE_DOWN)
                await vetoEntry.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.MANA_GREEN)))
                await vetoEntry.add_reaction(cast(Emoji, bot.get_emoji(hc_constants.MANA_WHITE)))
                await vetoEntry.add_reaction("🤮")
                await vetoEntry.add_reaction("🤔")
                
                thread = await vetoEntry.create_thread(name = vetoEntry.content[0:99])
                role = get(vetoEntry.author.guild.roles, id = hc_constants.VETO_COUNCIL)
                await thread.send(role.mention)


                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content = acceptContent)
                await acceptedChannel.send(content = "", file = file)
                await logChannel.send(content = logContent, file = copy2)
                await messageEntry.delete()
                continue
    print("------done checking submissions-----")




async def checkMasterpieceSubmissions(bot:commands.Bot):
    subChannel = bot.get_channel(hc_constants.MASTERPIECE_CHANNEL)
    vetoChannel = bot.get_channel(hc_constants.VETO_CHANNEL)
    acceptedChannel = bot.get_channel(hc_constants.MASTERPIECE_DISCUSSION_CHANNEL)
    logChannel = bot.get_channel(hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL)
    timeNow = datetime.now(timezone.utc)
    oneWeek = timeNow + timedelta(weeks=-1)
    messages = subChannel.history(after = oneWeek, limit = None)
    if messages is None:
        return

    messages = [message async for message in messages]
    for messageEntry in messages:
   
        if "@everyone" in messageEntry.content:
            continue # just ignore these
        upvote = get(messageEntry.reactions, emoji = hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji = hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at
            # card was voted in
            if ((upCount - downCount) > 31
                and len(messageEntry.attachments) > 0
                and messageAge >= timedelta(days = 1)
                and is_mork(messageEntry.author.id)):
                prettyValid = False
                async for user in upvote.users():
                   if is_admin(user):
                       prettyValid = True
                
                if downCount == 1 and not prettyValid:
                    user = await bot.fetch_user(hc_constants.LLLLLL) # If a message would be accepted, but there's only a single downvote, need llllll to add another downvote
                    await user.send("Verify " + messageEntry.jump_url)
                    continue
                file = await messageEntry.attachments[0].to_file()
                acceptContent = messageEntry.content + " was accepted"
                mention = f'<@{str(messageEntry.raw_mentions[0])}>'
                accepted_message_no_mentions = messageEntry.content.replace(mention, messageEntry.mentions[0].name)
                copy = await messageEntry.attachments[0].to_file()
                vetoEntry = await vetoChannel.send(content="HC5: "+accepted_message_no_mentions, file = copy)


                await vetoEntry.add_reaction(hc_constants.VOTE_UP)
                await vetoEntry.add_reaction(bot.get_emoji(hc_constants.CIRION_SPELLING))
                await vetoEntry.add_reaction(hc_constants.VOTE_DOWN)
                await vetoEntry.add_reaction(bot.get_emoji(hc_constants.MANA_GREEN))
                await vetoEntry.add_reaction(bot.get_emoji(hc_constants.MANA_WHITE))
                await vetoEntry.add_reaction("🤮")
                await vetoEntry.add_reaction("🤔")
                
                thread = await vetoEntry.create_thread(name = vetoEntry.content[0:99])
                role:Role = get(vetoEntry.author.guild.roles, id = hc_constants.VETO_COUNCIL)
                await thread.send(role.mention)


                copy2 = await messageEntry.attachments[0].to_file()
                logContent = f"{acceptContent}, message id: {messageEntry.id}, upvotes: {upCount}, downvotes: {downCount}"
                await acceptedChannel.send(content = acceptContent)
                await acceptedChannel.send(content = "", file = file)
                await logChannel.send(content = logContent, file = copy2)
                await messageEntry.delete()
                continue
    print("------done checking submissions-----")