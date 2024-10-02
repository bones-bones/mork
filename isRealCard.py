from discord import TextChannel
from cardNameRequest import cardNameRequest
from discord.ext import commands


# Shouldn't need to do this # cause of som esupertyping
async def isRealCard(cardName: str, ctx: commands.Context | TextChannel):
    """Helps determine exact matches for cards in the database"""
    name = cardNameRequest(cardName.lower())
    isMatch = name == cardName.lower()

    if not isMatch:
        await ctx.send(
            f"unable to find an exact match for {cardName}. did you mean: {name}"
        )
    return isMatch
