from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4.dammit import EncodingDetector

from app.core.exceptions import AppError
from app.utils.public_url import normalize_public_url


MAX_HTML_BYTES = 2_000_000
REDIRECT_CODES = {301, 302, 303, 307, 308}
REQUEST_HEADER_NAMES = (
    "User-Agent",
    "Accept",
    "Accept-Encoding",
    "Accept-Language",
    "Range",
    "Host",
    "Connection",
    "Cache-Control",
    "Upgrade-Insecure-Requests",
    "Sec-Fetch-Dest",
    "Sec-Fetch-Mode",
    "Sec-Fetch-Site",
)
RESPONSE_HEADER_NAMES = (
    "content-type",
    "content-length",
    "content-encoding",
    "content-range",
    "x-robots-tag",
    "retry-after",
)


def visible_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    lookup = {key.lower(): value for key, value in headers.items()}
    return {key: lookup[key.lower()] for key in REQUEST_HEADER_NAMES if key.lower() in lookup}


def visible_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {key: headers[key] for key in RESPONSE_HEADER_NAMES if key in headers}


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str
    response_time_ms: int
    redirect_chain: list[dict[str, Any]]
    truncated: bool
    size_bytes: int = 0
    request_headers: dict[str, str] = field(default_factory=dict)


async def fetch_public(
    url: str,
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str] | None = None,
    validate_url: bool = True,
    before_request: Callable[[str], Awaitable[None]] | None = None,
    on_response: Callable[[httpx.Response], None] | None = None,
) -> FetchResult:
    current = await normalize_public_url(url) if validate_url else url
    requested = current
    redirects = []
    started = time.perf_counter()
    for _ in range(6):
        if before_request:
            await before_request(current)
        async with client.stream("GET", current, headers=headers, follow_redirects=False) as response:
            if on_response is not None:
                on_response(response)
            if response.status_code in REDIRECT_CODES and response.headers.get("location"):
                target = await normalize_public_url(urljoin(current, response.headers["location"]))
                redirects.append({"status_code": response.status_code, "from": current, "to": target})
                current = target
                continue

            body = bytearray()
            truncated = False
            async for chunk in response.aiter_bytes(chunk_size=65536):
                remaining = MAX_HTML_BYTES - len(body)
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
            encoding = response.charset_encoding
            if not encoding and "html" in response.headers.get("content-type", "").lower():
                encoding = EncodingDetector.find_declared_encoding(bytes(body[:4096]), is_html=True)
            try:
                text = body.decode(encoding or "utf-8", errors="replace")
            except LookupError:
                text = body.decode("utf-8", errors="replace")
            return FetchResult(
                requested,
                str(response.url),
                response.status_code,
                dict(response.headers),
                text,
                round((time.perf_counter() - started) * 1000),
                redirects,
                truncated,
                len(body),
                visible_request_headers(response.request.headers),
            )
    raise AppError(502, "Too many redirects while testing URL")
