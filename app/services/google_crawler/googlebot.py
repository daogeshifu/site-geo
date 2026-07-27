from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.services.google_crawler.browser_raw import (
    BrowserRawHtmlService,
    BrowserRawResponse,
)
from app.services.google_crawler.common import inspect_html, issue, status_from_issues
from app.utils.public_url import normalize_public_url


GOOGLEBOT_SMARTPHONE_UA = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile "
    "Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
ACCESS_CHALLENGE_STATUS_CODES = {401, 403, 406, 418, 429, 446, 451}
ACCESS_CHALLENGE_MARKERS = (
    "access denied",
    "request blocked",
    "captcha",
    "cf-chl-",
    "cloudflare ray id",
    "akamai",
)
MAX_HTML_BYTES = 2_000_000
REDIRECT_CODES = {301, 302, 303, 307, 308}


@dataclass
class GooglebotRun:
    result: dict[str, Any]
    html: str


@dataclass
class _HttpResult:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str
    response_time_ms: int
    redirect_chain: list[dict[str, Any]]
    truncated: bool


class GooglebotService:
    """Fetch and diagnose a URL with a Googlebot Smartphone-like request."""

    def __init__(self, *, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = timeout_seconds or settings.request_timeout_seconds
        self.browser_raw_service = BrowserRawHtmlService(
            timeout_seconds=self.timeout_seconds
        )

    @staticmethod
    def _is_access_challenge(
        response: _HttpResult | BrowserRawResponse,
    ) -> bool:
        if response.status_code in ACCESS_CHALLENGE_STATUS_CODES:
            return True
        if response.status_code not in {400, 503}:
            return False
        evidence = " ".join(
            (
                response.headers.get("server", ""),
                response.headers.get("cf-ray", ""),
                response.headers.get("x-sucuri-id", ""),
                response.text[:2000],
            )
        ).lower()
        return any(marker in evidence for marker in ACCESS_CHALLENGE_MARKERS)

    async def _fetch(
        self,
        url: str,
        *,
        client: httpx.AsyncClient,
        validate_url: bool = True,
    ) -> _HttpResult:
        current = await normalize_public_url(url) if validate_url else url
        requested = current
        redirects: list[dict[str, Any]] = []
        started_at = time.perf_counter()

        for _ in range(6):
            response = await client.get(current, follow_redirects=False)
            if response.status_code in REDIRECT_CODES and response.headers.get("location"):
                next_url = urljoin(current, response.headers["location"])
                next_url = await normalize_public_url(next_url)
                redirects.append(
                    {
                        "status_code": response.status_code,
                        "from": current,
                        "to": next_url,
                    }
                )
                current = next_url
                continue

            raw = response.content
            truncated = len(raw) > MAX_HTML_BYTES
            raw = raw[:MAX_HTML_BYTES]
            encoding = response.encoding or "utf-8"
            try:
                text = raw.decode(encoding, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return _HttpResult(
                requested_url=requested,
                final_url=str(response.url),
                status_code=response.status_code,
                headers={key.lower(): value for key, value in response.headers.items()},
                text=text,
                response_time_ms=int((time.perf_counter() - started_at) * 1000),
                redirect_chain=redirects,
                truncated=truncated,
            )
        raise AppError(502, "Too many redirects while testing URL")

    async def _inspect_robots(
        self,
        url: str,
        *,
        client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = await self._fetch(robots_url, client=client)
        except (AppError, httpx.RequestError, httpx.TimeoutException):
            return {
                "url": robots_url,
                "status_code": None,
                "allowed": None,
                "state": "unavailable",
                "detail": "robots.txt could not be fetched; Google may use a cached copy or temporarily pause crawling.",
            }

        return self._robots_result(response, url=url, robots_url=robots_url)

    def _robots_result(
        self,
        response: _HttpResult | BrowserRawResponse,
        *,
        url: str,
        robots_url: str,
    ) -> dict[str, Any]:
        if self._is_access_challenge(response):
            return {
                "url": robots_url,
                "status_code": response.status_code,
                "allowed": None,
                "state": "access_challenge",
                "detail": (
                    f"robots.txt returned HTTP {response.status_code}; the simulated "
                    "Googlebot request appears to be blocked by a WAF or bot-verification policy."
                ),
            }
        if 400 <= response.status_code < 500:
            return {
                "url": robots_url,
                "status_code": response.status_code,
                "allowed": True,
                "state": "not_found",
                "detail": "No usable robots.txt was found; crawling is treated as allowed.",
            }
        if response.status_code >= 500:
            return {
                "url": robots_url,
                "status_code": response.status_code,
                "allowed": None,
                "state": "server_error",
                "detail": "robots.txt returned a server error; Google can temporarily pause crawling.",
            }

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        allowed = parser.can_fetch("Googlebot", url)
        return {
            "url": robots_url,
            "status_code": response.status_code,
            "allowed": allowed,
            "state": "allowed" if allowed else "blocked",
            "detail": "The Googlebot product token is allowed for this URL." if allowed else "robots.txt disallows Googlebot for this URL.",
        }

    async def run(self, url: str) -> GooglebotRun:
        normalized = await normalize_public_url(url)
        headers = {
            "User-Agent": GOOGLEBOT_SMARTPHONE_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }
        timeout = httpx.Timeout(self.timeout_seconds, connect=min(10.0, self.timeout_seconds))
        async with httpx.AsyncClient(headers=headers, timeout=timeout, http2=True) as client:
            robots = await self._inspect_robots(normalized, client=client)
            try:
                response = await self._fetch(normalized, client=client)
            except httpx.TimeoutException as exc:
                raise AppError(504, "Googlebot simulation timed out") from exc
            except httpx.RequestError as exc:
                raise AppError(502, f"Googlebot simulation failed: {exc}") from exc

        access_challenge = self._is_access_challenge(response)
        fallback_response: BrowserRawResponse | None = None
        fallback_user_agent: str | None = None
        analysis_response = response
        if access_challenge:
            fallback_user_agent = self.browser_raw_service.user_agent
            parsed = urlparse(normalized)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                fallback_response = await self.browser_raw_service.fetch(normalized)
            except AppError:
                fallback_response = None
            else:
                if fallback_response.status_code == 200:
                    analysis_response = fallback_response
                    try:
                        fallback_robots_response = (
                            await self.browser_raw_service.fetch(robots_url)
                        )
                    except AppError:
                        pass
                    else:
                        robots = self._robots_result(
                            fallback_robots_response,
                            url=normalized,
                            robots_url=robots_url,
                        )

        content = inspect_html(analysis_response.text, analysis_response.final_url)
        header_directives = [
            item.strip().lower()
            for item in analysis_response.headers.get("x-robots-tag", "").split(",")
            if item.strip()
        ]
        directives = sorted(set(content["directives"] + header_directives))
        noindex = any(item == "none" or item.startswith("noindex") for item in directives)
        nofollow = any(item == "none" or item.startswith("nofollow") for item in directives)
        content_type = analysis_response.headers.get("content-type", "")

        issues: list[dict[str, str]] = []
        score = 100
        if access_challenge:
            score -= 15
            fallback_status = (
                fallback_response.status_code if fallback_response is not None else None
            )
            issues.append(
                issue(
                    "googlebot_access_challenge",
                    "high",
                    "模拟 Googlebot 请求被 WAF 或反爬策略拦截",
                    (
                        f"Googlebot UA 返回 HTTP {response.status_code}；"
                        f"普通浏览器 UA 对照请求返回 HTTP {fallback_status or 'unknown'}。"
                        "由于请求并非来自 Google 官方 IP，不能据此断言真实 Googlebot 被阻止。"
                    ),
                    "使用 Search Console URL Inspection 确认真实 Googlebot；同时检查 CDN/WAF 是否按 Google 官方 IP 范围验证爬虫。",
                )
            )
        if robots["allowed"] is False:
            score -= 55
            issues.append(issue("robots_blocked", "critical", "Googlebot 被 robots.txt 阻止", robots["detail"], "在 robots.txt 中为 Googlebot 放行目标路径。"))
        elif robots["allowed"] is None:
            score -= 15
            issues.append(issue("robots_unavailable", "medium", "robots.txt 状态不确定", robots["detail"], "确保 /robots.txt 稳定返回 200 或明确的 404。"))
        if response.status_code != 200 and not access_challenge:
            deduction = 45 if response.status_code >= 400 else 20
            score -= deduction
            issues.append(issue("non_200", "critical" if response.status_code >= 400 else "high", f"页面返回 HTTP {response.status_code}", "Google 通常只会把 200 页面送入正常渲染与索引流程。", "让规范 URL 稳定返回 HTTP 200。"))
        if noindex:
            score -= 45
            issues.append(issue("noindex", "critical", "页面包含 noindex", f"检测到索引指令：{', '.join(directives)}", "移除 meta robots 或 X-Robots-Tag 中的 noindex（若希望页面被收录）。"))
        if "text/html" not in content_type.lower():
            score -= 20
            issues.append(issue("content_type", "high", "响应不是 HTML", f"Content-Type: {content_type or 'missing'}", "为网页返回正确的 text/html Content-Type。"))
        if not content["title"]:
            score -= 8
            issues.append(issue("missing_title", "medium", "缺少页面标题", "初始 HTML 中未检测到 title。", "在初始 HTML 的 head 中提供唯一、描述性的 title。"))
        if not content["h1"]:
            score -= 6
            issues.append(issue("missing_h1", "medium", "缺少 H1", "初始 HTML 中未检测到 H1。", "在初始 HTML 中提供清晰的页面主标题。"))
        if content["word_count"] < 50:
            score -= 12
            issues.append(issue("thin_initial_html", "high", "初始 HTML 可见内容过少", f"仅检测到约 {content['word_count']} 个词/字符单元，页面可能依赖 JavaScript。", "使用 SSR、静态生成或预渲染输出核心正文和链接。"))
        if analysis_response.truncated:
            score -= 5
            issues.append(issue("html_truncated", "medium", "HTML 超过模拟抓取上限", "本次分析只读取了前 2MB 解压后内容。", "减少 HTML 体积，把核心内容放在文档前部。"))

        score = max(0, min(100, score))
        indexable: bool | None
        if noindex or robots["allowed"] is False:
            indexable = False
        elif access_challenge:
            indexable = None
        else:
            indexable = response.status_code == 200
        checks = [
            {"key": "robots", "label": "robots.txt 允许抓取", "status": "pass" if robots["allowed"] is True else ("fail" if robots["allowed"] is False else "warning"), "detail": robots["detail"]},
            {
                "key": "http",
                "label": "Googlebot HTTP 响应",
                "status": "warning" if access_challenge else ("pass" if response.status_code == 200 else "fail"),
                "detail": (
                    f"模拟 UA 返回 {response.status_code}，疑似 WAF 校验；不能代表真实 Googlebot"
                    if access_challenge
                    else f"返回 {response.status_code}，耗时 {response.response_time_ms} ms"
                ),
            },
            {
                "key": "indexable",
                "label": "允许索引",
                "status": "warning" if indexable is None else ("pass" if indexable else "fail"),
                "detail": (
                    "模拟 Googlebot 被拦截，真实索引状态待 Search Console 确认"
                    if indexable is None
                    else "未发现 noindex"
                    if indexable
                    else f"发现 {', '.join(directives)}"
                    if noindex
                    else "当前响应不满足索引条件"
                ),
            },
            {"key": "content", "label": "初始 HTML 有核心内容", "status": "pass" if content["word_count"] >= 50 else "warning", "detail": f"约 {content['word_count']} 个词/字符单元"},
        ]
        result = {
            "service": "googlebot",
            "status": status_from_issues(issues, score=score),
            "score": score,
            "simulated": True,
            "user_agent": GOOGLEBOT_SMARTPHONE_UA,
            "access": {
                "state": "waf_challenge" if access_challenge else "ok",
                "suspected_waf": access_challenge,
                "browser_fallback_used": (
                    access_challenge
                    and fallback_response is not None
                    and fallback_response.status_code == 200
                ),
                "fallback_user_agent": fallback_user_agent,
                "control_transport": (
                    "curl_cffi_chrome"
                    if fallback_response is not None
                    else None
                ),
                "raw_html_source": (
                    "browser_control"
                    if fallback_response is not None
                    and fallback_response.status_code == 200
                    else "googlebot"
                ),
                "detail": (
                    "模拟 Googlebot UA 来自非 Google IP，被目标站点的 WAF/反爬策略拦截。"
                    if access_challenge
                    else "模拟请求未发现 WAF/反爬拦截。"
                ),
            },
            "request": {
                "requested_url": response.requested_url,
                "final_url": response.final_url,
                "status_code": response.status_code,
                "response_time_ms": response.response_time_ms,
                "redirect_count": len(response.redirect_chain),
                "redirect_chain": response.redirect_chain,
                "content_type": response.headers.get("content-type", ""),
                "html_bytes": len(
                    response.text.encode("utf-8", errors="ignore")
                ),
                "truncated": response.truncated,
            },
            "control_request": (
                {
                    "status_code": fallback_response.status_code,
                    "final_url": fallback_response.final_url,
                    "response_time_ms": fallback_response.response_time_ms,
                    "content_type": fallback_response.headers.get("content-type", ""),
                    "html_bytes": len(
                        fallback_response.text.encode("utf-8", errors="ignore")
                    ),
                }
                if fallback_response is not None
                else None
            ),
            "crawlability": robots,
            "indexability": {
                "indexable": indexable,
                "state": (
                    "unknown_googlebot_access"
                    if indexable is None
                    else "indexable"
                    if indexable
                    else "not_indexable"
                ),
                "noindex": noindex,
                "nofollow": nofollow,
                "directives": directives,
                "canonical": content["canonical"],
            },
            "content": {key: value for key, value in content.items() if key != "visible_text"},
            "checks": checks,
            "issues": issues,
        }
        return GooglebotRun(result=result, html=analysis_response.text)

    async def test(self, url: str) -> dict[str, Any]:
        return (await self.run(url)).result
