import base64
import io
import os
import re
import uuid
from typing import cast

import aiofiles
import discord
from discord.ext import commands
from gspread import Cell

import hc_constants
from cogs.HellscubeDatabase import getUnapprovedCardSheet
from deferred_reddit import format_deferred_manifest_entry, safe_card_filename
from hellfall_postcard import (
    PostcardSyncError,
    PostcardWrite,
    postcard_sync_enabled,
    rollback_postcard_write,
    sync_accepted_card,
)
from image_response_filename import (
    extension_from_image_bytes,
    mime_type_from_image_bytes,
)
from reddit_devvit import post_accept_via_devvit, reddit_accept_via_devvit_enabled
from reddit_functions import post_to_reddit, reddit_title_for_acceptance
from username_mappings import resolve_authors

cardSheetUnapproved = getUnapprovedCardSheet()

# Column BB (header UUID) — Hellfall card ``id`` from postcard response
_HELLFALL_ID_COL = 54

# Column BC (header Oracle ID) — Hellfall card ``oracle_id`` from postcard response
_ORACLE_ID_COL = 55

# Column W — accepted order
_ACCEPTED_ORDER_COL = 23


def _next_accepted_order_for_set(set_id: str) -> str:
    """Return the next accepted order for ``set_id`` (max leading digits in W + 1)."""
    condition = r"SCL\.\d+" if set_id.startswith("SCL") else set_id.replace("_", ".")
    rows = [c.row for c in cardSheetUnapproved.findall(condition, in_column=5)]
    cells = [cardSheetUnapproved.cell(row, _ACCEPTED_ORDER_COL) for row in rows]
    nums = [int(cell.value) for cell in cells if cell.value and cell.value.isdigit()]
    max_num = max(nums, default=0)
    return str(max_num + 1)


async def _resolve_accepted_image_url(
    *,
    file_data: bytes,
    card_name: str,
    author_name: str,
    set_id: str,
    hcid: str | None,
    require_hellfall_postcard: bool,
) -> tuple[str, PostcardWrite | None]:
    if not postcard_sync_enabled() and not require_hellfall_postcard:
        raise PostcardSyncError(
            "MORK_POSTCARD_SYNC is disabled; mork no longer uploads images to GCS"
        )

    image_base64 = base64.b64encode(file_data).decode("ascii")
    require_sync = require_hellfall_postcard
    postcard_write = await sync_accepted_card(
        name=card_name,
        image_base64=image_base64,
        image_mime_type=mime_type_from_image_bytes(file_data),
        creators=author_name,
        set_id=set_id,
        hcid=hcid,
        kind="card",
        require_sync=require_sync,
    )
    if require_sync and not postcard_write:
        raise PostcardSyncError("hellfall postcard sync did not complete")

    image_url = postcard_write.image_url if postcard_write else None
    if not image_url:
        raise PostcardSyncError("hellfall did not return imageUrl")
    return image_url, postcard_write


async def accept_card(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
    channelIdForCard: int = hc_constants.NINE_CARD_LIST,
    setId: str = hc_constants.ACTIVE_CUBE_ID,
    errata: bool = False,
    errataId: str | None = None,
    wasVetoed: bool = False,
    skip_reddit: bool = False,
    deferred_reddit_dir: str | None = None,
    require_hellfall_postcard: bool = False,
):
    """Accepts a card into the DB. This also includes posting it to reddit and the appropriate card list channel."""
    authorName = ";".join(resolve_authors(authorName))
    ext_match = re.search(r"(\.[^.]+)$", file.filename or "")
    os.makedirs("tempImages", exist_ok=True)

    file_data = file.fp.read()
    file_type = extension_from_image_bytes(file_data) or (
        ext_match.group(1) if ext_match else ".png"
    )
    if file_type.lower() == ".jpeg":
        file_type = ".jpg"
    new_file_name = safe_card_filename(cardName, file_type)
    image_path = f"tempImages/{uuid.uuid4().hex}{file_type}"
    file_copy_for_cardlist = discord.File(fp=io.BytesIO(file_data), filename=new_file_name)

    newCard = True

    async with aiofiles.open(image_path, "wb") as out:
        await out.write(file_data)
    index = 0
    next_id: str | None = None
    if errataId:
        cell = cardSheetUnapproved.find(errataId, in_column=1)
        if cell and cardName:
            newCard = False
            index = cell.row
    else:
        allHCIDs = [
            int(c)
            for c in cardSheetUnapproved.col_values(1)
            if c and isinstance(c, int) or (isinstance(c, str) and c.isdigit())
        ]
        if allHCIDs:
            index = len(allHCIDs) + 1
            next_id = str(max(allHCIDs) + 1)

    if cardName == "" and newCard:
        cardName = "NO NAME"
    if index == 0:
        raise IndexError("index not found")
    firestore_hcid = errataId or next_id
    postcard_write = None
    try:
        imageUrl, postcard_write = await _resolve_accepted_image_url(
            file_data=file_data,
            card_name=cardName,
            author_name=authorName,
            set_id=setId,
            hcid=firestore_hcid,
            require_hellfall_postcard=require_hellfall_postcard,
        )

        cardSheetUnapproved.update_cell(index, 3, imageUrl)

        if newCard:
            new_card_cells = [
                Cell(row=index, col=1, value=str(next_id)),
                Cell(row=index, col=2, value=cardName),
                Cell(row=index, col=4, value=authorName),
                Cell(row=index, col=5, value=setId.replace("_", ".")),
                Cell(
                    row=index,
                    col=_ACCEPTED_ORDER_COL,
                    value=_next_accepted_order_for_set(setId),
                ),
            ]
            if postcard_write is not None and postcard_write.hellfall_id:
                new_card_cells.append(
                    Cell(
                        row=index,
                        col=_HELLFALL_ID_COL,
                        value=postcard_write.hellfall_id,
                    )
                )
            if postcard_write is not None and postcard_write.oracle_id:
                new_card_cells.append(
                    Cell(
                        row=index,
                        col=_ORACLE_ID_COL,
                        value=postcard_write.oracle_id,
                    )
                )
            cardSheetUnapproved.update_cells(new_card_cells)
    except Exception:
        if postcard_write is not None:
            await rollback_postcard_write(postcard_write)
        if os.path.exists(image_path):
            os.remove(image_path)
        raise

    card_list_channel = cast(discord.TextChannel, bot.get_channel(channelIdForCard))
    await card_list_channel.send(file=file_copy_for_cardlist, content=cardMessage)

    if not errata and not errataId:
        card_message_for_reddit = cardMessage.replace("\n", " ").replace("\t", " ")
        reddit_title = reddit_title_for_acceptance(
            card_message_for_reddit, setId, was_vetoed=wasVetoed
        )
        if skip_reddit and deferred_reddit_dir:
            os.makedirs(deferred_reddit_dir, exist_ok=True)
            deferred_path = os.path.join(deferred_reddit_dir, new_file_name)
            os.rename(image_path, deferred_path)
            manifest_path = os.path.join(deferred_reddit_dir, "manifest.txt")
            async with aiofiles.open(manifest_path, "a", encoding="utf-8") as manifest:
                await manifest.write(
                    format_deferred_manifest_entry(
                        new_file_name,
                        card_message_for_reddit,
                        setId,
                        wasVetoed,
                    )
                    + "\n"
                )
        else:
            posted = False
            if reddit_accept_via_devvit_enabled():
                try:
                    await post_accept_via_devvit(
                        title=reddit_title,
                        image_url=imageUrl,
                        flair_id=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
                    )
                    posted = True
                except Exception as e:
                    print("Devvit acceptance post failed; falling back to asyncpraw:", e)
            if not posted:
                try:
                    await post_to_reddit(
                        image_path=image_path,
                        set_id=setId,
                        card_message=card_message_for_reddit,
                        was_vetoed=wasVetoed,
                        flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
                    )
                except Exception as e:
                    print("tried to post to reddit", e)
            if os.path.exists(image_path):
                os.remove(image_path)
    elif os.path.exists(image_path):
        os.remove(image_path)
