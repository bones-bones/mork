"""
Border prep transform: arc-aware corner stretch + edge stretch.

This is the production border transform — ``download_and_upload_images_gcs.py``'s
``prepare_card_for_printing`` and ``process_printable_card.py`` both delegate here.
Padding fill strategy:

  1. Paste the source card centered on a larger canvas (same border ladder).
  2. Detect the card's rounded frame-corner radius at each inner corner.
  3. Fill top / bottom / left / right bands by stretching the nearest card edge.
     4. Sample a quarter-circle just inside each card corner, then stretch that colour
     radially through each outer padding L-corner to the image edge.

Does not upload or touch sheets — local file in, PNG out.

Example:
  python scripts/prepare_card_for_printing_stretch.py card.png
  python scripts/prepare_card_for_printing_stretch.py card.png -o card_prepared.png
  python scripts/prepare_card_for_printing_stretch.py card.png --highlight-samples
  python scripts/prepare_card_for_printing_stretch.py card.png --highlight-arc
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import mork_repo_root  # noqa: F401

_scripts = str(Path(__file__).resolve().parent)
if _scripts in sys.path:
    sys.path.remove(_scripts)
sys.path.insert(0, _scripts)

from PIL import Image, ImageDraw
from printable_image_fixes import (
    _color_distance,
    _corner_box,
    _corner_l_arm_segments,
    _detect_full_bleed_corners,
    _in_corner_junction,
    _is_neutral_grey,
    _on_corner_gutter_seam,
    _substantial_full_bleed,
    _wedge_offsets,
    _wedge_xy,
)
from printable_image_qa import _detect_border_seam_lines, inpaint_border_seam_lines

_CORNERS = ("TL", "TR", "BL", "BR")


def _brightness(p: tuple[int, ...]) -> int:
    return (p[0] + p[1] + p[2]) // 3


def _card_corner_xy(corner: str, u: float, v: float, w: int, h: int, ext: int) -> tuple[int, int]:
    """Map distances into the card from the inner frame corner (ext, ext) etc."""
    if corner == "TL":
        return (int(round(ext + u)), int(round(ext + v)))
    if corner == "TR":
        return (int(round(w - ext - 1 - u)), int(round(ext + v)))
    if corner == "BL":
        return (int(round(ext + u)), int(round(h - ext - 1 - v)))
    return (int(round(w - ext - 1 - u)), int(round(h - ext - 1 - v)))


def _clamp_xy(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))


_CORNERS = ("TL", "TR", "BL", "BR")


def _arc_detect_r_max(ext: int, *, bordered: bool = False) -> int:
    """Search limit for frame-corner radius (full-bleed corners can exceed ext)."""
    if bordered:
        # Bordered cards: the print round sits near the ext line, not deep in frame art.
        return ext + max(4, min(8, ext // 2))
    return ext + max(16, ext // 2 + 8)


def _detect_card_corner_arc(
    px, corner: str, w: int, h: int, ext: int, *, bordered: bool = False
) -> float:
    """
    Estimate rounded frame-corner radius on the pasted card (inside the card).

    Looks for a colour step just inside each inner corner along a quarter circle.
    """
    best_r = 0.0
    best_score = 0.0
    r_max = _arc_detect_r_max(ext, bordered=bordered)
    candidates: list[tuple[int, float]] = []
    for ri in range(4, int(r_max) + 1):
        score = 0.0
        hits = 0
        for step in range(8, 28):
            t = step / 28.0 * (math.pi / 2.0)
            cu, cv = math.cos(t), math.sin(t)
            ui, vi = (ri - 2) * cu, (ri - 2) * cv
            uo, vo = (ri + 3) * cu, (ri + 3) * cv
            iix, iiy = _clamp_xy(*_card_corner_xy(corner, ui, vi, w, h, ext), w, h)
            oox, ooy = _clamp_xy(*_card_corner_xy(corner, uo, vo, w, h, ext), w, h)
            diff = _color_distance(px[iix, iiy][:3], px[oox, ooy][:3])
            if diff > 18:
                score += diff
                hits += 1
        if hits >= 4 and score >= 80:
            candidates.append((ri, score))
            if score > best_score:
                best_score = score
                best_r = float(ri)
    if not candidates:
        return 0.0
    # Prefer the largest radius that still sees a strong edge (avoids r≈6 on full-bleed).
    threshold = best_score * 0.65
    good = [float(r) for r, s in candidates if s >= threshold]
    return max(good) if good else best_r


def _extend_symmetric_full_bleed(
    full_bleed: frozenset[str], per: dict[str, float], ext: int
) -> frozenset[str]:
    """Bottom inner-corner samples sit on the footer; mirror top full-bleed detection."""
    if not {"TL", "TR"}.issubset(full_bleed):
        return full_bleed
    top_r = max(per.get("TL", 0.0), per.get("TR", 0.0))
    if top_r >= ext - 4:
        return frozenset(full_bleed | {"BL", "BR"})
    return full_bleed


def _resolve_shared_corner_radius(
    px, w: int, h: int, ext: int
) -> tuple[float, dict[str, float], frozenset[str]]:
    """
    One frame-corner radius for the whole card.

    Per-corner detection can misread a single corner (e.g. dark footer at BR);
    arced cards share the same round, so use the largest confident detection.
    Full-bleed cards: derive radius from top corners (bottom sees footer contrast).

    Bordered cards: a large radius often marks the *inner* border/art step (e.g.
    Whale Visions at 251px detecting r≈18 into sky). Prefer the smaller outer
    print-round cluster when detections are clearly bimodal.
    """
    full_bleed_pre = _detect_full_bleed_corners(px, w, h, ext, band=ext)
    bordered = not _substantial_full_bleed(full_bleed_pre)
    per = {
        corner: _detect_card_corner_arc(px, corner, w, h, ext, bordered=bordered)
        for corner in _CORNERS
    }
    full_bleed = _extend_symmetric_full_bleed(full_bleed_pre, per, ext)
    positive = [r for r in per.values() if r > 0]
    if not positive:
        return 0.0, per, full_bleed
    if _substantial_full_bleed(full_bleed):
        top_r = max(per.get("TL", 0.0), per.get("TR", 0.0))
        large = [r for r in positive if r >= ext - 4]
        if top_r >= ext - 4:
            return top_r, per, full_bleed
        if large:
            return max(large), per, full_bleed
    if bordered and len(positive) >= 2:
        lo, hi = min(positive), max(positive)
        if hi > lo * 1.8 + 6:
            mid = 0.5 * (lo + hi)
            low = [r for r in positive if r <= mid]
            # Outer print round is the small cluster, when plausible for this scale.
            if low and max(low) <= max(float(ext + 4), 16.0) and (len(low) >= 2 or max(low) >= 5.0):
                return max(low), per, full_bleed
    return max(positive), per, full_bleed


def _card_arc_radius(radius: float) -> float:
    return max(4.0, float(radius))


def _arc_sample_inset(ext: int, radius: float, *, corner: str = "TL") -> float:
    """
    How far inward from the frame round to place the sampling arc.

    Must clear the anti-aliased rim on the rounded edge while staying on the
    solid border mat. Small cards (thin mat in px) need a shallower inset.
    """
    r = _card_arc_radius(radius)
    # AA clear scales gently with pad ladder; never eat most of a small round.
    aa_clear = 2.0 if ext <= 16 else 3.0 if ext <= 24 else 4.0
    inset = min(
        max(aa_clear, r * (0.28 if ext <= 16 else 0.4)),
        max(0.0, r - 2.0),
        max(aa_clear, ext * 0.45),
    )
    if corner in ("BL", "BR"):
        inset = min(max(0.0, r - 2.0), inset + (0.5 if ext <= 16 else 1.0))
    return inset


def _arc_center(corner: str, ext: int, radius: float, w: int, h: int) -> tuple[float, float]:
    """Center of the card frame's outer rounded corner (vertex at inner frame corner)."""
    r = _card_arc_radius(radius)
    if corner == "TL":
        return ext + r, ext + r
    if corner == "TR":
        return w - ext - 1 - r, ext + r
    if corner == "BL":
        return ext + r, h - ext - 1 - r
    return w - ext - 1 - r, h - ext - 1 - r


def _sample_arc_radius(radius: float, ext: int, *, corner: str = "TL") -> float:
    """Sampling arc just inside the detected outer round (past AA, on solid mat)."""
    r = _card_arc_radius(radius)
    inset = _arc_sample_inset(ext, radius, corner=corner)
    return max(1.5, r - inset)


def _is_bright_registration(p: tuple[int, int, int]) -> bool:
    return _is_neutral_grey(p) and _brightness(p) >= 200


def _is_arc_rim_fringe(p: tuple[int, int, int], mat: tuple[int, int, int]) -> bool:
    """
    Anti-aliased rim along the rounded frame edge — pale (or dark) fringe that
    must not be stretched into the corner wedge.
    """
    pb, mb = _brightness(p), _brightness(mat)
    if _color_distance(p, mat) < 18:
        return False
    # Dark mat (typical black border): skip pale/mid grey AA (even ~40–70).
    if mb < 80:
        if _is_neutral_grey(p) and pb >= max(35, mb + 25):
            return True
        if _color_distance(p, (255, 255, 255)) <= 40:
            return True
        return pb >= mb + 30
    # Light mat (white / pale border): skip darker AA fringes.
    if mb > 200:
        if _is_neutral_grey(p) and pb <= min(180, mb - 35):
            return True
        return pb <= mb - 45
    # Mid-tone mats: treat strong brightness swings as rim.
    return abs(pb - mb) >= 50 and _is_neutral_grey(p)


def _is_padding_registration(p: tuple[int, int, int]) -> bool:
    """White/grey crop ticks in outer padding (MTG.Design etc.)."""
    if _is_bright_registration(p):
        return True
    return max(p) - min(p) <= 12 and _brightness(p) >= 215


def _is_l_arm_pixel(p: tuple[int, int, int]) -> bool:
    """Crop/registration mark pixel including grey gradient tails."""
    if max(p) - min(p) > 45:
        return False
    return _brightness(p) >= 100


def _is_faint_l_arm_pixel(p: tuple[int, int, int]) -> bool:
    """Grey registration tails just below the main L-arm cutoff."""
    if max(p) - min(p) > 45:
        return False
    return _brightness(p) >= 90


def _expand_rect(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    pad: int,
    w: int,
    h: int,
) -> tuple[int, int, int, int]:
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(w, x1 + pad),
        min(h, y1 + pad),
    )


def _strip_line_score(
    px,
    xs: range,
    ys: range,
    w: int,
    h: int,
    ext: int,
) -> float:
    total = 0
    bright = 0
    for y in ys:
        for x in xs:
            if _on_pasted_card(x, y, w, h, ext):
                continue
            total += 1
            if _is_l_arm_pixel(px[x, y][:3]):
                bright += 1
    return bright / total if total else 0.0


def _segment_to_rect(
    axis: str,
    fixed: int,
    start: int,
    end: int,
    *,
    thickness: int,
    w: int,
    h: int,
) -> tuple[int, int, int, int]:
    """Expand a 1D L-arm segment into a paint rectangle."""
    half = max(1, thickness // 2)
    if axis == "h":
        return (
            max(0, start),
            max(0, fixed - half),
            min(w, end),
            min(h, fixed + half + 1),
        )
    return (
        max(0, fixed - half),
        max(0, start),
        min(w, fixed + half + 1),
        min(h, end),
    )


def _rect_padding_pixels(
    px,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int]:
    """Count padding pixels in a rect and how many look like registration marks."""
    bright = 0
    total = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _on_pasted_card(x, y, w, h, ext):
                continue
            total += 1
            if _is_l_arm_pixel(px[x, y][:3]):
                bright += 1
    return bright, total


def _longest_bright_run(
    scores: list[float],
    *,
    threshold: float,
    max_thickness: int,
) -> tuple[tuple[int, int] | None, float]:
    best: tuple[int, int] | None = None
    best_avg = 0.0
    i = 0
    n = len(scores)
    while i < n:
        while i < n and scores[i] < threshold:
            i += 1
        j = i
        while j < n and scores[j] >= threshold:
            j += 1
        run = j - i
        if 1 <= run <= max_thickness:
            avg = sum(scores[i:j]) / run
            if avg > best_avg:
                best = (i, j)
                best_avg = avg
        i = j
    return best, best_avg


def _detect_padding_l_arm_rects(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
    reach: int,
) -> list[tuple[int, int, int, int]]:
    """
    Find crop-tick L arms in the two padding strips adjacent to each corner.

    Scans top/left (etc.) bands for bright column and row runs, returns full-span
    paint rectangles with a small margin.
    """
    max_thick = max(8, ext // 4)
    min_score = 0.28
    pad = max(2, ext // 8)
    rects: list[tuple[int, int, int, int]] = []

    def add_col_rect(x0: int, x1: int, y0: int, y1: int) -> None:
        rects.append(_expand_rect(x0, y0, x1, y1, pad=pad, w=w, h=h))

    def add_row_rect(x0: int, x1: int, y0: int, y1: int) -> None:
        rects.append(_expand_rect(x0, y0, x1, y1, pad=pad, w=w, h=h))

    if corner == "TL":
        col_scores = [
            _strip_line_score(px, range(x, x + 1), range(ext), w, h, ext) for x in range(reach)
        ]
        run, avg = _longest_bright_run(col_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            add_col_rect(run[0], run[1], 0, ext)

        row_scores = [
            _strip_line_score(px, range(reach), range(y, y + 1), w, h, ext) for y in range(ext)
        ]
        run, avg = _longest_bright_run(row_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            add_row_rect(0, reach, run[0], run[1])

        side_row_scores = [
            _strip_line_score(px, range(ext), range(y, y + 1), w, h, ext) for y in range(ext, reach)
        ]
        run, avg = _longest_bright_run(
            side_row_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            add_row_rect(0, ext, run[0] + ext, run[1] + ext)

        side_col_scores = [
            _strip_line_score(px, range(x, x + 1), range(ext, reach), w, h, ext) for x in range(ext)
        ]
        run, avg = _longest_bright_run(
            side_col_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            add_col_rect(run[0], run[1], ext, reach)

    elif corner == "TR":
        col_scores = [
            _strip_line_score(px, range(x, x + 1), range(ext), w, h, ext)
            for x in range(w - reach, w)
        ]
        run, avg = _longest_bright_run(col_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            x0 = w - reach + run[0]
            add_col_rect(x0, x0 + (run[1] - run[0]), 0, ext)

        row_scores = [
            _strip_line_score(px, range(w - reach, w), range(y, y + 1), w, h, ext)
            for y in range(ext)
        ]
        run, avg = _longest_bright_run(row_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            add_row_rect(w - reach, w, run[0], run[1])

        side_row_scores = [
            _strip_line_score(px, range(w - ext, w), range(y, y + 1), w, h, ext)
            for y in range(ext, reach)
        ]
        run, avg = _longest_bright_run(
            side_row_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            add_row_rect(w - ext, w, run[0] + ext, run[1] + ext)

        side_col_scores = [
            _strip_line_score(px, range(x, x + 1), range(ext, reach), w, h, ext)
            for x in range(w - ext, w)
        ]
        run, avg = _longest_bright_run(
            side_col_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            x0 = w - ext + run[0]
            add_col_rect(x0, x0 + (run[1] - run[0]), ext, reach)

    elif corner == "BL":
        col_scores = [
            _strip_line_score(px, range(x, x + 1), range(h - ext, h), w, h, ext)
            for x in range(reach)
        ]
        run, avg = _longest_bright_run(col_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            add_col_rect(run[0], run[1], h - ext, h)

        row_scores = [
            _strip_line_score(px, range(reach), range(y, y + 1), w, h, ext)
            for y in range(h - ext, h)
        ]
        run, avg = _longest_bright_run(row_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            add_row_rect(0, reach, run[0], run[1])

        side_row_scores = [
            _strip_line_score(px, range(ext), range(y, y + 1), w, h, ext)
            for y in range(h - reach, h - ext)
        ]
        run, avg = _longest_bright_run(
            side_row_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            add_row_rect(0, ext, h - reach + run[0], h - reach + run[1])

        side_col_scores = [
            _strip_line_score(px, range(x, x + 1), range(h - reach, h - ext), w, h, ext)
            for x in range(ext)
        ]
        run, avg = _longest_bright_run(
            side_col_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            add_col_rect(run[0], run[1], h - reach, h - ext)

    elif corner == "BR":
        col_scores = [
            _strip_line_score(px, range(x, x + 1), range(h - ext, h), w, h, ext)
            for x in range(w - reach, w)
        ]
        run, avg = _longest_bright_run(col_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            x0 = w - reach + run[0]
            add_col_rect(x0, x0 + (run[1] - run[0]), h - ext, h)

        row_scores = [
            _strip_line_score(px, range(w - reach, w), range(y, y + 1), w, h, ext)
            for y in range(h - ext, h)
        ]
        run, avg = _longest_bright_run(row_scores, threshold=min_score, max_thickness=max_thick)
        if run and avg >= min_score:
            add_row_rect(w - reach, w, run[0], run[1])

        side_row_scores = [
            _strip_line_score(px, range(w - ext, w), range(y, y + 1), w, h, ext)
            for y in range(h - reach, h - ext)
        ]
        run, avg = _longest_bright_run(
            side_row_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            add_row_rect(w - ext, w, h - reach + run[0], h - reach + run[1])

        side_col_scores = [
            _strip_line_score(px, range(x, x + 1), range(h - reach, h - ext), w, h, ext)
            for x in range(w - ext, w)
        ]
        run, avg = _longest_bright_run(
            side_col_scores, threshold=min_score, max_thickness=max_thick
        )
        if run and avg >= min_score:
            x0 = w - ext + run[0]
            add_col_rect(x0, x0 + (run[1] - run[0]), h - reach, h - ext)

    return rects


def _mop_corner_l_pixels(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
    reach: int,
    fill: tuple[int, int, int],
) -> int:
    """Final pass: any remaining L-arm pixels in the corner padding wedge."""
    changed = 0
    if corner == "TL":
        x0, y0, x1, y1 = 0, 0, reach, reach
    elif corner == "TR":
        x0, y0, x1, y1 = w - reach, 0, w, reach
    elif corner == "BL":
        x0, y0, x1, y1 = 0, h - reach, reach, h
    else:
        x0, y0, x1, y1 = w - reach, h - reach, w, h

    for y in range(y0, y1):
        for x in range(x0, x1):
            if _on_pasted_card(x, y, w, h, ext):
                continue
            if _is_faint_l_arm_pixel(px[x, y][:3]) and px[x, y][:3] != fill:
                px[x, y] = fill
                changed += 1
    return changed


def _paint_padding_rect(
    px,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    w: int,
    h: int,
    ext: int,
    fill: tuple[int, int, int],
) -> int:
    changed = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _on_pasted_card(x, y, w, h, ext):
                continue
            if px[x, y][:3] != fill:
                px[x, y] = fill
                changed += 1
    return changed


def _fill_padding_l_marks(
    px,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int],
) -> int:
    """
    Paint solid rectangles over confident crop/registration L-arms in padding.

    Uses gutter seam geometry plus bright column/row detection for stretched ticks.
    """
    reach = ext + max(24, ext)
    thickness = max(8, ext // 3)
    min_frac = 0.22
    changed = 0
    seen: set[tuple[int, int, int, int]] = set()

    for corner in _CORNERS:
        dynamic = _detect_padding_l_arm_rects(px, corner, w, h, ext, reach)
        for x0, y0, x1, y1 in dynamic:
            if x1 <= x0 or y1 <= y0:
                continue
            key = (x0, y0, x1, y1)
            if key in seen:
                continue
            seen.add(key)
            changed += _paint_padding_rect(px, x0, y0, x1, y1, w, h, ext, bg_rgb)

        for axis, fixed, start, end in _corner_l_arm_segments(corner, w, h, ext):
            x0, y0, x1, y1 = _segment_to_rect(
                axis, fixed, start, end, thickness=thickness, w=w, h=h
            )
            if x1 <= x0 or y1 <= y0:
                continue
            key = (x0, y0, x1, y1)
            if key in seen:
                continue
            bright, total = _rect_padding_pixels(px, x0, y0, x1, y1, w, h, ext)
            if total < 3 or bright / total < min_frac:
                continue
            seen.add(key)
            changed += _paint_padding_rect(px, x0, y0, x1, y1, w, h, ext, bg_rgb)

        changed += _mop_corner_l_pixels(px, corner, w, h, ext, reach, bg_rgb)
    return changed


def _rounded_corner_center(
    corner: str, ext: int, radius: float, w: int, h: int
) -> tuple[float, float]:
    return _arc_center(corner, ext, radius, w, h)


def _point_on_rounded_corner_arc(
    corner: str,
    cx: float,
    cy: float,
    radius: float,
    theta: float,
    *,
    arc_radius: float | None = None,
) -> tuple[int, int]:
    """Point on the sampling arc at angle theta from its center."""
    r = _card_arc_radius(radius) if arc_radius is None else arc_radius
    return (
        int(round(cx + r * math.cos(theta))),
        int(round(cy + r * math.sin(theta))),
    )


def _arc_theta_sweep(corner: str) -> tuple[float, float]:
    """Angle range (start, end) tracing the outer arc into the padding wedge."""
    if corner == "TL":
        return math.pi, math.pi * 1.5
    if corner == "TR":
        return -math.pi * 0.5, 0.0
    if corner == "BL":
        return math.pi * 0.5, math.pi
    return 0.0, math.pi * 0.5


def _clamp_theta_to_arc(corner: str, theta: float) -> float:
    t0, t1 = _arc_theta_sweep(corner)
    if corner in ("TL", "BL") and theta < 0:
        theta += 2 * math.pi
    return max(t0, min(t1, theta))


def _sample_card_arc_point(
    corner: str,
    u_pad: float,
    v_pad: float,
    radius: float,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int]:
    """
    Point on the card's sampling arc for one wedge pixel.

    Radial stretch: angle from round center through the padding pixel, sample on arc.
    """
    cx, cy = _arc_center(corner, ext, radius, w, h)
    x, y = _clamp_xy(*_wedge_xy(corner, u_pad, v_pad, w, h, ext), w, h)
    sample_r = _sample_arc_radius(radius, ext, corner=corner)
    theta = _clamp_theta_to_arc(corner, math.atan2(y - cy, x - cx))
    sx, sy = _point_on_rounded_corner_arc(corner, cx, cy, radius, theta, arc_radius=sample_r)
    return _clamp_xy(sx, sy, w, h)


def _sample_card_arc_point_at_pixel(
    corner: str,
    x: int,
    y: int,
    radius: float,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int]:
    """Project from round center through a padding pixel onto the sampling arc."""
    cx, cy = _arc_center(corner, ext, radius, w, h)
    sample_r = _sample_arc_radius(radius, ext, corner=corner)
    theta = _clamp_theta_to_arc(corner, math.atan2(y - cy, x - cx))
    sx, sy = _point_on_rounded_corner_arc(corner, cx, cy, radius, theta, arc_radius=sample_r)
    return _clamp_xy(sx, sy, w, h)


def _sample_card_arc_colors(
    px,
    corner: str,
    x: int,
    y: int,
    radius: float,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
) -> tuple[int, int, int]:
    """
    Walk sample radii from outer arc inward onto the solid border mat.

    Skips bright registration and anti-aliased rim fringe so pale hairlines on
    the rounded edge are not stretched into the corner wedge.
    """
    cx, cy = _arc_center(corner, ext, radius, w, h)
    theta = _clamp_theta_to_arc(corner, math.atan2(y - cy, x - cx))
    outer_r = _card_arc_radius(radius)
    inner_r = _sample_arc_radius(radius, ext, corner=corner)
    mat = (
        _bottom_mat_color(px, corner, w, h, ext)
        if corner in ("BL", "BR")
        else _top_mat_color(px, corner, w, h, ext)
    )
    # Prefer probes on/inside the mat arc; only skim the outer rim to skip.
    step = max(1.0, (outer_r - inner_r) / 4.0) if outer_r > inner_r else 1.5
    # Walk far enough past AA (often 4–6px) to land on solid mat.
    inward = max(6.0, outer_r * 0.45)
    radii: list[float] = []
    # Start near the intended sample arc, not on the pale outer rim.
    for probe in (inner_r + 0.5, inner_r, inner_r - 1.0):
        if probe >= 1.0 and (not radii or abs(probe - radii[-1]) > 0.4):
            radii.append(probe)
    sr = inner_r - step
    while sr >= max(1.0, outer_r - inward):
        if not radii or abs(sr - radii[-1]) > 0.4:
            radii.append(sr)
        sr -= step
    if not radii:
        radii = [inner_r]

    card_color: tuple[int, int, int] | None = None
    last = mat
    for sample_r in radii:
        sx, sy = _clamp_xy(
            *_point_on_rounded_corner_arc(corner, cx, cy, radius, theta, arc_radius=sample_r),
            w,
            h,
        )
        last = px[sx, sy][:3]
        if bg_rgb is not None and _color_distance(last, bg_rgb) < 35:
            continue
        if _is_bright_registration(last):
            continue
        if _is_arc_rim_fringe(last, mat):
            continue
        # Solid border mat on the arc is the stretch colour we want. Only walk
        # above the footer when the hit is footer-like but not the mat itself
        # (full-bleed bottoms with text sitting on the round).
        if corner in ("BL", "BR") and _looks_like_footer(last, mat):
            if _color_distance(last, mat) < 18:
                card_color = mat
                break
            walked = _walk_card_above_footer(px, sx, sy, w, h, ext, mat)
            if walked is not None and not _is_arc_rim_fringe(walked, mat):
                card_color = walked
                break
            continue
        card_color = last
        break
    if card_color is not None:
        return card_color
    # Prefer solid mat over whatever rim pixel was last seen.
    return mat if _is_arc_rim_fringe(last, mat) or _is_bright_registration(last) else last


def _mat_color_for_corner(px, corner: str, w: int, h: int, ext: int) -> tuple[int, int, int] | None:
    if corner in ("TL", "TR"):
        return _top_mat_color(px, corner, w, h, ext)
    if corner in ("BL", "BR"):
        return _bottom_mat_color(px, corner, w, h, ext)
    return None


def _snap_arc_stretch_to_mat(
    px,
    corner: str,
    color: tuple[int, int, int],
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
    full_bleed: frozenset[str] | None = None,
) -> tuple[int, int, int]:
    """Pull arc samples onto the corner mat colour — avoids grey seams at fill edges."""
    bleed = full_bleed or frozenset()
    mat = _mat_color_for_corner(px, corner, w, h, ext)
    if mat is None:
        return color
    if bg_rgb is not None and _color_distance(color, bg_rgb) < 40:
        return mat
    if _is_bright_registration(color):
        return mat
    if _is_arc_rim_fringe(color, mat):
        return mat
    if _is_neutral_grey(color) and _color_distance(color, mat) > 12:
        if corner in ("BL", "BR") and corner in bleed:
            if _brightness(color) < 200:
                return color
        return mat
    return color


def _top_row_inboard_color(
    px, sx: int, w: int, h: int, ext: int, *, corner: str
) -> tuple[int, int, int]:
    """Walk from card column sx along the top row past white frame."""
    y = ext
    sx = max(ext, min(w - ext - 1, sx))
    for dx in range(max(20, (w - 2 * ext) // 4)):
        cx = sx + dx if corner == "TL" else sx - dx
        if cx < ext or cx >= w - ext:
            break
        c = px[cx, y][:3]
        if _is_bright_registration(c):
            continue
        if _color_distance(c, (255, 255, 255)) <= 25:
            continue
        return c
    return px[sx, y][:3]


def _top_edge_ref_at_arc(
    px,
    corner: str,
    x: int,
    y: int,
    radius: float,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int, int]:
    sx, _sy = _sample_card_arc_point_at_pixel(corner, x, y, radius, w, h, ext)
    return _top_row_inboard_color(px, sx, w, h, ext, corner=corner)


def _top_stripe_color(px, corner: str, w: int, h: int, ext: int) -> tuple[int, int, int]:
    """Dominant top-edge stripe on full-bleed cards (skips white frame + gradients)."""
    y = ext
    skip = max(8, ext // 3)
    span = max(20, (w - 2 * ext) // 3)
    if corner == "TL":
        xs = range(ext + skip, min(w - ext, ext + span))
    else:
        xs = range(w - ext - 1 - skip, max(ext, w - ext - span), -1)
    best: tuple[int, int, int] | None = None
    xs_list = list(xs)
    for i, x in enumerate(xs_list):
        c = px[x, y][:3]
        if _is_bright_registration(c):
            continue
        if _color_distance(c, (255, 255, 255)) <= 25:
            continue
        if max(c) - min(c) < 12 and _brightness(c) >= 225:
            continue
        if i + 1 < len(xs_list):
            nxt = px[xs_list[i + 1], y][:3]
            if _color_distance(c, nxt) > 18:
                continue
        best = c
        break
    if best is not None:
        return best
    return _top_mat_color(px, corner, w, h, ext)


def _top_band_color(
    px,
    corner: str,
    w: int,
    h: int,
    ext: int,
    *,
    full_bleed: bool = False,
) -> tuple[int, int, int]:
    """Top-row colour for corner stretch — inboard stripe on full-bleed cards."""
    if full_bleed:
        return _top_stripe_color(px, corner, w, h, ext)
    return _top_mat_color(px, corner, w, h, ext)


def _is_flag_stripe_color(color: tuple[int, int, int]) -> bool:
    """Saturated flag-band stripe (Trans Rights), not muted corner art."""
    return max(color) - min(color) > 50 and (color[2] > 180 or (color[0] > 200 and color[1] > 130))


def _top_arc_sample_needs_fallback(
    color: tuple[int, int, int],
    bg_rgb: tuple[int, int, int] | None,
) -> bool:
    """Only replace arc samples that clearly missed the top stripe."""
    if bg_rgb is not None and _color_distance(color, bg_rgb) < 40:
        return True
    if _is_bright_registration(color):
        return True
    # Trans-flag pink stripe sampled too deep on the arc.
    if color[0] > 200 and 130 < color[1] < 220 and 150 < color[2] < 220:
        return True
    # Gold / yellow frame bleed on flag tops.
    if color[0] > 200 and color[1] > 180 and color[2] < 170:
        return True
    return False


def _stretch_color_from_card_arc_pixel(
    px,
    corner: str,
    x: int,
    y: int,
    radius: float,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
    full_bleed: frozenset[str] | None = None,
) -> tuple[int, int, int]:
    """Radial stretch from sampling arc inward past registration onto mat colour."""
    bleed = full_bleed or frozenset()
    color = _sample_card_arc_colors(px, corner, x, y, radius, w, h, ext, bg_rgb=bg_rgb)
    if corner in ("TL", "TR") and corner in bleed:
        stripe = _top_stripe_color(px, corner, w, h, ext)
        if not _is_flag_stripe_color(stripe):
            # Illustrated full-bleed tops (e.g. DIY): keep the radial arc sample so
            # corner art stretches through the wedge; only registration falls back.
            if _is_bright_registration(color):
                color = _top_edge_ref_at_arc(px, corner, x, y, radius, w, h, ext)
            return color
        ref = _top_edge_ref_at_arc(px, corner, x, y, radius, w, h, ext)
        edge = _edge_stretch_color(px, corner, x, y, w, h, ext)
        if _top_arc_sample_needs_fallback(color, bg_rgb):
            color = ref
        elif _brightness(color) < 90 and _color_distance(color, ref) > 55:
            color = ref
        elif _color_distance(color, ref) > 55:
            color = ref
        elif _color_distance(edge, stripe) < 40 and _color_distance(color, edge) > 55:
            color = edge
    if corner in ("BL", "BR") and corner in bleed:
        mat = _bottom_mat_color(px, corner, w, h, ext)
        if (
            _in_padding_corner_zone(corner, x, y, w, h, ext)
            and color[2] > max(mat[2] + 45, 80)
            and color[0] < 130
        ):
            color = mat
    color = _snap_arc_stretch_to_mat(px, corner, color, w, h, ext, bg_rgb=bg_rgb, full_bleed=bleed)
    edge = _edge_stretch_color(px, corner, x, y, w, h, ext)
    mat = _mat_color_for_corner(px, corner, w, h, ext)
    # Do not prefer edge stretch when it is the pale AA rim — that recreates
    # the corner hairline the arc sample is meant to avoid.
    if mat is not None and _is_arc_rim_fringe(edge, mat):
        return color
    if _color_distance(color, edge) < 50:
        edge = _snap_arc_stretch_to_mat(
            px, corner, edge, w, h, ext, bg_rgb=bg_rgb, full_bleed=bleed
        )
        return edge
    return color


def _corner_reach(ext: int) -> int:
    return ext + max(12, ext // 2) + 2


def _on_pasted_card(x: int, y: int, w: int, h: int, ext: int) -> bool:
    return ext <= x < w - ext and ext <= y < h - ext


def _in_padding_corner_zone(corner: str, x: int, y: int, w: int, h: int, ext: int) -> bool:
    """Padding in the reach×reach corner box — never onto the pasted card."""
    if _on_pasted_card(x, y, w, h, ext):
        return False
    reach = _corner_reach(ext)
    if corner == "TL":
        return x <= reach and y <= reach
    if corner == "TR":
        return x >= w - 1 - reach and y <= reach
    if corner == "BL":
        return x <= reach and y >= h - 1 - reach
    return x >= w - 1 - reach and y >= h - 1 - reach


def _padding_uv(
    corner: str, x: int, y: int, w: int, h: int, ext: int
) -> tuple[float, float] | None:
    """Wedge offsets for any padding-corner pixel."""
    uv = _wedge_offsets(corner, x, y, w, h, ext)
    if uv is not None:
        return uv
    if not _in_padding_corner_zone(corner, x, y, w, h, ext):
        return None
    if corner == "TL":
        if x >= ext and y < ext:
            return (float(x - ext), float(ext - y))
        if x < ext and y >= ext:
            return (float(ext - x), float(y - ext))
    elif corner == "TR":
        if x < w - ext and y < ext:
            return (float(w - ext - x), float(ext - y))
        if x >= w - ext and y >= ext:
            return (float(x - (w - ext)), float(y - ext))
    elif corner == "BL":
        if x >= ext and y >= h - ext:
            return (float(x - ext), float(y - (h - ext)))
        if x < ext and y >= h - ext:
            return (float(ext - x), float(y - (h - ext)))
        if x < ext and y < h - ext:
            return (float(ext - x), float(h - ext - y))
    else:
        if x >= w - ext and y >= h - ext:
            return (float(x - (w - ext)), float(y - (h - ext)))
        if x < w - ext and y >= h - ext:
            return (float(w - ext - x), float(y - (h - ext)))
        if x >= w - ext and y < h - ext:
            return (float(x - (w - ext)), float(h - ext - y))
    return None


def _tip_cut(ext: int, radius: float) -> float:
    """u+v threshold: padding outside the card round gets arc stretch."""
    r = _card_arc_radius(radius)
    # Pull cutoff cardward so the arc wedge covers registration marks and the
    # L-seam origins at the round's tangent points (not only the outer tip).
    margin = max(8.0, ext * 0.35)
    return max(0.0, ext - r - margin)


def _needs_arc_corner_fill(
    corner: str, x: int, y: int, w: int, h: int, ext: int, radius: float
) -> bool:
    """Outer padding from the card round out to the print corner (arc wedge)."""
    if not _in_padding_corner_zone(corner, x, y, w, h, ext):
        return False
    uv = _padding_uv(corner, x, y, w, h, ext)
    if uv is None:
        return False
    u, v = uv
    return u + v >= _tip_cut(ext, radius)


def _corner_tip_xy(corner: str, w: int, h: int) -> tuple[int, int]:
    if corner == "TL":
        return 0, 0
    if corner == "TR":
        return w - 1, 0
    if corner == "BL":
        return 0, h - 1
    return w - 1, h - 1


def _ray_hit_image_edge(cx: float, cy: float, theta: float, w: int, h: int) -> tuple[int, int]:
    """Project a ray from the arc center to the image boundary."""
    dx, dy = math.cos(theta), math.sin(theta)
    ts: list[float] = []
    if dx > 1e-9:
        ts.append((w - 1 - cx) / dx)
    if dx < -1e-9:
        ts.append((0.0 - cx) / dx)
    if dy > 1e-9:
        ts.append((h - 1 - cy) / dy)
    if dy < -1e-9:
        ts.append((0.0 - cy) / dy)
    positive = [t for t in ts if t > 1e-6]
    if not positive:
        return _clamp_xy(int(round(cx)), int(round(cy)), w, h)
    t = min(positive)
    return _clamp_xy(int(round(cx + t * dx)), int(round(cy + t * dy)), w, h)


def _angle_in_sweep(theta: float, t0: float, t1: float) -> bool:
    """True if theta lies in the directed sweep from t0 to t1 (t1 >= t0)."""
    span = t1 - t0
    if span <= 0:
        return abs((theta - t0) % (2 * math.pi)) < 1e-9
    rel = (theta - t0) % (2 * math.pi)
    return rel <= span + 1e-9


def _narrow_arc_wedge_polygon(
    corner: str,
    cx: float,
    cy: float,
    theta: float,
    half_dtheta: float,
    inner_r: float,
    w: int,
    h: int,
    *,
    apex_theta: float | None = None,
) -> list[tuple[int, int]]:
    """
    Pie-slice from the sample arc out to the image edge / tip.

    Apex on the inward sample arc; outer edge follows ray hits and the image
    tip so the wedge stays several pixels wide at the pad (not a hairline).
    """
    at = theta if apex_theta is None else apex_theta
    th0 = theta - half_dtheta
    th1 = theta + half_dtheta
    sx = cx + inner_r * math.cos(at)
    sy = cy + inner_r * math.sin(at)
    # Start inside the sample arc so pale on-card AA is painted over.
    sx2 = cx + max(1.0, inner_r - 2.5) * math.cos(at)
    sy2 = cy + max(1.0, inner_r - 2.5) * math.sin(at)
    o0 = _ray_hit_image_edge(cx, cy, th0, w, h)
    o1 = _ray_hit_image_edge(cx, cy, th1, w, h)
    tip = _corner_tip_xy(corner, w, h)
    tip_th = math.atan2(tip[1] - cy, tip[0] - cx)
    if corner in ("TL", "BL") and tip_th < 0:
        tip_th += 2 * math.pi
    pts: list[tuple[int, int]] = [
        _clamp_xy(int(round(sx2)), int(round(sy2)), w, h),
        _clamp_xy(int(round(sx)), int(round(sy)), w, h),
        o0,
    ]
    if _angle_in_sweep(tip_th, th0, th1):
        pts.append(tip)
    pts.append(o1)
    # Collapsed outer hits (both rays land on the tip): fan along pad edges.
    if o0 == o1 or (o0 == tip and o1 == tip):
        band = max(8, int(round(math.degrees(half_dtheta) * 2)))
        if corner == "TL":
            pts.extend([(0, min(h - 1, band)), tip, (min(w - 1, band), 0)])
        elif corner == "TR":
            pts.extend([(w - 1, min(h - 1, band)), tip, (max(0, w - 1 - band), 0)])
        elif corner == "BL":
            pts.extend([(0, max(0, h - 1 - band)), tip, (min(w - 1, band), h - 1)])
        else:
            pts.extend(
                [
                    (w - 1, max(0, h - 1 - band)),
                    tip,
                    (max(0, w - 1 - band), h - 1),
                ]
            )
    dedup: list[tuple[int, int]] = []
    for p in pts:
        if not dedup or p != dedup[-1]:
            dedup.append(p)
    if len(dedup) >= 2 and dedup[0] == dedup[-1]:
        dedup.pop()
    return dedup


def _tangent_seam_quads(
    corner: str, cx: float, cy: float, w: int, h: int, ext: int, radius: float
) -> list[tuple[float, list[tuple[int, int]]]]:
    """
    Axis-aligned quads covering pale AA on the straight edges past each round tangent.

    Radial wedges from the arc center miss these L-seam pixels (they sit past the
    tangent, on the card edge row/col). Quads stay on the pad + edge strip only.
    Returns (sample_theta, quad) pairs so colour matches that tangent end.
    """
    band = _corner_reach(ext) + int(_card_arc_radius(radius)) + 16
    icx, icy = int(round(cx)), int(round(cy))
    t0, t1 = _arc_theta_sweep(corner)
    quads: list[tuple[float, list[tuple[int, int]]]] = []
    if corner == "TL":
        # Top edge (t1) past round; left edge (t0) past round.
        quads.append(
            (
                t1,
                [
                    (max(0, icx - 1), 0),
                    (min(w - 1, ext + band), 0),
                    (min(w - 1, ext + band), ext),
                    (max(0, icx - 1), ext),
                ],
            )
        )
        quads.append(
            (
                t0,
                [
                    (0, max(0, icy - 1)),
                    (ext, max(0, icy - 1)),
                    (ext, min(h - 1, ext + band)),
                    (0, min(h - 1, ext + band)),
                ],
            )
        )
    elif corner == "TR":
        quads.append(
            (
                t0,
                [
                    (max(0, w - ext - band), 0),
                    (min(w - 1, icx + 1), 0),
                    (min(w - 1, icx + 1), ext),
                    (max(0, w - ext - band), ext),
                ],
            )
        )
        quads.append(
            (
                t1,
                [
                    (w - 1 - ext, max(0, icy - 1)),
                    (w - 1, max(0, icy - 1)),
                    (w - 1, min(h - 1, ext + band)),
                    (w - 1 - ext, min(h - 1, ext + band)),
                ],
            )
        )
    elif corner == "BL":
        quads.append(
            (
                t0,
                [
                    (max(0, icx - 1), h - 1 - ext),
                    (min(w - 1, ext + band), h - 1 - ext),
                    (min(w - 1, ext + band), h - 1),
                    (max(0, icx - 1), h - 1),
                ],
            )
        )
        quads.append(
            (
                t1,
                [
                    (0, max(0, h - ext - band)),
                    (ext, max(0, h - ext - band)),
                    (ext, min(h - 1, icy + 1)),
                    (0, min(h - 1, icy + 1)),
                ],
            )
        )
    else:  # BR
        quads.append(
            (
                t1,
                [
                    (max(0, w - ext - band), h - 1 - ext),
                    (min(w - 1, icx + 1), h - 1 - ext),
                    (min(w - 1, icx + 1), h - 1),
                    (max(0, w - ext - band), h - 1),
                ],
            )
        )
        quads.append(
            (
                t0,
                [
                    (w - 1 - ext, max(0, h - ext - band)),
                    (w - 1, max(0, h - ext - band)),
                    (w - 1, min(h - 1, icy + 1)),
                    (w - 1 - ext, min(h - 1, icy + 1)),
                ],
            )
        )
    return quads


def _wedge_color_at_theta(
    px,
    corner: str,
    theta: float,
    radius: float,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
    full_bleed: frozenset[str] | None = None,
) -> tuple[int, int, int]:
    """
    Border colour for one arc angle — mat-aware sample on BL/BR vs TL/TR.

    Walks inward from a pad probe along the ray so pale rim AA is skipped.
    """
    mat = _mat_color_for_corner(px, corner, w, h, ext)
    cx, cy = _arc_center(corner, ext, radius, w, h)
    outer_r = _card_arc_radius(radius)
    pad_r = outer_r + max(2.0, ext * 0.5)
    pad_x, pad_y = _clamp_xy(
        int(round(cx + pad_r * math.cos(theta))),
        int(round(cy + pad_r * math.sin(theta))),
        w,
        h,
    )
    color = _sample_card_arc_colors(px, corner, pad_x, pad_y, radius, w, h, ext, bg_rgb=bg_rgb)
    color = _snap_arc_stretch_to_mat(
        px,
        corner,
        color,
        w,
        h,
        ext,
        bg_rgb=bg_rgb,
        full_bleed=full_bleed,
    )
    if mat is not None and (_is_arc_rim_fringe(color, mat) or _is_bright_registration(color)):
        return mat
    return color


def _draw_corner_arc_wedges(
    out: Image.Image,
    w: int,
    h: int,
    ext: int,
    radius: float,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
    full_bleed: frozenset[str] | None = None,
) -> int:
    """
    Draw many narrow arc wedges at each frame corner.

    For each angle on the sample arc: sample that point's border colour, then
    paint a pie-slice from the inward arc out through the AA rim and pad to
    the image edge. Skips full-bleed corners (those keep radial art stretch).
    """
    if radius <= 0:
        return 0
    bleed = full_bleed or frozenset()
    px = out.load()
    if px is None:
        return 0
    draw = ImageDraw.Draw(out)
    changed = 0
    outer_r = _card_arc_radius(radius)
    # Dense colour samples; wedges kept wide enough to cover tip pixels.
    n = max(72, int(outer_r * 8))
    # Pale AA often sits past the round tangents on the straight L-seams
    # (~30° past each end on typical 13px rounds) — overshoot to cover it.
    overshoot = math.radians(38)
    for corner in _CORNERS:
        if corner in bleed:
            continue
        cx, cy = _arc_center(corner, ext, radius, w, h)
        inner_r = _sample_arc_radius(radius, ext, corner=corner)
        tip = _corner_tip_xy(corner, w, h)
        tip_dist = max(1.0, math.hypot(cx - tip[0], cy - tip[1]))
        t0, t1 = _arc_theta_sweep(corner)
        span = (t1 - t0) + 2 * overshoot
        step = span / n
        # ≥~2.5px chord at the tip; heavy overlap so no hairline gaps.
        half = max(step * 1.25, math.atan2(2.5, tip_dist), math.radians(2.5))
        samples: list[tuple[float, float, tuple[int, int, int]]] = []
        for i in range(n + 1):
            th = (t0 - overshoot) + step * i
            th_s = _clamp_theta_to_arc(corner, th)
            color = _wedge_color_at_theta(
                px,
                corner,
                th_s,
                radius,
                w,
                h,
                ext,
                bg_rgb=bg_rgb,
                full_bleed=bleed,
            )
            samples.append((th, th_s, color))
        for th, th_s, color in samples:
            poly = _narrow_arc_wedge_polygon(
                corner,
                cx,
                cy,
                th,
                half,
                inner_r,
                w,
                h,
                apex_theta=th_s,
            )
            if len(poly) < 3:
                continue
            draw.polygon(poly, fill=color)
            changed += 1
        # Extra-wide tangent caps: cover L-seam AA past the round.
        for th_s, th_out in ((t0, t0 - overshoot), (t1, t1 + overshoot)):
            color = _wedge_color_at_theta(
                px,
                corner,
                th_s,
                radius,
                w,
                h,
                ext,
                bg_rgb=bg_rgb,
                full_bleed=bleed,
            )
            poly = _narrow_arc_wedge_polygon(
                corner,
                cx,
                cy,
                0.5 * (th_s + th_out),
                abs(th_out - th_s) * 0.55 + half,
                inner_r,
                w,
                h,
                apex_theta=th_s,
            )
            if len(poly) >= 3:
                draw.polygon(poly, fill=color)
                changed += 1
        # Axis-aligned L-seam strips (radial wedges miss edge AA past tangents).
        for th_s, quad in _tangent_seam_quads(corner, cx, cy, w, h, ext, radius):
            color = _wedge_color_at_theta(
                px,
                corner,
                th_s,
                radius,
                w,
                h,
                ext,
                bg_rgb=bg_rgb,
                full_bleed=bleed,
            )
            if len(quad) >= 3:
                draw.polygon(quad, fill=color)
                changed += 1
    return changed


def _bottom_mat_color(px, corner: str, w: int, h: int, ext: int) -> tuple[int, int, int]:
    """Solid bottom-border colour for corner padding (avoids white frame corners)."""
    iy = h - ext - 1
    span = max(8, (w - 2 * ext) // 4)
    if corner == "BL":
        return px[min(w - ext - 1, ext + span), iy][:3]
    return px[max(ext, w - ext - 1 - span), iy][:3]


def _bottom_round_radius(per_r: float, shared_r: float) -> float:
    """
    Print-corner cutout radius for one bottom corner.

    Per-corner detection sees the small cutout on cards whose frame arc is larger
    (e.g. Trans Rights: frame arc 44, cutout 7); fall back to the shared radius
    capped at a physical maximum.
    """
    if 0.0 < per_r <= 20.0:
        return max(4.0, per_r)
    return min(max(4.0, shared_r), 20.0)


def _cutout_radius_from_alpha(src: Image.Image, corner: str) -> float | None:
    """Cutout radius from source transparency (rounded corners cut into the alpha)."""
    src_px = src.load()
    if src_px is None:
        return None
    sw, sh = src.size
    box = 40
    best = 0
    for dv in range(min(box, sh)):
        for du in range(min(box, sw)):
            if corner == "TL":
                x, y = du, dv
            elif corner == "TR":
                x, y = sw - 1 - du, dv
            elif corner == "BL":
                x, y = du, sh - 1 - dv
            else:
                x, y = sw - 1 - du, sh - 1 - dv
            # Ignore straight card-edge transparency (not a print-corner round).
            if du == 0 or dv == 0:
                continue
            if src_px[x, y][3] < 250:
                best = max(best, max(du, dv) + 1)
    if best > 20:
        return None
    return float(best) if best >= 3 else None


def _baked_white_cutout_radius(px, corner: str, w: int, h: int, ext: int) -> float | None:
    """
    Cutout radius for print rounds baked into the art as white pixels.

    Measures bright pixels near the exact card corner (cutout body + anti-aliased
    rim). Only trustworthy up to a physical cutout size; None when the corner is
    not white-cut (dark art or coloured borders reaching the corner).
    """
    box = 18
    best = 0
    for dv in range(box):
        for du in range(box):
            if corner == "TL":
                x, y = ext + du, ext + dv
            elif corner == "TR":
                x, y = w - ext - 1 - du, ext + dv
            elif corner == "BL":
                x, y = ext + du, h - ext - 1 - dv
            else:
                x, y = w - ext - 1 - du, h - ext - 1 - dv
            p = px[x, y][:3]
            if (
                _brightness(p) >= 150
                and max(p) - min(p) <= 35
                and _color_distance(p, (255, 255, 255)) < 50
            ):
                best = max(best, max(du, dv) + 1)
    return float(best) if 3 <= best <= 20 else None


def _bottom_cutout_radii(
    px,
    src: Image.Image | None,
    w: int,
    h: int,
    ext: int,
    per_radii: dict[str, float],
    shared_r: float,
) -> dict[str, float]:
    """
    Print-corner cutout radius per bottom corner.

    Preference order: source alpha cutout, baked-in white cutout, per-corner /
    shared arc detection capped at a physical maximum.
    """
    out: dict[str, float] = {}
    for corner in ("BL", "BR"):
        r_alpha = _cutout_radius_from_alpha(src, corner) if src is not None else None
        r_white = _baked_white_cutout_radius(px, corner, w, h, ext)
        if r_alpha is not None:
            out[corner] = max(4.0, r_alpha)
        elif r_white is not None:
            out[corner] = max(4.0, r_white)
        elif shared_r > 0:
            out[corner] = _bottom_round_radius(per_radii.get(corner, 0.0), shared_r)
    return out


def _top_cutout_radii(
    px,
    src: Image.Image | None,
    w: int,
    h: int,
    ext: int,
    per_radii: dict[str, float],
    shared_r: float,
) -> dict[str, float]:
    """Print-corner cutout radius per top corner (alpha, baked white, or arc)."""
    out: dict[str, float] = {}
    for corner in ("TL", "TR"):
        r_alpha = _cutout_radius_from_alpha(src, corner) if src is not None else None
        r_white = _baked_white_cutout_radius(px, corner, w, h, ext)
        if r_alpha is not None:
            out[corner] = max(4.0, r_alpha)
        elif r_white is not None:
            out[corner] = max(4.0, r_white)
    if out:
        sym = min(out.values())
        out["TL"] = out["TR"] = sym
    return out


def _fan_color_top(
    px,
    corner: str,
    x: int,
    y: int,
    r_c: float,
    w: int,
    h: int,
    ext: int,
    *,
    full_bleed: frozenset[str],
) -> tuple[int, int, int]:
    """Fan colour for a top-corner cutout pixel."""
    if _is_flag_card(px, w, h, ext) and corner in full_bleed:
        stripe = _top_stripe_color(px, corner, w, h, ext)
        color = _fan_sample_on_round(px, corner, x, y, r_c, w, h, ext)
        if (
            _brightness(color) >= 180
            or _color_distance(color, (255, 255, 255)) < 40
            or _color_distance(color, stripe) > 70
        ):
            return stripe
        return color
    return _fan_sample_on_round(px, corner, x, y, r_c, w, h, ext)


def _fan_fill_top_corner_rounds(
    px,
    src: Image.Image | None,
    w: int,
    h: int,
    ext: int,
    per_radii: dict[str, float],
    shared_r: float,
    *,
    full_bleed: frozenset[str],
) -> int:
    """
    Repaint TL/TR print-corner cutouts by arc fanning.

    Catches opaque white baked into the source (Trans Rights) as well as
    transparent alpha cutouts. Flag cards fan the top stripe/sky colour, not
    gold frame bleed.
    """
    src_px = src.load() if src is not None else None
    sw, sh = src.size if src is not None else (0, 0)
    cutout_radii = _top_cutout_radii(px, src, w, h, ext, per_radii, shared_r)
    changed = 0
    for corner in ("TL", "TR"):
        if corner not in cutout_radii:
            continue
        r_c = cutout_radii[corner]

        zone: set[tuple[int, int]] = set()
        reach = int(r_c) + 4
        if corner == "TL":
            xs, ys = range(ext, ext + reach), range(ext, ext + reach)
        else:
            xs, ys = range(w - ext - reach, w - ext), range(ext, ext + reach)
        for y in ys:
            for x in xs:
                if _on_pasted_card(x, y, w, h, ext) and _outside_card_round(
                    corner, x, y, w, h, ext, r_c
                ):
                    zone.add((x, y))
        if src_px is not None:
            sbox = int(r_c) + 6
            if corner == "TL":
                sxs, sys = range(0, min(sw, sbox)), range(0, min(sh, sbox))
            else:
                sxs, sys = range(max(0, sw - sbox), sw), range(0, min(sh, sbox))
            for sy in sys:
                for sx in sxs:
                    if src_px[sx, sy][3] < 250:
                        zone.add((ext + sx, ext + sy))
                    elif _brightness(src_px[sx, sy][:3]) >= 240:
                        zone.add((ext + sx, ext + sy))

        # Bright rim along top edge past the round (opaque white anti-alias).
        rim = int(r_c) + 5
        if corner == "TL":
            vert = ((ext + du, ext + dv) for dv in range(rim) for du in range(3))
            horiz = ((ext + du, ext + dv) for du in range(rim) for dv in range(3))
        else:
            vert = ((w - ext - 1 - du, ext + dv) for dv in range(rim) for du in range(3))
            horiz = ((w - ext - 1 - du, ext + dv) for du in range(rim) for dv in range(3))
        for x, y in (*vert, *horiz):
            if _brightness(px[x, y][:3]) >= 200:
                zone.add((x, y))

        for x, y in zone:
            color = _fan_color_top(px, corner, x, y, r_c, w, h, ext, full_bleed=full_bleed)
            if px[x, y][:3] != color:
                px[x, y] = color
                changed += 1
    return changed


def _dark_bottom_round_inset(
    px, corner: str, r_c: float, w: int, h: int, ext: int
) -> tuple[int, int, int] | None:
    """
    Black-round detection: colour just inside the card's rounded bottom corner.

    Fans sample angles across the round (same sampling as the fan fill). When
    nearly all hits are dark the whole corner should be that colour; returns the
    darkest hit, else None.
    """
    if r_c <= 0:
        return None
    t0, t1 = _arc_theta_sweep(corner)
    hits = [
        _fan_sample_color(px, corner, t0 + (i / 8.0) * (t1 - t0), r_c, w, h, ext)
        for i in range(1, 8)
    ]
    dark = [c for c in hits if _brightness(c) < 60]
    if len(dark) < 6:
        return None
    return min(dark, key=_brightness)


def _fan_sample_color(
    px,
    corner: str,
    theta: float,
    r_c: float,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int, int]:
    """
    Card colour just inside the print-corner round at one angle.

    Walks inward from the round, skipping white anti-aliased rim and bright
    registration pixels. Falls back to the corner mat colour.
    """
    cx, cy = _arc_center(corner, ext, r_c, w, h)
    mat = (
        _top_mat_color(px, corner, w, h, ext)
        if corner in ("TL", "TR")
        else _bottom_mat_color(px, corner, w, h, ext)
    )
    sr = _card_arc_radius(r_c) - 2.0
    while sr >= 1.0:
        sx, sy = _clamp_xy(
            *_point_on_rounded_corner_arc(corner, cx, cy, r_c, theta, arc_radius=sr),
            w,
            h,
        )
        c = px[sx, sy][:3]
        sr -= 1.5
        if _is_bright_registration(c):
            continue
        if _color_distance(c, (255, 255, 255)) <= 25:
            continue
        if _is_arc_rim_fringe(c, mat):
            continue
        return c
    return mat


def _fan_sample_on_round(
    px,
    corner: str,
    x: int,
    y: int,
    r_c: float,
    w: int,
    h: int,
    ext: int,
) -> tuple[int, int, int]:
    """
    Fan fill for one pixel outside the print-corner round.

    Take the pixel's angle from the round's center and sample just inside the
    round at that angle; stretching those samples outward "fans" the card colour
    through the cutout.
    """
    cx, cy = _arc_center(corner, ext, r_c, w, h)
    theta = _clamp_theta_to_arc(corner, math.atan2(y - cy, x - cx))
    return _fan_sample_color(px, corner, theta, r_c, w, h, ext)


def _fan_fill_bottom_corner_rounds(
    px,
    src: Image.Image | None,
    w: int,
    h: int,
    ext: int,
    per_radii: dict[str, float],
    shared_r: float,
) -> int:
    """
    Repaint the small print-corner cutout zone at BL/BR by arc fanning.

    The zone is every on-card pixel beyond the cutout round (white/anti-aliased
    crescents, baked-in white corners, transparent cutouts). Each pixel gets the
    card colour sampled just inside the round at its own angle — no flood fill,
    so anti-aliased card edges are never crawled.
    """
    src_px = src.load() if src is not None else None
    sw, sh = src.size if src is not None else (0, 0)
    cutout_radii = _bottom_cutout_radii(px, src, w, h, ext, per_radii, shared_r)
    changed = 0
    for corner in ("BL", "BR"):
        if corner not in cutout_radii:
            continue
        r_c = cutout_radii[corner]

        zone: set[tuple[int, int]] = set()
        reach = int(r_c) + 4
        if corner == "BL":
            xs, ys = range(ext, ext + reach), range(h - ext - reach, h - ext)
        else:
            xs, ys = range(w - ext - reach, w - ext), range(h - ext - reach, h - ext)
        for y in ys:
            for x in xs:
                if _on_pasted_card(x, y, w, h, ext) and _outside_card_round(
                    corner, x, y, w, h, ext, r_c
                ):
                    zone.add((x, y))
        if src_px is not None:
            sbox = int(r_c) + 6
            if corner == "BL":
                sxs, sys = range(0, min(sw, sbox)), range(max(0, sh - sbox), sh)
            else:
                sxs, sys = range(max(0, sw - sbox), sw), range(max(0, sh - sbox), sh)
            for sy in sys:
                for sx in sxs:
                    if src_px[sx, sy][3] < 250:
                        zone.add((ext + sx, ext + sy))

        # Black rounds: clamp stray bright samples so the fan stays dark.
        inset = _dark_bottom_round_inset(px, corner, r_c, w, h, ext)

        if inset is not None:
            # Anti-aliased rim continues a few pixels up/along the card edges past
            # the round; clearly-bright edge-band pixels there are cutout residue.
            rim = int(r_c) + 5
            if corner == "BL":
                vert = ((ext + du, h - ext - 1 - dv) for dv in range(rim) for du in range(3))
                horiz = ((ext + du, h - ext - 1 - dv) for du in range(rim) for dv in range(3))
            else:
                vert = (
                    (w - ext - 1 - du, h - ext - 1 - dv) for dv in range(rim) for du in range(3)
                )
                horiz = (
                    (w - ext - 1 - du, h - ext - 1 - dv) for du in range(rim) for dv in range(3)
                )
            for x, y in (*vert, *horiz):
                if _brightness(px[x, y][:3]) >= 80:
                    zone.add((x, y))

        for x, y in zone:
            color = _fan_sample_on_round(px, corner, x, y, r_c, w, h, ext)
            if inset is not None and _brightness(color) >= 60:
                color = inset
            if px[x, y][:3] != color:
                px[x, y] = color
                changed += 1
    return changed


def _is_flag_card(px, w: int, h: int, ext: int) -> bool:
    """Full-bleed flag-stripe cards (e.g. Trans Rights) vs illustrated corners (DIY)."""
    return _is_flag_stripe_color(_top_stripe_color(px, "TL", w, h, ext))


def _looks_like_footer(color: tuple[int, int, int], mat: tuple[int, int, int]) -> bool:
    return _color_distance(color, mat) < 25 or sum(color) < 35


def _walk_card_above_footer(
    px,
    sx: int,
    sy: int,
    w: int,
    h: int,
    ext: int,
    mat: tuple[int, int, int],
    *,
    max_steps: int = 50,
) -> tuple[int, int, int] | None:
    """Step up the card from a footer hit until art/stripe colour appears."""
    sx = max(ext, min(w - ext - 1, sx))
    for dy in range(1, max_steps):
        cy = sy - dy
        if cy < ext:
            break
        c = px[sx, cy][:3]
        if _is_bright_registration(c):
            continue
        if _looks_like_footer(c, mat):
            continue
        return c
    return None


def _bottom_wedge_stretch_color(
    px, corner: str, x: int, y: int, w: int, h: int, ext: int
) -> tuple[int, int, int]:
    """Bottom padding wedge: stretch card art above the footer, not flat black."""
    mat = _bottom_mat_color(px, corner, w, h, ext)
    uv = _padding_uv(corner, x, y, w, h, ext)
    if uv is None:
        return _edge_stretch_color(px, corner, x, y, w, h, ext)
    u, v = uv
    reach = _corner_reach(ext)
    sy = h - ext - 1
    max_dy = min(50, h - 2 * ext)
    if corner == "BL":
        sx_arm = max(
            ext,
            min(ext + reach - 1, ext + int(u * (reach - 1) / max(1.0, float(ext)))),
        )
        for sx in dict.fromkeys([ext, sx_arm]):
            walked = _walk_card_above_footer(px, sx, sy, w, h, ext, mat)
            if walked is not None:
                return walked
            for dy in range(max_dy):
                c = px[sx, sy - dy][:3]
                if not _looks_like_footer(c, mat) and not _is_bright_registration(c):
                    return c
        sy2 = max(
            ext,
            min(h - ext - 1, h - ext - 1 - int(v * (reach - 1) / max(1.0, float(ext)))),
        )
        walked = _walk_card_above_footer(px, ext, sy2, w, h, ext, mat)
        if walked is not None:
            return walked
        for dy in range(max_dy):
            c = px[ext, sy2 - dy][:3]
            if not _looks_like_footer(c, mat) and not _is_bright_registration(c):
                return c
    else:
        sx_arm = max(
            w - ext - reach,
            min(
                w - ext - 1,
                w - ext - 1 - int(u * (reach - 1) / max(1.0, float(ext))),
            ),
        )
        for sx in dict.fromkeys([w - ext - 1, sx_arm]):
            walked = _walk_card_above_footer(px, sx, sy, w, h, ext, mat)
            if walked is not None:
                return walked
            for dy in range(max_dy):
                c = px[sx, sy - dy][:3]
                if not _looks_like_footer(c, mat) and not _is_bright_registration(c):
                    return c
        sy2 = max(
            ext,
            min(h - ext - 1, h - ext - 1 - int(v * (reach - 1) / max(1.0, float(ext)))),
        )
        walked = _walk_card_above_footer(px, w - ext - 1, sy2, w, h, ext, mat)
        if walked is not None:
            return walked
        for dy in range(max_dy):
            c = px[w - ext - 1, sy2 - dy][:3]
            if not _looks_like_footer(c, mat) and not _is_bright_registration(c):
                return c
    return mat


def _top_mat_color(px, corner: str, w: int, h: int, ext: int) -> tuple[int, int, int]:
    """Title-bar strip colour for top corner padding (avoids white frame L-arms)."""
    iy = ext
    span = max(8, (w - 2 * ext) // 4)
    if corner == "TL":
        return px[min(w - ext - 1, ext + span), iy][:3]
    return px[max(ext, w - ext - 1 - span), iy][:3]


def _grey_title_top_card(px, w: int, h: int, ext: int) -> bool:
    """Bordered cards with a neutral-grey title bar (e.g. Sparky), not coloured tops."""
    tl = _top_mat_color(px, "TL", w, h, ext)
    tr = _top_mat_color(px, "TR", w, h, ext)
    if not (_is_neutral_grey(tl) and _is_neutral_grey(tr)):
        return False
    mid = (_brightness(tl) + _brightness(tr)) // 2
    return 90 <= mid <= 170


def _edge_stretch_color(
    px, corner: str, x: int, y: int, w: int, h: int, ext: int
) -> tuple[int, int, int]:
    """Axis-aligned stretch from the nearest pasted card edge."""
    if corner == "TL":
        if y < ext:
            return px[min(w - ext - 1, max(ext, x)), ext][:3]
        return px[ext, y][:3]
    if corner == "TR":
        if y < ext:
            return px[min(w - ext - 1, max(ext, x)), ext][:3]
        return px[w - ext - 1, y][:3]
    if corner == "BL":
        if y >= h - ext:
            return _bottom_mat_color(px, corner, w, h, ext)
        return px[ext, y][:3]
    if y >= h - ext:
        return _bottom_mat_color(px, corner, w, h, ext)
    return px[w - ext - 1, y][:3]


def _l_zone_iterate_box(corner: str, w: int, h: int, ext: int) -> tuple[int, int, int, int]:
    reach = _corner_reach(ext)
    if corner == "TL":
        return (0, 0, reach + 1, reach + 1)
    if corner == "TR":
        return (w - reach - 1, 0, w, reach + 1)
    if corner == "BL":
        return (0, h - reach - 1, reach + 1, h)
    return (w - reach - 1, h - reach - 1, w, h)


def _stretch_color_from_card_arc(
    px,
    corner: str,
    u_pad: float,
    v_pad: float,
    radius: float,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
) -> tuple[int, int, int]:
    """Colour sampled on the card corner arc, stretched out through the wedge."""
    x, y = _clamp_xy(*_wedge_xy(corner, u_pad, v_pad, w, h, ext), w, h)
    return _stretch_color_from_card_arc_pixel(px, corner, x, y, radius, w, h, ext, bg_rgb=bg_rgb)


def _collect_corner_sample_points(
    px, w: int, h: int, ext: int
) -> tuple[dict[str, set[tuple[int, int]]], list[str]]:
    """Unique card-arc pixels used as stretch sources."""
    by_corner: dict[str, set[tuple[int, int]]] = {c: set() for c in ("TL", "TR", "BL", "BR")}
    notes: list[str] = []
    shared_r, _per, full_bleed = _resolve_shared_corner_radius(px, w, h, ext)
    if shared_r <= 0:
        return by_corner, notes
    for corner in _CORNERS:
        notes.append(f"{corner} arc r={shared_r:.0f}")
        x0, y0, x1, y1 = _corner_box(corner, w, h, ext)
        reach = ext + max(12, ext // 2) + 2
        if corner == "TL":
            box = (0, 0, reach, reach)
        elif corner == "TR":
            box = (w - reach, 0, w, reach)
        elif corner == "BL":
            box = (0, h - reach, reach, h)
        else:
            box = (w - reach, h - reach, w, h)
        x0, y0, x1, y1 = box
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_padding_corner_zone(corner, x, y, w, h, ext):
                    continue
                uv = _wedge_offsets(corner, x, y, w, h, ext)
                if uv is None:
                    continue
                by_corner[corner].add(_sample_card_arc_point(corner, *uv, shared_r, w, h, ext))
    return by_corner, notes


def _draw_sample_highlights(
    img: Image.Image,
    *,
    corner_points: dict[str, set[tuple[int, int]]],
    radii: dict[str, float],
    ext: int,
    dot_radius: int = 3,
) -> None:
    """Mark card sampling arc and source pixels in red."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    red = (255, 0, 0)

    for corner, radius in radii.items():
        _draw_card_corner_arc(draw, corner, radius, w, h, ext, color=red, width=2)
        for x, y in corner_points.get(corner, ()):
            draw.ellipse(
                (x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius),
                fill=red,
                outline=(200, 0, 0),
                width=1,
            )


def _draw_card_corner_arc(
    draw: ImageDraw.ImageDraw,
    corner: str,
    radius: float,
    w: int,
    h: int,
    ext: int,
    *,
    color: tuple[int, int, int],
    width: int = 2,
) -> None:
    """Sampling arc on the card (convex toward the padding wedge)."""
    cx, cy = _arc_center(corner, ext, radius, w, h)
    sample_r = _sample_arc_radius(radius, ext, corner=corner)
    t0, t1 = _arc_theta_sweep(corner)
    pts: list[tuple[int, int]] = []
    for i in range(49):
        theta = t0 + (i / 48.0) * (t1 - t0)
        pts.append(
            _clamp_xy(
                *_point_on_rounded_corner_arc(corner, cx, cy, radius, theta, arc_radius=sample_r),
                w,
                h,
            )
        )
    if len(pts) >= 2:
        draw.line(pts, fill=color, width=width)
    if corner == "TL":
        apex_theta = _clamp_theta_to_arc(corner, math.atan2(-cy, -cx))
    elif corner == "TR":
        apex_theta = _clamp_theta_to_arc(corner, math.atan2(-cy, w - 1 - cx))
    elif corner == "BL":
        apex_theta = _clamp_theta_to_arc(corner, math.atan2(h - 1 - cy, -cx))
    else:
        apex_theta = _clamp_theta_to_arc(corner, math.atan2(h - 1 - cy, w - 1 - cx))
    fx, fy = _clamp_xy(
        *_point_on_rounded_corner_arc(corner, cx, cy, radius, apex_theta, arc_radius=sample_r),
        w,
        h,
    )
    draw.ellipse((fx - 2, fy - 2, fx + 2, fy + 2), fill=(255, 255, 0))


def _collect_arc_pass_pixels(
    px, w: int, h: int, ext: int
) -> tuple[dict[str, float], set[tuple[int, int]]]:
    """Returns (radii, outer arc-triangle pixels in padding corners)."""
    radii: dict[str, float] = {}
    wedge_pixels: set[tuple[int, int]] = set()
    shared_r, _per, full_bleed = _resolve_shared_corner_radius(px, w, h, ext)
    if shared_r <= 0:
        return radii, wedge_pixels
    for corner in _CORNERS:
        radii[corner] = shared_r
        x0, y0, x1, y1 = _l_zone_iterate_box(corner, w, h, ext)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if _needs_arc_corner_fill(corner, x, y, w, h, ext, shared_r):
                    wedge_pixels.add((x, y))
    return radii, wedge_pixels


def _overlay_arc_highlight(
    img: Image.Image,
    *,
    radii: dict[str, float],
    changed_pixels: set[tuple[int, int]],
    wedge_pixels: set[tuple[int, int]],
    ext: int,
) -> Image.Image:
    """Stretched result with red overlays for arc pass output."""
    w, h = img.size
    base = img.convert("RGBA")
    tint = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tint_px = tint.load()
    if tint_px is None:
        raise RuntimeError("could not load tint pixels")

    for x, y in wedge_pixels:
        tint_px[x, y] = (255, 0, 0, 90)
    for x, y in changed_pixels:
        tint_px[x, y] = (255, 0, 0, 120)

    out = Image.alpha_composite(base, tint)
    draw = ImageDraw.Draw(out)
    for corner, radius in radii.items():
        _draw_card_corner_arc(draw, corner, radius, w, h, ext, color=(255, 0, 0), width=2)
    return out.convert("RGB")


def _inner_corner_stretch_color(
    px, corner: str, x: int, y: int, w: int, h: int, ext: int
) -> tuple[int, int, int]:
    """Stretch along L-arms by sampling the nearer card-edge seam (not both axes)."""
    uv = _padding_uv(corner, x, y, w, h, ext)
    if uv is None:
        return _edge_stretch_color(px, corner, x, y, w, h, ext)
    u, v = uv
    reach = _corner_reach(ext)
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
    else:
        if t_v >= t_u:
            sx = max(w - ext - reach, min(w - ext - 1, w - ext - 1 - int(t_u * (reach - 1))))
            sy = h - ext - 1
        else:
            sx = w - ext - 1
            sy = max(h - ext - reach, min(h - ext - 1, h - ext - 1 - int(t_v * (reach - 1))))
    color = px[sx, sy][:3]
    mat = _mat_color_for_corner(px, corner, w, h, ext)
    if mat is not None and (_is_arc_rim_fringe(color, mat) or _is_bright_registration(color)):
        return mat
    return color


def _gutter_mark_needs_recolor(p: tuple[int, int, int], mat: tuple[int, int, int]) -> bool:
    if not _is_neutral_grey(p):
        return False
    if _brightness(p) < 50:
        return False
    return _color_distance(p, mat) > 18


def _fill_bottom_corner_marks(px, w: int, h: int, ext: int) -> int:
    """Blacken registration marks on bottom gutter seams and junctions."""
    changed = 0
    reach = _corner_reach(ext)
    for corner in ("BL", "BR"):
        mat = _bottom_mat_color(px, corner, w, h, ext)
        if corner == "BL":
            x0, y0, x1, y1 = 0, h - ext - reach, ext + reach, h
        else:
            x0, y0, x1, y1 = w - ext - reach, h - ext - reach, w, h
        for y in range(y0, y1):
            for x in range(x0, x1):
                on_seam = _on_corner_gutter_seam(corner, x, y, w, h, ext)
                on_junction = _in_corner_junction(corner, x, y, w, h, ext)
                if not (on_seam or on_junction):
                    continue
                p = px[x, y][:3]
                if not (_gutter_mark_needs_recolor(p, mat) or _is_bright_registration(p)):
                    continue
                if p != mat:
                    px[x, y] = mat
                    changed += 1
    return changed


def _fill_top_corner_marks(px, w: int, h: int, ext: int, *, full_bleed: frozenset[str]) -> int:
    """Recolour registration marks on top gutter seams and junctions."""
    changed = 0
    reach = _corner_reach(ext)
    for corner in ("TL", "TR"):
        if corner in full_bleed:
            mat = _top_stripe_color(px, corner, w, h, ext)
        else:
            mat = _top_mat_color(px, corner, w, h, ext)
        if corner == "TL":
            x0, y0, x1, y1 = 0, 0, ext + reach, ext + reach
        else:
            x0, y0, x1, y1 = w - ext - reach, 0, w, ext + reach
        for y in range(y0, y1):
            for x in range(x0, x1):
                on_seam = _on_corner_gutter_seam(corner, x, y, w, h, ext)
                on_junction = _in_corner_junction(corner, x, y, w, h, ext)
                if not (on_seam or on_junction):
                    continue
                p = px[x, y][:3]
                if not (_gutter_mark_needs_recolor(p, mat) or _is_bright_registration(p)):
                    continue
                if p != mat:
                    px[x, y] = mat
                    changed += 1
    return changed


def _outside_card_round(
    corner: str, x: int, y: int, w: int, h: int, ext: int, outer_r: float
) -> bool:
    """On-card pixel beyond the rounded print corner (the artifact crescent zone)."""
    if corner == "TL":
        u, v = float(x - ext), float(y - ext)
    elif corner == "TR":
        u, v = float(w - ext - 1 - x), float(y - ext)
    elif corner == "BL":
        u, v = float(x - ext), float(h - ext - 1 - y)
    else:
        u, v = float(w - ext - 1 - x), float(h - ext - 1 - y)
    if u >= outer_r or v >= outer_r:
        return False
    return math.hypot(outer_r - u, outer_r - v) > outer_r - 1.5


def _fill_source_corner_rounds(
    px,
    src: Image.Image,
    w: int,
    h: int,
    ext: int,
    radius: float,
    *,
    full_bleed: frozenset[str],
    bg_rgb: tuple[int, int, int] | None,
) -> int:
    """
    Repaint the card's TL/TR rounded-corner cutouts using the source alpha channel.

    Pixels with alpha < 250 in a source corner box are exactly the round cutout
    plus its anti-aliased rim; they get the radial arc stretch so corner art
    continues in an arc. Bottom corners are handled by the fan fill.
    """
    if radius <= 0:
        return 0
    src_px = src.load()
    if src_px is None:
        return 0
    sw, sh = src.size
    reach = int(_card_arc_radius(radius)) + 4
    changed = 0
    for corner in ("TL", "TR"):
        if corner == "TL":
            box = (0, 0, min(sw, reach), min(sh, reach))
        else:
            box = (max(0, sw - reach), 0, sw, min(sh, reach))

        for sy in range(box[1], box[3]):
            for sx in range(box[0], box[2]):
                if src_px[sx, sy][3] >= 250:
                    continue
                x, y = ext + sx, ext + sy
                color = _stretch_color_from_card_arc_pixel(
                    px,
                    corner,
                    x,
                    y,
                    radius,
                    w,
                    h,
                    ext,
                    bg_rgb=bg_rgb,
                    full_bleed=full_bleed,
                )
                if px[x, y][:3] != color:
                    px[x, y] = color
                    changed += 1
    return changed


def _fill_corner_padding(
    px,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int] | None = None,
    full_bleed: frozenset[str] | None = None,
    shared_r: float | None = None,
    per_radii: dict[str, float] | None = None,
    src: Image.Image | None = None,
) -> tuple[int, list[str], set[str]]:
    """Fill padding corners: edge stretch inboard, arc stretch on the outer triangle."""
    notes: list[str] = []
    detected: set[str] = set()
    changed = 0
    grey_title_top = _grey_title_top_card(px, w, h, ext)
    if shared_r is None or full_bleed is None or per_radii is None:
        shared_r, per_radii, full_bleed = _resolve_shared_corner_radius(px, w, h, ext)
    if shared_r <= 0:
        return changed, notes, detected
    cutout_radii = _bottom_cutout_radii(px, src, w, h, ext, per_radii, shared_r)
    for corner in _CORNERS:
        radius = shared_r
        detected.add(corner)
        n_arc = 0
        n_edge = 0
        # Dark rounded bottom corners (black inset on the card round) mean the
        # whole padding corner must be that colour — no stretched streaks.
        dark_bottom_inset: tuple[int, int, int] | None = None
        if corner in cutout_radii:
            dark_bottom_inset = _dark_bottom_round_inset(
                px, corner, cutout_radii[corner], w, h, ext
            )
        x0, y0, x1, y1 = _l_zone_iterate_box(corner, w, h, ext)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not _in_padding_corner_zone(corner, x, y, w, h, ext):
                    continue
                if dark_bottom_inset is not None:
                    if px[x, y][:3] != dark_bottom_inset:
                        px[x, y] = dark_bottom_inset
                        changed += 1
                    n_arc += 1
                    continue
                if grey_title_top:
                    color = _stretch_color_from_card_arc_pixel(
                        px,
                        corner,
                        x,
                        y,
                        radius,
                        w,
                        h,
                        ext,
                        bg_rgb=bg_rgb,
                        full_bleed=full_bleed,
                    )
                    n_arc += 1
                elif corner in ("BL", "BR"):
                    flag_card = _is_flag_card(px, w, h, ext)
                    if corner in full_bleed and flag_card:
                        color = _bottom_mat_color(px, corner, w, h, ext)
                        n_arc += 1
                    elif corner in full_bleed:
                        if _needs_arc_corner_fill(corner, x, y, w, h, ext, radius):
                            color = _stretch_color_from_card_arc_pixel(
                                px,
                                corner,
                                x,
                                y,
                                radius,
                                w,
                                h,
                                ext,
                                bg_rgb=bg_rgb,
                                full_bleed=full_bleed,
                            )
                            mat = _bottom_mat_color(px, corner, w, h, ext)
                            if _looks_like_footer(color, mat):
                                color = _bottom_wedge_stretch_color(px, corner, x, y, w, h, ext)
                            n_arc += 1
                        else:
                            color = _bottom_wedge_stretch_color(px, corner, x, y, w, h, ext)
                            n_edge += 1
                    elif _needs_arc_corner_fill(corner, x, y, w, h, ext, radius):
                        color = _stretch_color_from_card_arc_pixel(
                            px,
                            corner,
                            x,
                            y,
                            radius,
                            w,
                            h,
                            ext,
                            bg_rgb=bg_rgb,
                            full_bleed=full_bleed,
                        )
                        n_arc += 1
                    else:
                        color = _inner_corner_stretch_color(px, corner, x, y, w, h, ext)
                        if _is_bright_registration(color):
                            color = _stretch_color_from_card_arc_pixel(
                                px,
                                corner,
                                x,
                                y,
                                radius,
                                w,
                                h,
                                ext,
                                bg_rgb=bg_rgb,
                                full_bleed=full_bleed,
                            )
                        n_edge += 1
                elif _needs_arc_corner_fill(corner, x, y, w, h, ext, radius):
                    color = _stretch_color_from_card_arc_pixel(
                        px,
                        corner,
                        x,
                        y,
                        radius,
                        w,
                        h,
                        ext,
                        bg_rgb=bg_rgb,
                        full_bleed=full_bleed,
                    )
                    n_arc += 1
                else:
                    color = _inner_corner_stretch_color(px, corner, x, y, w, h, ext)
                    if _is_bright_registration(color):
                        color = _stretch_color_from_card_arc_pixel(
                            px,
                            corner,
                            x,
                            y,
                            radius,
                            w,
                            h,
                            ext,
                            bg_rgb=bg_rgb,
                            full_bleed=full_bleed,
                        )
                    n_edge += 1
                if px[x, y][:3] != color:
                    changed += 1
                px[x, y] = color

        notes.append(f"{corner} arc r={radius:.0f}: {n_arc}px arc + {n_edge}px edge")
    return changed, notes, detected


def _fill_corner_arc_stretch_prepare(
    px, w: int, h: int, ext: int, *, bg_rgb: tuple[int, int, int] | None = None
) -> tuple[int, list[str], set[str]]:
    return _fill_corner_padding(px, w, h, ext, bg_rgb=bg_rgb)


def _border_for_width(width: int) -> int:
    if width <= 251:
        return 12
    if width <= 320:
        return 16
    if width <= 521:
        return 24
    if width <= 1000:
        return 32
    if width <= 1100:
        return 48
    return 64


def _in_any_padding_corner_zone(x: int, y: int, w: int, h: int, ext: int) -> bool:
    return any(
        _in_padding_corner_zone(corner, x, y, w, h, ext) for corner in ("TL", "TR", "BL", "BR")
    )


def _nearest_opaque_rgb(src_px, sx: int, sy: int, sw: int, sh: int) -> tuple[int, int, int] | None:
    """Nearest opaque source pixel — horizontal first, then vertical."""
    for dx in range(1, max(sw, sh)):
        for ox in (sx + dx, sx - dx):
            if 0 <= ox < sw and src_px[ox, sy][3] > 0:
                return src_px[ox, sy][:3]
        for oy in (sy + dx, sy - dx):
            if 0 <= oy < sh and src_px[sx, oy][3] > 0:
                return src_px[sx, oy][:3]
    return None


def _skip_bottom_corner_hole_fill(sx: int, sy: int, sw: int, sh: int, ext: int) -> bool:
    """Rounded bottom corners: keep canvas bleed-through instead of footer-grey fill."""
    reach = ext + max(12, ext // 2) + 2
    if sy < sh - reach:
        return False
    return sx < reach or sx >= sw - reach


def _fill_transparent_card_holes(px, src: Image.Image, ext: int, w: int, h: int) -> int:
    """Fill transparent source holes on the pasted card from nearest opaque art."""
    src_px = src.load()
    if src_px is None:
        return 0
    sw, sh = src.size
    changed = 0
    for sy in range(sh):
        for sx in range(sw):
            if src_px[sx, sy][3] > 0:
                continue
            if _skip_bottom_corner_hole_fill(sx, sy, sw, sh, ext):
                continue
            color = _nearest_opaque_rgb(src_px, sx, sy, sw, sh)
            if color is None:
                continue
            cx, cy = ext + sx, ext + sy
            if px[cx, cy][:3] != color:
                px[cx, cy] = color
                changed += 1
    return changed


_EDGE_CONTENT_DEPTH = 3
_EDGE_CONTENT_TOL = 24
_EDGE_CONTENT_MIN_RUN = 8


def _edge_content_mask(px, coords: list[tuple[int, int]], inboard: tuple[int, int]) -> list[bool]:
    """
    Flag edge pixels that are card art rather than rim/registration artefacts.

    Bites, tears and pale frames hold their colour several pixels inboard and
    span a wide run along the edge; anti-aliased rims are 1-2px deep and crop
    ticks only a few pixels wide.
    """
    dx, dy = inboard
    deep: list[bool] = []
    for x, y in coords:
        color = px[x, y][:3]
        deep.append(
            all(
                _color_distance(px[x + dx * s, y + dy * s][:3], color) <= _EDGE_CONTENT_TOL
                for s in range(1, _EDGE_CONTENT_DEPTH + 1)
            )
        )
    mask = [False] * len(coords)
    start = 0
    while start < len(deep):
        if not deep[start]:
            start += 1
            continue
        end = start
        while end < len(deep) and deep[end]:
            end += 1
        if end - start >= _EDGE_CONTENT_MIN_RUN:
            for i in range(start, end):
                mask[i] = True
        start = end
    return mask


def _fill_edge_stretch(px, w: int, h: int, ext: int) -> int:
    """Stretch the outermost card edge row/column into each padding band."""
    changed = 0
    top_l = _top_mat_color(px, "TL", w, h, ext)
    top_r = _top_mat_color(px, "TR", w, h, ext)
    bot_l = _bottom_mat_color(px, "BL", w, h, ext)
    bot_r = _bottom_mat_color(px, "BR", w, h, ext)
    mid_x = (ext + (w - ext)) // 2
    mid_y = (ext + (h - ext)) // 2

    def clean_edge(color: tuple[int, int, int], mat: tuple[int, int, int]) -> tuple[int, int, int]:
        if _is_arc_rim_fringe(color, mat) or _is_bright_registration(color):
            return mat
        return color

    def put(x: int, y: int, color: tuple[int, int, int]) -> None:
        nonlocal changed
        if _in_any_padding_corner_zone(x, y, w, h, ext):
            return
        if px[x, y][:3] != color:
            px[x, y] = color
            changed += 1

    top_coords = [(x, ext) for x in range(ext, w - ext)]
    left_coords = [(ext, y) for y in range(ext, h - ext)]
    right_coords = [(w - ext - 1, y) for y in range(ext, h - ext)]
    top_keep = _edge_content_mask(px, top_coords, (0, 1))
    left_keep = _edge_content_mask(px, left_coords, (1, 0))
    right_keep = _edge_content_mask(px, right_coords, (-1, 0))

    for i, (sx, sy) in enumerate(top_coords):
        mat = top_l if sx < mid_x else top_r
        color = px[sx, sy][:3]
        if not top_keep[i]:
            color = clean_edge(color, mat)
        for y in range(ext):
            put(sx, y, color)
    for y in range(h - ext, h):
        for x in range(ext, w - ext):
            mat = bot_l if x < mid_x else bot_r
            put(x, y, clean_edge(px[x, h - ext - 1][:3], mat))
    for i, (sx, sy) in enumerate(left_coords):
        mat = top_l if sy < mid_y else bot_l
        color = px[sx, sy][:3]
        if not left_keep[i]:
            color = clean_edge(color, mat)
        for x in range(ext):
            put(x, sy, color)
    for i, (sx, sy) in enumerate(right_coords):
        mat = top_r if sy < mid_y else bot_r
        color = px[sx, sy][:3]
        if not right_keep[i]:
            color = clean_edge(color, mat)
        for x in range(w - ext, w):
            put(x, sy, color)
    return changed


def _fill_corner_arc_stretch(
    px, w: int, h: int, ext: int, *, bg_rgb: tuple[int, int, int] | None = None
) -> tuple[int, list[str], set[str]]:
    return _fill_corner_arc_stretch_prepare(px, w, h, ext, bg_rgb=bg_rgb)


def _apply_stretch_fills(
    out: Image.Image,
    w: int,
    h: int,
    ext: int,
    *,
    bg_rgb: tuple[int, int, int],
    src: Image.Image | None = None,
) -> tuple[int, int, list[str], set[str]]:
    """Edge stretch on straight bands, then corner padding (edge + arc triangle)."""
    px = out.load()
    if px is None:
        raise RuntimeError("could not load output pixels")
    shared_r, per_radii, full_bleed = _resolve_shared_corner_radius(px, w, h, ext)
    hole_changed = 0
    if src is not None:
        hole_changed = _fill_transparent_card_holes(px, src, ext, w, h)
    edge_changed = _fill_edge_stretch(px, w, h, ext)
    corner_changed, arc_notes, arcs_detected = _fill_corner_padding(
        px,
        w,
        h,
        ext,
        bg_rgb=bg_rgb,
        full_bleed=full_bleed,
        shared_r=shared_r,
        per_radii=per_radii,
        src=src,
    )
    gutter_changed = _fill_bottom_corner_marks(px, w, h, ext)
    gutter_changed += _fill_top_corner_marks(px, w, h, ext, full_bleed=full_bleed)
    if src is not None:
        gutter_changed += _fill_source_corner_rounds(
            px, src, w, h, ext, shared_r, full_bleed=full_bleed, bg_rgb=bg_rgb
        )
    gutter_changed += _fan_fill_bottom_corner_rounds(px, src, w, h, ext, per_radii, shared_r)
    gutter_changed += _fan_fill_top_corner_rounds(
        px, src, w, h, ext, per_radii, shared_r, full_bleed=full_bleed
    )
    gutter_changed += _fill_padding_l_marks(px, w, h, ext, bg_rgb=bg_rgb)
    repaired = out
    seam_total = 0
    for _ in range(5):
        repaired, seam_px = inpaint_border_seam_lines(repaired)
        seam_total += seam_px
        if seam_px == 0:
            break
        if not _detect_border_seam_lines(repaired, w, h, max(8, min(w, h) // 25)):
            break
    if seam_total:
        out.paste(repaired)
        gutter_changed += seam_total
    # Geometric arc wedges last: border colour from the inward arc out to the tip.
    wedge_changed = _draw_corner_arc_wedges(
        out,
        w,
        h,
        ext,
        shared_r,
        bg_rgb=bg_rgb,
        full_bleed=full_bleed,
    )
    return (
        edge_changed,
        corner_changed + gutter_changed + hole_changed + wedge_changed,
        arc_notes,
        arcs_detected,
    )


def prepare_card_for_printing_stretch_highlight(
    image_path: str,
    *,
    out_path: str | None = None,
) -> str:
    """
    Paste + border canvas; mark card sampling arc and source pixels in red.
    """
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    ext = _border_for_width(width)
    bg_rgb = img.getpixel((int(width / 2), 5))[:3]

    new_w = width + ext * 2
    new_h = height + ext * 2
    out = Image.new("RGB", (new_w, new_h), bg_rgb)
    out.paste(img, (ext, ext), img)

    px = out.load()
    if px is None:
        raise RuntimeError("could not load output pixels")

    corner_points, notes = _collect_corner_sample_points(px, new_w, new_h, ext)
    radii = {n.split()[0]: float(n.split("r=")[1]) for n in notes}
    _draw_sample_highlights(out, corner_points=corner_points, radii=radii, ext=ext)

    counts = {c: len(pts) for c, pts in corner_points.items() if pts}
    if out_path is None:
        base, _ = os.path.splitext(image_path)
        out_path = f"{base}_stretch_samples.png"
    out.save(out_path, "PNG")
    print(f"[stretch-debug] {os.path.basename(out_path)}")
    print(f"  arcs: {', '.join(notes) if notes else 'none'}")
    print(f"  unique arc sample points: {counts}")
    return out_path


def prepare_card_for_printing_stretch_highlight_arc(
    image_path: str,
    *,
    out_path: str | None = None,
) -> str:
    """
    Run edge + arc stretch, then overlay what the arc pass drew.

    Red quarter-circle = sampling arc on the card (just inside the frame corner).
    Light red tint = padding L-corners filled by stretching the sampling arc.
    Brighter red = pixels rewritten by the arc pass.
    """
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    ext = _border_for_width(width)
    bg_rgb = img.getpixel((int(width / 2), 5))[:3]

    new_w = width + ext * 2
    new_h = height + ext * 2
    out = Image.new("RGB", (new_w, new_h), bg_rgb)
    out.paste(img, (ext, ext), img)

    px = out.load()
    if px is None:
        raise RuntimeError("could not load output pixels")

    radii, wedge_pixels = _collect_arc_pass_pixels(px, new_w, new_h, ext)
    before: dict[tuple[int, int], tuple[int, int, int]] = {
        (x, y): px[x, y][:3] for (x, y) in wedge_pixels
    }
    _, arc_changed, arc_notes, _ = _apply_stretch_fills(
        out, new_w, new_h, ext, bg_rgb=bg_rgb, src=img
    )
    changed_pixels = {(x, y) for (x, y) in wedge_pixels if px[x, y][:3] != before[(x, y)]}

    highlighted = _overlay_arc_highlight(
        out,
        radii=radii,
        changed_pixels=changed_pixels,
        wedge_pixels=wedge_pixels,
        ext=ext,
    )

    if out_path is None:
        base, _ = os.path.splitext(image_path)
        out_path = f"{base}_stretch_arc.png"
    highlighted.save(out_path, "PNG")
    print(f"[stretch-arc-debug] {os.path.basename(out_path)}")
    print(f"  arcs: {', '.join(arc_notes) if arc_notes else 'none'}")
    print(f"  arc pass changed {arc_changed}px ({len(changed_pixels)} wedge pixels)")
    for corner, radius in radii.items():
        print(f"  {corner}: card arc r={_card_arc_radius(radius):.0f}")
    return out_path


def ensure_landscape_orientation(
    image_path: str,
    *,
    log_tag: str = "stretch",
) -> bool:
    """
    Rotate portrait sources 90° CCW so the canvas is landscape (Plane cards).

    Overwrites ``image_path`` when a rotation is applied. Returns True if rotated.
    """
    with Image.open(image_path) as im:
        w, h = im.size
        if w >= h:
            return False
        rotated = im.transpose(Image.Transpose.ROTATE_90)
        fmt = "PNG" if image_path.lower().endswith(".png") else (im.format or "PNG")
        rotated.save(image_path, fmt)
    print(f"[{log_tag}] rotated portrait {w}x{h} → landscape for Plane horizontal align")
    return True


def prepare_card_for_printing_stretch(
    image_path: str,
    *,
    out_path: str | None = None,
    log_tag: str = "stretch",
    force_landscape: bool = False,
) -> str:
    """
    Border-expand using arc-aware corner stretch + edge stretch.

    When ``force_landscape`` is True (Plane cards), portrait sources are rotated
    to landscape before padding so the printable stays horizontally aligned.

    Returns the output PNG path.
    """
    if force_landscape:
        ensure_landscape_orientation(image_path, log_tag=log_tag)

    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    ext = _border_for_width(width)
    bg_rgb = img.getpixel((int(width / 2), 5))[:3]

    new_w = width + ext * 2
    new_h = height + ext * 2
    out = Image.new("RGB", (new_w, new_h), bg_rgb)
    out.paste(img, (ext, ext), img)

    px = out.load()
    if px is None:
        raise RuntimeError("could not load output pixels")

    edge_changed, arc_changed, arc_notes, _ = _apply_stretch_fills(
        out, new_w, new_h, ext, bg_rgb=bg_rgb, src=img
    )

    if out_path is None:
        base, _ = os.path.splitext(image_path)
        out_path = f"{base}_stretch.png"
    out.save(out_path, "PNG")
    note_str = "; ".join(arc_notes) if arc_notes else "no arcs detected"
    print(
        f"[{log_tag}] {os.path.basename(out_path)}  arcs={arc_changed}px edges={edge_changed}px ({note_str})"
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Source card PNG/JPG")
    parser.add_argument("-o", "--output", help="Output path (default: <stem>_stretch.png)")
    parser.add_argument(
        "--highlight-samples",
        action="store_true",
        help="Debug: save PNG with red dots on every corner sample point (no stretch fill)",
    )
    parser.add_argument(
        "--highlight-arc",
        action="store_true",
        help="Debug: run stretch then overlay detected/sample arcs and arc-pass pixels",
    )
    args = parser.parse_args()
    if args.highlight_samples:
        prepare_card_for_printing_stretch_highlight(args.image, out_path=args.output)
    elif args.highlight_arc:
        prepare_card_for_printing_stretch_highlight_arc(args.image, out_path=args.output)
    else:
        prepare_card_for_printing_stretch(args.image, out_path=args.output)


if __name__ == "__main__":
    main()
