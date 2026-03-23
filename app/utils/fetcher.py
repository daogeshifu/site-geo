from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import AppError


@dataclass
class FetchedResponse:
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str
    response_time_ms: int


@retry(
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    stop=stop_after_attempt(settings.request_retries),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
async def _send_request(client: httpx.AsyncClient, method: str, url: str) -> httpx.Response:
    return await client.request(method, url)


async def fetch_url(
    url: str,
    client: httpx.AsyncClient | None = None,
    method: str = "GET",
) -> FetchedResponse:
    owns_client = client is None
    request_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds),
        follow_redirects=True,
        headers={"User-Agent": settings.default_user_agent},
    )
    started_at = time.perf_counter()
    try:
        response = await _send_request(request_client, method, url)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise AppError(502, f"Failed to fetch URL: {url}", str(exc)) from exc
    finally:
        if owns_client:
            await request_client.aclose()

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return FetchedResponse(
        final_url=str(response.url),
        status_code=response.status_code,
        headers={key: value for key, value in response.headers.items()},
        text=response.text,
        response_time_ms=elapsed_ms,
    )
