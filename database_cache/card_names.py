"""Card name aliases — ported from hellfall shared nameHandling."""

from __future__ import annotations

import re
from itertools import product
from typing import Any

from database_cache.database_utils import fixName
from database_cache.setHandling import fixSetCode, isSetCode

_ANGLE_SET_CODE_RE = re.compile(r"^(.*) <([^>]+)>$")


def split_angle_set_code(text: str) -> tuple[str, str | None]:
    match = _ANGLE_SET_CODE_RE.match(text)
    if not match:
        return text, None
    name, raw_code = (part.strip() for part in match.groups())
    if raw_code.upper() == "HC" or isSetCode(raw_code):
        return name, fixSetCode(raw_code)
    return text, None


def _combine_face_names(face_names: list[list[str]]) -> list[str]:
    if not face_names:
        return []
    combinations = list(face_names[0])
    for current_face in face_names[1:]:
        combinations = [
            f"{prefix} // {name}" for prefix, name in product(combinations, current_face)
        ]
    return combinations


def _card_faces(card: dict[str, Any], *, drop_faces: bool) -> list[dict[str, Any]]:
    faces = card.get("card_faces")
    if not isinstance(faces, list):
        return [card]
    if drop_faces:
        return [face for face in faces if not face.get("drop_face")]
    return faces


def get_all_names(card: dict[str, Any], *, drop_faces: bool = False) -> list[str]:
    """All exact-match names for a card (aliases, faces, export names, etc.)."""
    fixed = fixName(card["name"])
    names = [fixed]
    name, code = split_angle_set_code(fixed)
    if name != fixed:
        names.append(name)
    while names[-1].endswith(" <hc>"):
        names.append(split_angle_set_code(names[-1])[0])
    if card.get("flavor_name"):
        names.append(fixName(str(card["flavor_name"])))
    if card.get("export_name"):
        names.append(fixName(str(card["export_name"])))
    if "card_faces" not in card and not code:
        return names

    name_set = set(names)

    def add_name(value: str) -> None:
        name_set.add(fixName(value))

    if "card_faces" in card:
        faces = _card_faces(card, drop_faces=drop_faces)
        face_names = []
        for face in faces:
            face_name_list = [face["name"]]
            if face.get("flavor_name"):
                face_name_list.append(str(face["flavor_name"]))
            if face.get("export_name"):
                face_name_list.append(str(face["export_name"]))
            face_names.append(face_name_list)
        card_faces = card.get("card_faces")
        if isinstance(card_faces, list):
            for i in range(len(card_faces)):
                for j in range(i + 1, len(card_faces)):
                    for combined in _combine_face_names(face_names[i:j]):
                        add_name(combined)

    if code:
        ending = f" <{code.lower()}>"
        for existing in list(name_set):
            if not existing.endswith(ending):
                add_name(f"{existing}{ending}")

    return list(name_set)
