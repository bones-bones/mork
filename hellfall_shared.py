import json
import os
from typing import Any, Optional

import aiohttp

class ResponseError(Exception):
    """Raised when the response reader fails."""


def get_api_url() -> str:
    return os.environ.get("HELLFALL_API_URL", "").rstrip("/")

def get_api_key() -> str:
    return os.environ.get("HELLFALL_POSTCARD_API_KEY", "")

def get_auth_headers(api_key:str|None=None) -> dict[str, str]:
    headers = {"Content-Type": "application/json",}
    if api_key:
       headers["Authorization"] = f"Bearer {api_key}"
    return headers
    
def get_request_timeout(*, image_base64: Optional[str]=None) -> aiohttp.ClientTimeout:
    if image_base64:
        # Large base64 uploads can exceed the default 30s (e.g. ~2.7MB payloads).
        total = max(120, 60 + len(image_base64) // 50_000)
        return aiohttp.ClientTimeout(total=min(total, 300))
    return aiohttp.ClientTimeout(total=30)
async def read_response_json(resp: aiohttp.ClientResponse) -> Any:
    body = await resp.text()
    if not body.strip():
        raise ResponseError(f"empty_response HTTP {resp.status}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        snippet = body[:200]
        raise ResponseError(
            f"invalid_json HTTP {resp.status}: {snippet!r}"
        ) from exc
