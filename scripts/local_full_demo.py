"""
Local printable pipeline wrapper.

Runs fix_and_reassess with the canonical order:
  Database source → prepare_card_for_printing → fix → reassess

Example:
  python scripts/local_full_demo.py --id 950 --id 957
  python scripts/local_full_demo.py --id 950 --skip-reassess
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", dest="card_ids", action="append", required=True)
    parser.add_argument(
        "--output-dir",
        default="scripts/data/fix_compare/local_demo",
    )
    parser.add_argument("--skip-reassess", action="store_true")
    parser.add_argument("--vision-corners", default="off")
    args, extra = parser.parse_known_args()

    script = Path(__file__).resolve().parent / "fix_and_reassess.py"
    cmd = [
        sys.executable,
        str(script),
        "--local-only",
        "--from-db",
        "--output-dir",
        args.output_dir,
        "--vision-corners",
        args.vision_corners,
    ]
    if args.skip_reassess:
        cmd.append("--skip-reassess")
    for cid in args.card_ids:
        cmd.extend(["--id", cid])
    cmd.extend(extra)
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
