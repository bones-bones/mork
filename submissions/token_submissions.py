import base64
import re
from datetime import UTC, datetime, timedelta
from typing import cast

from discord import Message
from discord.ext import commands
from discord.utils import get
from gspread import Cell

import hc_constants
from get_card_message import parseCardNameAndAuthor
from getters import (
    getTokenListChannel,
    getTokenSubmissionChannel,
)
from hellfall_postcard import (
    PostcardSyncError,
    rollback_postcard_write,
    sync_accepted_card,
)
from image_response_filename import content_type_for_ext, extension_from_image_bytes
from is_mork import is_mork
from shared_vars import googleClient

tokenUnapproved = googleClient.open_by_key(hc_constants.HELLSCUBE_DATABASE).worksheet(
    hc_constants.TOKEN_UNAPPROVED
)

# Column L (header UUID) — Hellfall card ``id`` from postcard response
_HELLFALL_ID_COL = 12
# Column M (header Oracle ID) — Hellfall card ``oracle_id`` from postcard response
_ORACLE_ID_COL = 13
# Column J — collector number
_COLLECTOR_NUMBER_COL = 10


def _next_token_collector_number() -> str:
    """Return the next token collector number (max leading digits in J + 1)."""
    collectors = tokenUnapproved.col_values(_COLLECTOR_NUMBER_COL)
    max_num = 0
    for cn in collectors:
        match = re.match(r"^(\d+)", str(cn))
        if match:
            max_num = max(max_num, int(match.group(1)))
    return str(max_num + 1)


async def checkTokenSubmissions(bot: commands.Bot):
    print("checking token submissions")
    subChannel = getTokenSubmissionChannel(bot)

    timeNow = datetime.now(UTC)
    fourWeek = timeNow + timedelta(weeks=-2)
    messages = subChannel.history(after=fourWeek, limit=None)
    if messages is None:
        return

    messages = [message async for message in messages]
    for messageEntry in messages:
        messageEntry = cast(Message, messageEntry)
        if (
            "@everyone" in messageEntry.content
            or "@here" in messageEntry.content
            or len(messageEntry.attachments) == 0
            or not is_mork(messageEntry.author.id)
        ):
            continue  # just ignore these
        acceptReact = get(messageEntry.reactions, emoji=hc_constants.ACCEPT)
        if acceptReact and acceptReact.count > 0:  # TODO: does this do anything?
            prettyValid = True
            async for user in acceptReact.users():
                if is_mork(user.id):
                    prettyValid = False
                    break
            if not prettyValid:
                continue

        upvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_UP)
        downvote = get(messageEntry.reactions, emoji=hc_constants.VOTE_DOWN)
        if upvote and downvote:
            upCount = upvote.count
            downCount = downvote.count
            messageAge = timeNow - messageEntry.created_at

            positiveMargin = upCount - downCount
            if positiveMargin >= 5 and messageAge >= timedelta(days=1):
                await acceptTokenSubmission(bot=bot, message=messageEntry)

    print("------done checking submissions-----")


async def acceptTokenSubmission(bot: commands.Bot, message: Message):
    tokenListChannel = getTokenListChannel(bot)
    accepted_message_no_mentions = message.clean_content

    for index, mentionEntry in enumerate(message.raw_mentions):
        accepted_message_no_mentions = accepted_message_no_mentions.replace(
            f"<@{mentionEntry}>", message.mentions[index].name
        )

    first_line = accepted_message_no_mentions.split("\n")[0]
    cardName, creator = parseCardNameAndAuthor(first_line)
    relatedCards = accepted_message_no_mentions.split("\n")[1]

    file = await message.attachments[0].to_file()
    copy = await message.attachments[0].to_file()

    extension = re.search(r"\.([^.]*)$", file.filename)
    file_data = file.fp.read()
    fileType = extension_from_image_bytes(file_data) or (extension.group() if extension else ".png")
    if fileType.lower() == ".jpeg":
        fileType = ".jpg"
    new_file_name = f"{cardName.replace('/', '|')}{fileType}"
    copy.filename = new_file_name
    image_base64 = base64.b64encode(file_data).decode("ascii")

    allCardNames = tokenUnapproved.col_values(1)

    matching_cards = [
        name for name in allCardNames if isinstance(name, str) and name.startswith(cardName)
    ]
    max_number = 0
    for card in matching_cards:
        # TODO: Use regex instead
        suffix = card[len(cardName) :]
        if suffix and suffix.isdigit():
            max_number = max(max_number, int(suffix))

    final_card_name = f"{cardName}{max_number + 1}"

    dbRowIndex = len(allCardNames) + 1

    postcard_write = None
    try:
        postcard_write = await sync_accepted_card(
            name=final_card_name,
            image_base64=image_base64,
            image_mime_type=content_type_for_ext(fileType),
            creators=creator,
            set_id="HCT",
            hcid=final_card_name,
            kind="token",
            require_sync=True,
        )
        if not postcard_write or not postcard_write.image_url:
            raise PostcardSyncError("hellfall did not return imageUrl")
        imageUrl = postcard_write.image_url

        token_cells = [
            Cell(row=dbRowIndex, col=1, value=final_card_name),
            Cell(row=dbRowIndex, col=2, value=imageUrl),
            Cell(row=dbRowIndex, col=6, value=relatedCards),
            Cell(row=dbRowIndex, col=8, value=creator),
            Cell(
                row=dbRowIndex,
                col=_COLLECTOR_NUMBER_COL,
                value=_next_token_collector_number(),
            ),
        ]
        if postcard_write is not None and postcard_write.hellfall_id:
            token_cells.append(
                Cell(
                    row=dbRowIndex,
                    col=_HELLFALL_ID_COL,
                    value=postcard_write.hellfall_id,
                )
            )
        if postcard_write is not None and postcard_write.oracle_id:
            token_cells.append(
                Cell(
                    row=dbRowIndex,
                    col=_ORACLE_ID_COL,
                    value=postcard_write.oracle_id,
                )
            )
        tokenUnapproved.update_cells(token_cells)
        await tokenListChannel.send(
            content=cardName + " by " + creator + "\n" + relatedCards,
            file=copy,
        )
        await message.add_reaction(hc_constants.ACCEPT)

    except Exception:
        if postcard_write is not None:
            await rollback_postcard_write(postcard_write)
        raise
