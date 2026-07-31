import os
from dataclasses import dataclass

import hc_constants
from reddit_functions import post_to_reddit

DEFERRED_REDDIT_ROOT = "deferred_reddit"


@dataclass
class DeferredRedditPost:
    image_path: str
    title: str
    batch_dir: str
    filename: str


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
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue
                filename, title = parts
                image_path = os.path.join(batch_dir, filename)
                if os.path.isfile(image_path):
                    pending.append(
                        DeferredRedditPost(image_path, title, batch_dir, filename)
                    )
    return pending


def _is_reddit_media_too_large(exc: BaseException) -> bool:
    return "too large" in str(exc).lower()


def _is_reddit_media_upload_failed(exc: BaseException) -> bool:
    return "attempted media upload action has failed" in str(exc).lower()


def _cleanup_deferred_batch(batch_dir: str) -> None:
    manifest_path = os.path.join(batch_dir, "manifest.txt")
    remaining_lines: list[str] = []
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as manifest:
            for line in manifest:
                line = line.rstrip("\n")
                if not line:
                    continue
                filename = line.split("\t", 1)[0]
                if os.path.isfile(os.path.join(batch_dir, filename)):
                    remaining_lines.append(line)
        if remaining_lines:
            with open(manifest_path, "w", encoding="utf-8") as manifest:
                manifest.write("\n".join(remaining_lines) + "\n")
        else:
            os.remove(manifest_path)
    if os.path.isdir(batch_dir) and not os.listdir(batch_dir):
        os.rmdir(batch_dir)


async def process_deferred_reddit_posts(count: int) -> tuple[int, list[str]]:
    posts = list_pending_deferred_posts()[:count]
    posted = 0
    errors: list[str] = []
    affected_batches: set[str] = set()
    for post in posts:
        try:
            await post_to_reddit(
                image_path=post.image_path,
                title=post.title,
                flair=hc_constants.OFFICIAL_HC_REDDIT_FLAIR,
            )
            os.remove(post.image_path)
            posted += 1
            affected_batches.add(post.batch_dir)
        except Exception as e:
            if _is_reddit_media_too_large(e) or _is_reddit_media_upload_failed(e):
                os.remove(post.image_path)
                posted += 1
                affected_batches.add(post.batch_dir)
            else:
                errors.append(f"{post.filename}: {e}")
    for batch_dir in affected_batches:
        _cleanup_deferred_batch(batch_dir)
    return posted, errors
