"""
Pull images from GCS, fix border fuckups (irregular black/white borders,
corner artifacts, bleeding), then re-upload to the same GCS paths.

Target: clean, uniform outer border like the reference cards (e.g. Halvesies,
Winter Cube, Pet Gravyard) — solid black border, no streaks or artifacts.
"""

import mork_repo_root  # noqa: E402

import os
import tempfile
from typing import Tuple, List

import google.auth
from google.cloud import storage
from PIL import Image

os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "./bot_secrets/client_secrets.json")

credentials, project_id = google.auth.default()
storage_client = storage.Client(credentials=credentials)
GCS_BUCKET_NAME = "hellscube-printable-images"
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# How much to consider "background" (black/grey/white) at edges
BG_LUMINANCE_MIN = 5   # below this = black
BG_LUMINANCE_MAX = 250  # above this = white
BG_SATURATION_MAX = 30  # low sat = grey

# Pixels with luminance above this are treated as "artifact" when border is black
ARTIFACT_LUMINANCE_MIN = 200
# Pixels in border zone with saturation below this can be filled (grey junk)
ARTIFACT_SATURATION_MAX = 40

# Luminance threshold: edge pixels above this = white border, below = black border
WHITE_BORDER_LUMINANCE_THRESHOLD = 128
# How close a pixel must be to the border color to be kept (sum of channel diffs)
BORDER_COLOR_TOLERANCE = 80

# Only touch pixels within this many pixels of the image edge (avoids cropping into card)
BORDER_ZONE_MAX_PX = 35

# Uniform border to add after crop (pixels, black) — only used when not filling
UNIFORM_BORDER_PX = 2

# Dry-run output folder (relative to script dir)
DRY_RUN_OUTPUT_DIR = "fix_borders_dry_run"


def _luminance(rgb: Tuple[int, ...]) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _color_distance(pixel: Tuple[int, ...], fill_color: Tuple[int, int, int], is_rgba: bool) -> int:
    """Sum of absolute channel differences; pixel can be 3 or 4 components."""
    r, g, b = pixel[0], pixel[1], pixel[2]
    return abs(r - fill_color[0]) + abs(g - fill_color[1]) + abs(b - fill_color[2])


def _pixel_is_artifact(
    pixel: Tuple[int, ...], is_rgba: bool, fill_color: Tuple[int, int, int]
) -> bool:
    """True if pixel in border zone does not match the border color (should be filled)."""
    if is_rgba and len(pixel) > 3 and pixel[3] < 128:
        return True
    return _color_distance(pixel, fill_color, is_rgba) > BORDER_COLOR_TOLERANCE


def _get_border_fill_color(img: Image.Image, band: int) -> Tuple[int, int, int]:
    """
    Sample pixels in the edge band; decide white vs black border by majority luminance.
    Returns the border color to use for filling artifacts.
    """
    pixels = img.load()
    if pixels is None:
        return (0, 0, 0)
    w, h = img.size
    samples: List[Tuple[int, int, int]] = []
    # Sample in the edge band only
    for x in [0, 1, min(3, w - 1), max(0, w - 4), max(0, w - 2), w - 1]:
        if x >= w:
            continue
        for y in [0, 1, min(3, h - 1), max(0, h - 4), max(0, h - 2), h - 1]:
            if y >= h:
                continue
            if x >= band and x < w - band and y >= band and y < h - band:
                continue  # skip center
            p = pixels[x, y]
            if isinstance(p, int):
                rgb = (p, p, p)
            else:
                rgb = p[:3]
            samples.append(rgb)

    if not samples:
        return (0, 0, 0)

    light = [s for s in samples if _luminance(s) >= WHITE_BORDER_LUMINANCE_THRESHOLD]
    dark = [s for s in samples if _luminance(s) < WHITE_BORDER_LUMINANCE_THRESHOLD]

    if len(light) >= len(dark):
        # White border: use lightest sample (or pure white if none)
        if not light:
            return (255, 255, 255)
        fill = max(light, key=_luminance)
        return (int(fill[0]), int(fill[1]), int(fill[2]))
    else:
        # Black border: use darkest sample
        fill = min(dark, key=_luminance)
        return (int(fill[0]), int(fill[1]), int(fill[2]))


def _pixel_is_background(pixel: Tuple[int, ...], is_rgba: bool) -> bool:
    """True if pixel looks like border/background (black, near-black, grey, white)."""
    r, g, b = pixel[0], pixel[1], pixel[2]
    a = pixel[3] if is_rgba and len(pixel) > 3 else 255
    if a < 128:
        return True
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum <= BG_LUMINANCE_MIN or lum >= BG_LUMINANCE_MAX:
        return True
    sat = max(r, g, b) - min(r, g, b)
    if sat <= BG_SATURATION_MAX:
        return True
    return False


def _find_content_bbox(img: Image.Image) -> Tuple[int, int, int, int]:
    """
    Find the axis-aligned bounding box of card content by scanning from each
    edge inward until we hit non-background pixels.
    """
    pixels = img.load()
    if pixels is None:
        return (0, 0, img.size[0], img.size[1])
    w, h = img.size
    is_rgba = img.mode == "RGBA"

    def is_bg(x: int, y: int) -> bool:
        p = pixels[x, y]
        if isinstance(p, int):
            return p <= BG_LUMINANCE_MIN or p >= BG_LUMINANCE_MAX
        return _pixel_is_background(p, is_rgba)

    # Top: scan down
    top = 0
    for y in range(h):
        if not all(is_bg(x, y) for x in range(w)):
            top = max(0, y - 1)
            break
    # Bottom: scan up
    bottom = h - 1
    for y in range(h - 1, -1, -1):
        if not all(is_bg(x, y) for x in range(w)):
            bottom = min(h - 1, y + 1)
            break
    # Left: scan right
    left = 0
    for x in range(w):
        if not all(is_bg(x, y) for y in range(h)):
            left = max(0, x - 1)
            break
    # Right: scan left
    right = w - 1
    for x in range(w - 1, -1, -1):
        if not all(is_bg(x, y) for y in range(h)):
            right = min(w - 1, x + 1)
            break

    return (left, top, right + 1, bottom + 1)


def fix_card_borders(image_path: str, out_path: str | None = None) -> str:
    """
    Only touch a fixed band around the image edges: fill artifact pixels in that
    band with the dominant border color. Interior of the card is never modified.
    """
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size

    band = min(BORDER_ZONE_MAX_PX, w // 4, h // 4)  # at most 1/4 of smaller dimension
    if band <= 0:
        save_path = out_path or image_path
        img.convert("RGB").save(save_path)
        return save_path

    fill_color = _get_border_fill_color(img, band)
    fill_color_rgba = fill_color + (255,)
    pixels = img.load()
    is_rgba = True
    if pixels is None:
        save_path = out_path or image_path
        img.convert("RGB").save(save_path)
        return save_path

    for y in range(h):
        for x in range(w):
            # Only in the edge band (never touch center)
            if x >= band and x < w - band and y >= band and y < h - band:
                continue
            p = pixels[x, y]
            if isinstance(p, int):
                p = (p, p, p, 255)
            if _pixel_is_artifact(p, is_rgba, fill_color):
                pixels[x, y] = fill_color_rgba

    save_path = out_path or image_path
    img.convert("RGB").save(save_path)
    return save_path


def download_blob(blob) -> str:
    """Download blob to a temp file; return path."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    blob.download_to_filename(path)
    return path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix card border fuckups in GCS images")
    parser.add_argument("--prefix", default="", help="Only process blobs with this prefix")
    parser.add_argument("--dry-run", action="store_true", help="Don't upload; save fixed images to a folder in this dir")
    parser.add_argument("--limit", type=int, default=0, help="Max number of blobs to process (0 = all)")
    args = parser.parse_args()

    # Dry-run: save to folder in script/project dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dry_run_dir = os.path.join(script_dir, DRY_RUN_OUTPUT_DIR)
    if args.dry_run:
        os.makedirs(dry_run_dir, exist_ok=True)
        print(f"Dry run: saving fixed images to {dry_run_dir}")

    blobs = list(bucket.list_blobs(prefix=args.prefix))
    if args.limit:
        blobs = blobs[: args.limit]

    # Filter to likely image blobs (names often like "CardName.png-123-side 1")
    def is_likely_image(name: str) -> bool:
        n = name.lower()
        return ".png" in n or ".jpg" in n or n.endswith(".jpeg")
    blobs = [b for b in blobs if is_likely_image(b.name)]

    print(f"Found {len(blobs)} image blob(s) to process.")

    for i, blob in enumerate(blobs):
        name = blob.name
        print(f"[{i+1}/{len(blobs)}] {name}")
        try:
            path = download_blob(blob)
            try:
                if args.dry_run:
                    # Safe filename ending in .png so PIL and filesystems are happy
                    safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")
                    if not safe_name.lower().endswith(".png"):
                        safe_name = safe_name + ".png"
                    out_path = os.path.join(dry_run_dir, safe_name)
                    fix_card_borders(path, out_path)
                    print(f"  Saved: {out_path}")
                else:
                    fix_card_borders(path, path)
                    blob.upload_from_filename(path, content_type="image/png")
                    print(f"  Uploaded: {name}")
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
        except Exception as e:
            print(f"  Error: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
