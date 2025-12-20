import random
from typing import Optional, Any
import hc_constants
from shared_vars import drive


def is_mork(user_id: int):
    """Is the id passed in the id of a MORK"""
    return (
        user_id == hc_constants.MORK
        or user_id == hc_constants.MORK_2
        or user_id == hc_constants.MORK_3
    )


def reasonableCard():
    """This function is used to determine if a card gets auto-magically accepted. Be sure to add 1000 each time it happens"""
    return random.randint(0, 4000) == 69


def uploadToDrive(path: str, id: Optional[str] = None):
    file_to_upload: dict[str, Any] = {"parents": [{"id": hc_constants.IMAGES_FOLDER}]}
    if id:
        file_to_upload["id"] = id

    file = drive.CreateFile(file_to_upload)
    file.SetContentFile(path)
    file.Upload()
    return file["id"]


def getDriveUrl(id: str):
    return f"https://lh3.googleusercontent.com/d/{id}"
