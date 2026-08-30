"""GCS manifest of #submissions card images for the daily Reddit gallery."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import storage

from gcs_card_images import DEFAULT_BUCKET, DEFAULT_CREDENTIALS, public_gcs_url
from image_response_filename import extension_from_image_bytes, with_image_extension

DEFAULT_MANIFEST_OBJECT = "mork/submissions-gallery-manifest.json"
DEFAULT_MANIFEST_URL = (
    f"https://storage.googleapis.com/{DEFAULT_BUCKET}/{DEFAULT_MANIFEST_OBJECT}"
)
MANIFEST_RETENTION_DAYS = 7


def manifest_url() -> str:
    return os.environ.get("SUBMISSIONS_GALLERY_MANIFEST_URL", DEFAULT_MANIFEST_URL).strip()


def _manifest_object_key() -> str:
    url = manifest_url()
    marker = f"storage.googleapis.com/{DEFAULT_BUCKET}/"
    if marker in url:
        return url.split(marker, 1)[1]
    return DEFAULT_MANIFEST_OBJECT


def _storage_client() -> storage.Client:
    credentials_path = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CREDENTIALS
    )
    return storage.Client.from_service_account_json(credentials_path)


def _empty_manifest() -> dict[str, Any]:
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "entries": [],
    }


def load_manifest() -> dict[str, Any]:
    client = _storage_client()
    blob = client.bucket(DEFAULT_BUCKET).blob(_manifest_object_key())
    if not blob.exists():
        return _empty_manifest()
    raw = blob.download_as_text()
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return _empty_manifest()
    return data


def _prune_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=MANIFEST_RETENTION_DAYS)
    kept: list[dict[str, Any]] = []
    for entry in entries:
        submitted_at = entry.get("submittedAt")
        if not submitted_at:
            continue
        try:
            ts = datetime.fromisoformat(str(submitted_at))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            kept.append(entry)
    return kept


def append_submission(
    *,
    message_id: str,
    image_bytes: bytes,
    filename: str,
    card_name: str = "",
) -> str:
    """Upload submission image to GCS and append to the gallery manifest."""
    ext = os.path.splitext(filename)[1].lower() or ".png"
    sniffed = extension_from_image_bytes(image_bytes[:16])
    if sniffed:
        ext = sniffed
    object_key = with_image_extension(f"submissions-gallery/{message_id}", ext)

    client = _storage_client()
    bucket = client.bucket(DEFAULT_BUCKET)
    blob = bucket.blob(object_key)
    content_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext.lower(), "application/octet-stream")
    blob.upload_from_string(image_bytes, content_type=content_type)
    blob.cache_control = "public, max-age=31536000"
    blob.patch()

    image_url = public_gcs_url(DEFAULT_BUCKET, object_key)
    manifest = load_manifest()
    entries = _prune_entries(list(manifest.get("entries", [])))
    entries = [e for e in entries if e.get("messageId") != str(message_id)]
    entries.append(
        {
            "messageId": str(message_id),
            "imageUrl": image_url,
            "submittedAt": datetime.now(timezone.utc).isoformat(),
            "cardName": card_name.strip(),
        }
    )
    manifest["entries"] = entries
    manifest["updatedAt"] = datetime.now(timezone.utc).isoformat()

    manifest_blob = bucket.blob(_manifest_object_key())
    manifest_blob.upload_from_string(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    manifest_blob.cache_control = "public, max-age=60"
    manifest_blob.patch()
    return image_url


def entries_last_24h(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = manifest if manifest is not None else load_manifest()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent: list[dict[str, Any]] = []
    for entry in data.get("entries", []):
        submitted_at = entry.get("submittedAt")
        image_url = entry.get("imageUrl")
        if not submitted_at or not image_url:
            continue
        try:
            ts = datetime.fromisoformat(str(submitted_at))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            recent.append(entry)
    return recent
