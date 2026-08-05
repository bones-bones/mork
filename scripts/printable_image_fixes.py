"""
Defect-specific PIL fixes for printable card images.

Companion to ``printable_image_qa.py``: QA detects issues; this module attempts
targeted repairs on the *current* printable PNG (not a re-run of border prep).

The observed script artifacts are:
  * thin, bright **L-shaped crop/registration marks** hugging the four image
    corners (in the background/border, just outside the card frame), and
  * occasionally one whole side whose outer border band is the wrong (light)
    color on an otherwise black-bordered card.

Both fixes are deliberately *surgical*: they only touch the small corner regions
and the erroneous outer strip, so gradient borders, colored borders, and white
borders are left intact.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import requests
from PIL import Image

from printable_image_qa import (
    KNOWN_DEFECT_TAGS,
    extract_corner_crops,
    inpaint_border_seam_lines,
    ollama_chat,
    suitable_for_corner_crops,
)

DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

# Defects we can attempt to repair in-place on the printable image.
FIXABLE = frozenset(
    {
        "corner_color_mismatch",
        "conversion_bleed",
        "border_seam_lines",
    }
)

# Defects that need human intervention or a different source file.
UNFIXABLE = frozenset(
    {
        "corner_trim",  # art already clipped; padding won't restore lost pixels
        "wrong_silhouette",
        "multi_card_in_one_file",
    }
)

@dataclass
class FixResult:
    out_path: str
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pixels_changed: int = 0


@dataclass
class FixRetryContext:
    """Reassess feedback fed into a second vision-guided fix pass."""

    original_defects: list[str]
    remaining_defects: list[str]
    upload_reason: str
    verdict: str
    heuristic_flags: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: str = ""


def _border_band(w: int, h: int) -> int:
    return max(8, min(w, h) // 25)


def extension_width(w: int, h: int) -> int:
    """Width of the conversion-added border band (matches prepare_card_for_printing)."""
    return infer_added_border(w, h) or 16


def _in_extension(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """True when (x, y) lies in the outer extension padding, not the original card."""
    return x < ext or x >= w - ext or y < ext or y >= h - ext


def _corner_apex_reach(ext: int) -> int:
    """How far past the ext line corner L-mark tips may sit."""
    return max(8, ext // 2)


def _in_corner_apex(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Small squares at each corner just inside the extension boundary."""
    reach = _corner_apex_reach(ext)
    if ext <= x < ext + reach and ext <= y < ext + reach:
        return True
    if w - ext - reach <= x < w - ext and ext <= y < ext + reach:
        return True
    if ext <= x < ext + reach and h - ext - reach <= y < h - ext:
        return True
    if w - ext - reach <= x < w - ext and h - ext - reach <= y < h - ext:
        return True
    return False


def _in_corner_junction(
    corner: str, x: int, y: int, w: int, h: int, ext: int
) -> bool:
    """Padding/card seam square at a named corner (includes y=ext / x=ext rows)."""
    reach = _corner_apex_reach(ext)
    if corner == "TL":
        return ext <= x < ext + reach and ext <= y < ext + reach
    if corner == "TR":
        return w - ext - reach <= x < w - ext and ext <= y < ext + reach
    if corner == "BL":
        return ext <= x < ext + reach and h - ext - reach <= y < h - ext
    return w - ext - reach <= x < w - ext and h - ext - reach <= y < h - ext


def _bottom_gutter_arm_reach(ext: int) -> int:
    """How far above the bottom ext line L-mark arms may sit."""
    return max(8, ext)


def _bottom_gutter_arm_width(ext: int, band: int) -> int:
    return max(ext * 2 + 8, ext + band * 2)


def _bottom_gutter_wedge_reach(ext: int, band: int) -> int:
    """How far above the bottom ext line grey gutter wedges may sit."""
    return ext + band * 2


def _bottom_gutter_wedge_width(ext: int, band: int) -> int:
    return ext + band * 3


def _top_corner_match_reach(ext: int) -> int:
    return _corner_apex_reach(ext)


def _top_corner_match_width(ext: int, band: int) -> int:
    return _bottom_gutter_arm_width(ext, band)


def _in_bottom_gutter_arm(x: int, y: int, w: int, h: int, ext: int, band: int) -> bool:
    """Horizontal L-mark arms just inside the bottom extension line (side gutters only)."""
    reach = _bottom_gutter_arm_reach(ext)
    width = _bottom_gutter_arm_width(ext, band)
    if not (h - ext - reach <= y < h - ext):
        return False
    if ext <= x < _bl_bottom_gutter_x1(w, ext, width):
        return True
    return _br_bottom_gutter_x0(w, ext, width) <= x < w - ext


def _in_corner_fix_zone(
    x: int, y: int, w: int, h: int, ext: int, band: int, *, allow_apex: bool
) -> bool:
    if _in_extension(x, y, w, h, ext):
        return True
    if not allow_apex:
        return False
    return _in_corner_apex(x, y, w, h, ext) or _in_bottom_gutter_arm(
        x, y, w, h, ext, band
    )


def _brightness(p: tuple[int, int, int]) -> int:
    return (p[0] + p[1] + p[2]) // 3


def _color_distance(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _median_rgb(values: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    if not values:
        return (0, 0, 0)
    r = sorted(v[0] for v in values)
    g = sorted(v[1] for v in values)
    b = sorted(v[2] for v in values)
    m = len(values) // 2
    return (r[m], g[m], b[m])


# Corner descriptors: (name, x0, y0, x1, y1 are computed per-image). Each corner
# is processed in image space; ``outer`` flags mark which box edges sit on the
# image border (where the L-marks anchor).
_CORNERS = ("TL", "TR", "BL", "BR")


def _corner_box(name: str, w: int, h: int, size: int) -> tuple[int, int, int, int]:
    if name == "TL":
        return (0, 0, size, size)
    if name == "TR":
        return (w - size, 0, w, size)
    if name == "BL":
        return (0, h - size, size, h)
    return (w - size, h - size, w, h)  # BR


def _corner_padding_bg(
    px,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    w: int,
    h: int,
    corner: str,
    *,
    strip: int,
    arm: int,  # kept for call-site compatibility; not sampled (arms pulled in 162 wedges)
) -> tuple[int, int, int]:
    """Padding color from the exterior edge strip only (avoids diagonal 162 wedges)."""
    del arm
    samples: list[tuple[int, int, int]] = []
    if corner in ("BL", "BR"):
        for x in range(x0, x1):
            for y in range(max(y1 - strip, y0), y1):
                samples.append(px[x, y][:3])
    else:
        for x in range(x0, x1):
            for y in range(y0, min(y0 + strip, y1)):
                samples.append(px[x, y][:3])
    if not samples:
        box_pixels = [px[x, y][:3] for y in range(y0, y1) for x in range(x0, x1)]
        return _median_rgb(box_pixels)
    dark = [p for p in samples if _brightness(p) < 40]
    if corner in ("BL", "BR") and len(dark) >= len(samples) // 4:
        return _median_rgb(dark)
    return _median_rgb(samples)


@dataclass(frozen=True)
class _CornerPadStyle:
    fill: tuple[int, int, int]
    light: bool
    dark: bool

    @property
    def ref(self) -> int:
        return _brightness(self.fill)


def _sample_corner_border_color(
    px, corner: str, w: int, h: int, ext: int
) -> tuple[int, int, int] | None:
    """Sample the card frame color at y=ext (or y=h-ext-1) beside a top corner."""
    reach = ext + max(8, ext // 2)
    if corner == "TL":
        xs = range(ext, min(w - ext, ext + reach))
        row = ext
    elif corner == "TR":
        xs = range(max(ext, w - ext - reach), w - ext)
        row = ext
    else:
        return None
    samples = [px[x, row][:3] for x in xs]
    if not samples:
        return None
    # Drop near-white padding bleed; keep coloured frame and saturated border.
    filtered = [
        s
        for s in samples
        if _brightness(s) < 248 or max(s) - min(s) > 12
    ]
    if not filtered:
        filtered = samples
    return _median_rgb(filtered)


def _inner_corner_fill(
    px, corner: str, w: int, h: int, ext: int
) -> tuple[int, int, int]:
    """Card-frame colour just inside a corner — avoids white L-mark padding bleed."""
    reach = max(3, ext // 2 + 2)
    samples: list[tuple[int, int, int]] = []
    if corner == "TL":
        for y in range(ext, min(h - ext, ext + reach)):
            for x in range(ext, min(w - ext, ext + reach)):
                samples.append(px[x, y][:3])
    elif corner == "TR":
        for y in range(ext, min(h - ext, ext + reach)):
            for x in range(max(ext, w - ext - reach), w - ext):
                samples.append(px[x, y][:3])
    elif corner == "BL":
        for y in range(max(ext, h - ext - reach), h - ext):
            for x in range(ext, min(w - ext, ext + reach)):
                samples.append(px[x, y][:3])
    else:
        for y in range(max(ext, h - ext - reach), h - ext):
            for x in range(max(ext, w - ext - reach), w - ext):
                samples.append(px[x, y][:3])
    if not samples:
        return (0, 0, 0)
    filtered = [s for s in samples if _brightness(s) < 230]
    return _median_rgb(filtered or samples)


def _corner_fixup_fill(
    px, corner: str, w: int, h: int, ext: int
) -> tuple[int, int, int]:
    """Target fill for corner artifact removal; prefers inner frame when padding is white."""
    style = _corner_pad_style(px, corner, w, h, ext)
    if style.ref >= 220:
        inner = _inner_corner_fill(px, corner, w, h, ext)
        if _brightness(inner) < style.ref - 20:
            return inner
    if not style.dark:
        sampled = _sample_corner_border_color(px, corner, w, h, ext)
        if sampled is not None and corner in ("TL", "TR"):
            return sampled
    return style.fill


def _corner_pad_style(
    px, corner: str, w: int, h: int, ext: int
) -> _CornerPadStyle:
    """Padding tone and fill for the side(s) adjacent to this corner."""
    skip = max(1, min(w, h) // 10)
    if corner in ("TL", "TR"):
        samples = [
            px[x, y][:3]
            for x in range(skip, w - skip)
            for y in range(0, ext)
        ]
    else:
        samples = [
            px[x, y][:3]
            for x in range(skip, w - skip)
            for y in range(h - ext, h)
        ]
        edge: list[tuple[int, int, int]] = []
        if corner == "BL":
            edge = [px[x, y][:3] for x in range(0, ext) for y in range(h - ext, h)]
        elif corner == "BR":
            edge = [px[x, y][:3] for x in range(w - ext, w) for y in range(h - ext, h)]
        if edge:
            edge_med = sorted(_brightness(s) for s in edge)[len(edge) // 2]
            if edge_med >= 90:
                return _CornerPadStyle(_median_rgb(edge), True, False)
    if not samples:
        return _CornerPadStyle((0, 0, 0), False, True)
    brs = [_brightness(s) for s in samples]
    med = sorted(brs)[len(brs) // 2]
    if med < 55:
        dark = [s for s in samples if _brightness(s) < 40]
        fill = _median_rgb(dark if dark else samples)
        if _brightness(fill) >= 55:
            fill = (0, 0, 0)
        return _CornerPadStyle(fill, False, True)
    border = _sample_corner_border_color(px, corner, w, h, ext)
    fill = border if border is not None else _median_rgb(samples)
    return _CornerPadStyle(fill, med >= 100, False)


def _is_neutral_grey(p: tuple[int, int, int], *, spread: int = 8) -> bool:
    r, g, b = p
    return abs(r - g) <= spread and abs(g - b) <= spread


def _is_neutral_dark(p: tuple[int, int, int]) -> bool:
    return _brightness(p) < 40 or (_is_neutral_grey(p) and _brightness(p) < 90)


def _color_spread(p: tuple[int, int, int]) -> int:
    return max(p) - min(p)


def _corner_inner_samples(
    px, corner: str, w: int, h: int, ext: int, reach: int
) -> list[tuple[int, int, int]]:
    """Card pixels just inside the frame at a corner."""
    if corner == "TL":
        xs, ys = range(ext, ext + reach), range(ext, ext + reach)
    elif corner == "TR":
        xs, ys = range(w - ext - reach, w - ext), range(ext, ext + reach)
    elif corner == "BL":
        xs, ys = range(ext, ext + reach), range(h - ext - reach, h - ext)
    else:
        xs, ys = range(w - ext - reach, w - ext), range(h - ext - reach, h - ext)
    return [px[x, y][:3] for x in xs for y in ys]


def _corner_padding_samples(
    px, corner: str, w: int, h: int, ext: int, reach: int
) -> list[tuple[int, int, int]]:
    """Extension padding adjacent to a corner — never on-card."""
    if corner == "TL":
        top = [px[x, y][:3] for x in range(ext, ext + reach) for y in range(0, ext)]
        left = [px[x, y][:3] for x in range(0, ext) for y in range(ext, ext + reach)]
        return top + left
    if corner == "TR":
        top = [
            px[x, y][:3]
            for x in range(w - ext - reach, w - ext)
            for y in range(0, ext)
        ]
        right = [
            px[x, y][:3]
            for x in range(w - ext, w)
            for y in range(ext, ext + reach)
        ]
        return top + right
    if corner == "BL":
        bottom = [
            px[x, y][:3]
            for x in range(ext, ext + reach)
            for y in range(h - ext, h)
        ]
        left = [
            px[x, y][:3]
            for x in range(0, ext)
            for y in range(h - ext - reach, h - ext)
        ]
        return bottom + left
    bottom = [
        px[x, y][:3]
        for x in range(w - ext - reach, w - ext)
        for y in range(h - ext, h)
    ]
    right = [
        px[x, y][:3]
        for x in range(w - ext, w)
        for y in range(h - ext - reach, h - ext)
    ]
    return bottom + right


def _detect_full_bleed_corners(
    px, w: int, h: int, ext: int, *, band: int
) -> frozenset[str]:
    """
    Corners where card art reaches the frame edge (borderless / full-bleed).

    When detected, corner fixes must stay in outer padding only — never flood
    squares into the card interior.
    """
    del band
    reach = max(5, min(ext, _corner_apex_reach(ext)))
    full_bleed: set[str] = set()
    for corner in _CORNERS:
        inner = _corner_inner_samples(px, corner, w, h, ext, reach)
        padding = _corner_padding_samples(px, corner, w, h, ext, reach)
        if not inner or not padding:
            continue
        pad_med = _median_rgb(padding)
        inner_med = _median_rgb(inner)
        inner_spread = max(_color_spread(s) for s in inner)
        color_delta = _color_distance(inner_med, pad_med)
        if inner_spread >= 35 and color_delta >= 60:
            full_bleed.add(corner)
            continue
        if color_delta >= 120 and (
            not _is_neutral_grey(inner_med, spread=15) or inner_spread >= 25
        ):
            full_bleed.add(corner)
            continue
        if corner in ("BL", "BR") and _brightness(pad_med) < 55:
            non_neutral = sum(
                1 for s in inner if not _is_neutral_grey(s, spread=12)
            )
            if non_neutral >= max(2, len(inner) // 3) and inner_spread >= 20:
                full_bleed.add(corner)
    return frozenset(full_bleed)


def _resolve_full_bleed_corners(
    px,
    w: int,
    h: int,
    ext: int,
    band: int,
    full_bleed_corners: frozenset[str] | None,
) -> frozenset[str]:
    if full_bleed_corners is not None:
        return full_bleed_corners
    return _detect_full_bleed_corners(px, w, h, ext, band=band)


def _substantial_full_bleed(full_bleed_corners: frozenset[str]) -> bool:
    """True when most corners are borderless — skip band smear / speckle flatten."""
    return len(full_bleed_corners) >= 3


def _apex_corner_at(x: int, y: int, w: int, h: int, margin: int) -> str | None:
    left = x < margin
    right = x >= w - margin
    top = y < margin
    bot = y >= h - margin
    if top and left:
        return "TL"
    if top and right:
        return "TR"
    if bot and left:
        return "BL"
    if bot and right:
        return "BR"
    return None


def _center_span(w: int) -> tuple[int, int]:
    """Middle ~5/6 of width (preserve colored frame lines extending from top)."""
    return w // 12, (11 * w) // 12


def _bottom_frame_text_y0(h: int, ext: int) -> int:
    """Top row where bottom-left/right footer text may sit above the credit band."""
    return h - ext - max(52, ext + 24)


def _in_footer_text_zone(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Credits/set line band just above the bottom extension row."""
    y0 = h - ext - max(18, ext + 4)
    if y < y0 or y >= h - ext:
        return False
    x_lo, x_hi = _footer_text_x_span(w)
    return x_lo <= x < x_hi


def _footer_text_x_span(w: int) -> tuple[int, int]:
    """Horizontal span of collector/credit text (middle ~76% of width)."""
    return int(w * 0.12), int(w * 0.88)


def _in_br_pt_zone(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Power/toughness bubble and right-side collector text on the bottom frame."""
    y0 = _bottom_frame_text_y0(h, ext)
    if y < y0 or y >= h - ext:
        return False
    return x >= _footer_text_x_span(w)[1]


def _in_bl_footer_zone(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Collector number, set code, and artist credit on the bottom-left frame."""
    y0 = _bottom_frame_text_y0(h, ext)
    if y < y0 or y >= h - ext:
        return False
    return x < _footer_text_x_span(w)[0]


def _protected_bottom_text_zone(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Footer credits, bottom-left collector text, and bottom-right P/T."""
    return (
        _in_footer_text_zone(x, y, w, h, ext)
        or _in_bl_footer_zone(x, y, w, h, ext)
        or _in_br_pt_zone(x, y, w, h, ext)
    )


def _footer_blocks_corner_paint(
    x: int, y: int, w: int, h: int, ext: int, band: int
) -> bool:
    """True when bottom text/P/T should block corner artifact cleanup."""
    del band  # kept for call-site consistency
    return _protected_bottom_text_zone(x, y, w, h, ext)


def _bl_bottom_gutter_x1(w: int, ext: int, reach: int) -> int:
    """Right edge (exclusive) of BL bottom gutter fixes — never into credit text."""
    return min(ext + reach, _footer_text_x_span(w)[0])


def _br_bottom_gutter_x0(w: int, ext: int, reach: int) -> int:
    """Left edge (inclusive) of BR bottom gutter fixes — never into credit text."""
    return max(w - ext - reach, _footer_text_x_span(w)[1])


def _in_margin_speck_zone(
    x: int, y: int, w: int, h: int, ext: int, band: int
) -> bool:
    """
    Where margin speck/remnant fixes may paint.

    Extension padding, top corner gutters, and bottom side gutters only —
    never the interior side strips where rules text / frame art sit.
    """
    if _in_extension(x, y, w, h, ext):
        return True
    if _in_bl_footer_zone(x, y, w, h, ext) or _in_br_pt_zone(x, y, w, h, ext):
        return False
    margin = ext * 2 + band
    if y < margin and (x < margin or x >= w - margin):
        return True
    credit_top = h - ext - max(40, ext + 20)
    if y >= credit_top:
        if ext <= x < _bl_bottom_gutter_x1(w, ext, margin):
            return True
        if _br_bottom_gutter_x0(w, ext, margin) <= x < w - ext:
            return True
    return False


def _on_inner_card_border(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Coloured frame row/column at the junction between padding and card."""
    if y == ext and ext <= x < w - ext:
        return True
    if y == h - ext - 1 and ext <= x < w - ext:
        return True
    if x == ext and ext <= y < h - ext:
        return True
    if x == w - ext - 1 and ext <= y < h - ext:
        return True
    return False


def _on_card_frame_border_ring(x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Full inner frame rectangle — padding corners included."""
    return (
        y == ext
        or y == h - ext - 1
        or x == ext
        or x == w - ext - 1
    )


def _corner_band_pixels(
    corner: str, w: int, h: int, ext: int
) -> list[tuple[int, int]]:
    """Extension pixels in the corner margin bands (where registration lines sit)."""
    reach = ext * 3
    out: list[tuple[int, int]] = []

    def add(x0: int, x1: int, y0: int, y1: int) -> None:
        for y in range(max(0, y0), min(h, y1)):
            for x in range(max(0, x0), min(w, x1)):
                if _in_extension(x, y, w, h, ext):
                    out.append((x, y))

    if corner == "TL":
        add(0, reach, 0, ext + _corner_apex_reach(ext))
        add(0, ext + _corner_apex_reach(ext), 0, reach)
    elif corner == "TR":
        add(w - reach, w, 0, ext + _corner_apex_reach(ext))
        add(w - ext - _corner_apex_reach(ext), w, 0, reach)
    elif corner == "BL":
        add(0, reach, h - ext - _corner_apex_reach(ext), h)
        add(0, ext + _corner_apex_reach(ext), h - reach, h)
    else:  # BR
        add(w - reach, w, h - ext - _corner_apex_reach(ext), h)
        add(w - ext - _corner_apex_reach(ext), w, h - reach, h)
    return list(dict.fromkeys(out))


def fix_corner_registration_lines(
    img: Image.Image,
    ext: int,
    band: int,
    *,
    fade_bottom_card: bool | None = None,
) -> tuple[Image.Image, int]:
    """
    Remove thin vertical/horizontal registration lines in uniform corner padding.

    Targets faint crop/registration streaks left in extension bands (grey or black
    padding) without touching card frame content.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    band = _border_band(w, h)
    margin = ext * 2 + band
    changed = 0
    fade_bottom = _resolve_fade_bottom_card(px, w, h, ext, band, fade_bottom_card)
    for corner in _CORNERS:
        if fade_bottom and corner in ("BL", "BR"):
            continue
        style = _corner_pad_style(px, corner, w, h, ext)
        ref = style.ref
        fill = style.fill
        delta = 10 if style.light else 30
        pixels = _corner_band_pixels(corner, w, h, ext)
        if not pixels:
            continue
        pixel_set = set(pixels)

        def off_color(x: int, y: int) -> bool:
            return abs(_brightness(px[x, y]) - ref) > delta

        xs = sorted({x for x, _ in pixels})
        for x in xs:
            if x == ext or x == w - ext - 1:
                continue
            col = [(x, y) for x2, y in pixels if x2 == x and off_color(x, y)]
            if len(col) < 5:
                continue
            ys = [y for _, y in col]
            ylo, yhi = min(ys), max(ys)
            if yhi - ylo + 1 > len(col) + 4:
                continue
            thick = sum(
                1
                for tx in range(x - 2, x + 3)
                if any(
                    (tx, y) in pixel_set and off_color(tx, y)
                    for y in range(ylo, yhi + 1)
                )
            )
            if thick > 4:
                continue
            for x0, y0 in col:
                if _on_inner_card_border(x0, y0, w, h, ext):
                    continue
                p = px[x0, y0][:3]
                if not _is_neutral_grey(p) and _brightness(p) > 30:
                    continue
                if _protected_bottom_text_zone(x0, y0, w, h, ext):
                    continue
                if px[x0, y0][:3] != fill:
                    px[x0, y0] = fill
                    changed += 1

            # Thin vertical lines often bleed one row onto the frame seam (y=ext).
            if corner in ("TL", "TR") and yhi >= ext - 1:
                for ax in range(x - 2, x + 3):
                    if ax < 0 or ax >= w or ax == ext or ax == w - ext - 1:
                        continue
                    ay = ext
                    if not off_color(ax, ay):
                        continue
                    p = px[ax, ay][:3]
                    if not _is_neutral_grey(p) or _brightness(p) < 80:
                        continue
                    if _protected_bottom_text_zone(ax, ay, w, h, ext):
                        continue
                    if px[ax, ay][:3] != fill:
                        px[ax, ay] = fill
                        changed += 1

        if corner in ("TL", "TR"):
            reach = ext * 3
            x_start = 0 if corner == "TL" else w - reach
            x_end = reach if corner == "TL" else w
            for ax in range(x_start, x_end):
                if ax == ext or ax == w - ext - 1:
                    continue
                ay = ext
                if not off_color(ax, ay):
                    continue
                p = px[ax, ay][:3]
                if not _is_neutral_grey(p) or _brightness(p) < 80:
                    continue
                if _protected_bottom_text_zone(ax, ay, w, h, ext):
                    continue
                if px[ax, ay][:3] != fill:
                    px[ax, ay] = fill
                    changed += 1

        ys = sorted({y for _, y in pixels})
        for y in ys:
            if y == ext or y == h - ext - 1:
                continue
            row = [(x, y) for x, y2 in pixels if y2 == y and off_color(x, y)]
            if len(row) < 5:
                continue
            xs_r = [x for x, _ in row]
            xlo, xhi = min(xs_r), max(xs_r)
            if xhi - xlo + 1 > len(row) + 4:
                continue
            thick = sum(
                1
                for ty in range(y - 2, y + 3)
                if any(
                    (x, ty) in pixel_set and off_color(x, ty)
                    for x in range(xlo, xhi + 1)
                )
            )
            if thick > 4:
                continue
            for x0, y0 in row:
                if _on_inner_card_border(x0, y0, w, h, ext):
                    continue
                p = px[x0, y0][:3]
                if not _is_neutral_grey(p) and _brightness(p) > 30:
                    continue
                if _protected_bottom_text_zone(x0, y0, w, h, ext):
                    continue
                if px[x0, y0][:3] != fill:
                    px[x0, y0] = fill
                    changed += 1

    return out, changed


def guard_no_text_whitening(
    before: Image.Image,
    working: Image.Image,
    ext: int,
    *,
    brighten_tol: int = 25,
) -> int:
    """
    Hard safety net: this script must NEVER whiten text.

    Any pixel in the bottom credit/footer band that a fix step made brighter than
    the source is reverted to the original. Fixes in this band only ever darken
    (blacken padding/corner wedges), so reverting brightening can only undo
    accidental damage to collector/set/artist/copyright text.
    """
    w, h = working.size
    bpx = before.load()
    apx = working.load()
    if bpx is None or apx is None:
        return 0
    y0 = h - ext - max(40, ext + 20)
    reverted = 0
    for y in range(y0, h):
        for x in range(w):
            b = bpx[x, y][:3]
            a = apx[x, y][:3]
            if a == b:
                continue
            if _brightness(a) - _brightness(b) > brighten_tol:
                apx[x, y] = b
                reverted += 1
    return reverted


def guard_no_content_blackening(
    before: Image.Image,
    working: Image.Image,
    ext: int,
    *,
    band: int,
    content_bright: int = 150,
    dark_after: int = 55,
    full_bleed_corners: frozenset[str] | None = None,
) -> int:
    """
    Safety net: never blacken bright card content (text boxes, P/T bubbles,
    light frames, white footer glyphs).

    Reverts any pixel inside the card region (outside the conversion extension)
    that was clearly bright in the source but got painted near-black by a fix
    step. Corner apex squares on bordered cards are exempt so legitimate
    white L-mark removal at the padding junction is preserved; full-bleed
    corners are never exempt.
    """
    w, h = working.size
    bpx = before.load()
    apx = working.load()
    if bpx is None or apx is None:
        return 0
    apex = ext + max(band, _corner_apex_reach(ext))
    if full_bleed_corners is None and bpx is not None:
        full_bleed_corners = _detect_full_bleed_corners(bpx, w, h, ext, band=band)
    elif full_bleed_corners is None:
        full_bleed_corners = frozenset()

    def _in_corner_apex_zone(x: int, y: int) -> bool:
        corner = _apex_corner_at(x, y, w, h, apex)
        if corner is None or corner in full_bleed_corners:
            return False
        return (x < apex or x >= w - apex) and (y < apex or y >= h - apex)

    def _in_fixable_outer_margin(x: int, y: int) -> bool:
        """Side/top outer margins where margin/speck fixes may repaint."""
        if _in_bl_footer_zone(x, y, w, h, ext) or _in_br_pt_zone(x, y, w, h, ext):
            return False
        return _in_margin_speck_zone(x, y, w, h, ext, band)

    reverted = 0
    for y in range(h):
        for x in range(w):
            if _in_extension(x, y, w, h, ext):
                continue
            if _in_corner_apex_zone(x, y):
                continue
            if _in_fixable_outer_margin(x, y):
                continue
            b = bpx[x, y][:3]
            a = apx[x, y][:3]
            if a == b:
                continue
            if _brightness(b) >= content_bright and _brightness(a) < dark_after:
                apx[x, y] = b
                reverted += 1
    return reverted


def guard_no_corner_lightening(
    before: Image.Image,
    working: Image.Image,
    ext: int,
    *,
    band: int,
    dark_before: int = 95,
    lighten_delta: int = 40,
) -> int:
    """
    Revert corner-fix steps that repainted dark title/glyph pixels with frame
    border colour on light cards.
    """
    w, h = working.size
    bpx = before.load()
    apx = working.load()
    if bpx is None or apx is None:
        return 0
    margin = ext * 2 + band
    title_y1 = min(h - ext, ext + 44)
    reverted = 0
    for y in range(ext, title_y1):
        for x in range(margin, w - margin):
            if _in_extension(x, y, w, h, ext):
                continue
            b = bpx[x, y][:3]
            a = apx[x, y][:3]
            if a == b:
                continue
            if _brightness(b) >= dark_before:
                continue
            if _brightness(a) - _brightness(b) < lighten_delta:
                continue
            apx[x, y] = b
            reverted += 1
    return reverted


def _seed_corner_arms(
    name: str,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    w: int,
    h: int,
    *,
    ring: int,
    arm: int,
    add_seed,
) -> None:
    """Seed only the L-shaped arms at the image corner, not the full box edge span."""
    if name == "TL":
        for x in range(x0, min(x0 + arm, x1)):
            for y in range(y0, min(y0 + ring, y1)):
                add_seed(x, y)
        for y in range(y0, min(y0 + arm, y1)):
            for x in range(x0, min(x0 + ring, x1)):
                add_seed(x, y)
    elif name == "TR":
        for x in range(max(x1 - arm, x0), x1):
            for y in range(y0, min(y0 + ring, y1)):
                add_seed(x, y)
        for y in range(y0, min(y0 + arm, y1)):
            for x in range(max(x1 - ring, x0), x1):
                add_seed(x, y)
    elif name == "BL":
        for x in range(x0, min(x0 + arm, x1)):
            for y in range(max(y1 - ring, y0), y1):
                add_seed(x, y)
        for y in range(max(y1 - arm, y0), y1):
            for x in range(x0, min(x0 + ring, x1)):
                add_seed(x, y)
    else:  # BR
        for x in range(max(x1 - arm, x0), x1):
            for y in range(max(y1 - ring, y0), y1):
                add_seed(x, y)
        for y in range(max(y1 - arm, y0), y1):
            for x in range(max(x1 - ring, x0), x1):
                add_seed(x, y)


def fix_corner_notches(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    only_corners: frozenset[str] | None = None,
    full_bleed_corners: frozenset[str] | None = None,
    tol: int = 70,
    max_fill_frac: float = 0.35,
    min_bright_above_bg: int = 18,
    size_extra: int = 0,
    ring_extra: int = 0,
) -> tuple[Image.Image, int]:
    """
    Remove bright L-shaped crop marks at image corners.

    Padding bg from the exterior edge strip only; seeds on short L-arms.

    Dark borders: flood bright marks (white L registration lines).
    Light top borders: flood darker neutral-grey wedges to match that strip.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    size = min(ext * 3, max(band * 2, ext * 2)) + size_extra
    ring = max(3, min(w, h) // 50) + ring_extra
    arm = ring * 4
    box_area = size * size
    repainted = 0
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)

    for name in _CORNERS:
        if only_corners is not None and name not in only_corners:
            continue
        x0, y0, x1, y1 = _corner_box(name, w, h, size)

        local_bg = _corner_padding_bg(px, x0, y0, x1, y1, w, h, name, strip=ring, arm=arm)
        local_bright = _brightness(local_bg)
        # Light-grey top padding: recolor darker neutral wedges only (not bottom corners).
        light_top = name in ("TL", "TR") and local_bright >= 100
        dark_bottom = name in ("BL", "BR") and local_bright < 55
        dark_padding = local_bright < 55
        light_padding = local_bright >= 100
        allow_apex = (dark_padding or light_padding) and name not in bleed
        if local_bright >= 240:
            fill_bg = _inner_corner_fill(px, name, w, h, ext)
        else:
            fill_bg = (0, 0, 0) if (dark_padding and not light_top) else local_bg
        mismatch_tol = 25 if light_top else tol

        def is_candidate(x: int, y: int) -> bool:
            p = px[x, y]
            ref = local_bg
            ref_bright = local_bright
            if local_bright >= 240 and _brightness(p) >= 235 and _is_neutral_grey(p):
                return _brightness(p) > _brightness(fill_bg) + 12
            if _color_distance(p, ref) <= mismatch_tol:
                return False
            if not _in_extension(x, y, w, h, ext):
                # Into-card apex/arm flooding: only lift clearly-bright white
                # registration tips. Never blacken footer text or mid-tone card
                # border/art (e.g. dark-green frame, grey credit glyphs).
                if name in bleed:
                    return False
                if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                    return False
                return _brightness(p) >= 150
            if light_top:
                # Grey registration wedges and bright white L-marks on light padding.
                if _is_neutral_grey(p) and _brightness(p) <= ref_bright - min_bright_above_bg:
                    return True
                return _brightness(p) >= ref_bright + min_bright_above_bg
            return _brightness(p) >= ref_bright + min_bright_above_bg

        seeds: deque[tuple[int, int]] = deque()
        seen: set[tuple[int, int]] = set()

        def add_seed(x: int, y: int) -> None:
            if not _in_corner_fix_zone(x, y, w, h, ext, band, allow_apex=allow_apex):
                return
            if (x, y) not in seen and is_candidate(x, y):
                seen.add((x, y))
                seeds.append((x, y))

        _seed_corner_arms(name, x0, y0, x1, y1, w, h, ring=ring, arm=arm, add_seed=add_seed)
        if light_top and not seeds:
            edge_y = y0
            for x in range(x0, x1):
                add_seed(x, edge_y)
        if light_top:
            reach = _corner_apex_reach(ext)
            if name == "TL":
                for y in range(ext, min(y1, ext + reach)):
                    for x in range(ext, min(x1, ext + reach)):
                        add_seed(x, y)
            elif name == "TR":
                for y in range(ext, min(y1, ext + reach)):
                    for x in range(max(x0, w - ext - reach), w - ext):
                        add_seed(x, y)
        if light_padding and name in ("BL", "BR"):
            reach = _corner_apex_reach(ext)
            arm_reach = _bottom_gutter_arm_reach(ext)
            arm_width = _bottom_gutter_arm_width(ext, band)
            if name == "BL":
                for y in range(max(y0, h - ext - reach), h - ext):
                    for x in range(ext, min(x1, ext + reach)):
                        add_seed(x, y)
                for y in range(h - ext - arm_reach, h - ext):
                    for x in range(ext, _bl_bottom_gutter_x1(w, ext, arm_width)):
                        add_seed(x, y)
            else:
                for y in range(max(y0, h - ext - reach), h - ext):
                    for x in range(max(x0, w - ext - reach), w - ext):
                        add_seed(x, y)
                for y in range(h - ext - arm_reach, h - ext):
                    for x in range(_br_bottom_gutter_x0(w, ext, arm_width), w - ext):
                        add_seed(x, y)
        if dark_bottom and not seeds:
            # Bottom corners on black padding: seed bright border pixels explicitly.
            if name == "BL":
                for x in range(x0, min(x0 + arm, x1)):
                    add_seed(x, h - 1)
                for y in range(max(y1 - arm, y0), y1):
                    add_seed(0, y)
            else:
                for x in range(max(x1 - arm, x0), x1):
                    add_seed(x, h - 1)
                for y in range(max(y1 - arm, y0), y1):
                    add_seed(w - 1, y)
        if dark_padding:
            # L-mark tips sit one pixel past the ext line at each corner.
            reach = _corner_apex_reach(ext)
            if name == "TL":
                for y in range(ext, min(y1, ext + reach)):
                    for x in range(ext, min(x1, ext + reach)):
                        add_seed(x, y)
            elif name == "TR":
                for y in range(ext, min(y1, ext + reach)):
                    for x in range(max(x0, w - ext - reach), w - ext):
                        add_seed(x, y)
            elif name == "BL":
                for y in range(max(y0, h - ext - reach), h - ext):
                    for x in range(ext, min(x1, ext + reach)):
                        add_seed(x, y)
                arm_reach = _bottom_gutter_arm_reach(ext)
                arm_width = _bottom_gutter_arm_width(ext, band)
                for y in range(h - ext - arm_reach, h - ext):
                    for x in range(ext, _bl_bottom_gutter_x1(w, ext, arm_width)):
                        add_seed(x, y)
            else:
                for y in range(max(y0, h - ext - reach), h - ext):
                    for x in range(max(x0, w - ext - reach), w - ext):
                        add_seed(x, y)
                arm_reach = _bottom_gutter_arm_reach(ext)
                arm_width = _bottom_gutter_arm_width(ext, band)
                for y in range(h - ext - arm_reach, h - ext):
                    for x in range(_br_bottom_gutter_x0(w, ext, arm_width), w - ext):
                        add_seed(x, y)

        collected: list[tuple[int, int]] = []
        while seeds:
            x, y = seeds.popleft()
            collected.append((x, y))
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                in_box = x0 <= nx < x1 and y0 <= ny < y1
                in_arm = allow_apex and (
                    _in_corner_apex(nx, ny, w, h, ext)
                    or _in_bottom_gutter_arm(nx, ny, w, h, ext, band)
                )
                if (
                    (in_box or in_arm)
                    and (nx, ny) not in seen
                    and _in_corner_fix_zone(
                        nx, ny, w, h, ext, band, allow_apex=allow_apex
                    )
                ):
                    if is_candidate(nx, ny):
                        seen.add((nx, ny))
                        seeds.append((nx, ny))

        if not collected or len(collected) > box_area * max_fill_frac:
            continue

        for x, y in collected:
            if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                continue
            if _in_corner_fix_zone(x, y, w, h, ext, band, allow_apex=allow_apex):
                px[x, y] = fill_bg
                repainted += 1

    return out, repainted


def _resolve_fade_bottom_card(
    px,
    w: int,
    h: int,
    ext: int,
    band: int,
    fade_bottom_card: bool | None,
) -> bool:
    """Use a pipeline snapshot when provided — padding edits can flip live detection."""
    if fade_bottom_card is not None:
        return fade_bottom_card
    return _fade_bottom_corner_card(px, w, h, ext, band)


def fix_corner_junction_marks(
    img: Image.Image,
    ext: int,
    *,
    fade_bottom_card: bool | None = None,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """
    Remove bright registration L-tips on the padding/card seam at each corner.

    ``_in_extension`` excludes x=ext / y=ext, so corner marks that straddle the
    junction survive vision and flood-fill steps unless handled explicitly.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    changed = 0
    band = _border_band(w, h)
    fade_bottom = _resolve_fade_bottom_card(px, w, h, ext, band, fade_bottom_card)
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)
    for corner in _CORNERS:
        if fade_bottom and corner in ("BL", "BR"):
            continue
        fill = _corner_fixup_fill(px, corner, w, h, ext)
        style = _corner_pad_style(px, corner, w, h, ext)
        reach = _corner_apex_reach(ext)
        if corner == "TL":
            x0, x1 = ext, ext + reach
            y0, y1 = ext, ext + reach
        elif corner == "TR":
            x0, x1 = w - ext - reach, w - ext
            y0, y1 = ext, ext + reach
        elif corner == "BL":
            x0, x1 = ext, ext + reach
            y0, y1 = h - ext - reach, h - ext
        else:
            x0, x1 = w - ext - reach, w - ext
            y0, y1 = h - ext - reach, h - ext
        for y in range(y0, y1):
            for x in range(x0, x1):
                if corner in bleed and not _in_extension(x, y, w, h, ext):
                    continue
                if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                    continue
                p = px[x, y][:3]
                artifact = _vision_artifact_pixel(p, fill, style=style)
                if not artifact and _brightness(p) >= 235 and _is_neutral_grey(p):
                    artifact = _brightness(p) > _brightness(fill) + 12
                if not artifact:
                    continue
                if p != fill:
                    px[x, y] = fill
                    changed += 1
    return out, changed


def fix_corner_bright_lmarks(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    fade_bottom_card: bool | None = None,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """Paint near-white neutral L-mark arms in corner zones to inner frame colour."""
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    size = min(ext * 3, max(band * 2, ext * 2))
    changed = 0
    fade_bottom = _resolve_fade_bottom_card(px, w, h, ext, band, fade_bottom_card)
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)
    for corner in _CORNERS:
        if fade_bottom and corner in ("BL", "BR"):
            continue
        allow_apex = corner not in bleed
        fill = _corner_fixup_fill(px, corner, w, h, ext)
        fill_bright = _brightness(fill)
        x0, y0, x1, y1 = _corner_box(corner, w, h, size)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_corner_fix_zone(
                    x, y, w, h, ext, band, allow_apex=allow_apex
                ):
                    continue
                if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                    continue
                p = px[x, y][:3]
                if _brightness(p) < 235 or not _is_neutral_grey(p):
                    continue
                if _brightness(p) <= fill_bright + 12:
                    continue
                if p != fill:
                    px[x, y] = fill
                    changed += 1
    return out, changed


def _corner_l_arm_segments(
    corner: str, w: int, h: int, ext: int
) -> list[tuple[str, int, int, int]]:
    """Horizontal/vertical L-arm segments on the frame seam in corner gutters only."""
    reach = ext + _corner_apex_reach(ext) + 2
    if corner == "TL":
        return [
            ("h", ext, ext, ext + reach),
            ("v", ext, ext, ext + reach),
            ("h", 0, 0, reach),
            ("v", 0, 0, reach),
        ]
    if corner == "TR":
        return [
            ("h", ext, w - ext - reach, w - ext),
            ("v", w - ext - 1, ext, ext + reach),
            ("h", 0, w - reach, w),
            ("v", w - 1, 0, reach),
        ]
    if corner == "BL":
        segs = [
            ("h", h - ext - 1, ext, ext + reach),
            ("v", ext, h - ext - reach, h - ext),
            ("h", h - ext, 0, reach),
            ("v", 0, h - ext - reach, h),
        ]
        for y in range(h - ext - reach, h - ext):
            segs.append(("h", y, 0, ext))
        return segs
    segs = [
        ("h", h - ext - 1, w - ext - reach, w - ext),
        ("v", w - ext - 1, h - ext - reach, h - ext),
        ("h", h - ext, w - reach, w),
        ("v", w - 1, h - ext - reach, h),
    ]
    for y in range(h - ext - reach, h - ext):
        segs.append(("h", y, w - ext, w))
    return segs


def _corner_l_apex_box(
    corner: str, w: int, h: int, ext: int
) -> tuple[int, int, int, int]:
    """Small square where inner and outer L arms meet at the image corner."""
    size = ext + _corner_apex_reach(ext) + 4
    return _corner_box(corner, w, h, size)


def _is_corner_l_arm_artifact(
    p: tuple[int, int, int],
    *,
    fill: tuple[int, int, int],
    style: _CornerPadStyle,
    inner: tuple[int, int, int],
    border: tuple[int, int, int] | None,
    tol: int = 28,
) -> bool:
    """Registration L-arm pixel on a frame seam in a corner gutter."""
    if _color_distance(p, fill) <= tol:
        return False
    br = _brightness(p)
    if style.light and br < 85:
        return False
    if _is_neutral_grey(p):
        if style.dark and br >= max(style.ref + 15, 55):
            return True
        if style.light and br >= style.ref + 18:
            return True
        if style.light and br <= style.ref - 18 and br >= 50:
            return True
    if style.dark:
        if br > style.ref + 20 and _color_distance(p, inner) > tol:
            return True
        if border and _color_distance(p, border) <= 22:
            return True
    if style.light and _color_distance(p, inner) > tol + 10:
        if border is None or _color_distance(p, border) > tol:
            return True
    return False


def _in_corner_l_apex_zone(
    corner: str, x: int, y: int, w: int, h: int, ext: int
) -> bool:
    """Padding-only apex where outer L arms meet — not inner card title area."""
    reach = ext + _corner_apex_reach(ext) + 2
    if corner == "TL":
        if x >= ext and y >= ext:
            return False
        return x < reach and y < reach
    if corner == "TR":
        if x < w - ext and y >= ext:
            return False
        return x >= w - reach and y < reach
    if corner == "BL":
        if x >= ext and y < h - ext:
            return False
        return x < reach and y >= h - reach
    if x < w - ext and y < h - ext:
        return False
    return x >= w - reach and y >= h - reach


def _corner_gutter_reach(ext: int) -> int:
    return ext + _corner_apex_reach(ext) + 2


def _on_corner_gutter_seam(
    corner: str, x: int, y: int, w: int, h: int, ext: int
) -> bool:
    """Frame seam or outer-padding L-arm in a corner gutter (not the centre title bar)."""
    reach = _corner_gutter_reach(ext)
    if corner == "TL":
        if y == ext and x < reach:
            return True
        if x == ext and y < reach:
            return True
        if y < ext and x < reach:
            return True
        return x < ext and y < reach
    if corner == "TR":
        if y == ext and x >= w - reach:
            return True
        if x == w - ext - 1 and y < reach:
            return True
        if y < ext and x >= w - reach:
            return True
        return x >= w - ext and y < reach
    if corner == "BL":
        if y == h - ext - 1 and ext <= x < _bl_bottom_gutter_x1(w, ext, reach):
            return True
        if x == ext and y >= h - reach:
            return True
        if y >= h - ext and x < reach:
            return True
        if x < ext and y >= h - reach:
            return True
        if x == ext and h - ext - reach <= y < h - ext:
            return True
        return x < ext and h - ext - reach <= y < h - ext
    if y == h - ext - 1 and _br_bottom_gutter_x0(w, ext, reach) <= x < w - ext:
        return True
    if x == w - ext - 1 and y >= h - reach:
        return True
    if y >= h - ext and x >= w - reach:
        return True
    if x >= w - ext and y >= h - reach:
        return True
    if x == w - ext - 1 and h - ext - reach <= y < h - ext:
        return True
    return x >= w - ext and h - ext - reach <= y < h - ext


def _in_corner_l_paint_zone(
    corner: str, x: int, y: int, w: int, h: int, ext: int
) -> bool:
    """Pixels safe to recolour for L-arm cleanup — corner gutter L only."""
    if _in_corner_l_apex_zone(corner, x, y, w, h, ext):
        return True
    return _on_corner_gutter_seam(corner, x, y, w, h, ext)


def _l_arm_skip_border_preserve(
    corner: str,
    x: int,
    y: int,
    w: int,
    h: int,
    ext: int,
    p: tuple[int, int, int],
    border: tuple[int, int, int] | None,
) -> bool:
    """Keep intentional frame border on the centre title bar, not corner L-arms."""
    if not (_on_inner_card_border(x, y, w, h, ext) and border):
        return False
    if _color_distance(p, border) > 25:
        return False
    return not _on_corner_gutter_seam(corner, x, y, w, h, ext)


def fix_corner_l_arm_seams(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    tol: int = 28,
    fade_bottom_card: bool | None = None,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """
    Remove thin L-shaped arms left on the frame seam in corner gutters.

    Targets white/grey and coloured registration marks (e.g. teal frame bleed on
    black padding, cream wedges on coloured top corners) without touching the
    central title-bar frame rows.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    changed = 0
    fade_bottom = _resolve_fade_bottom_card(px, w, h, ext, band, fade_bottom_card)
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)
    for corner in _CORNERS:
        if fade_bottom and corner in ("BL", "BR"):
            continue
        fill = _corner_fixup_fill(px, corner, w, h, ext)
        style = _corner_pad_style(px, corner, w, h, ext)
        inner = _inner_corner_fill(px, corner, w, h, ext)
        border = _sample_corner_border_color(px, corner, w, h, ext)
        for axis, fixed, start, end in _corner_l_arm_segments(corner, w, h, ext):
            if axis == "h":
                y = fixed
                for x in range(max(0, start), min(w, end)):
                    if corner in bleed and not _in_extension(x, y, w, h, ext):
                        continue
                    if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                        continue
                    if not _in_corner_l_paint_zone(corner, x, y, w, h, ext):
                        continue
                    p = px[x, y][:3]
                    if not _is_corner_l_arm_artifact(
                        p, fill=fill, style=style, inner=inner, border=border, tol=tol
                    ):
                        continue
                    if _l_arm_skip_border_preserve(
                        corner, x, y, w, h, ext, p, border
                    ):
                        continue
                    if p != fill:
                        px[x, y] = fill
                        changed += 1
            else:
                x = fixed
                for y in range(max(0, start), min(h, end)):
                    if corner in bleed and not _in_extension(x, y, w, h, ext):
                        continue
                    if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                        continue
                    if not _in_corner_l_paint_zone(corner, x, y, w, h, ext):
                        continue
                    p = px[x, y][:3]
                    if not _is_corner_l_arm_artifact(
                        p, fill=fill, style=style, inner=inner, border=border, tol=tol
                    ):
                        continue
                    if _l_arm_skip_border_preserve(
                        corner, x, y, w, h, ext, p, border
                    ):
                        continue
                    if p != fill:
                        px[x, y] = fill
                        changed += 1

        if corner in bleed:
            continue
        ax0, ay0, ax1, ay1 = _corner_l_apex_box(corner, w, h, ext)
        for y in range(ay0, ay1):
            for x in range(ax0, ax1):
                if not _in_corner_l_apex_zone(corner, x, y, w, h, ext):
                    continue
                if not _in_corner_l_paint_zone(corner, x, y, w, h, ext):
                    continue
                if _footer_blocks_corner_paint(x, y, w, h, ext, band):
                    continue
                p = px[x, y][:3]
                if not _is_corner_l_arm_artifact(
                    p, fill=fill, style=style, inner=inner, border=border, tol=tol
                ):
                    continue
                if _l_arm_skip_border_preserve(corner, x, y, w, h, ext, p, border):
                    continue
                if p != fill:
                    px[x, y] = fill
                    changed += 1
    return out, changed


def _run_corner_fixup_pass(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    corner_extra: int = 0,
    include_margin_cleanup: bool = True,
    fade_bottom_card: bool | None = None,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, list[tuple[str, int]]]:
    """One deterministic corner-cleanup sweep (notches, junction, bright L-marks, lines)."""
    working = img
    stats: list[tuple[str, int]] = []

    working, repainted = fix_corner_notches(
        working,
        band,
        ext,
        size_extra=corner_extra,
        ring_extra=corner_extra,
        full_bleed_corners=full_bleed_corners,
    )
    if repainted:
        stats.append(("cleared corner marks", repainted))

    working, junction_px = fix_corner_junction_marks(
        working,
        ext,
        fade_bottom_card=fade_bottom_card,
        full_bleed_corners=full_bleed_corners,
    )
    if junction_px:
        stats.append(("cleared corner junction marks", junction_px))

    working, bright_px = fix_corner_bright_lmarks(
        working,
        band,
        ext,
        fade_bottom_card=fade_bottom_card,
        full_bleed_corners=full_bleed_corners,
    )
    if bright_px:
        stats.append(("cleared bright corner L-marks", bright_px))

    working, reg_line_px = fix_corner_registration_lines(
        working, ext, band, fade_bottom_card=fade_bottom_card
    )
    if reg_line_px:
        stats.append(("cleared corner registration lines", reg_line_px))

    working, larm_px = fix_corner_l_arm_seams(
        working,
        band,
        ext,
        fade_bottom_card=fade_bottom_card,
        full_bleed_corners=full_bleed_corners,
    )
    if larm_px:
        stats.append(("cleared corner L-arm seams", larm_px))

    working, arc_uni_px, _ = fix_corner_arc_uniform(
        working, band, ext, full_bleed_corners=full_bleed_corners
    )
    if arc_uni_px:
        stats.append(("filled near-uniform corner arcs", arc_uni_px))

    if include_margin_cleanup:
        working, margin_speck_px = fix_margin_specks(working, ext)
        if margin_speck_px:
            stats.append(("removed margin specks", margin_speck_px))
        working, isolated_px = fix_isolated_margin_pixels(working, ext, band)
        working, isolated_px2 = fix_isolated_margin_pixels(working, ext, band)
        isolated_px += isolated_px2
        if isolated_px:
            stats.append(("removed isolated margin pixels", isolated_px))
        working, faint_px = fix_faint_corner_gutter_dust(
            working, ext, band, full_bleed_corners=full_bleed_corners
        )
        if faint_px:
            stats.append(("removed faint corner gutter dust", faint_px))

    return working, stats


# Border widths used by prepare_card_for_printing's size ladder.
_BORDER_LADDER = (16, 24, 32, 48, 64)


def _expected_border(orig_width: int) -> int:
    """Border width prepare_card_for_printing picks for a source image width."""
    if orig_width <= 320:
        return 16
    if orig_width <= 521:
        return 24
    if orig_width <= 1000:
        return 32
    if orig_width <= 1100:
        return 48
    return 64


def infer_added_border(w: int, h: int) -> int | None:
    """Added band width if this image plausibly came from the border-expand script."""
    del h
    for b in _BORDER_LADDER:
        orig = w - 2 * b
        if orig > 0 and _expected_border(orig) == b:
            return b
    return None


def _tiled_band_fraction(px, w: int, h: int, b: int, *, tol: int = 8) -> float:
    """Fraction of sampled band lines constant along the extension direction."""
    step = 7
    total = 0
    constant = 0

    def is_const(pixels: list[tuple[int, int, int]]) -> bool:
        p0 = pixels[0]
        return all(
            abs(p[0] - p0[0]) <= tol and abs(p[1] - p0[1]) <= tol and abs(p[2] - p0[2]) <= tol
            for p in pixels
        )

    for x in range(b, w - b, step):
        total += 2
        if is_const([px[x, y][:3] for y in range(0, b)]):
            constant += 1
        if is_const([px[x, y][:3] for y in range(h - b, h)]):
            constant += 1
    for y in range(b, h - b, step):
        total += 2
        if is_const([px[x, y][:3] for x in range(0, b)]):
            constant += 1
        if is_const([px[x, y][:3] for x in range(w - b, w)]):
            constant += 1
    return constant / total if total else 0.0


def _moving_median_line(line: list[tuple[int, int, int]], window: int) -> list[tuple[int, int, int]]:
    """Per-channel moving median; kills hairline spikes, keeps gradients."""
    n = len(line)
    half = window // 2
    out: list[tuple[int, int, int]] = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out.append(_median_rgb(line[lo:hi]))
    return out


def fix_tiled_band(
    img: Image.Image,
    *,
    min_constant_frac: float = 0.80,
) -> tuple[Image.Image, int, int | None]:
    """
    Rebuild the conversion script's added border band from a smoothed copy of
    the card's own edge rows/columns.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0, None

    b = infer_added_border(w, h)
    if b is None or w <= 2 * b + 10 or h <= 2 * b + 10:
        return out, 0, None
    if _tiled_band_fraction(px, w, h, b) < min_constant_frac:
        return out, 0, b

    window = max(9, min(w, h) // 24) | 1
    raw_top = [px[x, b][:3] for x in range(b, w - b)]
    raw_bottom = [px[x, h - b - 1][:3] for x in range(b, w - b)]
    top = _moving_median_line(raw_top, window)
    bottom = _moving_median_line(raw_bottom, window)
    cx0, cx1 = _center_span(w)
    for i, raw in enumerate(raw_top):
        x = b + i
        if not _is_neutral_dark(raw) and cx0 <= x < cx1:
            top[i] = raw
    left = _moving_median_line([px[b, y][:3] for y in range(b, h - b)], window)
    right = _moving_median_line([px[w - b - 1, y][:3] for y in range(b, h - b)], window)

    changed = 0

    def paint(x: int, y: int, color: tuple[int, int, int]) -> None:
        nonlocal changed
        if px[x, y][:3] != color:
            px[x, y] = color
            changed += 1

    def paint_band_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        """Only retile neutral/dark band pixels; never smear color into side gutters."""
        cur = px[x, y][:3]
        if not _is_neutral_dark(cur):
            return
        colored = not _is_neutral_dark(color)
        if colored and (x < cx0 or x >= cx1):
            return
        paint(x, y, color)

    for x in range(w):
        i = min(max(x - b, 0), len(top) - 1)
        for y in range(0, b):
            paint_band_pixel(x, y, top[i])
        for y in range(h - b, h):
            paint_band_pixel(x, y, bottom[i])
    for y in range(b, h - b):
        j = y - b
        for x in range(0, b):
            if _is_neutral_dark(px[x, y][:3]):
                paint(x, y, left[j])
        for x in range(w - b, w):
            if _is_neutral_dark(px[x, y][:3]):
                paint(x, y, right[j])

    return out, changed, b


def fix_inset_line_marks(
    img: Image.Image,
    *,
    gap: int = 6,
    mean_drop: int = 40,
    pixel_drop: int = 30,
) -> tuple[Image.Image, list[str], int]:
    """
    Remove thin crop/edge mark lines inside the card region (through textured
    borders). Repair is per-pixel inpainting from brighter cross-axis neighbors.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None or w < 120 or h < 120:
        return out, [], 0

    b = infer_added_border(w, h) or 0
    ext = b if b else 16

    def bright(p: tuple[int, ...]) -> int:
        return (p[0] + p[1] + p[2]) // 3

    x0, x1 = int(w * 0.25), int(w * 0.75)
    y0, y1 = int(h * 0.25), int(h * 0.75)

    def row_mean(y: int) -> float:
        vals = [bright(px[x, y]) for x in range(x0, x1, 2)]
        return sum(vals) / len(vals)

    def col_mean(x: int) -> float:
        vals = [bright(px[x, y]) for y in range(y0, y1, 2)]
        return sum(vals) / len(vals)

    def _is_uniform_dark_mark(horizontal: bool, pos: int) -> bool:
        rng = range(x0, x1) if horizontal else range(y0, y1)
        dark = [
            bright(px[t, pos] if horizontal else px[pos, t])
            for t in rng
            if bright(px[t, pos] if horizontal else px[pos, t]) < 80
        ]
        if len(dark) < 30:
            return False
        mean = sum(dark) / len(dark)
        var = sum((v - mean) ** 2 for v in dark) / len(dark)
        return mean <= 16 and var <= 100

    cx0, cx1 = _center_span(w)

    def row_has_colored_center(y: int) -> bool:
        return any(
            not _is_neutral_dark(px[x, y][:3])
            for x in range(cx0, cx1, 2)
        )

    ext_rows = [
        *range(gap, min(ext, h - gap)),
        *range(max(h - ext, gap), h - gap),
    ]
    ext_cols = [
        *range(gap, min(ext, w - gap)),
        *range(max(w - ext, gap), w - gap),
    ]
    line_rows = [
        y
        for y in ext_rows
        if row_mean(y) < min(row_mean(y - gap), row_mean(y + gap)) - mean_drop
        and _is_uniform_dark_mark(True, y)
        and not row_has_colored_center(y)
    ]
    line_cols = [
        x
        for x in ext_cols
        if col_mean(x) < min(col_mean(x - gap), col_mean(x + gap)) - mean_drop
        and _is_uniform_dark_mark(False, x)
    ]

    changed = 0
    for y in line_rows:
        for x in range(w):
            if not _in_extension(x, y, w, h, ext):
                continue
            if not _is_neutral_dark(px[x, y][:3]):
                continue
            up, dn = px[x, y - gap], px[x, y + gap]
            floor = min(bright(up), bright(dn))
            if bright(px[x, y]) < floor - pixel_drop:
                px[x, y] = (
                    (up[0] + dn[0]) // 2,
                    (up[1] + dn[1]) // 2,
                    (up[2] + dn[2]) // 2,
                )
                changed += 1
    for x in line_cols:
        for y in range(h):
            if not _in_extension(x, y, w, h, ext):
                continue
            if not _is_neutral_dark(px[x, y][:3]):
                continue
            lt, rt = px[x - gap, y], px[x + gap, y]
            floor = min(bright(lt), bright(rt))
            if bright(px[x, y]) < floor - pixel_drop:
                px[x, y] = (
                    (lt[0] + rt[0]) // 2,
                    (lt[1] + rt[1]) // 2,
                    (lt[2] + rt[2]) // 2,
                )
                changed += 1

    marks = [f"row {y}" for y in line_rows] + [f"col {x}" for x in line_cols]
    return out, marks, changed


def fix_dark_speckle(
    img: Image.Image,
    *,
    dark_thresh: int = 30,
    min_delta: int = 4,
) -> tuple[Image.Image, int]:
    """Flatten near-black noise in the outer border zone to one uniform dark color."""
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    ext = extension_width(w, h)

    def bright(p: tuple[int, ...]) -> int:
        return (p[0] + p[1] + p[2]) // 3

    dark: list[tuple[int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if not _in_extension(x, y, w, h, ext):
                continue
            p = px[x, y][:3]
            if bright(p) < dark_thresh:
                dark.append(p)
    if len(dark) < 500:
        return out, 0
    fill = _median_rgb(dark)

    changed = 0
    for y in range(h):
        for x in range(w):
            if not _in_extension(x, y, w, h, ext):
                continue
            p = px[x, y][:3]
            if bright(p) < dark_thresh and _color_distance(p, fill) > min_delta:
                px[x, y] = fill
                changed += 1
    return out, changed


def fix_margin_specks(
    img: Image.Image,
    ext: int,
    *,
    max_blob: int = 25,
    neighborhood_pad: int = 4,
    neighborhood_dark_frac: float = 0.78,
    speck_min_bright: int = 80,
    tiny_speck_min_bright: int = 40,
) -> tuple[Image.Image, int]:
    """
    Remove small isolated bright specks (stray crop/registration dust, broken
    trim lines) that sit on a near-black background in the outer edge margins.

    A speck qualifies only when it is small (<= ``max_blob`` px), reasonably
    bright, and its surrounding neighbourhood is overwhelmingly near-black — so
    real art, title/rules text, and bright frame elements (which sit on the
    coloured/textured frame, not pure black) are left untouched. The bottom
    credit/footer band is excluded entirely so collector text is never harmed.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    band = _border_band(w, h)
    margin = ext * 2 + band
    credit_top = h - ext - max(40, ext + 20)

    def br(x: int, y: int) -> int:
        return _brightness(px[x, y])

    def in_scan_region(x: int, y: int) -> bool:
        if _on_card_frame_border_ring(x, y, w, h, ext):
            return False
        if _in_footer_text_zone(x, y, w, h, ext):
            return False
        return _in_margin_speck_zone(x, y, w, h, ext, band)

    changed = 0
    seen: set[tuple[int, int]] = set()
    for y in range(h):
        for x in range(w):
            if (x, y) in seen or not in_scan_region(x, y):
                continue
            if br(x, y) < tiny_speck_min_bright:
                continue
            blob: list[tuple[int, int]] = []
            stack = deque([(x, y)])
            seen.add((x, y))
            too_big = False
            while stack:
                cx, cy = stack.popleft()
                blob.append((cx, cy))
                if len(blob) > max_blob:
                    too_big = True
                    break
                for nx, ny in (
                    (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1),
                    (cx - 1, cy - 1), (cx + 1, cy + 1), (cx - 1, cy + 1), (cx + 1, cy - 1),
                ):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                        if not in_scan_region(nx, ny):
                            continue
                        if br(nx, ny) >= speck_min_bright or (
                            len(blob) < max_blob
                            and br(nx, ny) >= tiny_speck_min_bright
                        ):
                            seen.add((nx, ny))
                            stack.append((nx, ny))
            if too_big or not blob:
                continue
            if not all(
                br(bx, by) >= speck_min_bright
                or (len(blob) <= max_blob and br(bx, by) >= tiny_speck_min_bright)
                for bx, by in blob
            ):
                continue
            xs = [p[0] for p in blob]
            ys = [p[1] for p in blob]
            blob_set = set(blob)
            dark = tot = 0
            dark_px: list[tuple[int, int, int]] = []
            for xx in range(min(xs) - neighborhood_pad, max(xs) + neighborhood_pad + 1):
                for yy in range(min(ys) - neighborhood_pad, max(ys) + neighborhood_pad + 1):
                    if (xx, yy) in blob_set or not (0 <= xx < w and 0 <= yy < h):
                        continue
                    tot += 1
                    if br(xx, yy) < 40:
                        dark += 1
                        dark_px.append(px[xx, yy][:3])
            if not tot or dark / tot < neighborhood_dark_frac:
                continue
            fill = _median_rgb(dark_px) if dark_px else (0, 0, 0)
            for bx, by in blob:
                if px[bx, by][:3] != fill:
                    px[bx, by] = fill
                    changed += 1
    return out, changed


def fix_isolated_margin_pixels(
    img: Image.Image,
    ext: int,
    band: int,
) -> tuple[Image.Image, int]:
    """Remove lone off-color pixels on side/bottom outer margins (not credit text)."""
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    margin = ext * 2 + band
    credit_top = h - ext - max(40, ext + 20)
    changed = 0

    def br(x: int, y: int) -> int:
        return _brightness(px[x, y])

    for y in range(h):
        for x in range(w):
            if not _in_margin_speck_zone(x, y, w, h, ext, band):
                continue
            if _on_card_frame_border_ring(x, y, w, h, ext):
                continue
            if _in_footer_text_zone(x, y, w, h, ext):
                continue
            if br(x, y) < 40:
                continue
            bright_nbr = sum(
                1
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if not (dx == dy == 0)
                and 0 <= x + dx < w
                and 0 <= y + dy < h
                and br(x + dx, y + dy) >= 35
            )
            if bright_nbr > 1:
                continue
            dark_px: list[tuple[int, int, int]] = []
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and br(nx, ny) < 40:
                        dark_px.append(px[nx, ny][:3])
            fill = _median_rgb(dark_px) if dark_px else (0, 0, 0)
            if px[x, y][:3] != fill:
                px[x, y] = fill
                changed += 1

    return out, changed


def fix_faint_corner_gutter_dust(
    img: Image.Image,
    ext: int,
    band: int,
    *,
    max_bright: int = 44,
    dark_neighbor_frac: float = 0.72,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """
    Blacken ultra-faint neutral-grey arc dust in top corner gutters on near-black
    padding (anti-alias remnants along the rounded card corner curve).
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    margin = ext * 2 + band
    changed = 0
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)

    def br(x: int, y: int) -> int:
        return _brightness(px[x, y])

    def in_top_gutter(x: int, y: int) -> bool:
        if y >= margin:
            return False
        return x < margin or x >= w - margin

    def on_top_gutter_frame_row(x: int, y: int) -> bool:
        """Top frame row only in side gutters — not across the title bar."""
        return y == ext and (x < margin or x >= w - margin)

    def on_side_gutter_frame_col(x: int, y: int) -> bool:
        """Side frame columns only in top gutters — not down the card body."""
        if y >= margin:
            return False
        return x == ext or x == w - ext - 1

    def _allows_card_seam_paint(x: int, y: int) -> bool:
        """Frame-seam pixels on bordered cards only — never full-bleed art."""
        corner = _apex_corner_at(x, y, w, h, margin)
        if corner is None or corner in bleed:
            return False
        return on_top_gutter_frame_row(x, y) or on_side_gutter_frame_col(x, y)

    for y in range(h):
        for x in range(w):
            in_gutter = (
                in_top_gutter(x, y)
                or on_top_gutter_frame_row(x, y)
                or on_side_gutter_frame_col(x, y)
            )
            if not in_gutter:
                continue
            if not _in_extension(x, y, w, h, ext) and not _allows_card_seam_paint(x, y):
                continue
            if not _in_margin_speck_zone(x, y, w, h, ext, band):
                continue
            if _on_card_frame_border_ring(x, y, w, h, ext) and not (
                on_top_gutter_frame_row(x, y) or on_side_gutter_frame_col(x, y)
            ):
                continue
            p = px[x, y][:3]
            bright = br(x, y)
            if bright == 0 or bright > max_bright or not _is_neutral_grey(p):
                continue
            dark = tot = 0
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx == dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        tot += 1
                        if br(nx, ny) < 12:
                            dark += 1
            if not tot or dark / tot < dark_neighbor_frac:
                continue
            if p != (0, 0, 0):
                px[x, y] = (0, 0, 0)
                changed += 1

    return out, changed


def fix_bottom_gutter_corners(
    img: Image.Image,
    band: int,
    *,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """
    Blacken neutral-grey conversion gutter wedges in the bottom image corners
    (BL/BR) without touching top/side padding or colored card frame pixels.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    ext = extension_width(w, h)
    size = ext * 2
    changed = 0
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)

    def _near_black(x: int, y: int) -> bool:
        for nx in range(max(0, x - 2), min(w, x + 3)):
            for ny in range(max(0, y - 2), min(h, y + 3)):
                if _brightness(px[nx, ny]) < 40:
                    return True
        return False

    def _on_image_corner_edge(x: int, y: int, corner: str) -> bool:
        if y >= h - 3:
            return True
        if corner == "BL" and x < 3:
            return True
        if corner == "BR" and x >= w - 3:
            return True
        return False

    for name in ("BL", "BR"):
        if name in bleed:
            continue
        x0, y0, x1, y1 = _corner_box(name, w, h, size)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_extension(x, y, w, h, ext):
                    continue
                p = px[x, y][:3]
                if not _is_neutral_grey(p):
                    continue
                br = _brightness(p)
                if br < 80 or br > 220:
                    continue
                if not (_near_black(x, y) or _on_image_corner_edge(x, y, name)):
                    continue
                px[x, y] = (0, 0, 0)
                changed += 1

    strip = max(2, min(w, h) // 200)
    skip = max(1, min(w, h) // 10)
    bottom_vals = [
        _brightness(px[x, y])
        for x in range(skip, w - skip)
        for y in range(h - strip, h)
    ]
    if bottom_vals and sorted(bottom_vals)[len(bottom_vals) // 2] < 55:
        top_vals = [
            _brightness(px[x, y])
            for x in range(skip, w - skip)
            for y in range(0, strip)
        ]
        top_med = sorted(top_vals)[len(top_vals) // 2] if top_vals else 255
        if top_med <= 150:
            wedge_reach = _bottom_gutter_wedge_reach(ext, band)
            wedge_width = _bottom_gutter_wedge_width(ext, band)
            black = (0, 0, 0)
            y0, y1 = h - ext - wedge_reach, h - ext
            wedge_zones = (
                ("BL", ext, ext + wedge_width),
                ("BR", w - ext - wedge_width, w - ext),
            )
            for corner_name, x_lo, x_hi in wedge_zones:
                if corner_name in bleed:
                    continue
                for x in range(x_lo, x_hi):
                    col = [px[x, y][:3] for y in range(y0, y1)]
                    if not col:
                        continue
                    # A real gutter column is essentially all-black with a grey
                    # wedge. Columns holding bright card content (white text box,
                    # P/T bubble, light frame) must never be blackened.
                    bright_ct = sum(1 for c in col if _brightness(c) > 165)
                    dark_ct = sum(1 for c in col if _brightness(c) < 40)
                    if bright_ct > 2 or dark_ct < len(col) // 2:
                        continue
                    if any(
                        not _in_extension(x, y, w, h, ext)
                        and not _in_bottom_gutter_arm(x, y, w, h, ext, band)
                        and _brightness(px[x, y]) > 35
                        for y in range(y0, y1)
                    ):
                        continue
                    for y in range(y0, y1):
                        if _protected_bottom_text_zone(x, y, w, h, ext):
                            continue
                        if not _in_extension(x, y, w, h, ext) and not _in_bottom_gutter_arm(
                            x, y, w, h, ext, band
                        ):
                            continue
                        p = px[x, y][:3]
                        if not _is_neutral_grey(p) or not (80 <= _brightness(p) <= 150):
                            continue
                        if p != black:
                            px[x, y] = black
                            changed += 1

    return out, changed


def _inpaint_matte_neighbors(
    px, x: int, y: int, w: int, h: int, *, max_bright: int = 75
) -> tuple[int, int, int] | None:
    """Median colour from nearby matte neighbours (cross-axis first)."""
    refs: list[tuple[int, int, int]] = []
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -2), (0, 2)):
        nx, ny = x + dx, y + dy
        if nx < 0 or nx >= w or ny < 0 or ny >= h:
            continue
        p = px[nx, ny][:3]
        if _brightness(p) <= max_bright:
            refs.append(p)
    if not refs:
        return None
    return _median_rgb(refs)


def _inpaint_corner_tip_neighbors(
    px, x: int, y: int, w: int, h: int, *, radius: int = 3, ref_max_bright: int = 13
) -> tuple[int, int, int] | None:
    """Prefer slightly darker matte neighbours in a small radius."""
    refs: list[tuple[int, int, int]] = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                continue
            p = px[nx, ny][:3]
            if _brightness(p) <= ref_max_bright:
                refs.append(p)
    if refs:
        return _median_rgb(refs)
    return _inpaint_matte_neighbors(px, x, y, w, h)


def fix_bottom_corner_gutter_tips(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """
    Soft-blend the small bright BL/BR gutter tip (beside DS / mirror on BR).

    Only repaints local outliers in a tiny corner patch using nearby matte colours —
    never flat black, never the full gutter band.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    strip = max(2, min(w, h) // 200)
    skip = max(1, min(w, h) // 10)
    bottom_vals = [
        _brightness(px[x, y])
        for x in range(skip, w - skip)
        for y in range(h - strip, h)
    ]
    if not bottom_vals or sorted(bottom_vals)[len(bottom_vals) // 2] >= 55:
        return out, 0

    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)
    changed = 0
    tip_depth = max(10, ext // 3)
    tip_width = max(12, ext // 2)
    y0, y1 = h - ext - tip_depth, h - ext
    zones = []
    if "BL" not in bleed:
        zones.append((range(ext, min(ext + tip_width, _footer_text_x_span(w)[0])), y0, y1))
    if "BR" not in bleed:
        zones.append(
            (
                range(max(w - ext - tip_width, _footer_text_x_span(w)[1]), w - ext),
                y0,
                y1,
            )
        )

    for x_range, y_lo, y_hi in zones:
        for y in range(y_lo, y_hi):
            for x in x_range:
                if _in_footer_text_zone(x, y, w, h, ext):
                    continue
                p = px[x, y][:3]
                br = _brightness(p)
                if br < 15 or br >= 80:
                    continue
                fill = _inpaint_corner_tip_neighbors(px, x, y, w, h)
                if fill is None or fill == p or _brightness(fill) >= br:
                    continue
                px[x, y] = fill
                changed += 1

    # Padding-wedge tip: last few rows of x < ext at the BL/BR image corners.
    pad_rows = max(4, ext // 6)
    pad_zones: list[tuple[int, int]] = []
    if "BL" not in bleed:
        pad_zones.append((0, ext))
    if "BR" not in bleed:
        pad_zones.append((w - ext, w))
    for x_lo, x_hi in pad_zones:
        for y in range(h - pad_rows, h):
            for x in range(x_lo, x_hi):
                p = px[x, y][:3]
                br = _brightness(p)
                if br < 15 or br >= 80:
                    continue
                fill = _inpaint_corner_tip_neighbors(px, x, y, w, h)
                if fill is None or fill == p or _brightness(fill) >= br:
                    continue
                px[x, y] = fill
                changed += 1

    return out, changed


def _wedge_offsets(
    corner: str, x: int, y: int, w: int, h: int, ext: int
) -> tuple[float, float] | None:
    """Distances from the card corner into the outer padding wedge."""
    if corner == "TL":
        if x >= ext or y >= ext:
            return None
        return (float(ext - x), float(ext - y))
    if corner == "TR":
        if x < w - ext or y >= ext:
            return None
        return (float(x - (w - ext)), float(ext - y))
    if corner == "BL":
        if x >= ext or y < h - ext:
            return None
        return (float(ext - x), float(y - (h - ext)))
    if x < w - ext or y < h - ext:
        return None
    return (float(x - (w - ext)), float(y - (h - ext)))


def _wedge_xy(
    corner: str, u: float, v: float, w: int, h: int, ext: int
) -> tuple[int, int]:
    """Map wedge offsets back to image coordinates."""
    if corner == "TL":
        return (int(round(ext - u)), int(round(ext - v)))
    if corner == "TR":
        return (int(round(w - ext + u)), int(round(ext - v)))
    if corner == "BL":
        return (int(round(ext - u)), int(round(h - ext + v)))
    return (int(round(w - ext + u)), int(round(h - ext + v)))


def _clamp_xy(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))


def _detect_cut_arc_radius(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
) -> float:
    """Estimate quarter-circle cut radius; 0 when no arc boundary is visible."""
    best_r = 0.0
    best_score = 0.0
    r_max = ext + _corner_apex_reach(ext) + 2
    for ri in range(4, int(r_max) + 1):
        score = 0.0
        hits = 0
        for step in range(8, 28):
            t = step / 28.0 * (math.pi / 2.0)
            u = ri * math.cos(t)
            v = ri * math.sin(t)
            sx, sy = _wedge_xy(corner, u, v, w, h, ext)
            if not (0 <= sx < w and 0 <= sy < h):
                continue
            ui, vi = u * max(0.2, (ri - 2.0) / ri), v * max(0.2, (ri - 2.0) / ri)
            uo, vo = u * min(ri + 3.0, r_max) / ri, v * min(ri + 3.0, r_max) / ri
            iix, iiy = _clamp_xy(*_wedge_xy(corner, ui, vi, w, h, ext), w, h)
            oox, ooy = _clamp_xy(*_wedge_xy(corner, uo, vo, w, h, ext), w, h)
            if _on_card_frame_border_ring(oox, ooy, w, h, ext):
                continue
            pi, po = px[iix, iiy][:3], px[oox, ooy][:3]
            diff = _color_distance(pi, po)
            if diff > 20:
                score += diff
                hits += 1
        if hits >= 4 and score > best_score:
            best_score = score
            best_r = float(ri)
    return best_r if best_score >= 100 else 0.0


def _detect_cut_line(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
) -> bool:
    """True when a straight diagonal cut (u + v ≈ ext) is visible in the wedge."""
    score = 0.0
    hits = 0
    step = max(1, ext // 6)
    for u_i in range(step, ext, step):
        u = float(u_i)
        v = float(ext - u_i)
        sx, sy = _clamp_xy(*_wedge_xy(corner, u, v, w, h, ext), w, h)
        ui, vi = u * 0.65, v * 0.65
        uo, vo = min(u * 1.25, ext - 1.0), min(v * 1.25, ext - 1.0)
        iix, iiy = _clamp_xy(*_wedge_xy(corner, ui, vi, w, h, ext), w, h)
        oox, ooy = _clamp_xy(*_wedge_xy(corner, uo, vo, w, h, ext), w, h)
        if _on_card_frame_border_ring(oox, ooy, w, h, ext):
            continue
        diff = _color_distance(px[iix, iiy][:3], px[oox, ooy][:3])
        if diff > 25:
            score += diff
            hits += 1
    return hits >= 2 and score >= 80


def _inside_cut_wedge(
    corner: str, x: int, y: int, w: int, h: int, ext: int, *, radius: float
) -> bool:
    uv = _wedge_offsets(corner, x, y, w, h, ext)
    if uv is None:
        return False
    u, v = uv
    if radius > 0:
        return math.hypot(u, v) <= radius + 0.5
    return u + v < ext - 0.5


def _wedge_cut_colors(
    px, corner: str, w: int, h: int, ext: int, *, radius: float
) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    x0, y0, x1, y1 = _corner_box(corner, w, h, ext)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _inside_cut_wedge(corner, x, y, w, h, ext, radius=radius):
                colors.append(px[x, y][:3])
    return colors


def _wedge_needs_cut_stretch(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
    *,
    radius: float,
    tol: int = 35,
) -> bool:
    """Wedge fill differs from the border colour just inside the cut — needs stretch."""
    wedge = _wedge_cut_colors(px, corner, w, h, ext, radius=radius)
    if len(wedge) < 8:
        return False
    target = _sample_corner_border_color(px, corner, w, h, ext)
    if target is None:
        target = _inner_corner_fill(px, corner, w, h, ext)
    wedge_med = _median_rgb(wedge)
    if _color_distance(wedge_med, target) <= tol:
        return False
    off = sum(1 for c in wedge if _color_distance(c, target) > tol)
    return off >= max(3, len(wedge) // 8)


def _default_cut_arc_radius(ext: int) -> float:
    return float(ext)


def _sample_across_cut(
    px,
    corner: str,
    u: float,
    v: float,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int, int]:
    """Walk from a wedge pixel toward the card until the frame border is hit."""
    angle = math.atan2(v, u) if u > 0 or v > 0 else 0.0
    start_r = max(1.0, math.hypot(u, v))
    for ri in range(int(start_r), ext * 3 + 4):
        sr = float(ri)
        su = sr * math.cos(angle)
        sv = sr * math.sin(angle)
        sx, sy = _clamp_xy(*_wedge_xy(corner, su, sv, w, h, ext), w, h)
        on_frame = False
        if corner == "TL":
            on_frame = sx >= ext or sy >= ext
        elif corner == "TR":
            on_frame = sx <= w - ext - 1 or sy >= ext
        elif corner == "BL":
            on_frame = sx >= ext or sy <= h - ext - 1
        else:
            on_frame = sx <= w - ext - 1 or sy <= h - ext - 1
        if on_frame:
            style = _corner_pad_style(px, corner, w, h, ext)
            if style.dark:
                return style.fill
            if _on_corner_gutter_seam(corner, sx, sy, w, h, ext):
                if _brightness(style.fill) < 60:
                    return style.fill
            return px[sx, sy][:3]
    target = _sample_corner_border_color(px, corner, w, h, ext)
    if target is not None:
        return target
    return _inner_corner_fill(px, corner, w, h, ext)


def _fade_frame_edge_color(
    px,
    xf: int,
    y: int,
    w: int,
    h: int,
    ext: int,
    reach: int,
    *,
    corner: str | None = None,
    bright_cutoff: int = 100,
    dark_inner_cutoff: int = 35,
) -> tuple[int, int, int]:
    """Walk inward on a frame column to the dark gradient edge."""
    if corner is None:
        corner = "BL" if xf <= w // 2 else "BR"
    ylo = max(0, h - ext - reach)
    iy = h - ext - 1
    sy = max(ylo, min(iy, y))
    while sy > ylo and _brightness(px[xf, sy][:3]) >= 235:
        sy -= 1
    inner = _inner_corner_fill(px, corner, w, h, ext)
    if _brightness(inner) < 50:
        while sy > ylo and _brightness(px[xf, sy][:3]) >= dark_inner_cutoff:
            sy -= 1
    else:
        while sy > ylo and _brightness(px[xf, sy][:3]) >= bright_cutoff:
            sy -= 1
    return px[xf, max(ylo, sy)][:3]


def _sample_across_cut_fade(
    px,
    corner: str,
    u: float,
    v: float,
    w: int,
    h: int,
    ext: int,
    reach: int,
) -> tuple[int, int, int]:
    """Ray-walk like ``_sample_across_cut`` but skip pale/white frame-edge rows."""
    angle = math.atan2(v, u) if u > 0 or v > 0 else 0.0
    start_r = max(1.0, math.hypot(u, v))
    for ri in range(int(start_r), ext * 3 + 4):
        sr = float(ri)
        su = sr * math.cos(angle)
        sv = sr * math.sin(angle)
        sx, sy = _clamp_xy(*_wedge_xy(corner, su, sv, w, h, ext), w, h)
        on_frame = False
        if corner == "TL":
            on_frame = sx >= ext or sy >= ext
        elif corner == "TR":
            on_frame = sx <= w - ext - 1 or sy >= ext
        elif corner == "BL":
            on_frame = sx >= ext or sy <= h - ext - 1
        else:
            on_frame = sx <= w - ext - 1 or sy <= h - ext - 1
        if on_frame:
            if corner == "BL":
                xf = max(ext, sx)
                yf = min(h - ext - 1, sy)
                return _fade_frame_edge_color(px, xf, yf, w, h, ext, reach)
            if corner == "BR":
                xf = min(w - ext - 1, sx)
                yf = min(h - ext - 1, sy)
                return _fade_frame_edge_color(px, xf, yf, w, h, ext, reach)
            return px[sx, sy][:3]
    if corner == "BL":
        return _fade_frame_edge_color(px, ext, h - ext - 1, w, h, ext, reach)
    if corner == "BR":
        return _fade_frame_edge_color(px, w - ext - 1, h - ext - 1, w, h, ext, reach)
    return _inner_corner_fill(px, corner, w, h, ext)


def _stretch_cut_arc(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
    radius: float,
    *,
    band: int,
    sample_fn=None,
) -> int:
    """Fill inside a detected quarter-circle cut by sampling outward from the arc."""
    del band
    changed = 0
    x0, y0, x1, y1 = _corner_box(corner, w, h, ext)
    for y in range(y0, y1):
        for x in range(x0, x1):
            uv = _wedge_offsets(corner, x, y, w, h, ext)
            if uv is None:
                continue
            u, v = uv
            if math.hypot(u, v) > radius + 0.5:
                continue
            if _on_card_frame_border_ring(x, y, w, h, ext):
                continue
            if _in_footer_text_zone(x, y, w, h, ext):
                continue
            if sample_fn is not None:
                color = sample_fn(px, corner, u, v, w, h, ext)
            else:
                color = _sample_across_cut(px, corner, u, v, w, h, ext)
            if px[x, y][:3] != color:
                px[x, y] = color
                changed += 1
    return changed


def _stretch_cut_line(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
    *,
    band: int,
    sample_fn=None,
) -> int:
    """Fill inside a straight diagonal cut by stretching border pixels to the image corner."""
    changed = 0
    reach = ext + band
    x0, y0, x1, y1 = _corner_box(corner, w, h, ext)
    for y in range(y0, y1):
        for x in range(x0, x1):
            uv = _wedge_offsets(corner, x, y, w, h, ext)
            if uv is None:
                continue
            u, v = uv
            if u + v >= ext - 0.5:
                continue
            if _on_card_frame_border_ring(x, y, w, h, ext):
                continue
            if _in_footer_text_zone(x, y, w, h, ext):
                continue
            t_u = u / max(1.0, float(ext))
            t_v = v / max(1.0, float(ext))
            if corner == "TL":
                if t_v >= t_u:
                    sx = max(ext, min(ext + reach - 1, ext + int(t_u * (reach - 1))))
                    sy = ext
                else:
                    sx = ext
                    sy = max(ext, min(ext + reach - 1, ext + int(t_v * (reach - 1))))
            elif corner == "TR":
                if t_v >= t_u:
                    sx = max(w - ext - reach, min(w - ext - 1, w - ext - 1 - int(t_u * (reach - 1))))
                    sy = ext
                else:
                    sx = w - ext - 1
                    sy = max(ext, min(ext + reach - 1, ext + int(t_v * (reach - 1))))
            elif corner == "BL":
                if t_v >= t_u:
                    sx = max(ext, min(ext + reach - 1, ext + int(t_u * (reach - 1))))
                    sy = h - ext - 1
                else:
                    sx = ext
                    sy = max(h - ext - reach, min(h - ext - 1, h - ext - 1 - int(t_v * (reach - 1))))
            else:  # BR
                if t_v >= t_u:
                    sx = max(w - ext - reach, min(w - ext - 1, w - ext - 1 - int(t_u * (reach - 1))))
                    sy = h - ext - 1
                else:
                    sx = w - ext - 1
                    sy = max(h - ext - reach, min(h - ext - 1, h - ext - 1 - int(t_v * (reach - 1))))
            if sample_fn is not None:
                color = sample_fn(px, corner, u, v, w, h, ext)
            else:
                color = px[sx, sy][:3]
            if px[x, y][:3] != color:
                px[x, y] = color
                changed += 1
    return changed


def fix_cut_corner_stretch(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    fade_bottom_card: bool | None = None,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int, list[str]]:
    """
    Detect rounded-corner cut (arc or diagonal line) in each padding wedge and
    stretch border pixels from the cut boundary out to the image corner.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0, []

    total = 0
    notes: list[str] = []
    fade_bottom = _resolve_fade_bottom_card(px, w, h, ext, band, fade_bottom_card)
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)
    for corner in _CORNERS:
        if fade_bottom and corner in ("BL", "BR"):
            continue
        if corner in bleed:
            continue
        radius = _detect_cut_arc_radius(px, corner, w, h, ext)
        mode = "arc" if radius > 0 else ""
        if not radius and _detect_cut_line(px, corner, w, h, ext):
            mode = "line"
        elif not radius and _wedge_needs_cut_stretch(
            px, corner, w, h, ext, radius=_default_cut_arc_radius(ext)
        ):
            radius = _default_cut_arc_radius(ext)
            mode = "arc"

        if mode == "arc" and radius > 0:
            n = _stretch_cut_arc(px, corner, w, h, ext, radius, band=band)
            if n:
                notes.append(f"{corner} arc r={radius:.0f}: {n}px")
                total += n
        elif mode == "line":
            n = _stretch_cut_line(px, corner, w, h, ext, band=band)
            if n:
                notes.append(f"{corner} line cut: {n}px")
                total += n

    return out, total, notes


def _fade_bottom_inner_corner(px, w: int, h: int, ext: int, band: int) -> bool:
    """Inner BL/BR corner block fades dark — use outward gradient stretch, not black fill."""
    reach = ext + band
    inner_block = [
        px[x, y][:3]
        for x in range(ext, ext + reach)
        for y in range(h - ext - reach, h - ext)
    ] + [
        px[x, y][:3]
        for x in range(w - ext - reach, w - ext)
        for y in range(h - ext - reach, h - ext)
    ]
    if not inner_block:
        return False
    dark_frac = sum(1 for s in inner_block if _brightness(s) < 40) / len(inner_block)
    return dark_frac >= 0.12


def _fade_bottom_corner_card(
    px, w: int, h: int, ext: int, band: int
) -> bool:
    """Bottom padding is still light while the inner corner block fades to dark."""
    if not _fade_bottom_inner_corner(px, w, h, ext, band):
        return False
    corner_light = [
        _brightness(px[x, y])
        for x in list(range(0, ext)) + list(range(w - ext, w))
        for y in range(h - ext, h)
    ]
    if not corner_light:
        return False
    return sorted(corner_light)[len(corner_light) // 2] >= 90


def _fade_l_arm_needs_stretch(p: tuple[int, int, int]) -> bool:
    """Bright or pale registration remnants on fade-bottom L-arm seams."""
    br = _brightness(p)
    if br >= 170:
        return True
    return _is_neutral_grey(p) and br >= 85


def _fade_bottom_l_arm_color(
    px,
    corner: str,
    x: int,
    y: int,
    w: int,
    h: int,
    ext: int,
    reach: int,
    sample_fade,
) -> tuple[int, int, int]:
    xf = ext if corner == "BL" else w - ext - 1
    uv = _wedge_offsets(corner, x, y, w, h, ext)
    if uv is not None:
        return sample_fade(px, corner, *uv, w, h, ext)
    return _fade_frame_edge_color(px, xf, y, w, h, ext, reach)


def fix_fade_bottom_edge_stretch(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    fade_bottom_card: bool | None = None,
) -> tuple[Image.Image, int]:
    """
    On gradient-fade bottom corners, stretch dark edge colour into BL/BR wedges.

    Finds the inner gradient edge (skipping pale/white registration rows), then
    ray-stretches that colour through cut-corner arcs and the full gutter band.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None or not _resolve_fade_bottom_card(
        px, w, h, ext, band, fade_bottom_card
    ):
        return out, 0

    reach = ext + band
    changed = 0

    def sample_fade(px, corner, u, v, w, h, ext):
        return _sample_across_cut_fade(px, corner, u, v, w, h, ext, reach)

    for corner in ("BL", "BR"):
        radius = _detect_cut_arc_radius(px, corner, w, h, ext)
        mode = "arc" if radius > 0 else ""
        if not radius and _detect_cut_line(px, corner, w, h, ext):
            mode = "line"
        elif not radius and _wedge_needs_cut_stretch(
            px, corner, w, h, ext, radius=_default_cut_arc_radius(ext)
        ):
            radius = _default_cut_arc_radius(ext)
            mode = "arc"

        if mode == "arc" and radius > 0:
            n = _stretch_cut_arc(
                px,
                corner,
                w,
                h,
                ext,
                radius,
                band=band,
                sample_fn=sample_fade,
            )
            changed += n
        elif mode == "line":
            n = _stretch_cut_line(
                px, corner, w, h, ext, band=band, sample_fn=sample_fade
            )
            changed += n

        x0, y0, x1, y1 = _corner_box(corner, w, h, ext + reach)
        cx0, cx1 = _center_span(w)
        xf = ext if corner == "BL" else w - ext - 1
        for y in range(max(y0, h - ext - reach), y1):
            for x in range(x0, x1):
                if corner == "BL":
                    if not (x < ext and y >= h - ext - reach):
                        continue
                elif not (x >= w - ext and y >= h - ext - reach):
                    continue
                if x == ext or x == w - ext - 1:
                    continue
                if y == h - ext - 1 and cx0 <= x < cx1:
                    continue
                if _in_footer_text_zone(x, y, w, h, ext):
                    continue
                uv = _wedge_offsets(corner, x, y, w, h, ext)
                if uv:
                    color = sample_fade(px, corner, *uv, w, h, ext)
                else:
                    color = _fade_frame_edge_color(px, xf, y, w, h, ext, reach)
                if px[x, y][:3] != color:
                    px[x, y] = color
                    changed += 1

        ax0, ay0, ax1, ay1 = _corner_l_apex_box(corner, w, h, ext)
        for y in range(ay0, ay1):
            for x in range(ax0, ax1):
                if not _in_corner_l_apex_zone(corner, x, y, w, h, ext):
                    continue
                if not _in_corner_l_paint_zone(corner, x, y, w, h, ext):
                    continue
                if _in_footer_text_zone(x, y, w, h, ext):
                    continue
                if not _fade_l_arm_needs_stretch(px[x, y][:3]):
                    continue
                color = _fade_bottom_l_arm_color(
                    px, corner, x, y, w, h, ext, reach, sample_fade
                )
                if px[x, y][:3] != color:
                    px[x, y] = color
                    changed += 1

        # Bottom frame-row gutter specs sit inside x<w-ext but outside the apex
        # box; the wedge loop only covers padding (x>=w-ext on BR).
        reach_arm = ext + _corner_apex_reach(ext) + 2
        iy = h - ext - 1
        if corner == "BL":
            x_vals = range(ext, min(w - ext, _bl_bottom_gutter_x1(w, ext, reach_arm)))
            xf = ext
        else:
            x_vals = range(max(ext, _br_bottom_gutter_x0(w, ext, reach_arm)), w - ext)
            xf = w - ext - 1
        for x in x_vals:
            if _footer_blocks_corner_paint(x, iy, w, h, ext, band):
                continue
            if not _fade_l_arm_needs_stretch(px[x, iy][:3]):
                continue
            color = _fade_frame_edge_color(px, xf, iy, w, h, ext, reach)
            if px[x, iy][:3] != color:
                px[x, iy] = color
                changed += 1

    return out, changed


def fix_colored_top_corner_padding(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    tol: int = 35,
) -> tuple[Image.Image, int]:
    """Repaint TL/TR extension padding to the coloured frame border sampled at y=ext."""
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    changed = 0
    reach = min(ext * 3, max(band * 2, ext * 2))
    for corner in ("TL", "TR"):
        style = _corner_pad_style(px, corner, w, h, ext)
        if not style.light:
            continue
        fill = _sample_corner_border_color(px, corner, w, h, ext) or style.fill
        x0, y0, x1, y1 = _corner_box(corner, w, h, reach)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_extension(x, y, w, h, ext):
                    continue
                if _on_card_frame_border_ring(x, y, w, h, ext):
                    continue
                if _color_distance(px[x, y][:3], fill) > tol:
                    px[x, y] = fill
                    changed += 1

    return out, changed


def fix_bottom_corner_specks(
    img: Image.Image,
    ext: int,
    *,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int]:
    """
    Remove small grey L-mark chips in bottom corner gutters when the
    bottom padding is dark. Preserves bright credit text (br >= 150).
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    band = _border_band(w, h)
    style = _corner_pad_style(px, "BL", w, h, ext)
    if not style.dark:
        return out, 0

    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)
    fill = style.fill
    y0 = max(ext, h - ext - 3)
    y1 = min(h, h - ext + 1)
    changed = 0

    for corner in ("BL", "BR"):
        if corner in bleed:
            continue
        for y in range(y0, y1):
            for x in range(w):
                if not (
                    _in_extension(x, y, w, h, ext)
                    or _in_bottom_gutter_arm(x, y, w, h, ext, band)
                ):
                    continue
                if corner == "BL" and x >= _bl_bottom_gutter_x1(w, ext, ext * 2):
                    continue
                if corner == "BR" and x < _br_bottom_gutter_x0(w, ext, ext * 2):
                    continue
                p = px[x, y][:3]
                br = _brightness(p)
                if br >= 150 or not _is_neutral_grey(p) or not (100 <= br <= 145):
                    continue
                if not _near_black_px(px, x, y, w, h):
                    continue
                if p != fill:
                    px[x, y] = fill
                    changed += 1

    return out, changed


def fix_top_corner_match(img: Image.Image, band: int, ext: int) -> tuple[Image.Image, int]:
    """
    On light-grey top padding, lift dark neutral wedges at TL/TR so they match
    the card top border color sampled from the frame edge.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0

    strip = max(2, min(w, h) // 200)
    skip = max(1, min(w, h) // 10)
    top_vals = [
        _brightness(px[x, y])
        for x in range(skip, w - skip)
        for y in range(0, strip)
    ]
    if not top_vals:
        return out, 0
    top_med = sorted(top_vals)[len(top_vals) // 2]
    if top_med < 100 or top_med > 190:
        return out, 0

    cx0, cx1 = _center_span(w)
    border_samples = [
        px[x, ext][:3]
        for x in range(cx0, cx1)
        if _brightness(px[x, ext]) >= 140
        and (
            not _is_neutral_grey(px[x, ext][:3])
            or _brightness(px[x, ext]) >= 175
        )
    ]
    if not border_samples:
        return out, 0
    fill = _median_rgb(border_samples)
    fill_bright = _brightness(fill)
    if fill_bright < top_med + 12:
        return out, 0

    reach = _top_corner_match_reach(ext)
    width = _top_corner_match_width(ext, band)
    min_bright = fill_bright - 12
    changed = 0

    for y in range(ext, ext + reach):
        for x in range(ext, ext + width):
            p = px[x, y][:3]
            if _is_neutral_grey(p) and _brightness(p) < min_bright:
                px[x, y] = fill
                changed += 1
        for x in range(w - ext - width, w - ext):
            p = px[x, y][:3]
            if _is_neutral_grey(p) and _brightness(p) < min_bright:
                px[x, y] = fill
                changed += 1

    return out, changed


def _corner_arc_zone_box(name: str, w: int, h: int, reach: int) -> tuple[int, int, int, int]:
    """Square anchored at an image corner covering its padding + arc junction."""
    if name == "TL":
        return (0, 0, reach, reach)
    if name == "TR":
        return (w - reach, 0, w, reach)
    if name == "BL":
        return (0, h - reach, reach, h)
    return (w - reach, h - reach, w, h)  # BR


def fix_corner_arc_uniform(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    minority_frac: float = 0.20,
    tol: int = 60,
    full_bleed_corners: frozenset[str] | None = None,
) -> tuple[Image.Image, int, list[str]]:
    """
    Fill faint corner + arc remnants on near-uniform padding.

    Rule (per corner): look at the corner+arc zone — the outer padding plus the
    small apex band where the padding meets the card frame. If that zone is
    mostly ONE color and under ``minority_frac`` (20%) of its pixels are some
    other color, repaint the off-color minority to the dominant color.

    This wipes faint specks, thin crop/registration lines, and pale arc
    remnants without disturbing real card art: if the zone held meaningful card
    content (a light frame, gradient, etc.) it would be too mixed to be "mostly
    one color", so the rule simply does not fire.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0, []

    reach = ext + _corner_apex_reach(ext) + 4
    repainted = 0
    notes: list[str] = []
    bleed = _resolve_full_bleed_corners(px, w, h, ext, band, full_bleed_corners)

    for name in _CORNERS:
        if name in bleed:
            continue
        x0, y0, x1, y1 = _corner_arc_zone_box(name, w, h, reach)
        zone: list[tuple[int, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_corner_fix_zone(
                    x, y, w, h, ext, band, allow_apex=name not in bleed
                ):
                    continue
                if _in_footer_text_zone(x, y, w, h, ext):
                    continue
                if _on_card_frame_border_ring(x, y, w, h, ext):
                    continue
                zone.append((x, y))
        if len(zone) < 16:
            continue

        dominant = _median_rgb([px[x, y][:3] for x, y in zone])
        minority = [
            (x, y)
            for x, y in zone
            if _color_distance(px[x, y][:3], dominant) > tol
        ]
        if not minority or len(minority) > len(zone) * minority_frac:
            continue

        for x, y in minority:
            if px[x, y][:3] != dominant:
                px[x, y] = dominant
                repainted += 1
        if minority:
            notes.append(
                f"{name}: {len(minority)}px -> dominant ({len(minority) / len(zone):.0%})"
            )

    return out, repainted, notes


def fix_side_border(
    img: Image.Image,
    band: int,
    ext: int,
    *,
    dark_thresh: int = 55,
    light_thresh: int = 150,
) -> tuple[Image.Image, list[str]]:
    """
    On a black-bordered card, recolor a whole side whose outer band is wrongly
    light (e.g. an un-blackened right/top edge) to black.

    Self-gating: only fires when at least two edges are clearly dark *and* at
    least one edge is clearly light, so colored/white-bordered cards and cards
    on light backgrounds are untouched. Per-scanline it blackens only the
    contiguous light run from the image edge inward, stopping at the first dark
    pixel — so the real (dark) border and card art are preserved.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, []

    strip = max(2, min(w, h) // 200)  # outermost band sampled to classify edge
    skip = max(1, min(w, h) // 10)  # ignore corner zones when classifying
    max_depth = ext

    def edge_brightness(edge: str) -> int:
        vals: list[int] = []
        if edge in ("top", "bottom"):
            ys = range(0, strip) if edge == "top" else range(h - strip, h)
            for x in range(skip, w - skip):
                for y in ys:
                    vals.append(_brightness(px[x, y]))
        else:
            xs = range(0, strip) if edge == "left" else range(w - strip, w)
            for y in range(skip, h - skip):
                for x in xs:
                    vals.append(_brightness(px[x, y]))
        if not vals:
            return 0
        return sorted(vals)[len(vals) // 2]

    bright = {e: edge_brightness(e) for e in ("top", "bottom", "left", "right")}
    dark_edges = [e for e, b in bright.items() if b < dark_thresh]
    light_edges = [e for e, b in bright.items() if b > light_thresh]

    if len(dark_edges) < 2 or not light_edges:
        return out, []

    black = (0, 0, 0)
    fixed: list[str] = []

    for edge in light_edges:
        changed = 0
        if edge in ("top", "bottom"):
            for x in range(w):
                ys = range(h) if edge == "top" else range(h - 1, -1, -1)
                depth = 0
                for y in ys:
                    if depth >= max_depth or _brightness(px[x, y]) <= light_thresh:
                        break
                    if not _in_extension(x, y, w, h, ext):
                        break
                    px[x, y] = black
                    changed += 1
                    depth += 1
        else:
            for y in range(h):
                xs = range(w) if edge == "left" else range(w - 1, -1, -1)
                depth = 0
                for x in xs:
                    if depth >= max_depth or _brightness(px[x, y]) <= light_thresh:
                        break
                    if not _in_extension(x, y, w, h, ext):
                        break
                    px[x, y] = black
                    changed += 1
                    depth += 1
        if changed:
            fixed.append(edge)

    return out, fixed


@dataclass
class CornerArcGuide:
    corner: str
    needs_fix: bool
    center_pct: tuple[float, float]
    radius_inner: float
    radius_outer: float
    note: str


@dataclass
class CornerFixGuide:
    corner: str
    model_flagged: bool
    needs_fix: bool
    artifact: str
    bbox_pct: tuple[float, float, float, float] | None
    note: str


_CORNER_LOCATE_PROMPT = """You inspect printable Magic-style card PNGs with added outer padding for printing.

Images (in order):
0 = full canvas
1 = top-left crop
2 = top-right crop
3 = bottom-left crop
4 = bottom-right crop

Find small **conversion artifacts only** in the outer padding: white/grey L-shaped crop marks, registration triangles, or grey smears where padding meets the card frame.

Do NOT flag the card's own border art, frame texture, rules text, or intentional design. Only artifacts in the added padding outside the card rectangle.

Return JSON only — an array of exactly four objects, one per corner in order TL, TR, BL, BR:
[
  {{
    "corner": "TL",
    "artifact": "white_l_mark|grey_wedge|none",
    "needs_fix": true,
    "fill_bbox_pct": [x0, y0, x1, y1],
    "note": "brief"
  }}
]

Rules for fill_bbox_pct (percent of full image, 0–100):
- Tight box around the artifact pixels only (typically under 8% width and height).
- Must lie in outer padding, not over card art.
- null when needs_fix is false.
- Canvas is {w}x{h} px: y near 0 = top padding, y near {h} = bottom padding.

Card: {card_name}"""


_CORNER_ARC_LOCATE_PROMPT = """You inspect a printable card PNG **after** a first pass removed L-shaped crop marks from the outer padding.

Images (in order):
0 = full canvas (post first-pass)
1 = top-left crop
2 = top-right crop
3 = bottom-left crop
4 = bottom-right crop

Find any remaining **curved arc** of white/light pixels at each corner — remnants of the old rounded card corner at the padding/card junction. These are thin quarter-circle arcs, not the card frame texture.

Do NOT flag intentional card border art, gradients, or frame bubbles.

Return JSON only — array of four objects (TL, TR, BL, BR):
[
  {{
    "corner": "TL",
    "needs_fix": true,
    "arc_center_pct": [x, y],
    "arc_radius_px": [inner, outer],
    "note": "brief"
  }}
]

Rules:
- arc_center_pct: center of the quarter-circle in percent of full image (0–100), usually near the card corner (~{ext_pct_x:.1f}%, ~{ext_pct_y:.1f}% for TL).
- arc_radius_px: inner and outer radius in **pixels** (typical arc: inner 3–6, outer 12–22).
- null arc_radius_px when needs_fix is false.
- Canvas is {w}x{h} px.

Card: {card_name}"""


_CORNER_LOCATE_RETRY_PROMPT = """You inspect a printable Magic-style card PNG **after** an automated fix pass that still failed quality review.

Images (in order):
0 = full canvas (post first-pass fix)
1 = top-left crop
2 = top-right crop
3 = bottom-left crop
4 = bottom-right crop

First-pass reassessment context:
{retry_context}

Find **remaining** conversion artifacts in the outer padding that the first pass missed: white/grey L-shaped crop marks, registration triangles, or grey smears where padding meets the card frame. Prioritize corners tied to the remaining defect tags above.

Do NOT flag the card's own border art, frame texture, rules text, or intentional design.

Return JSON only — an array of exactly four objects, one per corner in order TL, TR, BL, BR:
[
  {{
    "corner": "TL",
    "artifact": "white_l_mark|grey_wedge|none",
    "needs_fix": true,
    "fill_bbox_pct": [x0, y0, x1, y1],
    "note": "brief"
  }}
]

Rules for fill_bbox_pct (percent of full image, 0–100):
- Tight box around the artifact pixels only (typically under 8% width and height).
- Must lie in outer padding, not over card art.
- null when needs_fix is false.
- Canvas is {w}x{h} px: y near 0 = top padding, y near {h} = bottom padding.

Card: {card_name}"""


_CORNER_ARC_LOCATE_RETRY_PROMPT = """You inspect a printable card PNG **after** a first fix pass that still failed quality review.

Images (in order):
0 = full canvas (post first-pass fix)
1 = top-left crop
2 = top-right crop
3 = bottom-left crop
4 = bottom-right crop

First-pass reassessment context:
{retry_context}

Find any **remaining** curved arc of white/light pixels at each corner — remnants of the old rounded card corner at the padding/card junction. These are thin quarter-circle arcs, not the card frame texture. Look more carefully than the first pass, especially where remaining defects mention corners, seams, or conversion bleed.

Do NOT flag intentional card border art, gradients, or frame bubbles.

Return JSON only — array of four objects (TL, TR, BL, BR):
[
  {{
    "corner": "TL",
    "needs_fix": true,
    "arc_center_pct": [x, y],
    "arc_radius_px": [inner, outer],
    "note": "brief"
  }}
]

Rules:
- arc_center_pct: center of the quarter-circle in percent of full image (0–100), usually near the card corner (~{ext_pct_x:.1f}%, ~{ext_pct_y:.1f}% for TL).
- arc_radius_px: inner and outer radius in **pixels** (typical arc: inner 3–6, outer 12–22).
- null arc_radius_px when needs_fix is false.
- Canvas is {w}x{h} px.

Card: {card_name}"""


def _format_retry_context_block(ctx: FixRetryContext) -> str:
    lines = [
        f"- Original defects: {', '.join(ctx.original_defects) or 'none'}",
        f"- Still failing / target this pass: {', '.join(ctx.remaining_defects) or 'none'}",
        f"- Reassess verdict: {ctx.verdict}",
        f"- PIL heuristic flags: {', '.join(ctx.heuristic_flags) or 'none'}",
        f"- Review issues: {', '.join(ctx.issues) or 'none'}",
    ]
    if ctx.notes.strip():
        lines.append(f"- Review notes: {ctx.notes.strip()[:300]}")
    if ctx.upload_reason.strip():
        lines.append(f"- Upload blocked because: {ctx.upload_reason.strip()}")
    return "\n".join(lines)


def _card_name_from_path(image_path: str) -> str:
    card_stem = Path(image_path).stem.replace("_before", "")
    if "_" in card_stem:
        return card_stem.split("_", 1)[-1].replace("_", " ")
    return card_stem


def _parse_json_array_blob(raw: str) -> list[dict]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty model response")
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    bracket = re.search(r"\[[\s\S]*\]", text)
    if bracket:
        candidates.append(bracket.group(0))
    last_err: Exception | None = None
    for chunk in candidates:
        try:
            data = json.loads(chunk)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError as e:
            last_err = e
    raise ValueError(f"could not parse JSON array from: {text[:400]!r}") from last_err


def _ollama_reachable(host: str, timeout: float = 2.0) -> bool:
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout)
        return resp.ok
    except requests.RequestException:
        return False


def _pct_bbox_to_px(
    bbox_pct: tuple[float, float, float, float], w: int, h: int
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox_pct
    px0 = max(0, min(w, int(round(x0 / 100.0 * w))))
    py0 = max(0, min(h, int(round(y0 / 100.0 * h))))
    px1 = max(0, min(w, int(round(x1 / 100.0 * w))))
    py1 = max(0, min(h, int(round(y1 / 100.0 * h))))
    if px0 > px1:
        px0, px1 = px1, px0
    if py0 > py1:
        py0, py1 = py1, py0
    return px0, py0, px1, py1


def _coerce_bbox_to_pct(
    bbox: tuple[float, float, float, float], w: int, h: int
) -> tuple[float, float, float, float]:
    """Accept model bboxes as either 0–100 percent or absolute pixels."""
    x0, y0, x1, y1 = bbox
    if max(bbox) > 100:
        use_pixels = True
    elif x1 <= w and y1 <= h and (x1 - x0) <= w * 0.2 and (y1 - y0) <= h * 0.2:
        use_pixels = True
    else:
        use_pixels = False
    if not use_pixels:
        return bbox
    return (
        x0 / w * 100.0,
        y0 / h * 100.0,
        x1 / w * 100.0,
        y1 / h * 100.0,
    )


def _snap_bbox_to_corner(
    corner: str, bbox_pct: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Keep model boxes in the expected canvas quadrant."""
    x0, y0, x1, y1 = bbox_pct
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    if corner == "TL" and (cx > 50 or cy > 50):
        return (0.0, 0.0, 8.0, 8.0)
    if corner == "TR" and (cx < 50 or cy > 50):
        return (92.0, 0.0, 100.0, 8.0)
    if corner == "BL" and (cx > 50 or cy < 50):
        return (0.0, 92.0, 8.0, 100.0)
    if corner == "BR" and (cx < 50 or cy < 50):
        return (92.0, 92.0, 100.0, 100.0)
    return bbox_pct


def _normalize_corner_guide(
    raw: dict, *, w: int | None = None, h: int | None = None
) -> CornerFixGuide:
    corner = str(raw.get("corner", "")).strip().upper()
    if corner not in _CORNERS:
        corner = "TL"
    artifact = str(raw.get("artifact", "none")).strip().lower() or "none"
    needs_fix = bool(raw.get("needs_fix", False))
    bbox_pct: tuple[float, float, float, float] | None = None
    raw_bbox = raw.get("fill_bbox_pct")
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        try:
            bbox_pct = tuple(float(v) for v in raw_bbox)  # type: ignore[assignment]
            if w and h:
                bbox_pct = _coerce_bbox_to_pct(bbox_pct, w, h)
                bbox_pct = _snap_bbox_to_corner(corner, bbox_pct)
        except (TypeError, ValueError):
            bbox_pct = None
    if needs_fix and bbox_pct is None:
        needs_fix = False
    note = str(raw.get("note", "")).strip()
    flagged = artifact != "none" or needs_fix
    return CornerFixGuide(
        corner=corner,
        model_flagged=flagged,
        needs_fix=needs_fix,
        artifact=artifact,
        bbox_pct=bbox_pct,
        note=note,
    )


def locate_corner_fixes(
    image_path: str,
    *,
    card_name: str = "",
    host: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
    retry_context: FixRetryContext | None = None,
) -> list[CornerFixGuide]:
    """Ask a vision model for tight per-corner repaint boxes in the outer padding."""
    host = host or DEFAULT_OLLAMA_HOST
    model = model or DEFAULT_VISION_MODEL
    corner_temps: list[str] = []
    try:
        with Image.open(image_path) as im:
            w, h = im.size
        image_paths = [image_path]
        if suitable_for_corner_crops(w, h):
            corner_temps, image_paths = extract_corner_crops(image_path)
        name = card_name or _card_name_from_path(image_path)
        if retry_context is not None:
            prompt = _CORNER_LOCATE_RETRY_PROMPT.format(
                card_name=name,
                w=w,
                h=h,
                retry_context=_format_retry_context_block(retry_context),
            )
        else:
            prompt = _CORNER_LOCATE_PROMPT.format(
                card_name=name,
                w=w,
                h=h,
            )
        raw = ollama_chat(
            host=host,
            model=model,
            prompt=prompt,
            image_paths=image_paths,
            timeout=timeout,
            temperature=0.1,
        )
        items = _parse_json_array_blob(raw)
        guides = [
            _normalize_corner_guide(item, w=w, h=h)
            for item in items
            if isinstance(item, dict)
        ]
        if len(guides) < 4:
            by_corner = {g.corner: g for g in guides}
            guides = [
                by_corner.get(
                    name,
                    CornerFixGuide(name, False, False, "none", None, "missing from model"),
                )
                for name in _CORNERS
            ]
        return guides
    finally:
        for p in corner_temps:
            try:
                os.remove(p)
            except OSError:
                pass


def _card_corner_center_pct(corner: str, w: int, h: int, ext: int) -> tuple[float, float]:
    if corner == "TL":
        return (ext / w * 100.0, ext / h * 100.0)
    if corner == "TR":
        return ((w - ext) / w * 100.0, ext / h * 100.0)
    if corner == "BL":
        return (ext / w * 100.0, (h - ext) / h * 100.0)
    return ((w - ext) / w * 100.0, (h - ext) / h * 100.0)


def _default_arc_radius(ext: int) -> tuple[float, float]:
    return (3.0, min(18.0, float(ext + 6)))


def _center_near_corner(
    corner: str,
    center_pct: tuple[float, float],
    w: int,
    h: int,
    ext: int,
    *,
    tol_pct: float = 18.0,
) -> bool:
    expected = _card_corner_center_pct(corner, w, h, ext)
    return (
        abs(center_pct[0] - expected[0]) <= tol_pct
        and abs(center_pct[1] - expected[1]) <= tol_pct
    )


def _normalize_arc_guide(
    raw: dict, *, w: int, h: int, ext: int
) -> CornerArcGuide:
    corner = str(raw.get("corner", "")).strip().upper()
    if corner not in _CORNERS:
        corner = "TL"
    needs_fix = bool(raw.get("needs_fix", False))
    center_pct = _card_corner_center_pct(corner, w, h, ext)
    raw_center = raw.get("arc_center_pct")
    if isinstance(raw_center, (list, tuple)) and len(raw_center) == 2:
        try:
            cx, cy = float(raw_center[0]), float(raw_center[1])
            if max(cx, cy) > 100:
                cx = cx / w * 100.0
                cy = cy / h * 100.0
            candidate = (cx, cy)
            if _center_near_corner(corner, candidate, w, h, ext):
                center_pct = candidate
        except (TypeError, ValueError):
            pass

    r_inner, r_outer = _default_arc_radius(ext)
    raw_radius = raw.get("arc_radius_px") or raw.get("arc_radius_pct")
    if isinstance(raw_radius, (list, tuple)) and len(raw_radius) == 2:
        try:
            ri, ro = float(raw_radius[0]), float(raw_radius[1])
            if max(ri, ro) <= 100:
                r_inner, r_outer = max(1.0, ri), max(ri + 2.0, ro)
            else:
                scale = min(w, h) / 100.0
                r_inner, r_outer = ri * scale, ro * scale
        except (TypeError, ValueError):
            pass
    r_inner = max(2.0, min(r_inner, ext))
    r_outer = max(r_inner + 3.0, r_outer, _default_arc_radius(ext)[1])
    r_outer = min(r_outer, 18.0, ext + _corner_apex_reach(ext) + 4)

    note = str(raw.get("note", "")).strip()
    if needs_fix and r_outer <= 0:
        needs_fix = False
    return CornerArcGuide(
        corner=corner,
        needs_fix=needs_fix,
        center_pct=center_pct,
        radius_inner=r_inner,
        radius_outer=r_outer,
        note=note,
    )


def locate_corner_arcs(
    image_path: str,
    *,
    card_name: str = "",
    host: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
    retry_context: FixRetryContext | None = None,
) -> list[CornerArcGuide]:
    """Second vision pass: quarter-circle arc remnants at the card corners."""
    host = host or DEFAULT_OLLAMA_HOST
    model = model or DEFAULT_VISION_MODEL
    corner_temps: list[str] = []
    try:
        with Image.open(image_path) as im:
            w, h = im.size
        ext = extension_width(w, h)
        image_paths = [image_path]
        if suitable_for_corner_crops(w, h):
            corner_temps, image_paths = extract_corner_crops(image_path)
        tl_pct = _card_corner_center_pct("TL", w, h, ext)
        name = card_name or _card_name_from_path(image_path)
        if retry_context is not None:
            prompt = _CORNER_ARC_LOCATE_RETRY_PROMPT.format(
                card_name=name,
                w=w,
                h=h,
                ext_pct_x=tl_pct[0],
                ext_pct_y=tl_pct[1],
                retry_context=_format_retry_context_block(retry_context),
            )
        else:
            prompt = _CORNER_ARC_LOCATE_PROMPT.format(
                card_name=name,
                w=w,
                h=h,
                ext_pct_x=tl_pct[0],
                ext_pct_y=tl_pct[1],
            )
        raw = ollama_chat(
            host=host,
            model=model,
            prompt=prompt,
            image_paths=image_paths,
            timeout=timeout,
            temperature=0.1,
        )
        items = _parse_json_array_blob(raw)
        guides = [
            _normalize_arc_guide(item, w=w, h=h, ext=ext)
            for item in items
            if isinstance(item, dict)
        ]
        if len(guides) < 4:
            by_corner = {g.corner: g for g in guides}
            guides = [
                by_corner.get(
                    name,
                    CornerArcGuide(
                        name,
                        False,
                        _card_corner_center_pct(name, w, h, ext),
                        *_default_arc_radius(ext),
                        "missing from model",
                    ),
                )
                for name in _CORNERS
            ]
        return guides
    finally:
        for p in corner_temps:
            try:
                os.remove(p)
            except OSError:
                pass


def _pct_center_to_px(
    center_pct: tuple[float, float], w: int, h: int
) -> tuple[int, int]:
    cx, cy = center_pct
    return (
        max(0, min(w - 1, int(round(cx / 100.0 * w)))),
        max(0, min(h - 1, int(round(cy / 100.0 * h)))),
    )


def _in_corner_arc(
    x: int,
    y: int,
    corner: str,
    cx: int,
    cy: int,
    r_inner: float,
    r_outer: float,
) -> bool:
    dx, dy = x - cx, y - cy
    if corner == "TL" and (dx < 0 or dy < 0):
        return False
    if corner == "TR" and (dx > 0 or dy < 0):
        return False
    if corner == "BL" and (dx < 0 or dy > 0):
        return False
    if corner == "BR" and (dx > 0 or dy > 0):
        return False
    r = math.hypot(dx, dy)
    return r_inner <= r <= r_outer


def _near_black_px(px, x: int, y: int, w: int, h: int) -> bool:
    for nx in range(max(0, x - 2), min(w, x + 3)):
        for ny in range(max(0, y - 2), min(h, y + 3)):
            if _brightness(px[nx, ny]) < 40:
                return True
    return False


def _arc_artifact_pixel(
    p: tuple[int, int, int],
    *,
    style: _CornerPadStyle,
) -> bool:
    br = _brightness(p)
    if br >= 200:
        return True
    if not _is_neutral_grey(p):
        return False
    if style.light:
        return br >= style.ref + 25
    if style.dark:
        return 85 <= br <= 190
    return 120 <= br <= 190


def apply_corner_arc_guides(
    img: Image.Image,
    guides: list[CornerArcGuide],
    *,
    band: int,
    ext: int,
) -> tuple[Image.Image, int, list[str]]:
    """Repaint pixels on a vision-located quarter-circle arc at each card corner."""
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0, []

    repainted = 0
    notes: list[str] = []
    reach = ext + _corner_apex_reach(ext) + 4

    for guide in guides:
        if not guide.needs_fix:
            continue
        cx, cy = _pct_center_to_px(guide.center_pct, w, h)
        r_inner = guide.radius_inner
        r_outer = guide.radius_outer
        x0 = max(0, cx - int(math.ceil(r_outer)) - 1)
        x1 = min(w, cx + int(math.ceil(r_outer)) + 2)
        y0 = max(0, cy - int(math.ceil(r_outer)) - 1)
        y1 = min(h, cy + int(math.ceil(r_outer)) + 2)

        style = _corner_pad_style(px, guide.corner, w, h, ext)
        fill_bg = style.fill

        corner_changed = 0
        candidates = 0
        to_paint: list[tuple[int, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_corner_arc(x, y, guide.corner, cx, cy, r_inner, r_outer):
                    continue
                # Small corner-only zone: padding plus one apex band inside the frame.
                if guide.corner == "TL" and not (x < ext + reach and y < ext + reach):
                    continue
                if guide.corner == "TR" and not (x >= w - ext - reach and y < ext + reach):
                    continue
                if guide.corner == "BL" and not (x < ext + reach and y >= h - ext - reach):
                    continue
                if guide.corner == "BR" and not (
                    x >= w - ext - reach and y >= h - ext - reach
                ):
                    continue
                if _in_footer_text_zone(x, y, w, h, ext):
                    continue
                p = px[x, y][:3]
                if not _near_black_px(px, x, y, w, h):
                    continue
                if not _arc_artifact_pixel(p, style=style):
                    continue
                candidates += 1
                if p != fill_bg:
                    to_paint.append((x, y))
        if candidates == 0 or candidates > 40:
            continue
        for x, y in to_paint:
            px[x, y] = fill_bg
            corner_changed += 1
        if corner_changed:
            repainted += corner_changed
            notes.append(
                f"{guide.corner}: {corner_changed}px arc r={r_inner:.0f}-{r_outer:.0f}"
            )

    return out, repainted, notes


def _vision_artifact_pixel(
    p: tuple[int, int, int],
    ref_bg: tuple[int, int, int],
    *,
    style: _CornerPadStyle,
) -> bool:
    br = _brightness(p)
    ref = _brightness(ref_bg)
    if style.light:
        # Light-grey padding: only bright registration marks, not the padding itself.
        return br >= 200 or br >= ref + 35
    if style.dark:
        if br >= 200:
            return True
        if _is_neutral_grey(p) and br >= max(ref + 35, 80):
            return True
        return br >= 140 and _color_distance(p, ref_bg) > 60
    return br >= 200 or br >= ref + 45


def _expand_bbox_toward_card(
    corner: str,
    bx0: int,
    by0: int,
    bx1: int,
    by1: int,
    *,
    w: int,
    h: int,
    ext: int,
    band: int,
) -> tuple[int, int, int, int]:
    """Artifacts sit where padding meets the card, not always on the image rim."""
    pad = ext + max(band // 2, 8)
    if corner == "TL":
        return (bx0, by0, min(w, bx1 + pad), min(h, by1 + pad))
    if corner == "TR":
        return (max(0, bx0 - pad), by0, bx1, min(h, by1 + pad))
    if corner == "BL":
        return (bx0, max(0, by0 - pad), min(w, bx1 + pad), by1)
    return (max(0, bx0 - pad), max(0, by0 - pad), bx1, by1)


def apply_vision_corner_guides(
    img: Image.Image,
    guides: list[CornerFixGuide],
    *,
    band: int,
    ext: int,
) -> tuple[Image.Image, int, list[str]]:
    """Repaint only within vision-model bboxes; skips heuristic corner boxes."""
    out = img.convert("RGB").copy()
    w, h = out.size
    px = out.load()
    if px is None:
        return out, 0, []

    max_area = max(w * h // 25, ext * ext * 4)
    ring = max(3, min(w, h) // 50)
    repainted = 0
    notes: list[str] = []

    for guide in guides:
        if not guide.needs_fix or guide.bbox_pct is None:
            continue
        bx0, by0, bx1, by1 = _pct_bbox_to_px(guide.bbox_pct, w, h)
        bx0, by0, bx1, by1 = _expand_bbox_toward_card(
            guide.corner, bx0, by0, bx1, by1, w=w, h=h, ext=ext, band=band
        )
        if bx1 <= bx0 or by1 <= by0:
            continue
        if (bx1 - bx0) * (by1 - by0) > max_area:
            notes.append(f"{guide.corner}: skipped oversized bbox")
            continue

        style = _corner_pad_style(px, guide.corner, w, h, ext)
        fill_bg = style.fill

        corner_changed = 0
        for y in range(by0, by1):
            for x in range(bx0, bx1):
                if not (
                    _in_extension(x, y, w, h, ext)
                    or _in_corner_junction(guide.corner, x, y, w, h, ext)
                ):
                    continue
                p = px[x, y][:3]
                if not _vision_artifact_pixel(p, fill_bg, style=style):
                    continue
                if p != fill_bg:
                    px[x, y] = fill_bg
                    corner_changed += 1
        if corner_changed:
            repainted += corner_changed
            notes.append(f"{guide.corner}: {corner_changed}px ({guide.artifact})")

    return out, repainted, notes


def _apply_vision_corner_pipeline(
    working: Image.Image,
    image_path: str,
    *,
    card_name: str,
    host: str,
    model: str,
    band: int,
    ext: int,
    retry_context: FixRetryContext | None = None,
) -> tuple[Image.Image, list[str]]:
    """Vision locate + repaint for L-marks and quarter-circle arcs."""
    notes: list[str] = []
    retry = retry_context is not None
    try:
        guides = locate_corner_fixes(
            image_path,
            card_name=card_name,
            host=host,
            model=model,
            retry_context=retry_context,
        )
        working, repainted, vision_notes = apply_vision_corner_guides(
            working, guides, band=band, ext=ext
        )
        if repainted:
            notes.append(
                f"vision {'retry ' if retry else ''}corner fix: {repainted}px"
            )
        elif any(g.needs_fix for g in guides):
            notes.append("vision: flagged corners but no matching pixels")
        for vn in vision_notes:
            notes.append(f"  {vn}")
        if not any(g.needs_fix for g in guides):
            notes.append("vision: no corner artifacts flagged")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            arc_src = tmp.name
            working.save(arc_src)
        try:
            arc_guides = locate_corner_arcs(
                arc_src,
                card_name=card_name,
                host=host,
                model=model,
                retry_context=retry_context,
            )
            working, arc_px, arc_notes = apply_corner_arc_guides(
                working, arc_guides, band=band, ext=ext
            )
            if arc_px:
                notes.append(
                    f"vision {'retry ' if retry else ''}corner arcs: {arc_px}px"
                )
            for an in arc_notes:
                notes.append(f"  {an}")
        finally:
            try:
                os.remove(arc_src)
            except OSError:
                pass
    except Exception as exc:
        notes.append(f"vision corners unavailable ({exc}); using heuristics")
    return working, notes


def apply_fixes(
    image_path: str,
    defects: list[str],
    *,
    out_path: str | None = None,
    use_vision_corners: bool | None = None,
    ollama_host: str | None = None,
    vision_model: str | None = None,
) -> FixResult:
    """
    Apply in-place printable fixes for the given defect tags.

    All fixable border/corner defects route through the same surgical pipeline:
    repair the wrong-colored side band first (if any), then remove the bright
    corner L-marks. Unknown or unfixable tags are recorded in
    ``FixResult.skipped`` but do not block fixes for other tags.
    """
    tags = [d for d in defects if d in KNOWN_DEFECT_TAGS]
    skipped = [d for d in tags if d in UNFIXABLE]
    to_fix = [d for d in tags if d in FIXABLE]

    img = Image.open(image_path)
    w, h = img.size
    band = _border_band(w, h)
    ext = extension_width(w, h)
    working = img.convert("RGB")
    applied: list[str] = []
    notes: list[str] = []
    pixels_changed = 0

    if to_fix:
        before = working.copy()
        before_px = before.load()
        fade_bottom_card = (
            before_px is not None
            and _fade_bottom_corner_card(before_px, w, h, ext, band)
        )
        full_bleed_corners = (
            _detect_full_bleed_corners(before_px, w, h, ext, band=band)
            if before_px is not None
            else frozenset()
        )
        if full_bleed_corners:
            notes.append(
                f"full-bleed corners (padding-only fixes): {','.join(sorted(full_bleed_corners))}"
            )

        substantial_bleed = _substantial_full_bleed(full_bleed_corners)

        if not substantial_bleed:
            working, retiled, inferred = fix_tiled_band(working)
            if retiled:
                notes.append(f"retiled border band (b={inferred}): {retiled}px")

        working, line_marks, line_px = fix_inset_line_marks(working)
        if line_px:
            notes.append(
                f"inpainted line marks ({'; '.join(line_marks)}): {line_px}px"
            )

        if "border_seam_lines" in to_fix:
            working, seam_px = inpaint_border_seam_lines(working)
            if seam_px:
                notes.append(f"inpainted border seam lines: {seam_px}px")

        if not substantial_bleed:
            working, speckle_px = fix_dark_speckle(working)
            if speckle_px:
                notes.append(f"flattened dark border speckle: {speckle_px}px")

        working, gutter_px = fix_bottom_gutter_corners(
            working, band, full_bleed_corners=full_bleed_corners
        )
        if gutter_px:
            notes.append(f"blackened bottom gutter corners: {gutter_px}px")

        working, tip_px = fix_bottom_corner_gutter_tips(
            working, band, ext, full_bleed_corners=full_bleed_corners
        )
        if tip_px:
            notes.append(f"blended bottom corner gutter tips: {tip_px}px")

        working, speck_px = fix_bottom_corner_specks(
            working, ext, full_bleed_corners=full_bleed_corners
        )
        if speck_px:
            notes.append(f"cleared bottom corner specks: {speck_px}px")

        working, side_fixed = fix_side_border(working, band, ext)
        if side_fixed:
            notes.append(f"recolored side border(s): {', '.join(side_fixed)}")

        corner_extra = 2 if "corner_color_mismatch" in to_fix else 0
        host = ollama_host or DEFAULT_OLLAMA_HOST
        model = vision_model or DEFAULT_VISION_MODEL
        try_vision = (
            use_vision_corners
            if use_vision_corners is not None
            else _ollama_reachable(host)
        )
        if try_vision:
            card_name = _card_name_from_path(image_path)
            working, vision_notes = _apply_vision_corner_pipeline(
                working,
                image_path,
                card_name=card_name,
                host=host,
                model=model,
                band=band,
                ext=ext,
            )
            notes.extend(vision_notes)

        working, pass1_stats = _run_corner_fixup_pass(
            working,
            band,
            ext,
            corner_extra=corner_extra,
            fade_bottom_card=fade_bottom_card,
            full_bleed_corners=full_bleed_corners,
        )
        for label, count in pass1_stats:
            notes.append(f"{label}: {count}px")

        if {"TL", "TR"} - full_bleed_corners:
            working, top_match_px = fix_top_corner_match(working, band, ext)
            if top_match_px:
                notes.append(f"matched top corner border: {top_match_px}px")

            working, top_pad_px = fix_colored_top_corner_padding(working, band, ext)
            if top_pad_px:
                notes.append(f"matched coloured top corner padding: {top_pad_px}px")
        working, cut_px, cut_notes = fix_cut_corner_stretch(
            working,
            band,
            ext,
            fade_bottom_card=fade_bottom_card,
            full_bleed_corners=full_bleed_corners,
        )
        for cn in cut_notes:
            notes.append(f"cut corner stretch — {cn}")
        working, larm_px = fix_corner_l_arm_seams(
            working,
            band,
            ext,
            fade_bottom_card=fade_bottom_card,
            full_bleed_corners=full_bleed_corners,
        )
        if larm_px:
            notes.append(f"cleared corner L-arm seams: {larm_px}px")

        # Hard guard: never let any step whiten footer/credit text.
        reverted = guard_no_text_whitening(before, working, ext)
        if reverted:
            notes.append(f"reverted text whitening: {reverted}px")

        # Hard guard: never blacken bright card content (text boxes, P/T, frames).
        blackened = guard_no_content_blackening(
            before, working, ext, band=band, full_bleed_corners=full_bleed_corners
        )
        if blackened:
            notes.append(f"reverted content blackening: {blackened}px")

        lightened = guard_no_corner_lightening(before, working, ext, band=band)
        if lightened:
            notes.append(f"reverted corner lightening on content: {lightened}px")

        working, pass2_stats = _run_corner_fixup_pass(
            working,
            band,
            ext,
            corner_extra=corner_extra,
            fade_bottom_card=fade_bottom_card,
            full_bleed_corners=full_bleed_corners,
        )
        for label, count in pass2_stats:
            notes.append(f"corner pass 2 — {label}: {count}px")

        working, top_pad_px2 = fix_colored_top_corner_padding(working, band, ext)
        if top_pad_px2:
            notes.append(
                f"matched coloured top corner padding (pass 2): {top_pad_px2}px"
            )

        if fade_bottom_card and not {"BL", "BR"} <= full_bleed_corners:
            working, fade_edge_px = fix_fade_bottom_edge_stretch(
                working, band, ext, fade_bottom_card=fade_bottom_card
            )
            if fade_edge_px:
                notes.append(f"stretched fade bottom edge: {fade_edge_px}px")

        # We attempted the requested fixable defects via the corner/border pipeline.
        applied = list(to_fix)
        bpx, apx = before.load(), working.load()
        if bpx is not None and apx is not None:
            pixels_changed = sum(
                1
                for y in range(h)
                for x in range(w)
                if bpx[x, y] != apx[x, y]
            )

    dest = out_path or image_path
    working.convert("RGB").save(dest, "PNG")

    if skipped:
        notes.append(f"skipped unfixable: {', '.join(skipped)}")

    return FixResult(
        out_path=dest,
        applied=applied,
        skipped=skipped,
        notes=notes,
        pixels_changed=pixels_changed,
    )


def apply_guided_retry_fixes(
    image_path: str,
    defects: list[str],
    retry_context: FixRetryContext,
    *,
    out_path: str | None = None,
    ollama_host: str | None = None,
    vision_model: str | None = None,
) -> FixResult:
    """
    Second pass on an already-fixed PNG using reassess feedback for vision prompts.

    Does not re-run the full first-pass heuristic pipeline; vision retry plus
    targeted heuristics for the remaining defect tags only.
    """
    tags = [d for d in defects if d in KNOWN_DEFECT_TAGS]
    skipped = [d for d in tags if d in UNFIXABLE]
    to_fix = [d for d in tags if d in FIXABLE]

    img = Image.open(image_path)
    w, h = img.size
    band = _border_band(w, h)
    ext = extension_width(w, h)
    working = img.convert("RGB")
    applied: list[str] = []
    notes: list[str] = ["guided retry pass"]
    pixels_changed = 0

    if not to_fix:
        dest = out_path or image_path
        working.convert("RGB").save(dest, "PNG")
        return FixResult(
            out_path=dest,
            applied=applied,
            skipped=skipped,
            notes=notes + ["no fixable defects for retry"],
            pixels_changed=0,
        )

    before = working.copy()
    before_px = before.load()
    fade_bottom_card = (
        before_px is not None
        and _fade_bottom_corner_card(before_px, w, h, ext, band)
    )
    full_bleed_corners = (
        _detect_full_bleed_corners(before_px, w, h, ext, band=band)
        if before_px is not None
        else frozenset()
    )
    if full_bleed_corners:
        notes.append(
            f"retry full-bleed corners: {','.join(sorted(full_bleed_corners))}"
        )
    host = ollama_host or DEFAULT_OLLAMA_HOST
    model = vision_model or DEFAULT_VISION_MODEL
    card_name = _card_name_from_path(image_path)

    working, vision_notes = _apply_vision_corner_pipeline(
        working,
        image_path,
        card_name=card_name,
        host=host,
        model=model,
        band=band,
        ext=ext,
        retry_context=retry_context,
    )
    notes.extend(vision_notes)

    seam_tags = {"border_seam_lines", "conversion_bleed"}
    if seam_tags & set(to_fix):
        working, seam_px = inpaint_border_seam_lines(working)
        if seam_px:
            notes.append(f"retry inpainted border seam lines: {seam_px}px")
        working, line_marks, line_px = fix_inset_line_marks(working)
        if line_px:
            notes.append(
                f"retry inpainted line marks ({'; '.join(line_marks)}): {line_px}px"
            )
        working, side_fixed = fix_side_border(working, band, ext)
        if side_fixed:
            notes.append(f"retry recolored side border(s): {', '.join(side_fixed)}")

    corner_extra = 2 if "corner_color_mismatch" in to_fix else 0
    working, pass1_stats = _run_corner_fixup_pass(
        working,
        band,
        ext,
        corner_extra=corner_extra,
        fade_bottom_card=fade_bottom_card,
        full_bleed_corners=full_bleed_corners,
    )
    for label, count in pass1_stats:
        notes.append(f"retry {label}: {count}px")

    if "corner_color_mismatch" in to_fix:
        working, top_match_px = fix_top_corner_match(working, band, ext)
        if top_match_px:
            notes.append(f"retry matched top corner border: {top_match_px}px")
        working, top_pad_px = fix_colored_top_corner_padding(working, band, ext)
        if top_pad_px:
            notes.append(
                f"retry matched coloured top corner padding: {top_pad_px}px"
            )
        working, cut_px, cut_notes = fix_cut_corner_stretch(
            working,
            band,
            ext,
            fade_bottom_card=fade_bottom_card,
            full_bleed_corners=full_bleed_corners,
        )
        for cn in cut_notes:
            notes.append(f"retry cut corner stretch — {cn}")
        working, larm_px = fix_corner_l_arm_seams(
            working,
            band,
            ext,
            fade_bottom_card=fade_bottom_card,
            full_bleed_corners=full_bleed_corners,
        )
        if larm_px:
            notes.append(f"retry cleared corner L-arm seams: {larm_px}px")

    reverted = guard_no_text_whitening(before, working, ext)
    if reverted:
        notes.append(f"reverted text whitening: {reverted}px")

    blackened = guard_no_content_blackening(
        before, working, ext, band=band, full_bleed_corners=full_bleed_corners
    )
    if blackened:
        notes.append(f"reverted content blackening: {blackened}px")

    lightened = guard_no_corner_lightening(before, working, ext, band=band)
    if lightened:
        notes.append(f"reverted corner lightening on content: {lightened}px")

    working, pass2_stats = _run_corner_fixup_pass(
        working,
        band,
        ext,
        corner_extra=corner_extra,
        fade_bottom_card=fade_bottom_card,
        full_bleed_corners=full_bleed_corners,
    )
    for label, count in pass2_stats:
        notes.append(f"retry corner pass 2 — {label}: {count}px")

    working, top_pad_px2 = fix_colored_top_corner_padding(working, band, ext)
    if top_pad_px2:
        notes.append(
            f"retry matched coloured top corner padding (pass 2): {top_pad_px2}px"
        )

    working, fade_edge_px = fix_fade_bottom_edge_stretch(
        working, band, ext, fade_bottom_card=fade_bottom_card
    )
    if fade_edge_px:
        notes.append(f"retry stretched fade bottom edge: {fade_edge_px}px")

    applied = list(to_fix)
    bpx, apx = before.load(), working.load()
    if bpx is not None and apx is not None:
        pixels_changed = sum(
            1 for y in range(h) for x in range(w) if bpx[x, y] != apx[x, y]
        )

    dest = out_path or image_path
    working.convert("RGB").save(dest, "PNG")

    if skipped:
        notes.append(f"skipped unfixable: {', '.join(skipped)}")

    return FixResult(
        out_path=dest,
        applied=applied if pixels_changed else [],
        skipped=skipped,
        notes=notes,
        pixels_changed=pixels_changed,
    )


def parse_defect_tags(comment: str) -> list[str]:
    """Extract known defect tags from a bot comment string."""
    return [tag for tag in KNOWN_DEFECT_TAGS if tag in comment]
