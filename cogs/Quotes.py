import random
import discord
from discord.ext import commands
from is_mork import is_mork
from shared_vars import drive
from dpymenus import PaginatedMenu
import hc_constants

authorSplit = "$#$#$"
QUOTE_SPLIT = ";%;%;"


class QuotesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def quote(self, ctx: commands.Context, lookback=1):
        if lookback == 0:
            await ctx.send("^\nfucker")
            return
        if lookback > 100:
            await ctx.send("Can't look back more than 100 messages")
            return
        messages = ctx.history(limit=lookback + 1)
        messages = [message async for message in messages]
        message = messages[lookback]
        if "@" in message.content:
            await ctx.send(
                "You think you're fucking funny, bitch\n\nOh, I'll try to quote a ping it'll be funny and totally not annoying at all.\nYou're a bitch. You suck. Fuck you\n\nYou useless piece of shit. You absolute waste of space and air. You uneducated, ignorant, idiotic dumb swine, you’re an absolute embarrassment to humanity and all life as a whole. The magnitude of your failure just now is so indescribably massive that one hundred years into the future your name will be used as moniker of evil for heretics. Even if all of humanity put together their collective intelligence there is no conceivable way they could have thought up a way to fuck up on the unimaginable scale you just did. When Jesus died for our sins, he must not have seen the sacrilegious act we just witnessed you performing, because if he did he would have forsaken humanity long ago so that your birth may have never become reality. After you die, your skeleton will be displayed in a museum after being scientifically researched so that all future generations may learn not to generate your bone structure, because every tiny detail anyone may have in common with you degrades them to a useless piece of trash and a burden to society."
            )
            return
        user = message.author.name
        if is_mork(message.author.id) and ctx.channel.id != hc_constants.CUBE_CHANNEL:
            await ctx.send("The bot can't quote itself")
            return
        fileID = hc_constants.QUOTES_FILE

        await addToDrive(message.content, user, fileID)
        await ctx.send('"' + message.content + '"\n-' + user)

    @commands.command()
    async def rquote(self, ctx: commands.Context, lookback=1):
        if lookback == 0:
            await ctx.send("^\nfucker")
            return
        if lookback > 100:
            await ctx.send("Can't look back more than 100 messages")
            return
        messages = ctx.history(limit=lookback + 1)
        messages = [message async for message in messages]
        message = messages[lookback]
        if "@" in message.content:
            await ctx.send(
                "You think you're fucking funny, bitch\n\nOh, I'll try to quote a ping it'll be funny and totally not annoying at all.\nYou're a bitch. You suck. Fuck you\n\nYou useless piece of shit. You absolute waste of space and air. You uneducated, ignorant, idiotic dumb swine, you’re an absolute embarrassment to humanity and all life as a whole. The magnitude of your failure just now is so indescribably massive that one hundred years into the future your name will be used as moniker of evil for heretics. Even if all of humanity put together their collective intelligence there is no conceivable way they could have thought up a way to fuck up on the unimaginable scale you just did. When Jesus died for our sins, he must not have seen the sacrilegious act we just witnessed you performing, because if he did he would have forsaken humanity long ago so that your birth may have never become reality. After you die, your skeleton will be displayed in a museum after being scientifically researched so that all future generations may learn not to generate your bone structure, because every tiny detail anyone may have in common with you degrades them to a useless piece of trash and a burden to society."
            )
            return

        user = message.author.name
        if is_mork(message.author.id) and ctx.channel.id != hc_constants.CUBE_CHANNEL:
            await ctx.send("The bot can't quote itself")
            return
        fileID = hc_constants.QUOTES_FILE

        if message.reference:
            original_message = await message.channel.fetch_message(message.reference.message_id)
            if "@" in original_message.content:
                await ctx.send(
                    "You think you're fucking funny, bitch\n\nOh, I'll try to quote a ping it'll be funny and totally not annoying at all.\nYou're a bitch. You suck. Fuck you\n\nYou useless piece of shit. You absolute waste of space and air. You uneducated, ignorant, idiotic dumb swine, you’re an absolute embarrassment to humanity and all life as a whole. The magnitude of your failure just now is so indescribably massive that one hundred years into the future your name will be used as moniker of evil for heretics. Even if all of humanity put together their collective intelligence there is no conceivable way they could have thought up a way to fuck up on the unimaginable scale you just did. When Jesus died for our sins, he must not have seen the sacrilegious act we just witnessed you performing, because if he did he would have forsaken humanity long ago so that your birth may have never become reality. After you die, your skeleton will be displayed in a museum after being scientifically researched so that all future generations may learn not to generate your bone structure, because every tiny detail anyone may have in common with you degrades them to a useless piece of trash and a burden to society."
                )
                return
            if is_mork(original_message.author.id) and ctx.channel.id != hc_constants.CUBE_CHANNEL:
                await ctx.send("The bot can't quote itself")
                return
            await addToDrive(f'{original_message.author}: {original_message.content}\n⤷{message.content}', user, fileID)
            await ctx.send(f'"{original_message.author}: {original_message.content}\n\n⤷{message.content}"\n-{user}')
        else:
            await addToDrive(message.content, user, fileID)
            await ctx.send('"' + message.content + '"\n-' + user)
    
    @commands.command()
    async def randomquote(self, ctx: commands.Context, *user):
        fileID = hc_constants.QUOTES_FILE
        file = drive.CreateFile({"id": fileID})
        quoteList = file.GetContentString().split(QUOTE_SPLIT)
        for i in range(len(quoteList)):
            quoteList[i] = quoteList[i].split(authorSplit)
        if user:
            user = " ".join(user)
            tempList = []
            for i in quoteList:
                if i[1].lower() == user.lower():
                    tempList.append(i)
            quoteList = tempList
            if quoteList == []:
                await ctx.send("No quotes by " + user + " found. :(")
                return
        quote = random.choice(quoteList)
        message = quote[0]
        user = quote[1]
        await ctx.send('"' + message.replace("\\n", "\n") + '"\n-' + user)

    @commands.command()
    async def searchquote(self, ctx: commands.Context, text, *user):
        fileID = hc_constants.QUOTES_FILE
        file = drive.CreateFile({"id": fileID})
        quoteList = file.GetContentString().split(QUOTE_SPLIT)
        for i in range(len(quoteList)):
            quoteList[i] = quoteList[i].split(authorSplit)
        if user:
            user = " ".join(user)
            tempList = []
            for i in quoteList:
                if i[1].lower() == user.lower():
                    tempList.append(i)
            quoteList = tempList
            if quoteList == []:
                await ctx.send("No quotes by " + user + " found. :(")
                return
        tempList = []
        for i in quoteList:
            if text.lower() in i[0].lower():
                tempList.append(i)
        quoteList = tempList
        if quoteList == []:
            await ctx.send("No quotes with the text " + text + " found. :(")
            return
        if len(quoteList) > 50:
            await ctx.send(
                str(len(quoteList))
                + " quotes found, that's too many, be more specific please"
            )
            return
        elif len(quoteList) > 2:
            await createQuoteMenu(ctx, quoteList)
        else:
            message = ""
            for i in quoteList:
                message += '"' + i[0].replace("\\n", "\n") + '"\n-' + i[1] + "\n\n"
            await ctx.send(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuotesCog(bot))


async def addToDrive(message, user, fileID):
    text = ";%;%;"
    text += message
    text += authorSplit
    text += user
    file = drive.CreateFile({"id": fileID})
    update = file.GetContentString() + text
    file.SetContentString(update)
    file.Upload()


async def createQuoteMenu(ctx: commands.Context, quoteList):
    pageList = []
    for i in quoteList:
        page = discord.Embed(title=i[1], description=i[0])
        pageList.append(page)

    menu = (
        PaginatedMenu(ctx)
        .set_timeout(100)
        .add_pages(pageList)
        .show_skip_buttons()
        .hide_cancel_button()
        .persist_on_close()
        .show_page_numbers()
        .show_command_message()
    )
    await menu.open()
