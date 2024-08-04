from typing import cast
from discord import TextChannel
from discord.ext import commands

import hc_constants


def getVetoChannel(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.VETO_CHANNEL))


def getSubmissionDiscussionChannel(bot: commands.Bot):
    return cast(
        TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_DISCUSSION_CHANNEL)
    )


def getErrataSubmissionChannel(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.ERRATA_SUBMISSIONS))
