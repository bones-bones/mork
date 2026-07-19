import base64
import io
import os
import re
from typing import Optional, cast
import discord
from gspread import Cell
import hc_constants
from hellfall_postcard import (
    PostcardSyncError,
    PostcardWrite,
    postcard_sync_enabled,
    rollback_postcard_write,
    sync_accepted_card,
)
from is_mork import getDriveUrl, uploadToDrive
from shared_vars import googleClient
from discord.ext import commands


from reddit_functions import post_to_reddit
from username_mappings import resolve_authors

cardSheetUnapproved = googleClient.open_by_key(
    hc_constants.HELLSCUBE_DATABASE
).worksheet(hc_constants.DATABASE_UNAPPROVED)


async def _sync_card_to_hellfall(
    *,
    card_name: str,
    image_url: str,
    author_name: str,
    set_id: str,
    hcid: Optional[str],
):
    if not postcard_sync_enabled():
        return None
    return await sync_accepted_card(
        name=card_name,
        image=image_url,
        creators=author_name,
        set_id=set_id,
        hcid=hcid,
        kind="card",
    )


async def _resolve_accepted_image_url(
    *,
    file_data: bytes,
    image_path: str,
    card_name: str,
    author_name: str,
    set_id: str,
    hcid: Optional[str],
    image_id_to_update: Optional[str],
    require_hellfall_postcard: bool,
) -> tuple[str, Optional[PostcardWrite]]:
    if require_hellfall_postcard:
        image_base64 = base64.b64encode(file_data).decode("ascii")
        postcard_write: Optional[PostcardWrite] = None
        image_url: Optional[str] = None
        try:
            postcard_write = await sync_accepted_card(
                name=card_name,
                image_base64=image_base64,
                creators=author_name,
                set_id=set_id,
                hcid=hcid,
                kind="card",
                require_sync=True,
            )
            if postcard_write and postcard_write.image_url:
                image_url = postcard_write.image_url
        except PostcardSyncError as err:
            if str(err) != "invalid_body":
                raise
            postcard_write = None

        if not image_url:
            google_drive_file_id = uploadToDrive(
                image_path,
                image_id_to_update,
                folder_id=hc_constants.CURRENT_SET_FOLDER,
            )
            drive_url = getDriveUrl(google_drive_file_id)
            postcard_write = await sync_accepted_card(
                name=card_name,
                image=drive_url,
                creators=author_name,
                set_id=set_id,
                hcid=hcid,
                kind="card",
                require_sync=True,
            )
            image_url = (
                postcard_write.image_url
                if postcard_write and postcard_write.image_url
                else drive_url
            )

        if not postcard_write:
            raise PostcardSyncError("hellfall postcard sync did not complete")
        if not image_url:
            raise PostcardSyncError("hellfall did not return imageUrl")
        return image_url, postcard_write

    google_drive_file_id = uploadToDrive(
        image_path, image_id_to_update, folder_id=hc_constants.CURRENT_SET_FOLDER
    )
    image_url = getDriveUrl(google_drive_file_id)
    postcard_write = await _sync_card_to_hellfall(
        card_name=card_name,
        image_url=image_url,
        author_name=author_name,
        set_id=set_id,
        hcid=hcid,
    )
    return image_url, postcard_write


async def accept_card(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
    channelIdForCard: int = hc_constants.NINE_CARD_LIST,
    setId: str = "HC9.0",
    errata: bool = False,
    errataId: Optional[str] = None,
    wasVetoed: bool = False,
    skip_reddit: bool = False,
    deferred_reddit_dir: Optional[str] = None,
    require_hellfall_postcard: bool = False,
):
    """Accept a cards a card into the DB. This also includes posting it to reddit and the appropriate card list channel."""
    authorName = resolve_authors(authorName)
    extension = re.search("\.([^.]*)$", file.filename)
    file_type = (
        extension.group() if extension else ".png"
    )  # just guess that the file is a png
    new_file_name = f'{cardName.replace("/", "|")[:250]}{file_type}'
    image_path = f"tempImages/{new_file_name}"

    file_data = file.fp.read()
    file_copy_for_cardlist = discord.File(
        fp=io.BytesIO(file_data), filename=new_file_name
    )

    with open(image_path, "wb") as out:
        out.write(file_data)

    allCards = cardSheetUnapproved.get("A:E")
    index = [i for i in range(len(allCards)) if str(allCards[i][0]) == str(errataId)]

    newCard = True
    image_id_to_update = None
    # At least on match was found, and the name isn't blank. There really shouldn't be any nameless cards though cause it breaks
    if cardName != "" and index.__len__() > 0:
        dbRowIndex = index[0] + 1
        newCard = False
        image_id_to_update = allCards[index[0]][2].removeprefix(
            "https://lh3.googleusercontent.com/d/"
        )
    else:
        dbRowIndex = len(allCards) + 1
        if cardName == "":
            cardName = "NO NAME"

    next_id: Optional[str] = None
    if newCard:
        next_id = str(int(allCards[allCards.__len__() - 1][0]) + 1)

    firestore_hcid = errataId or next_id
    postcard_write = None
    try:
        imageUrl, postcard_write = await _resolve_accepted_image_url(
            file_data=file_data,
            image_path=image_path,
            card_name=cardName,
            author_name=authorName,
            set_id=setId,
            hcid=firestore_hcid,
            image_id_to_update=image_id_to_update,
            require_hellfall_postcard=require_hellfall_postcard,
        )

        cardSheetUnapproved.update_cell(dbRowIndex, 3, imageUrl)

        if newCard:
            cardSheetUnapproved.update_cells(
                [
                    Cell(row=dbRowIndex, col=1, value=str(next_id)),
                    Cell(row=dbRowIndex, col=2, value=cardName),
                    Cell(row=dbRowIndex, col=4, value=authorName),
                    Cell(row=dbRowIndex, col=5, value=setId),
                ]
            )
    except Exception:
        if postcard_write is not None:
            await rollback_postcard_write(postcard_write)
        if os.path.exists(image_path):
            os.remove(image_path)
        raise

    card_list_channel = cast(discord.TextChannel, bot.get_channel(channelIdForCard))
    await card_list_channel.send(file=file_copy_for_cardlist, content=cardMessage)

    if not errata and not errataId:
        reddit_title = (
            f"{cardMessage.replace('**', '')} "
            f"{'was accepted!' if not wasVetoed else 'was vetoed!'}"
        )
        if skip_reddit and deferred_reddit_dir:
            os.makedirs(deferred_reddit_dir, exist_ok=True)
            deferred_path = os.path.join(deferred_reddit_dir, new_file_name)
            os.rename(image_path, deferred_path)
            manifest_path = os.path.join(deferred_reddit_dir, "manifest.txt")
            with open(manifest_path, "a", encoding="utf-8") as manifest:
                manifest.write(f"{new_file_name}\t{reddit_title}\n")
        else:
            try:
                await post_to_reddit(
                    image_path=image_path,
                    title=reddit_title,
                    flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
                )
            except Exception as e:
                print("tried to post to reddit", e)
            if os.path.exists(image_path):
                os.remove(image_path)
    elif os.path.exists(image_path):
        os.remove(image_path)


async def accept_veto_card(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
):
    authorName = resolve_authors(authorName)
    extension = re.search("\\.([^.]*)$", file.filename)
    fileType = (
        extension.group() if extension else ".png"
    )  # just guess that the file is a png
    new_file_name = f'{cardName.replace("/", "|")}{fileType}'
    image_path = f"tempImages/{new_file_name}"

    file_data = file.fp.read()
    file_copy_for_cardlist = discord.File(
        fp=io.BytesIO(file_data), filename=new_file_name
    )
    cardListChannel = cast(
        discord.TextChannel, bot.get_channel(hc_constants.SIX_ONE_CARD_LIST)
    )
    vetoCardListChannel = cast(
        discord.TextChannel, bot.get_channel(hc_constants.VETO_CARD_LIST)
    )

    with open(image_path, "wb") as out:
        out.write(file_data)

    allCards = cardSheetUnapproved.get("A:E")
    index = [
        i
        for i in range(len(allCards))
        if allCards[i][1] == cardName and allCards[i][4] == "HCV"
    ]

    newCard = True
    image_id_to_update = None
    # At least on match was found, and the name isn't blank
    if cardName != "" and index.__len__() > 0:
        dbRowIndex = index[0] + 1
        newCard = False
        image_id_to_update = allCards[index[0]][1].removeprefix(
            "https://lh3.googleusercontent.com/d/"
        )
    else:
        dbRowIndex = len(allCards) + 1
        if cardName == "":
            cardName = "NO NAME"

    google_drive_file_id = uploadToDrive(image_path, image_id_to_update)

    imageUrl = getDriveUrl(google_drive_file_id)

    existing_hcid = None
    if not newCard and len(allCards[index[0]]) > 0 and allCards[index[0]][0]:
        existing_hcid = str(allCards[index[0]][0])

    postcard_write = None
    try:
        postcard_write = await _sync_card_to_hellfall(
            card_name=cardName,
            image_url=imageUrl,
            author_name=authorName,
            set_id="HCV",
            hcid=existing_hcid,
        )

        cardSheetUnapproved.update_cells(
            [
                Cell(row=dbRowIndex, col=3, value=imageUrl),
                Cell(row=dbRowIndex, col=5, value="HCV"),
            ]
        )

        if newCard:
            cardSheetUnapproved.update_cells(
                [
                    Cell(row=dbRowIndex, col=2, value=cardName),
                    Cell(row=dbRowIndex, col=4, value=authorName),
                ]
            )
    except Exception:
        if postcard_write is not None:
            await rollback_postcard_write(postcard_write)
        if os.path.exists(image_path):
            os.remove(image_path)
        raise

    os.remove(image_path)

    async for message in vetoCardListChannel.history(limit=None):
        if message.content == cardMessage:
            try:
                await message.delete()  # Delete message if it matches
                print(f"Deleted message: {message.content}")
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")

    async for message in cardListChannel.history(limit=None):
        if message.content == cardMessage:
            try:
                await message.delete()  # Delete message if it matches
                print(f"Deleted message: {message.content}")
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")

    await vetoCardListChannel.send(file=file_copy_for_cardlist, content=cardMessage)
