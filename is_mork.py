import os
import random
from typing import Any

import hc_constants
from shared_vars import drive

_DEFAULT_REASONABLE_CARD_MAX = 5000


def reasonable_card_max() -> int:
    """Upper bound for the auto-accept lottery (`random.randint(0, max)`)."""
    raw = os.environ.get("REASONABLE_CARD_MAX", str(_DEFAULT_REASONABLE_CARD_MAX)).strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_REASONABLE_CARD_MAX
    return value if value >= 0 else _DEFAULT_REASONABLE_CARD_MAX


def is_mork(user_id: int):
    """Is the id passed in the id of a MORK"""
    return (
        user_id == hc_constants.MORK
        or user_id == hc_constants.MORK_2
        or user_id == hc_constants.MORK_3
    )


def is_reddit_mirror_author(user_id: int) -> bool:
    """Discord user that posted a Reddit mirror link in #reddit."""
    return is_mork(user_id) or user_id == hc_constants.MORK_BRIDGE


def reasonable_card():
    """Auto-accept lottery. Bump REASONABLE_CARD_MAX (default 5000) after it fires."""
    return random.randint(0, reasonable_card_max()) == 69


def uploadToDrive(path: str, id: str | None = None, folder_id: str | None = None):
    folder = folder_id if folder_id else hc_constants.IMAGES_FOLDER
    file_to_upload: dict[str, Any] = {"parents": [{"id": folder}]}
    if id:
        file_to_upload["id"] = id

    file = drive.CreateFile(file_to_upload)
    file.SetContentFile(path)
    file.Upload()
    return file["id"]


def getDriveUrl(id: str):
    return f"https://lh3.googleusercontent.com/d/{id}"
