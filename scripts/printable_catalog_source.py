"""Load Hellfall catalog cards for the printable GCS pipeline.

Catalog image layout (best-effort, mirrors Database sheet columns C / T / AF / AP / AZ):

- Single-faced cards: only top-level ``image`` is used (same as sheet when column T is empty).
- Multi-faced cards: each ``card_faces[i]`` may have ``image``; face 0 falls back to top-level
  ``image`` when a face omits it. When more than one face URL is present, side 1 comes from the
  first face URL (not ``image`` alone), matching sheet behavior when column T is populated.

Type / supertype strings for vision QA are derived from ``type_line`` on the card or each face.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

SideEntry = tuple[str, str, str, int]


@dataclass(frozen=True)
class PrintableCatalogCard:
    """One catalog card ready for the printable sync loop."""

    card_id: str
    name: str
    card_set: str
    uses_primary: bool
    side_entries: list[SideEntry]
    source_row: int


def fetch_catalog(url: str, *, timeout: float = 120.0) -> dict[str, Any]:
    headers = {"User-Agent": "MorkPrintableSync/1.0 (+https://github.com/hellscube/mork)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"catalog JSON root must be object, got {type(data).__name__}")
    return data


def _cards_from_catalog_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "idMap" in payload:
        id_map = payload.get("idMap")
        if not isinstance(id_map, dict):
            raise ValueError("catalog idMap must be an object")
        return [v for v in id_map.values() if isinstance(v, dict)]
    cards = payload.get("data")
    if not isinstance(cards, list):
        keys = list(payload.keys())[:12]
        raise ValueError(f"catalog missing data list or idMap; keys={keys!r}")
    return [c for c in cards if isinstance(c, dict)]


def _type_and_supertype(type_line: str) -> tuple[str, str]:
    line = (type_line or "").strip()
    if not line:
        return "", ""
    parts = [p.strip() for p in line.split("—", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    if "Legendary" in line:
        return line, "Legendary"
    return line, ""


def side_entries_from_catalog_card(card: dict[str, Any]) -> tuple[bool, list[SideEntry]]:
    faces = card.get("card_faces")
    face_dicts: list[dict[str, Any]] = []
    if isinstance(faces, list) and faces:
        face_dicts = [f for f in faces if isinstance(f, dict)]

    if not face_dicts:
        image = (card.get("image") or "").strip()
        t, s = _type_and_supertype(str(card.get("type_line") or ""))
        if not image:
            return True, []
        return True, [(image, t, s, 0)]

    urls: list[str] = []
    meta: list[tuple[str, str]] = []
    for i, face in enumerate(face_dicts[:4]):
        url = (face.get("image") or "").strip()
        if not url and i == 0:
            url = (card.get("image") or "").strip()
        t, s = _type_and_supertype(str(face.get("type_line") or card.get("type_line") or ""))
        if url:
            urls.append(url)
            meta.append((t, s))

    if not urls:
        return True, []

    if len(urls) == 1:
        t, s = meta[0]
        return True, [(urls[0], t, s, 0)]

    return False, [(u, meta[i][0], meta[i][1], i) for i, u in enumerate(urls)]


def _printable_card_id(card: dict[str, Any]) -> str:
    hcid = card.get("hcid")
    if hcid is not None and str(hcid).strip():
        return str(hcid).strip()
    return str(card.get("id") or "").strip()


def iter_printable_catalog_cards(
    payload: dict[str, Any],
    *,
    first_ordinal: int = 2,
    last_ordinal: int | None = None,
) -> list[PrintableCatalogCard]:
    """Build printable work items in stable hcid order.

    ``first_ordinal`` / ``last_ordinal`` mirror Database sheet row numbers: ordinal 2 is the
    first card (same as ``--printable-first-row`` default).
    """
    raw = _cards_from_catalog_payload(payload)

    def _sort_key(c: dict[str, Any]) -> tuple[int, str]:
        h = c.get("hcid")
        try:
            return (int(str(h)), str(c.get("name") or ""))
        except (TypeError, ValueError):
            return (10**12, str(c.get("name") or ""))

    raw.sort(key=_sort_key)
    start_idx = max(0, first_ordinal - 2)
    end_idx = len(raw) if last_ordinal is None else min(len(raw), last_ordinal - 1)
    slice_cards = raw[start_idx:end_idx]

    out: list[PrintableCatalogCard] = []
    for offset, card in enumerate(slice_cards):
        card_set = str(card.get("set") or "").strip()
        if card_set == "HCV":
            continue
        uses_primary, side_entries = side_entries_from_catalog_card(card)
        if not side_entries:
            continue
        card_id = _printable_card_id(card)
        if not card_id:
            continue
        name = str(card.get("name") or "").strip() or card_id
        out.append(
            PrintableCatalogCard(
                card_id=card_id,
                name=name,
                card_set=card_set,
                uses_primary=uses_primary,
                side_entries=side_entries,
                source_row=first_ordinal + offset,
            )
        )
    return out
