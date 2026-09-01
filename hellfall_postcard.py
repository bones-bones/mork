"""Post accepted cards to hellfall via POST /api/cards/postcard."""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from hellfall_shared import (
    get_api_key,
    get_api_url,
    get_auth_headers,
    get_request_timeout,
    read_response_json,
)
from image_response_filename import mime_type_from_image_bytes


class PostcardSyncError(Exception):
    """Raised when hellfall postcard sync fails."""


@dataclass
class PostcardWrite:
    doc_id: str
    was_create: bool
    previous: dict[str, Any] | None
    image_url: str | None = None
    # Hellfall card UUID from response ``id`` (sheet BB / token L). Not always
    # equal to ``doc_id`` on updates — use this for sheet UUID columns.
    hellfall_id: str | None = None
    # Oracle card UUID from response ``oracle_id`` (sheet BC / token M).
    oracle_id: str | None = None


def postcard_sync_enabled() -> bool:
    return os.environ.get("MORK_POSTCARD_SYNC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _postcard_debug(msg: str) -> None:
    print(f"[postcard-debug] {msg}", flush=True)


def _postcard_request_context(
    *,
    kind: str,
    name: str,
    set_id: str,
    hcid: str | None,
    image: str | None,
    image_base64: str | None,
    image_mime_type: str | None,
) -> str:
    return (
        f"kind={kind} name={name!r} set={set_id!r} hcid={hcid!r} "
        f"has_image_url={bool(image)} has_image_base64={bool(image_base64)} "
        f"image_mime_type={image_mime_type!r}"
    )


def _sniff_mime_from_base64(image_base64: str) -> str | None:
    try:
        prefix = image_base64[:32]
        pad = "=" * ((4 - len(prefix) % 4) % 4)
        raw = base64.b64decode(prefix + pad, validate=False)
    except (binascii.Error, TypeError, AttributeError):
        return None
    return mime_type_from_image_bytes(raw)


def build_postcard_payload(
    *,
    name: str,
    creators: str,
    set_id: str,
    kind: str,
    image: str | None = None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
    hcid: str | None = None,
) -> dict[str, str]:
    """JSON body for POST /api/cards/postcard."""
    payload: dict[str, str] = {
        "name": name,
        "creators": creators,
        "set": set_id,
        "kind": kind,
    }
    if image_base64:
        payload["imageBase64"] = image_base64
        mime = (image_mime_type or "").strip() or _sniff_mime_from_base64(image_base64)
        if mime:
            payload["imageMimeType"] = mime
    elif image:
        payload["image"] = image
    if hcid:
        payload["hcid"] = hcid
    return payload


def _payload_summary(payload: dict[str, str]) -> str:
    summary = {key: value for key, value in payload.items() if key != "imageBase64"}
    if "imageBase64" in payload:
        summary["imageBase64"] = f"<{len(payload['imageBase64'])} chars>"
    return repr(summary)


async def sync_accepted_card(
    *,
    name: str,
    creators: str,
    set_id: str,
    image: str | None = None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
    hcid: str | None = None,
    kind: Literal["card", "token"] = "card",
    require_sync: bool = False,
) -> PostcardWrite | None:
    if not require_sync and not postcard_sync_enabled():
        return None

    api_url = get_api_url()
    api_key = get_api_key()
    if not api_url or not api_key:
        raise PostcardSyncError("HELLFALL_API_URL and HELLFALL_POSTCARD_API_KEY are required")

    if not image and not image_base64:
        raise PostcardSyncError("image or image_base64 is required")

    payload = build_postcard_payload(
        name=name,
        creators=creators,
        set_id=set_id,
        kind=kind,
        image=image,
        image_base64=image_base64,
        image_mime_type=image_mime_type,
        hcid=hcid,
    )

    request_context = _postcard_request_context(
        kind=kind,
        name=name,
        set_id=set_id,
        hcid=hcid,
        image=image,
        image_base64=image_base64,
        image_mime_type=payload.get("imageMimeType"),
    )
    _postcard_debug(
        f"POST /api/cards/postcard payload={_payload_summary(payload)} {request_context}"
    )

    timeout = get_request_timeout(image_base64=image_base64)
    async with (
        aiohttp.ClientSession().post(
            f"{api_url}/api/cards/postcard",
            json=payload,
            headers=get_auth_headers(api_key),
            timeout=timeout,
        ) as resp,
    ):
        data = await read_response_json(resp)
        if resp.status != 200:
            reason = data.get("reason") if isinstance(data, dict) else None
            _postcard_debug(
                "postcard HTTP error "
                f"status={resp.status} reason={reason!r} response={data!r} "
                f"{request_context} payload={_payload_summary(payload)}"
            )
            raise PostcardSyncError(reason or f"HTTP {resp.status}")
        if not isinstance(data, dict) or not data.get("ok"):
            _postcard_debug(f"postcard_failed response={data!r} {request_context}")
            raise PostcardSyncError("postcard_failed")

        previous = data.get("previous")
        image_url = data.get("imageUrl")
        # postcard.ts returns ``id`` (Hellfall UUID). Fall back to docId for
        # older responses where create used the same value for both.
        raw_id = data.get("id") or data.get("cardId") or data.get("docId")
        hellfall_id = str(raw_id) if raw_id else None
        oracle_id_raw = data.get("oracle_id")
        if oracle_id_raw is None:
            oracle_id_raw = data.get("oracleId")
        oracle_id = str(oracle_id_raw).strip() if oracle_id_raw is not None else ""
        if not oracle_id:
            _postcard_debug(
                "missing or empty oracle_id in postcard response "
                f"oracle_id_raw={oracle_id_raw!r} docId={data.get('docId')!r} "
                f"wasCreate={data.get('wasCreate')!r} id={data.get('id')!r} "
                f"hellfall_id={hellfall_id!r} response={data!r} {request_context}"
            )
            if oracle_id_raw is None:
                raise PostcardSyncError("postcard_missing_oracle_id")
            raise PostcardSyncError("postcard_empty_oracle_id")
        return PostcardWrite(
            doc_id=str(data["docId"]),
            was_create=bool(data["wasCreate"]),
            previous=previous if isinstance(previous, dict) else None,
            image_url=str(image_url) if image_url else None,
            hellfall_id=hellfall_id,
            oracle_id=oracle_id,
        )


async def rollback_postcard_write(write: PostcardWrite) -> None:
    api_url = get_api_url()
    api_key = get_api_key()
    if not api_url or not api_key:
        return

    payload: dict[str, Any] = {
        "docId": write.doc_id,
        "wasCreate": write.was_create,
    }
    if write.previous is not None:
        payload["previous"] = write.previous

    async with (
        aiohttp.ClientSession().post(
            f"{api_url}/api/cards/postcard/rollback",
            json=payload,
            headers=get_auth_headers(api_key),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp,
    ):
        if resp.status != 200:
            data = await read_response_json(resp)
            reason = data.get("reason") if isinstance(data, dict) else None
            raise PostcardSyncError(reason or f"rollback HTTP {resp.status}")
