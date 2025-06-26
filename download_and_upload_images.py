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


DRIVE_FOLDER_ID = (
    "1kLARqwx0D-8qdjO2IeOJVsz92uYNkLje"  # TODO: Set this to your Drive folder ID
)


def uploadToDrive(path: str):
    file = drive.CreateFile({"parents": [{"id": "1kLARqwx0D-8qdjO2IeOJVsz92uYNkLje"}]})
    file.SetContentFile(path)
    file.Upload()
    return file["id"]


# --- CONFIG ---
SOURCE_SHEET_KEY = hc_constants.HELLSCUBE_DATABASE
SOURCE_SHEET_NAME = "Database"


TARGET_SHEET_NAME = "PrintableDb"
TARGET_SHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"

# --- 1. Load source sheet and get image URLs ---
databaseSheets = googleClient.open_by_key(SOURCE_SHEET_KEY)
mainSheet = databaseSheets.worksheet(SOURCE_SHEET_NAME)


targetDb = googleClient.open_by_key(TARGET_SHEET_KEY)

targetSheet = targetDb.get_worksheet(0)

startIndex = 2935  # 2925
endIndex = 2940
cardNames = [cell.value for cell in mainSheet.range(f"A{startIndex}:A{endIndex}")]
primaryUrls = [cell.value for cell in mainSheet.range(f"B{startIndex}:B{endIndex}")]
side1Urls = [cell.value for cell in mainSheet.range(f"S{startIndex}:S{endIndex}")]
side2Urls = [cell.value for cell in mainSheet.range(f"AD{startIndex}:AD{endIndex}")]
side3Urls = [cell.value for cell in mainSheet.range(f"AN{startIndex}:AN{endIndex}")]
side4Urls = [cell.value for cell in mainSheet.range(f"AX{startIndex}:AX{endIndex}")]
cardSet = [cell.value for cell in mainSheet.range(f"D{startIndex}:D{endIndex}")]


def extend_card_borders(image_path: str) -> str:
    """
    Extends the borders of a card image with rounded corners.
    If the image already has white rounded corners, extends with white.
    Returns the path to the new image file.
    """
    # 750, 16,64
    img = Image.open(image_path).convert("RGBA")
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
    new_width = width + border * 2
    new_height = height + border * 2

    # Detect if corners are white (tolerance for near-white)
    def is_white(pixel, tol=16):
        return all(c >= 255 - tol for c in pixel[:3]) and (
            len(pixel) < 4 or pixel[3] > 200
        )

    corners = [
        img.getpixel((0, 0)),
        img.getpixel((width - 1, 0)),
        img.getpixel((0, height - 1)),
        img.getpixel((width - 1, height - 1)),
    ]
    corners_are_white = all(is_white(px) for px in corners)
    border_color = (255, 255, 255, 255) if corners_are_white else (0, 0, 0, 0)

    # Create new image with appropriate border color
    new_img = Image.new("RGBA", (new_width, new_height), border_color)

    # Create a rounded rectangle mask for the new image
    mask = Image.new("L", (new_width, new_height), 0)
    draw = ImageDraw.Draw(mask)
    corner_radius = int(min(width, height) * 0.08)
    draw.rounded_rectangle(
        [(0, 0), (new_width - 1, new_height - 1)],
        radius=corner_radius + border,
        fill=255,
    )

    # Create a mask for the original image to trim its corners
    orig_mask = Image.new("L", (width, height), 0)
    orig_draw = ImageDraw.Draw(orig_mask)
    orig_draw.rounded_rectangle(
        [(0, 0), (width - 1, height - 1)],
        radius=corner_radius,
        fill=255,
    )
    # Apply the mask to the original image
    trimmed_img = img.copy()
    trimmed_img.putalpha(orig_mask)

    # Paste the trimmed original image onto the center of the new image
    new_img.paste(trimmed_img, (border, border), trimmed_img)
    # Apply the rounded mask (only if not white corners)
    if not corners_are_white:
        new_img.putalpha(mask)

    # Save to a new file
    base, ext = os.path.splitext(image_path)
    new_path = f"{base}.png"
    new_img.save(new_path)
    return new_path


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
    # Use the most common color among corners as background
    bg_color = max(set(corners), key=corners.count)

    # Remove background (make transparent) using pixel access
    px = img.load()
    for y in range(height):
        for x in range(width):
            if is_bg(px[x, y], bg_color):
                px[x, y] = (255, 255, 255, 0)  # transparent

    # Create new image with extended border
    new_width = width + border * 2
    new_height = height + border * 2
    new_img = Image.new("RGBA", (new_width, new_height), (255, 255, 255, 0))

    # Paste original image in center
    new_img.paste(img, (border, border), img)

    # Sample border pixels and extend outward
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
    new_path = f"{base}_printready.png"
    new_img.save(new_path)
    return new_path


# --- 2. Download images and upload to Drive ---
results = []
for name, primaryUrl in zip(cardNames, primaryUrls):
    if not primaryUrl:
        continue
    try:
        # Download image
        response = requests.get(primaryUrl)
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
            image = Image.open(parsedFileName)
            parsedFileName = re.sub(r"\.jpg$", ".png", parsedFileName)

            image.save(parsedFileName, "png")

        prepare_card_for_printing(parsedFileName)

        # oi put it back
        # uploaded = uploadToDrive(parsedFileName)

        # oi put it back
        # targetSheet.append_row(list((name, getDriveUrl(uploaded))))

        # oi put it back
        # os.remove(parsedFileName)

    except Exception as e:
        print(f"Error processing {name}: {e}")
