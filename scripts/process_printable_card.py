"""
One-stop printable prep for Hellscube card images: border transform + vision assessment.

**Transform** — ``prepare_card_for_printing_stretch``: paste the card on a larger
canvas (12–64px border based on width), stretch the outermost card rows/columns
into the straight padding bands, and fill the padding corners by sampling a
quarter-circle just inside the card's rounded frame corner and stretching it
radially to the print corner. Covers white/transparent corner artifacts and
transparent holes in the source art.

**Assessment** — two-step Ollama vision QA (default ``qwen2.5vl:7b``) plus PIL
heuristics from ``printable_image_qa.review_image``. Verdict ``Y`` means
printable; ``N`` lists defect tags (``corner_color_mismatch``, ``corner_trim``,
``wrong_silhouette``, ``multi_card_in_one_file``, ``conversion_bleed``,
``border_seam_lines``). Non-card-shaped sources are warned about up front and
flagged as ``wrong_silhouette`` by the assessment.

Local files in, local PNGs out — no sheets, no GCS.

Examples:
  python scripts/process_printable_card.py card.png
  python scripts/process_printable_card.py cards/ -o out/
  python scripts/process_printable_card.py card.png --assess off
  python scripts/process_printable_card.py card.png --model qwen2.5vl:7b --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import mork_repo_root  # noqa: F401  pylint: disable=unused-import  (repo root on sys.path)

_scripts = str(Path(__file__).resolve().parent)
if _scripts in sys.path:
    sys.path.remove(_scripts)
sys.path.insert(0, _scripts)

import requests
from PIL import Image

from prepare_card_for_printing_stretch import prepare_card_for_printing_stretch
from printable_image_qa import (
    _detect_wrong_silhouette,
    cleanup_temp_paths,
    format_assessment_comment,
    resize_for_vision,
    review_image,
)

DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _iter_inputs(raw_paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in raw_paths:
        p = Path(raw)
        if p.is_dir():
            out.extend(
                sorted(
                    f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXTS
                )
            )
        elif p.is_file():
            out.append(p)
        else:
            print(f"warning: skipping missing input {raw}", file=sys.stderr)
    return out


def _ollama_ready(host: str, model: str) -> tuple[bool, str]:
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=3)
        resp.raise_for_status()
    except requests.RequestException as e:
        return False, f"Ollama unreachable at {host}: {e}"
    names = [m.get("name", "") for m in resp.json().get("models", [])]
    if not any(n == model or n.split(":")[0] == model for n in names):
        return False, f"model {model!r} not pulled (have: {', '.join(names) or 'none'})"
    return True, ""


def _assess(
    prepared: Path, args: argparse.Namespace, *, landscape_ok: bool = False
) -> dict:
    vision_path = str(prepared)
    scaled = ""
    if args.max_image_side > 0:
        vision_path, resized = resize_for_vision(str(prepared), args.max_image_side)
        if resized:
            scaled = vision_path
    try:
        review = review_image(
            image_path=vision_path,
            card_id=prepared.stem,
            card_name=prepared.stem,
            side_name="side 1",
            host=args.ollama_host,
            model=args.model,
            timeout=args.timeout,
            temperature=0.0,
            use_corner_crops=True,
            two_step=True,
            landscape_ok=landscape_ok,
        )
    finally:
        cleanup_temp_paths(scaled)
    return {
        "verdict": review.verdict,
        "issues": review.issues,
        "notes": review.notes,
        "heuristics": review.heuristic_flags,
        "comment": format_assessment_comment(review),
    }


def _output_path(src: Path, args: argparse.Namespace) -> Path:
    name = f"{src.stem}{args.suffix}.png"
    if args.output_dir:
        return Path(args.output_dir) / name
    return src.with_name(name)


def process_one(src: Path, args: argparse.Namespace, *, do_assess: bool) -> dict:
    result: dict = {"input": str(src)}
    landscape_ok = bool(args.plane)

    with Image.open(src) as im:
        w, h = im.size
    result["source_size"] = [w, h]
    if _detect_wrong_silhouette(w, h, landscape_ok=landscape_ok):
        expected = (
            "landscape ~1.16-1.67 w/h (Plane)"
            if landscape_ok
            else "portrait ~0.63-0.82 w/h"
        )
        result["shape_warning"] = (
            f"source {w}x{h} is not card-shaped ({expected} expected)"
        )
        print(f"  warning: {result['shape_warning']}")

    out_path = _output_path(src, args)
    prepare_card_for_printing_stretch(
        str(src),
        out_path=str(out_path),
        log_tag="transform",
        force_landscape=landscape_ok,
    )
    result["output"] = str(out_path)

    if do_assess:
        review = _assess(out_path, args, landscape_ok=landscape_ok)
        result["assessment"] = review
        tag = "PASS" if review["verdict"] == "Y" else "FAIL"
        detail = review["comment"] or review["notes"]
        print(f"  assess: {tag}" + (f" — {detail}" if detail else ""))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("inputs", nargs="+", help="Card image files and/or directories")
    parser.add_argument(
        "-o", "--output-dir", help="Output directory (default: beside each input)"
    )
    parser.add_argument(
        "--suffix",
        default="_printable",
        help="Output filename suffix (default: _printable)",
    )
    parser.add_argument(
        "--assess",
        choices=["auto", "on", "off"],
        default="auto",
        help="Vision assessment: auto (when Ollama is reachable), on (require), off",
    )
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--max-image-side",
        type=int,
        default=1280,
        help="Downscale copies sent to the vision model (0 = no scaling)",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--plane",
        action="store_true",
        help="Treat inputs as Plane cards (force landscape + landscape silhouette QA)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print a JSON summary at the end"
    )
    args = parser.parse_args()

    inputs = _iter_inputs(args.inputs)
    if not inputs:
        print("No input images found.", file=sys.stderr)
        return 1
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    do_assess = args.assess != "off"
    if do_assess:
        ok, why = _ollama_ready(args.ollama_host, args.model)
        if not ok:
            if args.assess == "on":
                print(f"Assessment required but unavailable: {why}", file=sys.stderr)
                return 1
            print(f"Skipping assessment: {why}")
            do_assess = False

    results: list[dict] = []
    failures = 0
    for src in inputs:
        print(f"[{src.name}]")
        try:
            result = process_one(src, args, do_assess=do_assess)
        except Exception as e:  # pylint: disable=broad-except  keep batch going
            print(f"  ERROR: {e}", file=sys.stderr)
            results.append({"input": str(src), "error": str(e)})
            failures += 1
            continue
        if result.get("assessment", {}).get("verdict") == "N":
            failures += 1
        results.append(result)

    passed = sum(
        1 for r in results if r.get("assessment", {}).get("verdict") == "Y"
    )
    print(
        f"\nDone: {len(results)} card(s), "
        + (
            f"{passed} pass / {failures} fail"
            if do_assess
            else "assessment skipped"
        )
    )
    if args.json:
        print(json.dumps(results, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
