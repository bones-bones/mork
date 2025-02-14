from datetime import datetime, timedelta, timezone
import random

from discord import Message
from attr import dataclass
from discord.ext import commands
from discord.utils import get


from getters import getVetoChannel
import hc_constants


"""
This function groups previous poll results. It's used in two ways: for the compile veto command, where actual processing is done, and in personalhell, which is a read-only op.
"""


async def getVetoPollsResults(bot: commands.Bot, ctx: commands.Context):
    vetoChannel = getVetoChannel(bot)
    timeNow = datetime.now(timezone.utc)
    fourWeeksAgo = timeNow + timedelta(days=-28 * 3)
    epicCatchphrases = [
        "If processing lasts more than 5 minutes, consult your doctor.",
        "on it, yo.",
        "ya ya gimme a sec",
        "processing...",
        "You're not the boss of me",
        "ok, zaddy~",
        "but what of the children?",
        "?",
        "workin' on it!",
        "on it!",
        "SIXEL!!! THEY'RE BULLYING ME!!!",
        "can do, cap'n!",
        "raseworter pro tip: run it back, but with less 'tude next time.",
        "who? oh yeah sure thing b0ss",
        "how about nyaaaa for a change?",
        "CAAAAAAAAAAAAAAN DO!",
        "i mean like, if you say so, man",
        "WOOOOOOOOOOOOOOOOOOOOOOOOOOOO",
        "*nuzzles u*",
        "it begins",
    ]

    await ctx.send(random.choice(epicCatchphrases))

    messages = vetoChannel.history(after=fourWeeksAgo, limit=None)

    if messages is None:
        return

    messages = [message async for message in messages]

    errataCardMessages: list[Message] = []
    acceptedCardMessages: list[Message] = []
    vetoCardMessages: list[Message] = []
    purgatoryCardMessages: list[Message] = []

    for messageEntry in messages:
        if len(messageEntry.attachments) == 0:
            continue

        messageAge = timeNow - messageEntry.created_at

        if (
            get(messageEntry.reactions, emoji=hc_constants.ACCEPT)
            or get(messageEntry.reactions, emoji=hc_constants.DELETE)
            or messageAge < timedelta(days=1)
        ):
            continue  # Skip cards that have been marked or are only a day old

        up = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        upvote = up.count if up else -1

        down = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
        downvote = down.count if down else -1

        erratas = get(
            messageEntry.reactions, emoji=bot.get_emoji(hc_constants.CIRION_SPELLING)
        )
        errata = erratas.count if erratas else -1

        # Errata needed case
        if errata > 4 and errata >= upvote and errata >= downvote:
            errataCardMessages.append(messageEntry)

        # Accepted case
        elif upvote > 4 and upvote >= downvote and upvote >= errata:
            acceptedCardMessages.append(messageEntry)

        # Veto case
        elif downvote > 4 and downvote >= upvote and downvote >= errata:
            vetoCardMessages.append(messageEntry)

        # Purgatorio Hell
        else:
            purgatoryCardMessages.append(messageEntry)

    return VetoPollResults(
        errataCardMessages=errataCardMessages,
        acceptedCardMessages=acceptedCardMessages,
        vetoCardMessages=vetoCardMessages,
        purgatoryCardMessages=purgatoryCardMessages,
    )


@dataclass
class VetoPollResults:
    errataCardMessages: list[Message]
    acceptedCardMessages: list[Message]
    vetoCardMessages: list[Message]
    purgatoryCardMessages: list[Message]
