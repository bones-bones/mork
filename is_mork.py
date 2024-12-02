import random
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
    return random.randint(0, 3000) == 69


def uploadToDrive(path: str):
    file = drive.CreateFile({"parents": [{"id": hc_constants.IMAGES_FOLDER}]})
    file.SetContentFile(path)
    file.Upload()
    return file["id"]


def getDriveUrl(id: str):
    return f"https://lh3.googleusercontent.com/d/{id}"
