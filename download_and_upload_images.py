import os
import re
from typing import cast
import requests
import tempfile
from is_mork import getDriveUrl
from shared_vars import googleClient
import hc_constants
from shared_vars import drive
from PIL import Image, ImageDraw


DRIVE_FOLDER_ID = "1kLARqwx0D-8qdjO2IeOJVsz92uYNkLje"


def uploadToDrive(path: str):
    file = drive.CreateFile({"parents": [{"id": "1kLARqwx0D-8qdjO2IeOJVsz92uYNkLje"}]})
    file.SetContentFile(path)
    file.Upload()
    return file["id"]


SOURCE_SHEET_KEY = hc_constants.HELLSCUBE_DATABASE
SOURCE_SHEET_NAME = "Database"


TARGET_SHEET_NAME = "PrintableDb"
TARGET_SHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"

# --- 1. Load source sheet and get image URLs ---
databaseSheets = googleClient.open_by_key(SOURCE_SHEET_KEY)
mainSheet = databaseSheets.worksheet(SOURCE_SHEET_NAME)


targetDb = googleClient.open_by_key(TARGET_SHEET_KEY)

targetSheet = targetDb.get_worksheet(0)

startIndex = 2925  # 2925
endIndex = 3835  # 10
cardNames = [cell.value for cell in mainSheet.range(f"A{startIndex}:A{endIndex}")]
primaryUrls = [cell.value for cell in mainSheet.range(f"B{startIndex}:B{endIndex}")]
side1Urls = [cell.value for cell in mainSheet.range(f"S{startIndex}:S{endIndex}")]
side2Urls = [cell.value for cell in mainSheet.range(f"AD{startIndex}:AD{endIndex}")]
side3Urls = [cell.value for cell in mainSheet.range(f"AN{startIndex}:AN{endIndex}")]
side4Urls = [cell.value for cell in mainSheet.range(f"AX{startIndex}:AX{endIndex}")]
cardSet = [cell.value for cell in mainSheet.range(f"D{startIndex}:D{endIndex}")]


def prepare_card_for_printing(image_path: str) -> str:
    """
    Prepares a Magic card image for printing:
    1. Adds alpha channel if not present.
    2. Removes background color (usually white/near-white corners).
    3. Samples the border of the card and extends it outward to create a new border.
    Returns the path to the new image file.
    """
    img = Image.open(image_path).convert("RGBA").copy()
    width, height = img.size

    width, height = img.size
    if width <= 251:
        border = 12
    if width <= 300:  # don't talk to me or my son
        border = 14
    elif width <= 521:
        border = 18
    elif width <= 1000:
        border = 32
    else:
        border = 64

    # Detect background color by sampling corners
    def is_bg(pixel, bg, tol=16):
        return all(abs(c - b) <= tol for c, b in zip(pixel[:3], bg[:3])) and (
            len(pixel) < 4 or pixel[3] > 200
        )

    corners = [
        img.getpixel((0, 0)),
        img.getpixel((width - 1, 0)),
        img.getpixel((0, height - 1)),
        img.getpixel((width - 1, height - 1)),
    ]

    top_center_for_bg = img.getpixel((int(width / 2), 1))
    # Use the most common color among corners as background
    corner_color = max(set(corners), key=corners.count)

    # Remove background (make transparent) using pixel access
    print(corner_color)
    if corner_color[0] != 0 and corner_color[1] != 0 and corner_color[2] != 0:
        px = img.load()
        for y in range(height):
            for x in range(width):
                if (y < border / 2 or y > height - border / 2) or (
                    x < border / 2 or x > width - border / 2
                ):
                    # if is_bg(px[x, y], corner_color):
                    px[x, y] = (255, 255, 255, 0)  # transparent

    # Create new image with extended border
    new_width = width + border * 2
    new_height = height + border * 2
    new_img = Image.new("RGBA", (new_width, new_height), top_center_for_bg)

    # Paste original image in center
    new_img.paste(img, (border, border), img)

    # grab a pixel slice off the border pixels and extend
    for i in range(border):
        # Top
        row = img.crop((0, 0, width, 1))
        new_img.paste(row, (border, i), row)
        # Bottom
        row = img.crop((0, height - 1, width, height))
        new_img.paste(row, (border, new_height - i - 1), row)
        # Left
        col = img.crop((0, 0, 1, height))
        new_img.paste(col, (i, border), col)
        # Right
        col = img.crop((width - 1, 0, width, height))
        new_img.paste(col, (new_width - i - 1, border), col)

    # Save to a new file
    base, ext = os.path.splitext(image_path)
    new_path = f"{base}.png"
    new_img.save(new_path)
    return new_path


# --- 2. Download images and upload to Drive ---
results = []
for name, primaryUrl, side1Url, side2Url, side3Url, side4Url, cardSet in zip(
    cardNames, primaryUrls, side1Urls, side2Urls, side3Urls, side4Urls, cardSet
):
    if not (cardSet == "HC6" or cardSet == "HCC"):
        continue

    sidesToPrint = (
        [primaryUrl]
        if side1Url == ""
        else filter(lambda x: x != "", [side1Url, side2Url, side3Url, side4Url])
    )

    try:
        for i, sideUrl in enumerate(sidesToPrint):
            # Download image
            response = requests.get(sideUrl)
            response.raise_for_status()
            unparsedFileName = response.headers.get("Content-Disposition")
            parsedFileName = cast(
                str,
                re.findall('inline;filename="(.*)"', str(unparsedFileName))[0],
            )

            with open(parsedFileName, "wb") as file:
                file.write(response.content)

            # convert to png if needed
            if parsedFileName.endswith(".jpg"):
                print("it di")
                jpgnameToRemove = parsedFileName
                image = Image.open(parsedFileName)
                parsedFileName = re.sub(r"\.jpg$", ".png", parsedFileName)

                image.save(parsedFileName, "png")
                os.remove(jpgnameToRemove)

            prepare_card_for_printing(parsedFileName)

            uploaded = uploadToDrive(parsedFileName)

            targetSheet.append_row(list((name, f"side {i+1}", getDriveUrl(uploaded))))

            # os.remove(parsedFileName)

    except Exception as e:
        print(f"Error processing {name}: {e}")
