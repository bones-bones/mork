from functools import reduce
import os
import re
from typing import cast
import requests
from is_mork import getDriveUrl
from shared_vars import googleClient
import hc_constants
from shared_vars import drive
from PIL import Image, ImageDraw


DRIVE_FOLDER_ID = "1kLARqwx0D-8qdjO2IeOJVsz92uYNkLje"

listing = drive.ListFile(
    {"q": f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}
).GetList()


def mergeObject(curr, next):
    curr[next["title"]] = next["id"]
    return curr


existingCardMappingObject = reduce(mergeObject, listing, {})


def uploadToDrive(path: str, filename: str):
    existingId = (
        existingCardMappingObject[filename]
        if filename in existingCardMappingObject
        else None
    )

    if existingId:
        file = drive.CreateFile({"id": existingId})

    else:
        file = drive.CreateFile(
            {"parents": [{"id": "1kLARqwx0D-8qdjO2IeOJVsz92uYNkLje"}]}
        )

    file.SetContentFile(path)
    file.Upload()
    return file["id"]


SOURCE_SHEET_KEY = hc_constants.HELLSCUBE_DATABASE
SOURCE_SHEET_NAME = "Tokens Database"  # "Database"


TARGET_SHEET_NAME = "PrintableDb"
TARGET_SHEET_KEY = "1FdnGhkjxnOAbjBEeLGC_QDMVcmEjoOLiuEkM9MeiPFs"

# --- 1. Load source sheet and get image URLs ---
databaseSheets = googleClient.open_by_key(SOURCE_SHEET_KEY)
mainSheet = databaseSheets.worksheet(SOURCE_SHEET_NAME)

targetDb = googleClient.open_by_key(TARGET_SHEET_KEY)


targetSheet = targetDb.get_worksheet(0)

current_printable_cards = targetSheet.col_values(1)
# do 176
startIndex = 1070
endIndex = 1080  # 1149  # 10
cardNames = [cell.value for cell in mainSheet.range(f"B{startIndex}:B{endIndex}")]
primaryUrls = [cell.value for cell in mainSheet.range(f"C{startIndex}:C{endIndex}")]
side1Urls = [
    ""
] * 1150  # [cell.value for cell in mainSheet.range(f"S{startIndex}:S{endIndex}")]
side2Urls = [
    ""
] * 1150  # [cell.value for cell in mainSheet.range(f"AD{startIndex}:AD{endIndex}")]
side3Urls = [
    ""
] * 1150  # [cell.value for cell in mainSheet.range(f"AN{startIndex}:AN{endIndex}")]
side4Urls = [
    ""
] * 1150  # [cell.value for cell in mainSheet.range(f"AX{startIndex}:AX{endIndex}")]
cardSet = [
    ""
] * 1150  # [cell.value for cell in mainSheet.range(f"D{startIndex}:D{endIndex}")]

# [
#     ""
# ] * 1150


def prepare_card_for_printing(image_path: str) -> str:
    """
    Prepares a scube card image for printing:
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
    if width <= 320:  # don't talk to me or my son
        border = 16
    elif width <= 521:
        border = 24
    elif width <= 1000:
        border = 32
    elif width <= 1100:
        border = 48
    else:
        border = 64

    # Detect background color by sampling corners
    def is_bg(pixel, bg, tol=40):
        return all(abs(c - b) <= tol for c, b in zip(pixel[:3], bg[:3])) and (
            len(pixel) < 4 or pixel[3] > 200
        )

    corners = [
        img.getpixel((1, 1)),
        img.getpixel((width - 1, 1)),
        img.getpixel((1, height - 1)),
        img.getpixel((width - 1, height - 1)),
    ]

    top_center_for_bg = img.getpixel((int(width / 2), 5))
    corner_color = max(set(corners), key=corners.count)

    # Remove background (make transparent) using pixel access
    print(
        corner_color[3],
        corners[0],
        min(
            color_diff(corners[0], (255, 255, 255, 255)),
            color_diff(corners[0], (0, 0, 0, 0)),
        ),
        min(
            color_diff(corners[1], (255, 255, 255, 255)),
            color_diff(corners[1], (0, 0, 0, 0)),
        ),
        min(
            color_diff(corners[2], (255, 255, 255, 255)),
            color_diff(corners[2], (0, 0, 0, 0)),
        ),
        min(
            color_diff(corners[3], (255, 255, 255, 255)),
            color_diff(corners[3], (0, 0, 0, 0)),
        ),
        color_diff(corners[0], top_center_for_bg),
    )
    # put back after magic wand test
    if (
        corner_color[3] != 0
        and min(
            color_diff(corners[0], (255, 255, 255, 255)),
            color_diff(corners[0], (0, 0, 0, 0)),
        )
        < 35
        and min(
            color_diff(corners[1], (255, 255, 255, 255)),
            color_diff(corners[1], (0, 0, 0, 0)),
        )
        < 35
        and min(
            color_diff(corners[2], (255, 255, 255, 255)),
            color_diff(corners[2], (0, 0, 0, 0)),
        )
        < 35
        and min(
            color_diff(corners[3], (255, 255, 255, 255)),
            color_diff(corners[3], (0, 0, 0, 0)),
        )
        < 35
        and color_diff(corners[0], top_center_for_bg) > 200
    ):

        # Draw equilateral triangles in each corner
        draw = ImageDraw.Draw(img)
        # Top-left
        draw.polygon(
            [(0, 0), (border, 0), (0, border)],
            fill=top_center_for_bg,  # img.getpixel((int(border / 3), int(border / 3))),
        )

        # tr
        draw.polygon(
            [(width, 0), (width, border), (width - border, 0)],
            fill=top_center_for_bg,  # img.getpixel((width - int(border / 3), int(border / 3))),
        )

        # bottom left
        draw.polygon(
            [(0, height), (border, height), (0, height - border)],
            fill=top_center_for_bg,  # img.getpixel((int(border / 3), height - int(border / 3))),
        )
        # bottom right
        draw.polygon(
            [(width, height), (width - border, height), (width, height - border)],
            fill=top_center_for_bg,  # img.getpixel((width - int(border / 3), height - int(border / 3))),
        )

    # Create new image with extended border
    new_width = width + border * 2
    new_height = height + border * 2
    new_img = Image.new("RGB", (new_width, new_height), top_center_for_bg)

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

    # Draw equilateral triangles in each corner
    draw = ImageDraw.Draw(new_img)
    # Top-left
    draw.polygon([(0, 0), (border, 0), (0, border)], fill=top_center_for_bg)
    # Top-right
    draw.polygon(
        [(new_width, 0), (new_width - border, 0), (new_width, border)],
        fill=top_center_for_bg,
    )
    # Bottom-left
    draw.polygon(
        [(0, new_height), (border, new_height), (0, new_height - border)],
        fill=top_center_for_bg,
    )
    # Bottom-right
    draw.polygon(
        [
            (new_width, new_height),
            (new_width - border, new_height),
            (new_width, new_height - border),
        ],
        fill=top_center_for_bg,
    )

    # Save to a new file
    base, ext = os.path.splitext(image_path)
    new_path = f"{base}.png"
    new_img.save(new_path)
    return new_path


def color_diff(
    c1: tuple[float, float, float, float], c2: tuple[float, float, float, float]
) -> float:
    """
    Returns the sum of absolute differences between two RGBA color tuples.
    """
    return sum(abs(a - b) for a, b in zip(c1, c2))


# --- 2. Download images and upload to Drive ---
results = []
for name, primaryUrl, side1Url, side2Url, side3Url, side4Url, cardSet in zip(
    cardNames, primaryUrls, side1Urls, side2Urls, side3Urls, side4Urls, cardSet
):
    print("name", name)
    # TODO put back
    # if not (cardSet == "HCC" or cardSet == "HCP"):
    #     continue

    sidesToPrint = (
        [primaryUrl]
        if side1Url == ""
        else filter(lambda x: x != "", [side1Url, side2Url, side3Url, side4Url])
    )

    try:
        for i, sideUrl in enumerate(sidesToPrint):
            print(i, sideUrl)
            # Download image
            response = requests.get(sideUrl)
            response.raise_for_status()
            unparsedFileName = response.headers.get("Content-Disposition")

            parsedFileName = cast(
                str,
                re.findall('inline;filename="(.*)"', str(unparsedFileName))[0],
            )
            print(parsedFileName)
            parsedFileName = (
                cast(str, name).replace("/", "|") + ".png"
                if ".png" in parsedFileName
                else cast(str, name).replace("/", "|") + ".jpg"
            )

            with open(parsedFileName, "wb") as file:
                file.write(response.content)

            # convert to png if needed
            if parsedFileName.endswith(".jpg"):
                print("jpg conversion path")
                jpgnameToRemove = parsedFileName
                image = Image.open(parsedFileName)
                parsedFileName = re.sub(r"\.jpg$", ".png", parsedFileName)

                image.save(parsedFileName, "png")
                os.remove(jpgnameToRemove)

            print(parsedFileName)
            prepare_card_for_printing(parsedFileName)

            # add back
            uploaded = uploadToDrive(parsedFileName, parsedFileName)

            ## TODO add a check here fore side 1 side 2
            current_entry_in_sheet = (
                current_printable_cards.index(name)
                if name in current_printable_cards
                else None
            )

            if current_entry_in_sheet == None:
                print(f"appending to sheet: {parsedFileName}")
                targetSheet.append_row(
                    list((name, f"side {i+1}", getDriveUrl(uploaded)))
                )
            else:
                print(f"updating sheet entry: {parsedFileName}")
                targetSheet.update_cell(
                    current_entry_in_sheet + 1, 3, getDriveUrl(uploaded)
                )

            os.remove(parsedFileName)

    except Exception as e:
        print(f"Error processing {name}: {e}")
