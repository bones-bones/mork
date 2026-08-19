"""Resolve Discord attachment filenames from image HTTP responses."""

from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlparse

_DRIVE_FILENAME_RE = re.compile(r'inline;filename="(.*)"')
_CONTENT_DISPOSITION_FILENAME_RE = re.compile(
    r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', re.I
)
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_CONTENT_TYPE_FOR_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def extension_from_image_bytes(body: bytes | None) -> str | None:
    """Return a lowercase image extension from magic bytes, or None if unknown."""
    if not body:
        return None
    if body.startswith(b"GIF8"):
        return ".gif"
    if body.startswith(_PNG_MAGIC):
        return ".png"
    if body.startswith(_JPEG_MAGIC):
        return ".jpg"
    if len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return ".webp"
    return None


def content_type_for_ext(ext: str | None) -> str | None:
    if not ext:
        return None
    if not ext.startswith("."):
        ext = f".{ext}"
    return _CONTENT_TYPE_FOR_EXT.get(ext.lower())


def mime_type_from_image_bytes(body: bytes | None) -> str | None:
    return content_type_for_ext(extension_from_image_bytes(body))


def extension_from_content_type(content_type: str | None) -> str | None:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if not ctype:
        return None
    if "gif" in ctype:
        return ".gif"
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "webp" in ctype:
        return ".webp"
    if "png" in ctype:
        return ".png"
    return None


def with_image_extension(filename: str, ext: str) -> str:
    """Set ``ext`` on ``filename``, replacing a known image suffix instead of appending."""
    if not ext.startswith("."):
        ext = f".{ext}"
    ext = ".jpg" if ext.lower() == ".jpeg" else ext.lower()
    root, old_ext = os.path.splitext(filename)
    if old_ext.lower() in _IMAGE_EXTENSIONS:
        return f"{root}{ext}"
    return f"{filename}{ext}"


def _candidate_filename(
    *,
    content_disposition: str | None,
    url: str,
    fallback_name: str,
) -> str:
    cd = content_disposition or ""

    drive_match = _DRIVE_FILENAME_RE.findall(cd)
    if drive_match:
        name = drive_match[0].strip()
        if name:
            return name

    cd_match = _CONTENT_DISPOSITION_FILENAME_RE.search(cd)
    if cd_match:
        fname = unquote(cd_match.group(1).strip('"'))
        if fname:
            return fname

    path = urlparse(url).path
    basename = unquote(path.rsplit("/", 1)[-1]) if path else ""
    if basename and "." in basename:
        ext = f".{basename.rsplit('.', 1)[-1].lower()}"
        if ext in _IMAGE_EXTENSIONS:
            return basename

    base = (fallback_name or "image").strip() or "image"
    return base


def filename_from_image_response(
    *,
    content_disposition: str | None,
    url: str,
    content_type: str | None = None,
    fallback_name: str = "image",
    body: bytes | None = None,
) -> str:
    """Drive ``inline;filename=`` first, then other CD forms, URL path, then fallback.

    Magic bytes and ``Content-Type`` win over a URL/Drive ``.png`` name when the
    bytes are actually a GIF (or another format).
    """
    candidate = _candidate_filename(
        content_disposition=content_disposition,
        url=url,
        fallback_name=fallback_name,
    )
    _, candidate_ext = os.path.splitext(candidate)
    candidate_ext = (
        candidate_ext.lower() if candidate_ext.lower() in _IMAGE_EXTENSIONS else ""
    )
    ext = (
        extension_from_image_bytes(body)
        or extension_from_content_type(content_type)
        or candidate_ext
        or ".png"
    )
    return with_image_extension(candidate, ext)
