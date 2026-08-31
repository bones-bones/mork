"""Smoke test for a VM or local tree after deploy — no Discord token required.

Usage (from repo root):
    python scripts/verify_vm_deploy.py
    python scripts/verify_vm_deploy.py --check-service
"""

from __future__ import annotations

import argparse
import compileall
import importlib
import re
import subprocess
import sys
from pathlib import Path

import mork_repo_root  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)
REQUIRED_IMPORTS = (
    "aiofiles",
    "aiohttp",
    "discord",
    "dotenv",
    "gspread",
    "pandas",
    "PIL",
    "asyncpraw",
)


def check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        ver = ".".join(map(str, MIN_PYTHON))
        raise SystemExit(f"Python {ver}+ required; got {sys.version.split()[0]}")


def check_required_imports() -> None:
    missing: list[str] = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise SystemExit(f"Missing pip packages: {', '.join(missing)}")


SKIP_PATH_RX = re.compile(r"(?:^|/)(\.git|\.worktrees|mork-devvit|node_modules|\.venv)(?:/|$)")


def check_syntax() -> None:
    ok = compileall.compile_dir(
        REPO_ROOT,
        quiet=1,
        rx=SKIP_PATH_RX,
    )
    if not ok:
        raise SystemExit("Syntax errors found (compileall failed)")


def check_utils_import() -> None:
    from utils import at

    assert at([1, 2, 3], 1) == 2
    assert at([1, 2, 3], 9, default=None) is None
    assert at([1, 2, 3], 9, default=0) == 0


def check_cog_imports() -> None:
    # Import top-level cog modules without starting the bot (no token, no bot.run).
    importlib.import_module("cogs.General")
    importlib.import_module("cogs.Quotes")


def check_service_active() -> None:
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", "mork"],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit("systemd unit mork is not active (systemctl is-active failed)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Mork deploy readiness on a VM")
    parser.add_argument(
        "--check-service",
        action="store_true",
        help="Also require systemd unit mork to be active",
    )
    parser.add_argument(
        "--with-cogs",
        action="store_true",
        help="Import cogs.General and cogs.Quotes (needs bot_secrets/ and .env on the VM)",
    )
    args = parser.parse_args()

    checks: list[tuple[str, callable]] = [
        ("python version", check_python_version),
        ("pip dependencies", check_required_imports),
        ("syntax (compileall)", check_syntax),
        ("utils.at", check_utils_import),
    ]
    if args.with_cogs:
        checks.append(("cog imports", check_cog_imports))
    if args.check_service:
        checks.append(("systemd mork", check_service_active))

    print(f"Repo: {REPO_ROOT}")
    print(f"Interpreter: {sys.executable} ({sys.version.split()[0]})")

    for label, fn in checks:
        fn()
        print(f"  ok  {label}")

    print("All checks passed.")


if __name__ == "__main__":
    main()
