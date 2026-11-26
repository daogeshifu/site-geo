"""Keep bounded HTML evidence separate from frequently-polled task JSON."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

MAX_SOURCE_BYTES = 2_000_000
HEADER_NAMES = {
    "content-type", "content-length", "cache-control", "last-modified",
    "etag", "x-robots-tag", "content-language", "server",
    "cf-mitigated", "cf-ray", "retry-after", "content-signal", "link",
    "x-served-by", "x-cdn", "x-waf-event-info",
}


def _source_path(key: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{64}", key):
        raise ValueError("Invalid source key")
    return Path(settings.cache_dir) / "page-sources" / f"{key}.html"


def _save_source(url: str, html: str) -> tuple[str | None, bool]:
    raw = html.encode("utf-8")
    truncated = len(raw) > MAX_SOURCE_BYTES
    raw = raw[:MAX_SOURCE_BYTES].decode("utf-8", errors="ignore").encode("utf-8")
    key = hashlib.sha256(url.encode("utf-8") + b"\0" + raw).hexdigest()
    try:
        path = _source_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(raw)
    except OSError:
        logging.getLogger(__name__).warning("Could not save page HTML evidence")
        return None, truncated
    return key, truncated


async def capture_page_metadata(response) -> dict:
    captured_at = datetime.now(timezone.utc).isoformat()
    source_key, truncated = await asyncio.to_thread(_save_source, response.final_url, response.text)
    redirect_chain = list(getattr(response, "redirect_chain", None) or [])
    redirect_count = getattr(response, "redirect_count", None)
    if redirect_count is None and hasattr(response, "redirect_chain"):
        redirect_count = len(redirect_chain)
    return {
        "fetched_at": captured_at,
        "status_code": response.status_code,
        "response_time_ms": response.response_time_ms,
        "ttfb_ms": getattr(response, "ttfb_ms", None),
        "response_headers": {key.lower(): value for key, value in response.headers.items() if key.lower() in HEADER_NAMES},
        "redirect_chain": redirect_chain,
        "redirect_count": redirect_count,
        "source_key": source_key,
        "source_truncated": truncated,
    }


async def read_page_source(key: str) -> str | None:
    try:
        return await asyncio.to_thread(_source_path(key).read_text, encoding="utf-8")
    except (OSError, ValueError):
        return None
