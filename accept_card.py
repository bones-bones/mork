import asyncio
import base64
import io
import os
import re
import uuid
from dataclasses import dataclass
from typing import cast

import aiofiles
import discord
from discord.ext import commands
from gspread import Cell

import hc_constants
from cogs.HellscubeDatabase import getUnapprovedCardSheet
from database_cache.database import get_card_by_id, get_id_by_hcid
from database_cache.setHandling import getVetoSetCode
from deferred_reddit import format_deferred_manifest_entry, safe_card_filename
from hellfall_postcard import (
    PostcardSyncError,
    PostcardWrite,
    rollback_postcard_write,
    sync_accepted_card,
)
from image_response_filename import (
    extension_from_image_bytes,
    mime_type_from_image_bytes,
)
from reddit_devvit import post_accept_via_devvit, reddit_accept_via_devvit_enabled
from reddit_functions import post_to_reddit, reddit_title_for_acceptance
from getters import getVetoChannel
from get_card_message import parseCardNameAndAuthor
from handle_veto_post import handle_veto_post
from hellfall_fetcher import getExactCard
from sheet_dual_write import sheet_dual_write_enabled
from username_mappings import resolve_authors

cardSheetUnapproved = getUnapprovedCardSheet()

# Serialize unapproved-sheet row/AO allocation + write. Concurrent accepts
# otherwise race across the postcard await and reuse the same row index.
_unapproved_sheet_lock = asyncio.Lock()

_HELLFALL_ID_COL = 54

_ORACLE_ID_COL = 55

# Column W — accepted order
_ACCEPTED_ORDER_COL = 23

# Hellfall getAcceptedOrderSet: all SCL drops share one AO pool under parent SCL.
# Must include SCL.X (and any SCL.*), not only SCL.<digits>.
_SCL_AO_POOL = re.compile(r"^SCL([._].+)?$", re.IGNORECASE)


@dataclass(frozen=True)
class PromotedSubmission:
    """Result of ``promote_from_submissions`` — card is in Hellfall + unapproved sheet."""

    hcid: str
    image_url: str
    sheet_row: int
    hellfall_id: str


def parse_errata_id_from_veto_content(content: str) -> str | None:
    """Second line ``Errata: <hcid>`` on veto poll messages."""
    lines = (content or "").splitlines()
    if len(lines) < 2:
        return None
    second = lines[1].strip()
    if not second.lower().startswith("errata:"):
        return None
    errata_id = second.split(":", 1)[1].strip()
    return errata_id or None


def _veto_poll_title_line(content: str) -> str:
    first = (content or "").splitlines()[0] if content else ""
    cube_prefix = f"{hc_constants.CUBE_NAME}:"
    if first.startswith(cube_prefix):
        return first[len(cube_prefix) :].strip()
    return first.strip()


def hcid_from_unapproved_hellfall_id(hellfall_id: str) -> str | None:
    """Resolve hcid from Hellfall print UUID (catalog first, then sheet col BB)."""
    card = get_card_by_id(hellfall_id)
    if card:
        hcid = str(card.hcid or "").strip()
        if hcid:
            return hcid
    if not sheet_dual_write_enabled():
        return None
    cell = cardSheetUnapproved.find(hellfall_id, in_column=_HELLFALL_ID_COL)
    if not cell:
        return None
    value = cardSheetUnapproved.cell(cell.row, 1).value
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def _image_url_from_catalog_hcid(hcid: str) -> str | None:
    card_uuid = get_id_by_hcid(hcid)
    if not card_uuid:
        return None
    card = get_card_by_id(card_uuid)
    if not card:
        return None
    url = str(card.image or "").strip()
    return url or None


def _normalize_set_code(set_id: str) -> str:
    return set_id.replace("_", ".")


def _next_accepted_order_for_set(set_id: str) -> str:
    """Return the next accepted order for ``set_id`` (max leading digits in W + 1).

    Uses two column reads instead of findall + per-row ``cell()`` calls, which
    burned Sheets quota and broke subsequent Scube Lair 🥈 accepts.

    SCL drops (SCL.1, SCL.X, …) share one counter; HCV.SCL is its own set.
    """
    set_values = cardSheetUnapproved.col_values(5)
    order_values = cardSheetUnapproved.col_values(_ACCEPTED_ORDER_COL)
    needle = _normalize_set_code(set_id)
    scl_pool = bool(_SCL_AO_POOL.match(needle))

    max_num = 0
    for i, sheet_set in enumerate(set_values):
        if not sheet_set or not isinstance(sheet_set, str):
            continue
        normalized = _normalize_set_code(sheet_set)
        if scl_pool:
            if not _SCL_AO_POOL.match(normalized):
                continue
        elif normalized != needle:
            continue
        if i >= len(order_values):
            continue
        match = re.match(r"^(\d+)", str(order_values[i]))
        if match:
            max_num = max(max_num, int(match.group(1)))
    return str(max_num + 1)


def _new_card_sheet_cells(
    *,
    index: int,
    sheet_hcid: str,
    card_name: str,
    author_name: str,
    set_id: str,
    postcard_write: PostcardWrite | None,
    include_accepted_order: bool,
) -> list[Cell]:
    cells = [
        Cell(row=index, col=1, value=str(sheet_hcid)),
        Cell(row=index, col=2, value=card_name),
        Cell(row=index, col=4, value=author_name),
        Cell(row=index, col=5, value=set_id.replace("_", ".")),
    ]
    if include_accepted_order:
        cells.append(
            Cell(
                row=index,
                col=_ACCEPTED_ORDER_COL,
                value=_next_accepted_order_for_set(set_id),
            )
        )
    if postcard_write is not None and postcard_write.hellfall_id:
        cells.append(
            Cell(row=index, col=_HELLFALL_ID_COL, value=postcard_write.hellfall_id)
        )
    if postcard_write is not None and postcard_write.oracle_id:
        cells.append(
            Cell(row=index, col=_ORACLE_ID_COL, value=postcard_write.oracle_id)
        )
    return cells


async def _sync_postcard_from_bytes(
    *,
    file_data: bytes,
    card_name: str,
    author_name: str,
    set_id: str,
    hcid: str | None,
) -> tuple[str, PostcardWrite]:
    image_base64 = base64.b64encode(file_data).decode("ascii")
    postcard_write = await sync_accepted_card(
        name=card_name,
        image_base64=image_base64,
        image_mime_type=mime_type_from_image_bytes(file_data),
        creators=author_name,
        set_id=set_id,
        hcid=hcid,
        kind="card",
    )

    image_url = postcard_write.image_url
    if not image_url:
        raise PostcardSyncError("hellfall did not return imageUrl")
    return image_url, postcard_write


async def promote_card_to_database(
    *,
    file_data: bytes,
    cardName: str,
    authorName: str,
    message_set_id: str = hc_constants.ACTIVE_CUBE_ID,
    existing_hcid: str | None = None,
) -> PromotedSubmission:
    """Hellfall postcard + unapproved sheet row (no accepted order).

    Creates a new card when ``existing_hcid`` is omitted; otherwise updates the
    existing print (hellpit resubmit, etc.)."""
    author_name = ";".join(resolve_authors(authorName))
    set_id = message_set_id
    if cardName == "":
        cardName = "NO NAME"

    postcard_write = None
    dual_write = sheet_dual_write_enabled()
    async with _unapproved_sheet_lock:
        existing_row = None
        index = 0
        if dual_write:
            existing_row = (
                cardSheetUnapproved.find(existing_hcid, in_column=1) if existing_hcid else None
            )
            index = (
                existing_row.row
                if existing_row
                else len(cardSheetUnapproved.get_all_values()) + 1
            )
        try:
            image_url, postcard_write = await _sync_postcard_from_bytes(
                file_data=file_data,
                card_name=cardName,
                author_name=author_name,
                set_id=set_id,
                hcid=existing_hcid,
            )
            sheet_hcid = existing_hcid or (postcard_write.hcid if postcard_write else None)
            if not sheet_hcid:
                raise PostcardSyncError("hellfall did not return hcid")
            hellfall_id = postcard_write.hellfall_id if postcard_write else None
            if not hellfall_id:
                raise PostcardSyncError("hellfall did not return id")

            if dual_write:
                cardSheetUnapproved.update_cell(index, 3, image_url)
                if existing_row:
                    cardSheetUnapproved.update_cells(
                        [
                            Cell(row=index, col=2, value=cardName),
                            Cell(row=index, col=4, value=author_name),
                            Cell(row=index, col=5, value=set_id.replace("_", ".")),
                        ]
                    )
                else:
                    cardSheetUnapproved.update_cells(
                        _new_card_sheet_cells(
                            index=index,
                            sheet_hcid=str(sheet_hcid),
                            card_name=cardName,
                            author_name=author_name,
                            set_id=set_id,
                            postcard_write=postcard_write,
                            include_accepted_order=False,
                        )
                    )
        except Exception:
            if postcard_write is not None:
                await rollback_postcard_write(postcard_write)
            raise

    return PromotedSubmission(
        hcid=str(sheet_hcid),
        image_url=image_url,
        sheet_row=index,
        hellfall_id=str(hellfall_id),
    )


async def intake_veto_poll_message(
    bot: commands.Bot,
    message: discord.Message,
    *,
    veto_council: int | None = None,
    submission_thread_url: str | None = None,
    existing_hcid: str | None = None,
    skip_postcard: bool = False,
    message_set_id: str | None = None,
) -> PromotedSubmission | None:
    """Hellfall + sheet on veto intake, then veto poll setup (hellpit, reactions, ``uuid:`` line).

    When ``skip_postcard`` is true (errata channel auto-promote), only runs ``handle_veto_post``.
    Errata lines on the message use postcard **update** with existing ``hcid``, not create."""
    if not message.attachments:
        raise PostcardSyncError("veto poll message has no attachment")

    errata_id = parse_errata_id_from_veto_content(message.content or "")
    title_line = _veto_poll_title_line(message.content or "")
    card_name, author_name = parseCardNameAndAuthor(title_line)

    promote_hcid = existing_hcid or errata_id
    set_id = message_set_id or hc_constants.ACTIVE_CUBE_ID
    if errata_id:
        errata_card = await getExactCard(errata_id)
        if errata_card:
            set_id = errata_card.set
            if not card_name:
                card_name = errata_card.name

    promoted: PromotedSubmission | None = None
    if not skip_postcard:
        file_data = await message.attachments[0].read()
        promoted = await promote_card_to_database(
            file_data=file_data,
            cardName=card_name or "NO NAME",
            authorName=author_name or "no author",
            message_set_id=set_id,
            existing_hcid=promote_hcid,
        )

    hellfall_uuid = promoted.hellfall_id if promoted else None
    await handle_veto_post(
        message=message,
        bot=bot,
        veto_council=veto_council,
        submission_thread_url=submission_thread_url,
        hellfall_uuid=hellfall_uuid,
    )
    return promoted


async def promote_from_submissions(
    bot: commands.Bot,
    veto_content: str,
    file: discord.File,
    cardName: str,
    authorName: str,
    message_set_id: str = hc_constants.ACTIVE_CUBE_ID,
    submission_thread_url: str | None = None,
    existing_hcid: str | None = None,
) -> PromotedSubmission:
    """Post to #veto-polls, then ``intake_veto_poll_message`` (postcard + poll setup)."""
    file_data = file.fp.read()
    attachment_filename = file.filename or "card.png"

    veto_channel = getVetoChannel(bot)
    veto_entry = await veto_channel.send(
        content=veto_content,
        file=discord.File(
            fp=io.BytesIO(file_data),
            filename=attachment_filename,
        ),
    )
    return await intake_veto_poll_message(
        bot,
        veto_entry,
        submission_thread_url=submission_thread_url,
        existing_hcid=existing_hcid,
        message_set_id=message_set_id,
    )


async def accept_card(
    bot: commands.Bot,
    cardMessage: str,
    file: discord.File,
    cardName: str,
    authorName: str,
    channelIdForCard: int = hc_constants.NINE_CARD_LIST,
    message_set_id: str = hc_constants.ACTIVE_CUBE_ID,
    errata: bool = False,
    errataId: str | None = None,
    wasVetoed: bool = False,
    skip_reddit: bool = False,
    deferred_reddit_dir: str | None = None,
    existing_hcid: str | None = None,
):
    """Card is official in the cube (accepted) or vetoed: card-list, Reddit, sheet finalize.

    Updates set + accepted order on the unapproved row; for submission cards that were
    already promoted, pass ``existing_hcid`` from the veto poll thread (no second postcard).

    Paths without promotion (scube lair, errata, …) still do database + cube in one call
    via postcard here.

    If the card was vetoed, ``message_set_id`` is the set it was vetoed *from*, not HCV."""
    set_id = (
        (getVetoSetCode(message_set_id) or message_set_id) if wasVetoed else message_set_id
    )
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
    dual_write = sheet_dual_write_enabled()
    finalize_hcid = existing_hcid if not errataId else None
    if (
        dual_write
        and finalize_hcid
        and not cardSheetUnapproved.find(finalize_hcid, in_column=1)
    ):
        finalize_hcid = None

    async with aiofiles.open(image_path, "wb") as out:
        await out.write(file_data)

    async with _unapproved_sheet_lock:
        index = 0
        if errataId:
            # Catalog is source of truth for errata identity (not approved sheet).
            if not get_id_by_hcid(errataId):
                raise PostcardSyncError(f"errata hcid {errataId} not found in catalog")
            newCard = False
            if dual_write:
                cell = cardSheetUnapproved.find(errataId, in_column=1)
                if cell:
                    index = cell.row
                else:
                    print(
                        f"[accept] errata hcid {errataId} in catalog but no unapproved "
                        "sheet row — postcard update only for this accept"
                    )
        elif finalize_hcid:
            newCard = False
            if dual_write:
                cell = cardSheetUnapproved.find(finalize_hcid, in_column=1)
                if not cell:
                    raise PostcardSyncError(f"no unapproved sheet row for hcid {finalize_hcid}")
                index = cell.row
            else:
                print(
                    f"[accept] SHEET_DUAL_WRITE=0: finalize hcid {finalize_hcid} "
                    "without sheet row — Hellfall postcard only, skipping sheet AO/set"
                )
        elif dual_write:
            index = len(cardSheetUnapproved.get_all_values()) + 1

        if cardName == "" and newCard:
            cardName = "NO NAME"
        # Errata may exist in catalog without an unapproved row (postcard-only update).
        if dual_write and index == 0 and finalize_hcid and not errataId:
            raise IndexError("index not found")
        if dual_write and index == 0 and errataId and newCard:
            raise IndexError("index not found")
        postcard_write = None
        imageUrl = ""
        try:
            if finalize_hcid and not errataId:
                if wasVetoed:
                    imageUrl, postcard_write = await _sync_postcard_from_bytes(
                        file_data=file_data,
                        card_name=cardName,
                        author_name=authorName,
                        set_id=set_id,
                        hcid=finalize_hcid,
                    )
                    if dual_write:
                        cardSheetUnapproved.update_cell(index, 3, imageUrl)
                        cardSheetUnapproved.update_cells(
                            [
                                Cell(row=index, col=5, value=set_id.replace("_", ".")),
                                Cell(
                                    row=index,
                                    col=_ACCEPTED_ORDER_COL,
                                    value=_next_accepted_order_for_set(set_id),
                                ),
                            ]
                        )
                else:
                    if dual_write:
                        imageUrl = str(cardSheetUnapproved.cell(index, 3).value or "").strip()
                    else:
                        imageUrl = _image_url_from_catalog_hcid(finalize_hcid) or ""
                    if not imageUrl:
                        raise PostcardSyncError(
                            f"missing image URL for hcid {finalize_hcid} "
                            "(sheet row or catalog)"
                        )
                    if dual_write:
                        cardSheetUnapproved.update_cells(
                            [
                                Cell(row=index, col=5, value=set_id.replace("_", ".")),
                                Cell(
                                    row=index,
                                    col=_ACCEPTED_ORDER_COL,
                                    value=_next_accepted_order_for_set(set_id),
                                ),
                            ]
                        )
            else:
                imageUrl, postcard_write = await _sync_postcard_from_bytes(
                    file_data=file_data,
                    card_name=cardName,
                    author_name=authorName,
                    set_id=set_id,
                    hcid=errataId,
                )

                if dual_write and index:
                    cardSheetUnapproved.update_cell(index, 3, imageUrl)

                if newCard:
                    sheet_hcid = errataId or (postcard_write.hcid if postcard_write else None)
                    if not sheet_hcid:
                        raise PostcardSyncError("hellfall did not return hcid")
                    if dual_write and index:
                        cardSheetUnapproved.update_cells(
                            _new_card_sheet_cells(
                                index=index,
                                sheet_hcid=str(sheet_hcid),
                                card_name=cardName,
                                author_name=authorName,
                                set_id=set_id,
                                postcard_write=postcard_write,
                                include_accepted_order=True,
                            )
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
        card_message_for_reddit = cardMessage.replace("\n", " ").replace("\t", " ")
        reddit_title = reddit_title_for_acceptance(
            card_message_for_reddit, message_set_id, was_vetoed=wasVetoed
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
                        message_set_id,
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
                        set_id=message_set_id,
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
