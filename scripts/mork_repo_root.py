"""Add the repository root to sys.path so scripts can import `shared_vars`, `hc_constants`, etc.

Run maintenance scripts from the repo root, e.g. `python scripts/download_and_upload_images_gcs.py`,
so paths like `./bot_secrets/client_secrets.json` resolve correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_rp = str(_root)
if _rp not in sys.path:
    sys.path.insert(0, _rp)
