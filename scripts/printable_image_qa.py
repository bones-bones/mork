"""
Vision + heuristic QA for printable Hellscube card images.

Used by ``review_printable_images.py`` and ``review_printable_benchmark.py``.
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from PIL import Image

_LABELS_JSON = Path(__file__).resolve().parent / "data" / "printable_qa_labels.json"

# Legacy alias; prefer load_benchmark_labels() for harness + benchmark scripts.
BENCHMARK_GROUND_TRUTH: dict[str, str] = {
    "765": "N",
    "434": "N",
    "486": "N",
    "2405": "N",
    "342": "Y",
    "343": "Y",
    "352": "Y",
    "456": "Y",
    "75": "Y",
    "175": "Y",
    "186": "Y",
    "135": "N",
}


def load_benchmark_labels() -> dict[str, dict[str, str]]:
    """Merge JSON human labels with built-in defaults. Values: verdict + optional note."""
    out: dict[str, dict[str, str]] = {
        cid: {"verdict": v, "note": ""} for cid, v in BENCHMARK_GROUND_TRUTH.items()
    }
    if _LABELS_JSON.is_file():
        with _LABELS_JSON.open(encoding="utf-8") as f:
            data = json.load(f)
        for cid, entry in (data.get("labels") or {}).items():
            if isinstance(entry, dict) and entry.get("verdict") in ("Y", "N"):
                out[str(cid)] = {
                    "verdict": entry["verdict"],
                    "note": str(entry.get("note") or ""),
                }
    return out


def benchmark_ground_truth() -> dict[str, str]:
    return {cid: e["verdict"] for cid, e in load_benchmark_labels().items()}


KNOWN_DEFECT_TAGS = frozenset(
    {
        "corner_color_mismatch",
        "corner_trim",
        "wrong_silhouette",
        "multi_card_in_one_file",
        "conversion_bleed",
        "border_seam_lines",
    }
)

DEFECT_ALIASES: dict[str, str] = {
    "corner_color": "corner_color_mismatch",
    "corner_mismatch": "corner_color_mismatch",
    "corner_clip": "corner_trim",
    "corner_clipping": "corner_trim",
    "trimmed_corners": "corner_trim",
    "wrong_shape": "wrong_silhouette",
    "bad_silhouette": "wrong_silhouette",
    "wrong_dimensions": "wrong_silhouette",
    "wrong_aspect": "wrong_silhouette",
    "wrong_aspect_ratio": "wrong_silhouette",
    "landscape_canvas": "wrong_silhouette",
    "multi_card": "multi_card_in_one_file",
    "two_cards": "multi_card_in_one_file",
    "split_card": "multi_card_in_one_file",
    "double_card": "multi_card_in_one_file",
    "bleed": "conversion_bleed",
    "border_bleed": "conversion_bleed",
    "smeared_border": "conversion_bleed",
    "border_seam": "border_seam_lines",
    "faint_lines": "border_seam_lines",
    "seam_lines": "border_seam_lines",
}

PROMPT_STEP1_DEFECTS = """Strict QA for a Hellscube printable card PNG after an automated border-expansion script.

You receive the full card plus zoomed crops of all four corners (5 images). Inspect every corner and the outer border band.

Flag SCRIPT/conversion defects only (not weird meme art). Use these tags exactly:
- corner_color_mismatch — corner patches clearly differ from the adjacent border strip (not intentional colored/non-black borders that are uniform)
- corner_trim — border visibly clips into printed card art/frame (not decorative frame corners)
- wrong_silhouette — canvas is not printable card dimensions (e.g. square file, extreme aspect vs expected card shape, huge letterboxing). {silhouette_rule}
- multi_card_in_one_file — two+ distinct card faces in one file that should be separate
- conversion_bleed — smeared/repeated edge strips, harsh seams, garbage pixels along the border
- border_seam_lines — faint scratch/hair lines running along the border band (extension artifacts)

Only list a tag when the defect is clearly visible. Do not guess. Empty defects [] is correct for clean borders.
Intentionally textured/patterned card borders (wood, stone, marble, etc.) are part of the card design, not defects.

Card id {card_id} | {card_name} | {side_name}

Reply with only valid JSON (no markdown fences):
{{"defects":["tag"] or [],"observations":"one sentence on corners/border"}}"""

PROMPT_STEP2_VERDICT = """Final verdict for this printable card PNG (full image + corner crops).

Step-1 JSON:
{step1_json}

Heuristic pre-checks: {heuristic_summary}

Rules:
- Heuristic pre-checks listed above are strong signals; if any, verdict N
- If step-1 lists only corner_color_mismatch but borders look intentionally uniform (e.g. colored border), verdict Y
- If step-1 lists corner_trim, only verdict N when art/frame is actually clipped
- border_seam_lines or conversion_bleed => N
- If step-1 defects is [] and borders look uniform, verdict Y
- Do not fail for weird meme art alone
- {silhouette_rule}

JSON only: {{"verdict":"Y"|"N","issues":["tag"],"notes":"one sentence"}}"""

PROMPT_SINGLE_PASS = """Strict QA for a Hellscube printable card PNG after border-expansion (full image + corner crops).

Verdict Y = acceptable to print. Verdict N = needs manual fixing.

Answer N if ANY conversion defect is clearly visible:
1. corner_color_mismatch — corners clearly off vs border (uniform non-black borders are OK)
2. corner_trim — border clips into art/frame (not decorative corners)
3. wrong_silhouette — not valid printable card dimensions/aspect. {silhouette_rule}
4. multi_card_in_one_file — two+ card faces in one file
5. conversion_bleed — smeared edges, harsh seams, garbage along the border
6. border_seam_lines — faint lines/scratches extending along the border band

Do not flag meme art alone. When borders look uniform, choose Y.
Intentionally textured/patterned card borders (wood, stone, marble, etc.) are part of the card design, not defects.

Card id {card_id} | {card_name} | {side_name}

JSON only: {{"verdict":"Y"|"N","issues":["tag"],"notes":"one sentence on corners/border"}}"""

SILHOUETTE_RULE_PORTRAIT = (
    "Expect a single portrait card (~0.63–0.82 w/h); landscape single-card canvas is N"
)
SILHOUETTE_RULE_LANDSCAPE = (
    "This is a Plane card — expect a single landscape card (~1.16–1.67 w/h); "
    "do NOT flag wrong_silhouette for normal landscape Plane dimensions"
)
LEGENDARY_CROWN_RULE = (
    "This is a Legendary card — the angular legend crown / notched title bar at "
    "the top (and matching frame lines on the sides) is intentional frame art, "
    "not border_seam_lines, corner_trim, or conversion_bleed"
)


def types_include_plane(types_cell: str) -> bool:
    """True when a Database type cell lists Plane (not Planeswalker)."""
    for part in re.split(r"[;,/]", types_cell or ""):
        if part.strip().lower() == "plane":
            return True
    return False


def supertypes_include_legendary(supertype_cell: str) -> bool:
    """True when a Database Supertype(s) cell lists Legendary."""
    for part in re.split(r"[;,/]", supertype_cell or ""):
        if part.strip().lower() == "legendary":
            return True
    return False


# Free-text cues mapped to defect tags (finalize_verdict + parse fallbacks)
PROSE_DEFECT_PATTERNS: list[tuple[str, str]] = [
    ("multi_card_in_one_file", r"\b(two|multiple|multi|double|split|side[- ]?by[- ]?side)\s+cards?\b"),
    ("multi_card_in_one_file", r"\bcollage\b"),
    ("multi_card_in_one_file", r"\bmore than one\b.*\bcard\b"),
    ("conversion_bleed", r"\b(bleed|smeared|garbage pixel|repeated edge|harsh seam)\b"),
    ("border_seam_lines", r"\b(faint|hair|scratch|thin).{0,30}\b(line|lines|seam)\b"),
    ("border_seam_lines", r"\b(line|lines).{0,30}\b(border|along)\b"),
    ("corner_color_mismatch", r"\b(corner|corners).{0,40}\b(mismatch|different color|off[- ]?color|discolor)\b"),
    ("corner_color_mismatch", r"\bcolor mismatch\b"),
    ("corner_trim", r"\b(corner|corners|border|edge).{0,40}\b(trim|clip|clipp|cropp)\b"),
    ("corner_trim", r"\btrimmed corners?\b"),
    ("wrong_silhouette", r"\b(wrong|bad|incorrect)\s+(print\s+)?(dimensions|aspect|size)\b"),
    ("wrong_silhouette", r"\b(landscape|square)\s+(canvas|image|file)\b"),
    ("wrong_silhouette", r"\b(extreme aspect|letterbox|huge margin)\b"),
]

SUSPICIOUS_PROSE_RE = re.compile(
    r"\b("
    r"corner|corners|border|bleed|trim|clipp|mismatch|seam|collage|"
    r"multi|two cards|side by side|conversion|artifact|smeared|clip"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class ReviewResult:
    verdict: str
    issues: list[str] = field(default_factory=list)
    notes: str = ""
    step1_defects: list[str] = field(default_factory=list)
    heuristic_flags: list[str] = field(default_factory=list)
    raw_step1: str = ""
    raw_step2: str = ""
    forced_n_reason: str = ""


def format_assessment_comment(review: ReviewResult, *, max_len: int = 500) -> str:
    """One-line sheet comment: defect tags + model notes (empty when verdict is Y)."""
    if review.verdict == "Y":
        return ""
    parts: list[str] = []
    if review.issues:
        parts.append(", ".join(review.issues))
    if review.notes:
        parts.append(review.notes.strip())
    if review.forced_n_reason:
        reason = review.forced_n_reason.strip()
        if reason and reason not in " ".join(parts):
            parts.append(reason)
    text = " — ".join(p for p in parts if p)
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def _prose_match_is_negated(text: str, match: re.Match[str]) -> bool:
    """Skip matches immediately preceded by no/not/without (e.g. 'no color mismatch')."""
    prefix = text[max(0, match.start() - 24) : match.start()]
    return bool(re.search(r"\b(no|not|without|none|clean)\s+\w*\s*$", prefix, re.IGNORECASE))


def defects_from_prose(text: str) -> list[str]:
    """Infer defect tags from free-text observations or raw model output."""
    if not text:
        return []
    found: list[str] = []
    for tag, pattern in PROSE_DEFECT_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            if not _prose_match_is_negated(text, m):
                found.append(tag)
                break
    return sorted(set(found))


def normalize_issues(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        tag = item.strip().lower().replace(" ", "_").replace("-", "_")
        if not tag or tag in ("tags", "none", "n/a"):
            continue
        tag = DEFECT_ALIASES.get(tag, tag)
        if tag in KNOWN_DEFECT_TAGS:
            out.append(tag)
        else:
            for known in KNOWN_DEFECT_TAGS:
                if known in tag or tag in known:
                    out.append(known)
                    break
    return sorted(set(out))


def _parse_json_blob(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty model response")
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        candidates.append(brace.group(0))
    last_err: Exception | None = None
    for chunk in candidates:
        try:
            data = json.loads(chunk)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as e:
            last_err = e
    raise ValueError(f"could not parse JSON from: {text[:400]!r}") from last_err


def parse_verdict_response(raw: str) -> tuple[str, dict[str, Any]]:
    data = _parse_json_blob(raw)
    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict in ("Y", "N"):
        return verdict, data
    good = data.get("good")
    if isinstance(good, bool):
        return ("Y" if good else "N"), data
    m = re.search(r"\b([YN])\b", raw.upper())
    if m:
        return m.group(1), data
    raise ValueError(f"no verdict in: {raw[:400]!r}")


def parse_defects_response(raw: str) -> tuple[list[str], str]:
    data = _parse_json_blob(raw)
    defects = normalize_issues(data.get("defects") or data.get("issues"))
    obs = str(data.get("observations") or data.get("notes") or "").strip()
    return defects, obs


def image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def resize_for_vision(src_path: str, max_side: int) -> tuple[str, bool]:
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        if max(w, h) <= max_side:
            return src_path, False
        scale = max_side / float(max(w, h))
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        fd, out = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        im.save(out, "JPEG", quality=92)
        return out, True


def suitable_for_corner_crops(w: int, h: int, *, landscape_ok: bool = False) -> bool:
    """Corner zooms are useful on normal single-card canvases (portrait or Plane landscape)."""
    if w <= 0 or h <= 0:
        return False
    if min(w, h) < 120:
        return False
    aspect = w / float(h)
    if landscape_ok:
        return 1.10 <= aspect <= 1.85
    return 0.55 <= aspect <= 0.90


def extract_corner_crops(src_path: str, frac: float = 0.18) -> tuple[list[str], list[str]]:
    """Return (temp paths, all paths including full image) for multi-image vision."""
    temps: list[str] = []
    paths: list[str] = [src_path]
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        cw = max(24, int(w * frac))
        ch = max(24, int(h * frac))
        boxes = [
            (0, 0, cw, ch),
            (w - cw, 0, w, ch),
            (0, h - ch, cw, h),
            (w - cw, h - ch, w, h),
        ]
        for i, box in enumerate(boxes):
            crop = im.crop(box)
            fd, out = tempfile.mkstemp(suffix=f"-corner{i}.jpg")
            os.close(fd)
            crop.save(out, "JPEG", quality=92)
            temps.append(out)
            paths.append(out)
    return temps, paths


def _avg_rgb(im: Image.Image) -> tuple[float, float, float]:
    px = list(im.getdata())
    if not px:
        return (0.0, 0.0, 0.0)
    n = len(px)
    return (sum(p[0] for p in px) / n, sum(p[1] for p in px) / n, sum(p[2] for p in px) / n)


def _color_dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def _rgb_spread(avgs: list[tuple[float, float, float]]) -> float:
    if not avgs:
        return 0.0
    per_ch = [
        max(a[i] for a in avgs) - min(a[i] for a in avgs) for i in range(3)
    ]
    return sum(per_ch)


def _corner_adjacent_dists(
    im: Image.Image, w: int, h: int, band: int
) -> list[float]:
    """Per-corner color distance to the border strip on the same side."""
    pairs = [
        ((0, 0, band * 2, band * 2), (band, 0, band * 4, band)),
        ((w - band * 2, 0, w, band * 2), (w - band * 4, 0, w - band, band)),
        ((0, h - band * 2, band * 2, h), (band, h - band, band * 4, h)),
        ((w - band * 2, h - band * 2, w, h), (w - band * 4, h - band, w - band, h)),
    ]
    dists: list[float] = []
    for cbox, ebox in pairs:
        dists.append(_color_dist(_avg_rgb(im.crop(cbox)), _avg_rgb(im.crop(ebox))))
    return dists


def _smooth_1d(values: list[float], kernel: int) -> list[float]:
    if not values:
        return []
    kernel = max(1, kernel)
    if kernel == 1:
        return list(values)
    half = kernel // 2
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        chunk = values[lo:hi]
        out.append(sum(chunk) / len(chunk))
    return out


def _ink_runs(mask: list[bool]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, on in enumerate(mask):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def _detect_multi_card(im: Image.Image, w: int, h: int) -> bool:
    """Landscape composites with a bright gutter between two card columns."""
    if h <= 0 or w / float(h) < 1.22:
        return False
    gw = min(240, w)
    gh = min(320, h)
    gray = im.convert("L").resize((gw, gh))
    px = gray.load()
    if px is None:
        return False
    col_sums = [
        float(sum(px[x, y] for y in range(gh))) for x in range(gw)
    ]
    if not col_sums or max(col_sums) <= 0:
        return False
    smooth = _smooth_1d(col_sums, max(5, gw // 25))
    vmax = max(smooth)
    lo, hi = int(gw * 0.12), int(gw * 0.88)
    if hi <= lo:
        return False
    valley = min(smooth[lo:hi]) / vmax
    if valley > 0.27:
        return False
    thresh = vmax * 0.42
    runs = _ink_runs([v > thresh for v in smooth])
    if len(runs) < 2:
        return False
    gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
    return max(gaps, default=0) >= gw * 0.035


def _detect_conversion_bleed(
    corner_dists: list[float],
    corner_avgs: list[tuple[float, float, float]],
) -> bool:
    """Uniform gray smear in all four corners vs a dark border ring."""
    if len(corner_dists) < 4 or len(corner_avgs) < 4:
        return False
    if any(d < 90 for d in corner_dists):
        return False
    if _rgb_spread(corner_avgs) > 22:
        return False
    corner_brightness = sum(sum(c) for c in corner_avgs) / (4 * 3)
    return corner_brightness > 45


def _detect_corner_color_mismatch(corner_dists: list[float]) -> bool:
    """Require strong, consistent corner vs edge mismatch (reduces false positives)."""
    hot = [d for d in corner_dists if d > 72]
    return len(hot) >= 3 and max(corner_dists, default=0) > 88


def _spikes_are_side_padding_junction(
    spike_indices: list[int],
    *,
    profile_len: int,
    strip_height: int,
    image_h: int,
    band: int,
    deep: int,
    vertical_side: bool,
) -> bool:
    """Side-strip contrast spikes at the grey/black bottom gutter — not seam lines."""
    if not vertical_side or not spike_indices or len(spike_indices) > 4:
        return False
    junction_start = image_h - max(deep * 4, band * 5, (image_h * 26) // 100)
    ys = [
        int(i / max(1, profile_len - 1) * max(1, strip_height - 1))
        for i in spike_indices
    ]
    return all(y >= junction_start for y in ys)


def _border_seam_strip_spikes(
    im: Image.Image,
    w: int,
    h: int,
    band: int,
) -> list[tuple[str, tuple[int, int, int, int], list[int], int]]:
    """
    Return seam spike clusters per border strip.

    Each entry: (label, box, spike_indices, profile_len) where box is
    (x0, y0, x1, y1) in image coordinates.
    """
    if w < 80 or h < 80:
        return []
    deep = max(12, min(band * 2, min(w, h) // 8))
    strips: list[tuple[str, tuple[int, int, int, int]]] = [
        ("top", (0, 0, w, deep)),
        ("bottom", (0, h - deep, w, h)),
        ("left", (0, 0, deep, h)),
        ("right", (w - deep, 0, w, h)),
    ]
    hits: list[tuple[str, tuple[int, int, int, int], list[int], int]] = []
    for label, box in strips:
        x0, y0, x1, y1 = box
        sw, sh = x1 - x0, y1 - y0
        if sw < 20 or sh < 20:
            continue
        strip = im.crop(box)
        vertical_side = sh > sw * 2
        gray = strip.convert("L").resize((min(160, sw), min(160, sh)))
        px = gray.load()
        if px is None:
            continue
        gw, gh = gray.size
        along_long = gw >= gh
        length = gw if along_long else gh
        cross = gh if along_long else gw
        profile: list[float] = []
        for i in range(length):
            vals = [
                float(px[i, j] if along_long else px[j, i])
                for j in range(cross)
            ]
            profile.append(max(vals) - min(vals))
        if not profile:
            continue
        med = sorted(profile)[len(profile) // 2]
        if med > 35:
            continue
        spike_positions: list[int] = []
        for i in range(2, len(profile) - 2):
            local = profile[i]
            if local < med + 14:
                continue
            neighbors = (
                profile[i - 1] + profile[i - 2] + profile[i + 1] + profile[i + 2]
            ) / 4
            if local > neighbors + 18 and local > 28:
                spike_positions.append(i)
        if not spike_positions:
            continue
        if _spikes_are_side_padding_junction(
            spike_positions,
            profile_len=length,
            strip_height=sh,
            image_h=h,
            band=band,
            deep=deep,
            vertical_side=vertical_side,
        ):
            continue
        clusters = 1
        for a, b in zip(spike_positions, spike_positions[1:]):
            if b - a > 2:
                clusters += 1
        if clusters <= 3:
            hits.append((label, box, spike_positions, length))
    return hits


def _detect_border_seam_lines(im: Image.Image, w: int, h: int, band: int) -> bool:
    """Faint high-contrast streaks in the outer border band (extension line artifacts)."""
    strips = _border_seam_strip_spikes(im, w, h, band)
    return len(strips) >= 2


def inpaint_border_seam_lines(
    img: Image.Image,
    *,
    gap: int = 2,
    line_half: int = 1,
) -> tuple[Image.Image, int]:
    """
    Paint over faint border-band seam streaks by blending colors from either side.

    Uses the same spike finder as ``_detect_border_seam_lines``; only touches
    pixels in the outer border strips when spikes are found.
    """
    out = img.convert("RGB").copy()
    w, h = out.size
    if w < 80 or h < 80:
        return out, 0
    px = out.load()
    if px is None:
        return out, 0

    band = max(8, min(w, h) // 25)
    strips = _border_seam_strip_spikes(out, w, h, band)
    if not strips:
        return out, 0

    changed = 0

    def blend_across(x: int, y: int, *, horizontal: bool) -> tuple[int, int, int]:
        if horizontal:
            y0, y1 = y - gap, y + gap
            if y0 < 0 or y1 >= h:
                return px[x, y][:3]
            a, b = px[x, y0][:3], px[x, y1][:3]
        else:
            x0, x1 = x - gap, x + gap
            if x0 < 0 or x1 >= w:
                return px[x, y][:3]
            a, b = px[x0, y][:3], px[x1, y][:3]
        return ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2, (a[2] + b[2]) // 2)

    for label, box, spikes, profile_len in strips:
        x0, y0, x1, y1 = box
        sw, sh = x1 - x0, y1 - y0
        for spike_i in spikes:
            t = spike_i / max(1, profile_len - 1)
            if label in ("top", "bottom"):
                x = x0 + int(round(t * max(0, sw - 1)))
                for y in range(y0, y1):
                    for dx in range(-line_half, line_half + 1):
                        xi = x + dx
                        if xi < 0 or xi >= w:
                            continue
                        new = blend_across(xi, y, horizontal=False)
                        if px[xi, y][:3] != new:
                            px[xi, y] = new
                            changed += 1
            else:
                y = y0 + int(round(t * max(0, sh - 1)))
                for x in range(x0, x1):
                    for dy in range(-line_half, line_half + 1):
                        yi = y + dy
                        if yi < 0 or yi >= h:
                            continue
                        new = blend_across(x, yi, horizontal=True)
                        if px[x, yi][:3] != new:
                            px[x, yi] = new
                            changed += 1

    return out, changed


def _gray_percentile(gray: Image.Image, pct: float) -> int:
    hist = gray.histogram()
    total = sum(hist)
    if total <= 0:
        return 0
    target = total * pct / 100.0
    acc = 0
    for value, count in enumerate(hist):
        acc += count
        if acc >= target:
            return value
    return 255


def _detect_wrong_silhouette(
    w: int, h: int, *, landscape_ok: bool = False
) -> bool:
    """Canvas aspect is not a normal printable card silhouette.

    Portrait default: ~63×88 mm (w/h ≈ 0.72).
    When ``landscape_ok`` (Plane cards): expect horizontal ~88×63 mm (w/h ≈ 1.39).
    """
    if h <= 0 or w <= 0:
        return False
    aspect = w / float(h)
    if landscape_ok:
        # Portrait Plane canvas after failed rotate, or extreme landscape.
        if h > w * 1.02:
            return True
        if aspect < 1.16 or aspect > 1.67:
            return True
        return False
    # Single-card landscape canvas (multi-card composites use multi_card_in_one_file).
    if w > h * 1.02:
        return True
    # Portrait but far from standard printable aspect.
    if aspect < 0.60 or aspect > 0.86:
        return True
    return False


def heuristic_checks(
    image_path: str, *, landscape_ok: bool = False, legendary_ok: bool = False
) -> list[str]:
    flags: list[str] = []
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        band = max(8, min(w, h) // 25)

        corners = [
            im.crop((0, 0, band * 2, band * 2)),
            im.crop((w - band * 2, 0, w, band * 2)),
            im.crop((0, h - band * 2, band * 2, h)),
            im.crop((w - band * 2, h - band * 2, w, h)),
        ]
        corner_avgs = [_avg_rgb(c) for c in corners]
        corner_dists = _corner_adjacent_dists(im, w, h, band)

        if _detect_multi_card(im, w, h):
            flags.append("multi_card_in_one_file")
        elif _detect_wrong_silhouette(w, h, landscape_ok=landscape_ok):
            flags.append("wrong_silhouette")
        elif not legendary_ok and _detect_conversion_bleed(corner_dists, corner_avgs):
            flags.append("conversion_bleed")
        elif not legendary_ok and _detect_border_seam_lines(im, w, h, band):
            flags.append("border_seam_lines")
        elif not legendary_ok and _detect_corner_color_mismatch(corner_dists):
            flags.append("corner_color_mismatch")

    return sorted(set(flags))


def _drop_false_landscape_silhouette(
    tags: list[str], *, landscape_ok: bool, w: int, h: int
) -> list[str]:
    """Drop vision wrong_silhouette when Plane landscape dimensions are valid."""
    if not landscape_ok or "wrong_silhouette" not in tags:
        return tags
    if _detect_wrong_silhouette(w, h, landscape_ok=True):
        return tags
    return [t for t in tags if t != "wrong_silhouette"]


# Legend crown frame art often triggers these heuristics / vision tags falsely.
LEGENDARY_CROWN_SOFT_DEFECTS = frozenset(
    {"border_seam_lines", "corner_trim", "corner_color_mismatch", "conversion_bleed"}
)


def _drop_false_legendary_crown_defects(
    tags: list[str], *, legendary_ok: bool
) -> list[str]:
    """Drop crown-related false positives on Legendary cards."""
    if not legendary_ok:
        return tags
    return [t for t in tags if t not in LEGENDARY_CROWN_SOFT_DEFECTS]


def ollama_chat(
    *,
    host: str,
    model: str,
    prompt: str,
    image_paths: list[str],
    timeout: float,
    temperature: float,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature},
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64(p) for p in image_paths],
            }
        ],
    }
    url = f"{host.rstrip('/')}/api/chat"
    resp = requests.post(url, json=payload, timeout=timeout)
    if resp.status_code >= 500 and len(image_paths) > 1:
        payload["messages"][0]["images"] = [image_b64(image_paths[0])]
        resp = requests.post(url, json=payload, timeout=timeout)
    if not resp.ok:
        detail = (resp.text or "").strip()[:400]
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason} for {url}"
            + (f": {detail}" if detail else ""),
            response=resp,
        )
    return (resp.json().get("message") or {}).get("content") or ""


# PIL signals trusted to fail a card without vision agreement
HIGH_CONFIDENCE_HEURISTICS = frozenset(
    {
        "multi_card_in_one_file",
        "conversion_bleed",
        "border_seam_lines",
        "wrong_silhouette",
    }
)

# Step-1 tags that must not be ignored when step-2 says Y
STEP1_SERIOUS_DEFECTS = frozenset(
    {
        "wrong_silhouette",
        "multi_card_in_one_file",
        "conversion_bleed",
        "border_seam_lines",
    }
)

# Step-1-only tags vision often over-reports; step-2 Y can override these alone
STEP1_SOFT_DEFECTS = frozenset({"corner_color_mismatch", "corner_trim"})


def applied_fixes_cleared(
    *,
    applied_fixes: list[str],
    original_defects: list[str],
    review: ReviewResult,
    fixable_tags: frozenset[str],
) -> tuple[bool, str]:
    """Each applied fixable defect must be gone from objective signals.

    When reassess verdict is Y, only PIL heuristics count — ``ReviewResult.issues``
    still includes unconfirmed step-1 tags and vision often lists a tag in issues
    while returning Y (e.g. Thallid 905). When verdict is N, issues + heuristics apply.
    """
    if review.verdict == "Y":
        remaining = set(review.heuristic_flags)
    else:
        remaining = set(review.heuristic_flags) | set(review.issues)
    targets = [
        t for t in applied_fixes if t in fixable_tags and t in original_defects
    ]
    still_bad = sorted(t for t in targets if t in remaining)
    if still_bad:
        return False, f"still present after fix: {', '.join(still_bad)}"
    return True, ""


def finalize_verdict(
    *,
    step2_verdict: str,
    step2_issues: list[str],
    step1_defects: list[str],
    heuristic_flags: list[str],
    step1_observations: str = "",
    step2_notes: str = "",
    raw_step1: str = "",
    raw_step2: str = "",
    default_unsure: str = "Y",
) -> tuple[str, str]:
    strong_heur = [h for h in heuristic_flags if h in HIGH_CONFIDENCE_HEURISTICS]

    soft_step1 = [t for t in step1_defects if t in STEP1_SOFT_DEFECTS]
    hard_step1 = [t for t in step1_defects if t in STEP1_SERIOUS_DEFECTS]

    if "wrong_silhouette" in step1_defects or "wrong_silhouette" in step2_issues:
        return "N", "wrong_silhouette"

    if step2_verdict == "Y":
        if strong_heur:
            issues = sorted(set(strong_heur) | set(step2_issues))
            return "N", f"heuristics override step2 Y: {', '.join(issues)}"
        # Step-1 alone often over-reports; require PIL heuristics to agree on serious tags.
        confirmed_serious = [t for t in hard_step1 if t in heuristic_flags]
        if confirmed_serious:
            return "N", f"confirmed serious: {', '.join(confirmed_serious)}"
        if soft_step1 or hard_step1:
            dropped = sorted(set(soft_step1) | set(hard_step1))
            return "Y", f"step2 Y overruled unconfirmed step1: {', '.join(dropped)}"
        return "Y", ""

    if strong_heur:
        issues = sorted(set(strong_heur) | set(hard_step1) | set(step2_issues))
        return "N", f"heuristics: {', '.join(strong_heur)}; issues={', '.join(issues)}"

    if step2_verdict == "N":
        # Step-2 N with only soft tags and no heuristics: treat as cautious Y unless issues listed.
        if not step2_issues and not strong_heur and not hard_step1:
            if soft_step1:
                return "Y", f"step2 bare N overruled soft step1: {', '.join(soft_step1)}"
            return "Y", "step2 bare N treated as cautious pass"
        if not heuristic_flags:
            dropped = sorted(set(hard_step1) | set(soft_step1) | set(step2_issues))
            return "Y", f"heuristics clear overruled step2 N: {', '.join(dropped)}"
        issues = sorted(set(hard_step1) | set(soft_step1) | set(step2_issues))
        return "N", f"step2 N; issues={', '.join(issues) or 'none'}"

    if hard_step1:
        return "N", f"step1 serious: {', '.join(hard_step1)}"
    if soft_step1:
        return "N", f"step1 soft only: {', '.join(soft_step1)}"

    return default_unsure, f"unclear step2 {step2_verdict!r}; default {default_unsure}"


def review_image(
    *,
    image_path: str,
    card_id: str,
    card_name: str,
    side_name: str,
    host: str,
    model: str,
    timeout: float,
    temperature: float = 0.0,
    use_corner_crops: bool = True,
    two_step: bool = True,
    landscape_ok: bool = False,
    legendary_ok: bool = False,
) -> ReviewResult:
    corner_temps: list[str] = []
    image_paths = [image_path]
    with Image.open(image_path) as _im:
        _w, _h = _im.size
    if use_corner_crops and suitable_for_corner_crops(
        _w, _h, landscape_ok=landscape_ok
    ):
        corner_temps, image_paths = extract_corner_crops(image_path)

    silhouette_rule = (
        SILHOUETTE_RULE_LANDSCAPE if landscape_ok else SILHOUETTE_RULE_PORTRAIT
    )
    if legendary_ok:
        silhouette_rule = f"{silhouette_rule}. {LEGENDARY_CROWN_RULE}"
    heuristic_flags = heuristic_checks(
        image_path, landscape_ok=landscape_ok, legendary_ok=legendary_ok
    )
    try:
        if two_step:
            raw1 = ollama_chat(
                host=host,
                model=model,
                prompt=PROMPT_STEP1_DEFECTS.format(
                    card_id=card_id,
                    card_name=card_name,
                    side_name=side_name,
                    silhouette_rule=silhouette_rule,
                ),
                image_paths=image_paths,
                timeout=timeout,
                temperature=temperature,
            )
            step1_defects, obs1 = parse_defects_response(raw1)
            step1_defects = _drop_false_landscape_silhouette(
                step1_defects, landscape_ok=landscape_ok, w=_w, h=_h
            )
            step1_defects = _drop_false_legendary_crown_defects(
                step1_defects, legendary_ok=legendary_ok
            )
            step1_payload = json.dumps(
                {"defects": step1_defects, "observations": obs1}
            )
            raw2 = ollama_chat(
                host=host,
                model=model,
                prompt=PROMPT_STEP2_VERDICT.format(
                    step1_json=step1_payload,
                    heuristic_summary=", ".join(heuristic_flags) or "none",
                    silhouette_rule=silhouette_rule,
                ),
                image_paths=image_paths,
                timeout=timeout,
                temperature=temperature,
            )
            step2_verdict, data2 = parse_verdict_response(raw2)
            step2_issues = normalize_issues(data2.get("issues"))
            step2_issues = _drop_false_landscape_silhouette(
                step2_issues, landscape_ok=landscape_ok, w=_w, h=_h
            )
            step2_issues = _drop_false_legendary_crown_defects(
                step2_issues, legendary_ok=legendary_ok
            )
            notes = str(data2.get("notes") or "").strip()
            verdict, forced = finalize_verdict(
                step2_verdict=step2_verdict,
                step2_issues=step2_issues,
                step1_defects=step1_defects,
                heuristic_flags=heuristic_flags,
                step1_observations=obs1,
                step2_notes=notes,
                raw_step1=raw1,
                raw_step2=raw2,
            )
            return ReviewResult(
                verdict=verdict,
                issues=sorted(
                    set(step1_defects) | set(step2_issues) | set(heuristic_flags)
                ),
                notes=notes or obs1,
                step1_defects=step1_defects,
                heuristic_flags=heuristic_flags,
                raw_step1=raw1,
                raw_step2=raw2,
                forced_n_reason=forced,
            )

        raw = ollama_chat(
            host=host,
            model=model,
            prompt=PROMPT_SINGLE_PASS.format(
                card_id=card_id,
                card_name=card_name,
                side_name=side_name,
                silhouette_rule=silhouette_rule,
            ),
            image_paths=image_paths,
            timeout=timeout,
            temperature=temperature,
        )
        step2_verdict, data2 = parse_verdict_response(raw)
        step2_issues = normalize_issues(data2.get("issues"))
        step2_issues = _drop_false_landscape_silhouette(
            step2_issues, landscape_ok=landscape_ok, w=_w, h=_h
        )
        step2_issues = _drop_false_legendary_crown_defects(
            step2_issues, legendary_ok=legendary_ok
        )
        notes = str(data2.get("notes") or "").strip()
        verdict, forced = finalize_verdict(
            step2_verdict=step2_verdict,
            step2_issues=step2_issues,
            step1_defects=[],
            heuristic_flags=heuristic_flags,
            step2_notes=notes,
            raw_step2=raw,
        )
        return ReviewResult(
            verdict=verdict,
            issues=sorted(set(step2_issues) | set(heuristic_flags)),
            notes=notes,
            heuristic_flags=heuristic_flags,
            raw_step2=raw,
            forced_n_reason=forced,
        )
    finally:
        for p in corner_temps:
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def cleanup_temp_paths(*paths: str) -> None:
    for p in paths:
        if p and os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
