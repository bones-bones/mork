"""Fail CI when Discord command names/aliases collide (case-insensitive).

discord.py refuses to load a cog when a new command name or alias collides with
an existing one. Static-scan ``cogs/`` and ``mork.py`` so that lands in CI
instead of at bot boot.

Usage (from repo root):
    python scripts/check_duplicate_commands.py
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = (
    REPO_ROOT / "cogs",
    REPO_ROOT / "mork.py",
)
COMMAND_DECORATOR_ATTRS = frozenset({"command", "group"})


@dataclass(frozen=True)
class NameBinding:
    name: str
    kind: str  # "command" or "alias"
    command: str
    path: Path
    lineno: int

    def location(self) -> str:
        try:
            rel = self.path.relative_to(REPO_ROOT)
        except ValueError:
            rel = self.path
        return f"{rel}:{self.lineno}"


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _str_list(node: ast.AST | None) -> list[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    values: list[str] = []
    for elt in node.elts:
        text = _const_str(elt)
        if text is None:
            return None
        values.append(text)
    return values


def _is_command_decorator(node: ast.AST) -> bool:
    """Match @commands.command / @bot.command / @commands.group(...)."""
    call = node
    if isinstance(node, ast.Call):
        call = node.func
    if isinstance(call, ast.Attribute) and call.attr in COMMAND_DECORATOR_ATTRS:
        return True
    return False


def _decorator_call(node: ast.AST) -> ast.Call | None:
    if isinstance(node, ast.Call) and _is_command_decorator(node):
        return node
    if _is_command_decorator(node):
        # Bare @commands.command — treat as Call with no args via synthetic empty.
        return ast.Call(func=node, args=[], keywords=[])  # type: ignore[arg-type]
    return None


def _bindings_for_function(
    func: ast.AsyncFunctionDef | ast.FunctionDef,
    path: Path,
) -> list[NameBinding]:
    for decorator in func.decorator_list:
        call = _decorator_call(decorator)
        if call is None:
            continue

        explicit_name: str | None = None
        aliases: list[str] = []
        for kw in call.keywords:
            if kw.arg == "name":
                explicit_name = _const_str(kw.value)
            elif kw.arg == "aliases":
                parsed = _str_list(kw.value)
                if parsed is not None:
                    aliases = parsed

        command_name = explicit_name or func.name
        bindings = [
            NameBinding(
                name=command_name,
                kind="command",
                command=command_name,
                path=path,
                lineno=func.lineno,
            )
        ]
        for alias in aliases:
            bindings.append(
                NameBinding(
                    name=alias,
                    kind="alias",
                    command=command_name,
                    path=path,
                    lineno=func.lineno,
                )
            )
        return bindings
    return []


def collect_bindings(paths: tuple[Path, ...] = SCAN_PATHS) -> list[NameBinding]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.py")))

    bindings: list[NameBinding] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                bindings.extend(_bindings_for_function(node, path))
    return bindings


def find_collisions(bindings: list[NameBinding]) -> dict[str, list[NameBinding]]:
    by_key: dict[str, list[NameBinding]] = defaultdict(list)
    for binding in bindings:
        by_key[binding.name.casefold()].append(binding)
    return {key: group for key, group in by_key.items() if len(group) > 1}


def format_collisions(collisions: dict[str, list[NameBinding]]) -> str:
    lines: list[str] = [
        "Duplicate Discord command names/aliases (case-insensitive):",
    ]
    for key in sorted(collisions):
        lines.append(f"  '{key}' claimed by:")
        for binding in collisions[key]:
            lines.append(
                f"    - {binding.kind} of !{binding.command} ({binding.location()})"
            )
    return "\n".join(lines)


def main() -> int:
    bindings = collect_bindings()
    collisions = find_collisions(bindings)
    if collisions:
        print(format_collisions(collisions), file=sys.stderr)
        return 1
    print(f"ok  no duplicate command names/aliases ({len(bindings)} bindings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
