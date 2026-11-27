import os
import random
import traceback
from datetime import UTC, datetime, timedelta
from typing import cast

import aiofiles
import discord

import hc_constants
from cogs.lifecycle.submissions_day_markers import is_submissions_card
from gcs_card_images import delete_gcs_public_url, upload_card_image
from reddit_devvit import post_gallery_via_devvit, reddit_gallery_via_devvit_enabled
from reddit_functions import post_gallery_to_reddit

GALLERY_TITLE = (
    "Some of Today's Submissions: Have any strong opinions on these cards? "
    "Join the discord to share them!"
)


async def _recent_submission_cards(bot) -> list[discord.Message]:
    sub_channel = cast(discord.TextChannel, bot.get_channel(hc_constants.SUBMISSIONS_CHANNEL))
    one_day = datetime.now(UTC) - timedelta(days=1)
    messages = [message async for message in sub_channel.history(after=one_day, limit=None)]
    filtered = [m for m in messages if is_submissions_card(m)]
    if not filtered:
        return []
    return random.sample(filtered, min(10, len(filtered)))


async def _download_discord_images(messages: list[discord.Message]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for message_entry in messages:
        file = await message_entry.attachments[0].to_file()
        file_data = file.fp.read()
        os.makedirs("tempImages", exist_ok=True)
        image_path = f"tempImages/{message_entry.id}{file.filename}"
        images.append({"image_path": image_path})
        async with aiofiles.open(image_path, "wb") as out:
            await out.write(file_data)
    return images


def _upload_gallery_urls(images: list[dict[str, str]]) -> list[str]:
    """Stage local Discord downloads on GCS so Devvit can fetch allowlisted HTTPS URLs."""
    urls: list[str] = []
    for image_entry in images:
        image_path = next(iter(image_entry.values()))
        basename = os.path.basename(image_path)
        object_name = f"submissions-gallery/{os.path.splitext(basename)[0]}"
        urls.append(upload_card_image(image_path, object_name=object_name))
    return urls


def _cleanup_gcs_urls(urls: list[str]) -> None:
    for url in urls:
        try:
            delete_gcs_public_url(url)
        except Exception:
            traceback.print_exc()
            print(f"daily submissions gallery: failed to delete staged GCS object {url}")


async def _post_via_asyncpraw(images: list[dict[str, str]]) -> None:
    await post_gallery_to_reddit(
        title=GALLERY_TITLE,
        images=images,
        flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
    )


async def post_daily_submissions(bot):
    """Pick recent #submissions polls from Discord, stage on GCS, post via Devvit."""
    picked = await _recent_submission_cards(bot)
    if not picked:
        print("daily submissions gallery: no images (discord)")
        return

    images = await _download_discord_images(picked)
    if not images:
        print("daily submissions gallery: no images (discord)")
        return

    gcs_urls: list[str] = []
    try:
        if not reddit_gallery_via_devvit_enabled():
            print(
                "daily submissions gallery: REDDIT_GALLERY_VIA_DEVVIT off; "
                "falling back to asyncpraw"
            )
            await _post_via_asyncpraw(images)
            return

        gcs_urls = _upload_gallery_urls(images)
        await post_gallery_via_devvit(
            title=GALLERY_TITLE,
            image_urls=gcs_urls,
            flair_id=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
        )
    except Exception:
        traceback.print_exc()
        print("daily submissions gallery: Devvit failed; falling back to asyncpraw")
        await _post_via_asyncpraw(images)
    finally:
        _cleanup_gcs_urls(gcs_urls)
        for image_entry in images:
            path = next(iter(image_entry.values()))
            if os.path.exists(path):
                os.remove(path)
