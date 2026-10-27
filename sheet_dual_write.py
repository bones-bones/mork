"""Optional Google Sheets mirror while Hellfall is system of record."""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes"})


def sheet_dual_write_enabled() -> bool:
    """When true, Mork still writes unapproved/token sheet rows (default on)."""
    raw = os.environ.get("SHEET_DUAL_WRITE", "1").strip().lower()
    return raw in _TRUTHY
