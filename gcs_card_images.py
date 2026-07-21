"""Upload accepted card/token images to Google Cloud Storage (hellscube-images).

Matches Hellfall postcard object naming so Database column C URLs stay compatible
with ``IMAGE_GCS_CARD_IMAGE_BUCKET``.
"""

from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import quote, unquote, urlparse

from google.cloud import storage

DEFAULT_BUCKET = os.environ.get("GCS_CARD_IMAGE_BUCKET", "hellscube-images")
DEFAULT_CREDENTIALS = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS", "./bot_secrets/client_secrets.json"
)
_GCS_HOSTS = frozenset({"storage.googleapis.com", "storage.cloud.google.com"})


def slug_object_name(name: str) -> str:
    base = name.strip() or "image"
    return re.sub(r"[^\w\-.]+", "_", base.replace("/", "|"), flags=re.UNICODE)[:180]


def public_gcs_url(bucket_name: str, object_key: str) -> str:
    encoded = "/".join(quote(segment, safe="") for segment in object_key.split("/"))
    return f"https://storage.googleapis.com/{bucket_name}/{encoded}"


def parse_gcs_public_url(
    url: str, expected_bucket: Optional[str] = None
) -> Optional[tuple[str, str]]:
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    if parsed.hostname not in _GCS_HOSTS:
        return None
    path_parts = [p for p in parsed.path.lstrip("/").split("/") if p]
    if len(path_parts) < 2:
        return None
    bucket = path_parts[0]
    object_key = unquote("/".join(path_parts[1:]))
    if not object_key:
        return None
    if expected_bucket and bucket != expected_bucket:
        return None
    return bucket, object_key


def _content_type_for_ext(ext: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext.lower(), "application/octet-stream")


def upload_card_image(
    path: str,
    *,
    object_name: str,
    existing_url: Optional[str] = None,
    bucket_name: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> str:
    """Upload a local image to the card-image bucket; return its public HTTPS URL.

    If ``existing_url`` points at the same bucket, overwrite that object (errata).
    Otherwise create ``{slug(object_name)}{ext}``.
    """
    bucket_name = bucket_name or DEFAULT_BUCKET
    credentials_path = credentials_path or DEFAULT_CREDENTIALS
    ext = os.path.splitext(path)[1].lower() or ".png"
    if ext == ".jpeg":
        ext = ".jpg"

    parsed = (
        parse_gcs_public_url(existing_url, expected_bucket=bucket_name)
        if existing_url
        else None
    )
    if parsed:
        object_key = parsed[1]
    else:
        object_key = f"{slug_object_name(object_name)}{ext}"

    client = storage.Client.from_service_account_json(credentials_path)
    blob = client.bucket(bucket_name).blob(object_key)
    blob.upload_from_filename(path, content_type=_content_type_for_ext(ext))
    blob.cache_control = "public, max-age=31536000"
    blob.patch()
    return public_gcs_url(bucket_name, object_key)
