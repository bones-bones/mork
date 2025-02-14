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


def getSubmissionsChannel(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))


def getTokenSubmissionChannel(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.TOKEN_SUBMISSIONS))


def getTokenListChannel(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.TOKEN_LIST))


def getBotTest(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.BOT_TEST_CHANNEL))


def getGraveyardChannel(bot: commands.Bot):
    return cast(TextChannel, bot.get_channel(hc_constants.GRAVEYARD_CARD_LIST))


def getMorkSubmissionsLoggingChannel(bot: commands.Bot):
    return cast(
        TextChannel, bot.get_channel(hc_constants.MORK_SUBMISSIONS_LOGGING_CHANNEL)
    )
