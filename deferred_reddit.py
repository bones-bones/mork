import json
import os
import re
from dataclasses import dataclass

import hc_constants
from reddit_devvit import (
    post_accept_via_devvit,
    reddit_deferred_via_devvit_enabled,
)
from reddit_functions import post_to_reddit, reddit_title_for_acceptance

DEFERRED_REDDIT_ROOT = "deferred_reddit"
_FILENAME_UNSAFE_RE = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def safe_card_filename(card_name: str, ext: str) -> str:
    """Filesystem-safe attachment/deferred image name; preserves Unicode."""
    safe = _FILENAME_UNSAFE_RE.sub("|", card_name.strip())
    if not safe:
        safe = "NO NAME"
    return f"{safe[:250]}{ext}"


def format_deferred_manifest_entry(
    filename: str,
    card_message: str,
    set_id: str,
    was_vetoed: bool,
    image_url: str | None = None,
) -> str:
    entry: dict = {
        "filename": filename,
        "card_message": card_message,
        "set_id": set_id,
        "was_vetoed": was_vetoed,
    }
    if image_url:
        entry["image_url"] = image_url
    return json.dumps(entry, ensure_ascii=False)


@dataclass
class DeferredRedditPost:
    image_path: str
    batch_dir: str
    filename: str
    title: str = ""
    card_message: str = ""
    set_id: str = ""
    was_vetoed: bool = False
    image_url: str = ""


def _parse_manifest_line(line: str) -> DeferredRedditPost | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        filename = data.get("filename")
        if not filename:
            return None
        return DeferredRedditPost(
            image_path="",
            batch_dir="",
            filename=filename,
            card_message=data.get("card_message", ""),
            set_id=data.get("set_id", ""),
            was_vetoed=bool(data.get("was_vetoed", False)),
            image_url=(data.get("image_url") or "").strip(),
        )
    parts = stripped.split("\t")
    if len(parts) == 2:
        filename, title = parts
        return DeferredRedditPost(
            image_path="",
            batch_dir="",
            filename=filename,
            title=title,
        )
    if len(parts) >= 4:
        filename, card_message, set_id, was_vetoed_str = parts[:4]
        return DeferredRedditPost(
            image_path="",
            batch_dir="",
            filename=filename,
            card_message=card_message,
            set_id=set_id,
            was_vetoed=was_vetoed_str == "1",
        )
    return None


def list_pending_deferred_posts() -> list[DeferredRedditPost]:
    if not os.path.isdir(DEFERRED_REDDIT_ROOT):
        return []
    pending: list[DeferredRedditPost] = []
    for batch_name in sorted(os.listdir(DEFERRED_REDDIT_ROOT)):
        batch_dir = os.path.join(DEFERRED_REDDIT_ROOT, batch_name)
        if not os.path.isdir(batch_dir):
            continue
        manifest_path = os.path.join(batch_dir, "manifest.txt")
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, encoding="utf-8") as manifest:
            for line in manifest:
                line = line.rstrip("\n")
                if not line:
                    continue
                post = _parse_manifest_line(line)
                if post is None:
                    continue
                image_path = os.path.join(batch_dir, post.filename)
                if os.path.isfile(image_path):
                    post.image_path = image_path
                    post.batch_dir = batch_dir
                    pending.append(post)
    return pending


async def count_pending_deferred_posts() -> int:
    """Pending count for the Mork-owned `deferred_reddit/` backlog."""
    return len(list_pending_deferred_posts())


def _deferred_reddit_title(post: DeferredRedditPost) -> str:
    if post.title:
        return post.title
    return reddit_title_for_acceptance(
        post.card_message,
        post.set_id,
        was_vetoed=post.was_vetoed,
    )


def _is_reddit_media_too_large(exc: BaseException) -> bool:
    return "too large" in str(exc).lower()


def _is_reddit_media_upload_failed(exc: BaseException) -> bool:
    return "attempted media upload action has failed" in str(exc).lower()


def _is_reddit_unsupported_media_type(exc: BaseException) -> bool:
    return "expected a mimetype starting with 'image'" in str(exc).lower()


def _manifest_filename(line: str) -> str | None:
    post = _parse_manifest_line(line)
    return post.filename if post else None


def _cleanup_deferred_batch(batch_dir: str) -> None:
    manifest_path = os.path.join(batch_dir, "manifest.txt")
    remaining_lines: list[str] = []
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as manifest:
            for line in manifest:
                line = line.rstrip("\n")
                if not line:
                    continue
                filename = _manifest_filename(line)
                if filename and os.path.isfile(os.path.join(batch_dir, filename)):
                    remaining_lines.append(line)
        if remaining_lines:
            with open(manifest_path, "w", encoding="utf-8") as manifest:
                manifest.write("\n".join(remaining_lines) + "\n")
        else:
            os.remove(manifest_path)
    if os.path.isdir(batch_dir) and not os.listdir(batch_dir):
        os.rmdir(batch_dir)


async def _post_deferred_via_asyncpraw(post: DeferredRedditPost) -> None:
    if post.title:
        await post_to_reddit(
            image_path=post.image_path,
            title=post.title,
            flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
        )
    else:
        await post_to_reddit(
            image_path=post.image_path,
            set_id=post.set_id,
            card_message=post.card_message,
            was_vetoed=post.was_vetoed,
            flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
        )


async def process_deferred_reddit_posts(count: int) -> tuple[int, list[str]]:
    """Drain Mork `deferred_reddit/` backlog.

    When ``REDDIT_DEFERRED_VIA_DEVVIT`` is on and the item has ``image_url``,
    post via Devvit ``/external/post-card``; otherwise (or on Devvit failure)
    fall back to asyncpraw with the local file.
    """
    posts = list_pending_deferred_posts()[:count]
    posted = 0
    errors: list[str] = []
    affected_batches: set[str] = set()
    via_devvit = reddit_deferred_via_devvit_enabled()

    for post in posts:
        title = _deferred_reddit_title(post)
        try:
            posted_via_devvit = False
            if via_devvit and post.image_url:
                try:
                    await post_accept_via_devvit(
                        title=title,
                        image_url=post.image_url,
                        flair_id=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
                    )
                    posted_via_devvit = True
                except Exception as e:
                    print(
                        "Devvit deferred post failed; falling back to asyncpraw:",
                        e,
                    )
            if not posted_via_devvit:
                await _post_deferred_via_asyncpraw(post)
            os.remove(post.image_path)
            posted += 1
            affected_batches.add(post.batch_dir)
        except Exception as e:
            if (
                _is_reddit_media_too_large(e)
                or _is_reddit_media_upload_failed(e)
                or _is_reddit_unsupported_media_type(e)
            ):
                os.remove(post.image_path)
                posted += 1
                affected_batches.add(post.batch_dir)
            else:
                errors.append(f"{post.filename}: {e}")

    for batch_dir in affected_batches:
        _cleanup_deferred_batch(batch_dir)
    return posted, errors
