import pprint as pp
from typing import cast

from discord import Member
from discord.ext import commands
from discord.utils import get


async def toggleRole(
    ctx: commands.Context[commands.Bot], roleID: int, roleName: str, addRoleName: bool = False
):
    if isinstance(ctx.message.author, Member) and isinstance(ctx.author, Member):
        role = get(ctx.message.author.guild.roles, id=roleID)
        if not role:
            return
        if addRoleName:
            roleName += f" {role.name}"
        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)
            await ctx.send(f"Removed {roleName} from {ctx.message.author}")
            return
        await ctx.author.add_roles(role)
        await ctx.send(f"Gave {ctx.message.author} {roleName}")


class RolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

    @commands.command()
    async def announcements(self, ctx: commands.Context[commands.Bot]):
        await toggleRole(ctx, 862806291844300830, "Announcements")

    @commands.command()
    async def vent(self, ctx: commands.Context):
        await toggleRole(ctx, 1003397744267898920, "Vent")

    @commands.command()
    async def becomeArtist(self, ctx: commands.Context):
        await toggleRole(ctx, 819320922666041355, "HCArtist")

    @commands.command()
    async def wantToDraft(self, ctx: commands.Context):
        await toggleRole(ctx, 661721357066698762, "WantToDraft")

    @commands.command()
    async def wantToEdh(self, ctx: commands.Context):
        await toggleRole(ctx, 720043670870425691, "WantToEdh")

    @commands.command()
    async def wantToJumpstart(self, ctx: commands.Context):
        await toggleRole(ctx, 733995427237724180, "WantToJumpstart")

    @commands.command()
    async def wantToConstructed(self, ctx: commands.Context):
        await toggleRole(ctx, 856927890120769576, "WantToConstructed")

    @commands.command()
    async def wantToLeaks(self, ctx: commands.Context):
        await toggleRole(ctx, 794254398775361578, "WantToLeaks")

    @commands.command()
    async def popcornCube(self, ctx: commands.Context):
        await toggleRole(ctx, 758033490133385308, "PopcornCube")

    @commands.command()
    async def pronoun(self, ctx: commands.Context, roleName):
        roleId = {
            "he": 745661999513469069,
            "she": 745662055842840718,
            "it": 745662178702655578,
            "they": 745662219001528340,
            "zir": 745662416280485929,
            "xir": 745662465639186465,
            "fae": 745662506915332247,
            "ey": 786272241234214923,
            "xe": 862497482709401620,
            "any": 867939179768729651,
            "all": 1006744588385534002,
            "gar": 1006737438967857242,
            "thou": 1006747294399471647,
            "ciri": 1006748383752507522,
            "who": 1006749672179765278,
            "sie": 1007104561674211419,
        }
        if roleName == "help":
            message = "To give yourself a pronoun role type !pronoun and the subjective version of that pronoun. (You can have as many as you want.) The current list of pronouns is:\n"
            for i in roleId:
                message += i + "\n"
            message += "If your pronouns are missing please tag llllll"
            await ctx.send(message)
            return
        if roleName in roleId:
            print(roleName)
            if isinstance(ctx.message.author, Member) and isinstance(ctx.author, Member):
                pp.pprint(cast(Member, ctx.author).roles)
                await toggleRole(ctx, int(roleId[roleName]), "the role", True)
                return
        await ctx.send(
            "This is not currently a pronoun role, make sure to type !pronoun and then only the subjective pronoun (Example !pronoun they), If your pronouns are missing please tag llllll"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
