"""Resolve Discord attachment filenames from image HTTP responses."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_DRIVE_FILENAME_RE = re.compile(r'inline;filename="(.*)"')
_CONTENT_DISPOSITION_FILENAME_RE = re.compile(
    r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', re.I
)
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


def _extension_from_content_type(content_type: str | None) -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if "png" in ctype:
        return ".png"
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "webp" in ctype:
        return ".webp"
    if "gif" in ctype:
        return ".gif"
    return ".png"


def filename_from_image_response(
    *,
    content_disposition: str | None,
    url: str,
    content_type: str | None = None,
    fallback_name: str = "image",
) -> str:
    """Drive ``inline;filename=`` first, then other CD forms, URL path, then fallback."""
    cd = content_disposition or ""

    drive_match = _DRIVE_FILENAME_RE.findall(cd)
    if drive_match:
        return drive_match[0].strip()

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

    ext = _extension_from_content_type(content_type)
    base = (fallback_name or "image").strip() or "image"
    if any(base.lower().endswith(image_ext) for image_ext in _IMAGE_EXTENSIONS):
        return base
    return f"{base}{ext}"
