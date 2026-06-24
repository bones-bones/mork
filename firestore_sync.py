"""Sync accepted cards from mork into Hellfall Firestore (hellscube/cards)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import uuid4

from google.cloud import firestore
from google.oauth2 import service_account

import hc_constants

_CLIENT_SECRETS_PATH = "./bot_secrets/client_secrets.json"
_FIRESTORE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_db: firestore.Client | None = None


class FirestoreSyncError(Exception):
    """Raised when a card cannot be written to Firestore."""


@dataclass
class FirestoreWrite:
    doc_id: str
    was_create: bool
    previous: dict[str, Any] | None


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        credentials = service_account.Credentials.from_service_account_file(
            _CLIENT_SECRETS_PATH,
            scopes=_FIRESTORE_SCOPES,
        )
        _db = firestore.Client(
            credentials=credentials,
            database=hc_constants.FIRESTORE_DATABASE_ID,
        )
    return _db


def _cards_col() -> firestore.CollectionReference:
    return _get_db().collection(hc_constants.FIRESTORE_CARDS_COLLECTION)


def _parse_creators(creators: str) -> list[str]:
    if not creators:
        return []
    if ";" in creators:
        return [part.strip() for part in creators.split(";") if part.strip()]
    return [creators.strip()] if creators.strip() else []


def _default_legalities() -> dict[str, str]:
    return {
        "standard": "not_legal",
        "4cb": "not_legal",
        "commander": "not_legal",
    }


def _build_stub_card(
    *,
    hcid: str,
    name: str,
    image: str,
    creators: str,
    set_id: str,
    card_id: Optional[str] = None,
    oracle_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "object": "card",
        "kind": "card",
        "id": card_id or str(uuid4()),
        "oracle_id": oracle_id or str(uuid4()),
        "hcid": hcid,
        "name": name,
        "set": set_id,
        "collector_number": "",
        "layout": "normal",
        "image_status": "highres",
        "image": image,
        "mana_cost": "",
        "mana_value": 0,
        "type_line": "",
        "colors": [],
        "color_identity": [],
        "color_identity_hybrid": "[]",
        "keywords": [],
        "legalities": _default_legalities(),
        "creators": _parse_creators(creators),
        "rulings": "",
        "finish": "nonfoil",
        "border_color": "black",
        "frame": "stamp",
        "oracle_text": "",
    }


def _build_stub_token(
    *,
    hcid: str,
    name: str,
    image: str,
    creators: str,
    card_id: Optional[str] = None,
    oracle_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "object": "card",
        "kind": "token",
        "id": card_id or str(uuid4()),
        "oracle_id": oracle_id or str(uuid4()),
        "hcid": hcid,
        "name": name,
        "set": "HCT",
        "collector_number": "",
        "layout": "token",
        "image_status": "highres",
        "image": image,
        "mana_cost": "",
        "mana_value": 0,
        "supertypes": ["Token"],
        "types": [],
        "subtypes": [],
        "type_line": "",
        "oracle_text": "",
        "power": "",
        "toughness": "",
        "colors": [],
        "color_identity": [],
        "color_identity_hybrid": "[]",
        "keywords": [],
        "legalities": _default_legalities(),
        "creators": _parse_creators(creators),
        "rulings": "",
        "finish": "nonfoil",
        "border_color": "black",
        "frame": "token_2003",
    }


def _find_by_hcid(hcid: str) -> firestore.DocumentSnapshot | None:
    matches = list(_cards_col().where("hcid", "==", hcid).limit(2).stream())
    if len(matches) > 1:
        raise FirestoreSyncError(f"multiple Firestore cards share hcid {hcid!r}")
    return matches[0] if matches else None


def _find_by_name_and_set(name: str, set_id: str) -> firestore.DocumentSnapshot | None:
    matches = list(
        _cards_col()
        .where("name", "==", name)
        .where("set", "==", set_id)
        .limit(2)
        .stream()
    )
    if len(matches) > 1:
        raise FirestoreSyncError(
            f"multiple Firestore cards share name={name!r} set={set_id!r}"
        )
    return matches[0] if matches else None


def _lookup_doc(
    *,
    hcid: Optional[str],
    name: str,
    set_id: str,
) -> firestore.DocumentSnapshot | None:
    if hcid:
        found = _find_by_hcid(hcid)
        if found:
            return found
    return _find_by_name_and_set(name, set_id)


def sync_accepted_card(
    *,
    name: str,
    image: str,
    creators: str,
    set_id: str,
    hcid: Optional[str] = None,
    kind: Literal["card", "token"] = "card",
) -> FirestoreWrite:
    """Upsert a sparse accepted card into Firestore. Raises FirestoreSyncError on failure."""
    lookup_hcid = hcid or name
    existing = _lookup_doc(hcid=lookup_hcid, name=name, set_id=set_id)

    if kind == "token":
        stub = _build_stub_token(
            hcid=lookup_hcid,
            name=name,
            image=image,
            creators=creators,
        )
    else:
        stub = _build_stub_card(
            hcid=lookup_hcid,
            name=name,
            image=image,
            creators=creators,
            set_id=set_id,
        )

    try:
        if existing and existing.exists:
            previous = existing.to_dict() or {}
            doc_id = existing.id
            update = {
                "name": name,
                "image": image,
                "image_status": "highres",
                "creators": _parse_creators(creators),
                "set": set_id if kind == "card" else "HCT",
            }
            if hcid:
                update["hcid"] = hcid
            existing.reference.update(update)
            return FirestoreWrite(doc_id=doc_id, was_create=False, previous=previous)

        doc_id = stub["id"]
        _cards_col().document(doc_id).set(stub)
        return FirestoreWrite(doc_id=doc_id, was_create=True, previous=None)
    except FirestoreSyncError:
        raise
    except Exception as exc:
        raise FirestoreSyncError(str(exc)) from exc


def rollback_firestore_write(write: FirestoreWrite) -> None:
    """Undo a Firestore write when a later accept step (e.g. sheet) fails."""
    doc_ref = _cards_col().document(write.doc_id)
    if write.was_create:
        doc_ref.delete()
        return
    if write.previous is not None:
        doc_ref.set(write.previous)


def firestore_sync_enabled() -> bool:
    """Allow disabling sync in dev via env without code changes."""
    import os

    return os.environ.get("MORK_FIRESTORE_SYNC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
