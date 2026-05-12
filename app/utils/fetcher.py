from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import AppError


@dataclass
class FetchedResponse:
    """HTTP 请求响应的标准化数据类"""

    final_url: str         # 跟随重定向后的最终 URL
    status_code: int
    headers: dict[str, str]
    text: str              # 响应正文文本
    response_time_ms: int  # 请求总耗时（毫秒）


@retry(
    # 仅对网络错误和超时进行重试（HTTP 4xx/5xx 不重试）
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    stop=stop_after_attempt(settings.request_retries),
    # 指数退避：初始 0.5s，最大 4s
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
async def _send_request(client: httpx.AsyncClient, method: str, url: str) -> httpx.Response:
    """带重试的底层 HTTP 请求（由 fetch_url 调用）"""
    return await client.request(method, url)


async def fetch_url(
    url: str,
    client: httpx.AsyncClient | None = None,
    method: str = "GET",
) -> FetchedResponse:
    """异步抓取 URL，自动处理重试、超时和响应时间统计

    Args:
        url: 目标 URL
        client: 可选的共享 httpx.AsyncClient（用于连接复用）
        method: HTTP 方法，默认 GET

    Returns:
        FetchedResponse（包含最终 URL、状态码、响应头、正文和耗时）

    Raises:
        AppError(502): 网络错误或超时（重试耗尽后）
    """
    # 若未注入 client，创建临时 client（finally 中关闭）
    owns_client = client is None
    DEFAULT_HEADERS = {
        # 基础浏览器身份
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),

        # 内容协商
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),

        "Accept-Language": "en-US,en;q=0.9",

        # 注意：httpx 会自动处理 gzip/br
        # 不建议手动写
        # "Accept-Encoding": "gzip, deflate, br",

        # Chrome 常见
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",

        # sec-ch-* 非常重要
        "sec-ch-ua": (
            '"Chromium";v="124", '
            '"Google Chrome";v="124", '
            '"Not-A.Brand";v="99"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',

        # fetch metadata
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",

        # keep alive
        "Connection": "keep-alive",
    }

    request_client = httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        http2=True,
        follow_redirects=True,
        timeout=httpx.Timeout(
            connect=10.0,
            read=20.0,
            write=20.0,
            pool=20.0,
        ),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=30,
        ),
        verify=True,
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
