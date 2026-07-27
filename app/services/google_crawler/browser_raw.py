from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from app.core.config import settings
from app.core.exceptions import AppError
from app.utils.public_url import normalize_public_url


DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
MAX_HTML_BYTES = 2_000_000
REDIRECT_CODES = {301, 302, 303, 307, 308}


@dataclass
class BrowserRawResponse:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str
    response_time_ms: int
    redirect_chain: list[dict[str, Any]]
    truncated: bool


class BrowserRawHtmlService:
    """Fetch the unrendered navigation response with a browser TLS fingerprint."""

    def __init__(self, *, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = timeout_seconds or settings.request_timeout_seconds
        configured = settings.default_user_agent.strip()
        self.user_agent = (
            configured
            if configured.startswith("Mozilla/5.0")
            and "googlebot" not in configured.lower()
            else DEFAULT_BROWSER_USER_AGENT
        )

    def _headers(self, url: str) -> dict[str, str]:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}/"
        return {
            "User-Agent": self.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Referer": origin,
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    def _request_once(self, url: str) -> Any:
        try:
            from curl_cffi import requests as curl_requests
        except ImportError as exc:
            raise AppError(
                500,
                "Browser raw HTML transport is unavailable; install curl-cffi.",
            ) from exc
        return curl_requests.get(
            url,
            headers=self._headers(url),
            impersonate="chrome",
            allow_redirects=False,
            timeout=self.timeout_seconds,
        )

    async def fetch(self, url: str) -> BrowserRawResponse:
        current = await normalize_public_url(url)
        requested = current
        redirects: list[dict[str, Any]] = []
        started_at = time.perf_counter()

        for _ in range(6):
            try:
                response = await asyncio.to_thread(self._request_once, current)
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    502,
                    f"Browser raw HTML request failed: {exc}",
                ) from exc

            status_code = int(response.status_code)
            location = response.headers.get("location")
            if status_code in REDIRECT_CODES and location:
                next_url = await normalize_public_url(urljoin(current, location))
                redirects.append(
                    {
                        "status_code": status_code,
                        "from": current,
                        "to": next_url,
                    }
                )
                current = next_url
                continue

            raw = bytes(response.content)
            truncated = len(raw) > MAX_HTML_BYTES
            raw = raw[:MAX_HTML_BYTES]
            encoding = response.encoding or "utf-8"
            try:
                text = raw.decode(encoding, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return BrowserRawResponse(
                requested_url=requested,
                final_url=str(response.url),
                status_code=status_code,
                headers={
                    str(key).lower(): str(value)
                    for key, value in response.headers.items()
                },
                text=text,
                response_time_ms=int((time.perf_counter() - started_at) * 1000),
                redirect_chain=redirects,
                truncated=truncated,
            )

        raise AppError(502, "Too many redirects while fetching browser raw HTML")
