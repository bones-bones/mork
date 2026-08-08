"""
Spike: two-pass vision corner fix — L-mark bboxes, then quarter-circle arcs.

Example:
  python scripts/spike_vision_corner_fix.py \\
    scripts/data/fix_compare/935_Skeletal_Uprising_side_1_before.png

Writes:
  scripts/data/fix_compare/<name>_vision_guide.json
  scripts/data/fix_compare/<name>_vision_arc_guide.json
  scripts/data/fix_compare/<name>_vision_after.png
"""

from __future__ import annotations

import json
import mork_repo_root  # noqa: E402
import sys
from pathlib import Path

from printable_image_fixes import (
    apply_corner_arc_guides,
    apply_vision_corner_guides,
    extension_width,
    locate_corner_arcs,
    locate_corner_fixes,
    _border_band,
)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    src = Path(sys.argv[1]).resolve()
    if not src.is_file():
        print(f"Not found: {src}", file=sys.stderr)
        sys.exit(1)

    stem = src.stem.replace("_before", "")
    out_dir = src.parent
    card_name = stem.split("_", 1)[-1].replace("_", " ") if "_" in stem else stem

    print(f"Pass 1 — L-mark bboxes: {src.name}")
    guides = locate_corner_fixes(str(src), card_name=card_name)

    guide_path = out_dir / f"{stem}_vision_guide.json"
    guide_path.write_text(
        json.dumps(
            [
                {
                    "corner": g.corner,
                    "model_flagged": g.model_flagged,
                    "needs_fix": g.needs_fix,
                    "artifact": g.artifact,
                    "fill_bbox_pct": list(g.bbox_pct) if g.bbox_pct else None,
                    "note": g.note,
                }
                for g in guides
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {guide_path}")

    from PIL import Image

    img = Image.open(src).convert("RGB")
    w, h = img.size
    band = _border_band(w, h)
    ext = extension_width(w, h)
    fixed, repainted, notes = apply_vision_corner_guides(
        img, guides, band=band, ext=ext
    )
    print(f"Pass 1 repainted ~{repainted}px")
    for n in notes:
        print(f"  {n}")

    pass1_path = out_dir / f"{stem}_vision_pass1.png"
    fixed.save(pass1_path)

    print(f"\nPass 2 — corner arcs: {pass1_path.name}")
    arc_guides = locate_corner_arcs(str(pass1_path), card_name=card_name)
    arc_path = out_dir / f"{stem}_vision_arc_guide.json"
    arc_path.write_text(
        json.dumps(
            [
                {
                    "corner": g.corner,
                    "needs_fix": g.needs_fix,
                    "arc_center_pct": list(g.center_pct),
                    "arc_radius_px": [g.radius_inner, g.radius_outer],
                    "note": g.note,
                }
                for g in arc_guides
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {arc_path}")
    for g in arc_guides:
        flag = "FIX" if g.needs_fix else "skip"
        print(
            f"  {g.corner:>2} [{flag}] center%={[round(c, 1) for c in g.center_pct]} "
            f"r={g.radius_inner:.0f}-{g.radius_outer:.0f}  {g.note!r}"
        )

    fixed, arc_px, arc_notes = apply_corner_arc_guides(
        fixed, arc_guides, band=band, ext=ext
    )
    after_path = out_dir / f"{stem}_vision_after.png"
    fixed.save(after_path)
    print(f"\nPass 2 repainted ~{arc_px}px -> {after_path}")
    for n in arc_notes:
        print(f"  {n}")
    print(f"Total ~{repainted + arc_px}px")


if __name__ == "__main__":
    main()
