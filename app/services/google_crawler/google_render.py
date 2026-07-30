from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.services.google_crawler.common import (
    inspect_html,
    issue,
    request_http_metadata,
    status_from_issues,
)
from app.services.google_crawler.googlebot import GOOGLEBOT_SMARTPHONE_UA
from app.utils.public_url import normalize_public_url


class GoogleRenderService:
    """Approximate Google's Web Rendering Service with headless Chromium."""

    @staticmethod
    async def _navigation_details(response: Any) -> tuple[dict[str, str], list[dict[str, Any]]]:
        if response is None:
            return {}, []
        try:
            headers = {
                str(key).lower(): str(value)
                for key, value in (await response.all_headers()).items()
            }
        except Exception:
            headers = {
                str(key).lower(): str(value)
                for key, value in getattr(response, "headers", {}).items()
            }

        requests: list[Any] = []
        current = response.request
        while current is not None and len(requests) < 7:
            requests.append(current)
            current = current.redirected_from
        requests.reverse()

        redirects: list[dict[str, Any]] = []
        for index, request in enumerate(requests[:-1]):
            try:
                redirect_response = await request.response()
            except Exception:
                redirect_response = None
            if redirect_response is None:
                continue
            redirects.append(
                {
                    "status_code": redirect_response.status,
                    "from": request.url,
                    "to": requests[index + 1].url,
                }
            )
        return headers, redirects

    async def test(
        self,
        url: str,
        *,
        initial_html: str = "",
        crawl_allowed: bool | None = True,
        user_agent: str | None = None,
        mode: str = "googlebot",
    ) -> dict[str, Any]:
        normalized = await normalize_public_url(url)
        if crawl_allowed is False:
            return self._skipped(
                "robots_blocked",
                "robots.txt 阻止了 Googlebot；Google Search 不会继续渲染这个页面。",
            )
        if not settings.allow_playwright:
            return self._skipped(
                "renderer_disabled",
                "服务器未启用 Playwright 渲染。请设置 ALLOW_PLAYWRIGHT=true 并安装 Chromium。",
            )
        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            return self._skipped(
                "renderer_unavailable",
                "Playwright 未安装。请安装项目渲染依赖和 Chromium。",
            )

        console_errors: list[str] = []
        page_errors: list[str] = []
        failed_resources: list[dict[str, str]] = []
        http_errors: list[dict[str, Any]] = []
        blocked_private_resources: list[str] = []
        started_at = time.perf_counter()
        final_url = normalized
        status_code: int | None = None
        response_headers: dict[str, str] = {}
        redirect_chain: list[dict[str, Any]] = []
        timed_out = False

        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox"],
                )
            except PlaywrightError:
                return self._skipped(
                    "renderer_launch_failed",
                    "Chromium 无法启动。请安装与 Playwright 版本匹配的浏览器运行时。",
                )
            effective_user_agent = user_agent or GOOGLEBOT_SMARTPHONE_UA
            context = await browser.new_context(
                user_agent=effective_user_agent,
                viewport={"width": 412, "height": 915},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                locale="en-US",
                timezone_id="America/Los_Angeles",
            )
            page = await context.new_page()
            validated_origins = {
                f"{urlparse(normalized).scheme}://{urlparse(normalized).netloc}"
            }

            async def guard_route(route: Any) -> None:
                request_url = route.request.url
                if not request_url.startswith(("http://", "https://")):
                    await route.continue_()
                    return
                parsed_request = urlparse(request_url)
                origin = f"{parsed_request.scheme}://{parsed_request.netloc}"
                if origin in validated_origins:
                    await route.continue_()
                    return
                try:
                    await normalize_public_url(request_url)
                except Exception:
                    if len(blocked_private_resources) < 20:
                        blocked_private_resources.append(request_url)
                    await route.abort("blockedbyclient")
                    return
                validated_origins.add(origin)
                await route.continue_()

            await page.route("**/*", guard_route)
            page.on(
                "console",
                lambda message: console_errors.append(message.text[:500])
                if message.type == "error" and len(console_errors) < 20
                else None,
            )
            page.on(
                "pageerror",
                lambda error: page_errors.append(str(error)[:500])
                if len(page_errors) < 20
                else None,
            )
            page.on(
                "requestfailed",
                lambda request: failed_resources.append(
                    {
                        "url": request.url,
                        "reason": (request.failure or "request failed")[:300],
                    }
                )
                if len(failed_resources) < 30
                else None,
            )
            page.on(
                "response",
                lambda response: http_errors.append(
                    {"url": response.url, "status_code": response.status}
                )
                if response.status >= 400 and len(http_errors) < 30
                else None,
            )

            try:
                response = await page.goto(
                    normalized,
                    wait_until="domcontentloaded",
                    timeout=int(settings.google_render_timeout_seconds * 1000),
                )
                status_code = response.status if response else None
                response_headers, redirect_chain = await self._navigation_details(response)
                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=int(settings.google_render_network_idle_seconds * 1000),
                    )
                except PlaywrightTimeoutError:
                    timed_out = True
                final_url = page.url
                rendered_html = await page.content()
            except PlaywrightTimeoutError:
                timed_out = True
                final_url = page.url
                rendered_html = await page.content()
            except PlaywrightError as exc:
                page_errors.append(str(exc)[:500])
                final_url = page.url
                rendered_html = await page.content()
            finally:
                await context.close()
                await browser.close()

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        initial = inspect_html(initial_html, normalized)
        rendered = inspect_html(rendered_html, final_url)
        word_delta = rendered["word_count"] - initial["word_count"]
        link_delta = rendered["internal_link_count"] - initial["internal_link_count"]
        content_retention = (
            round(rendered["word_count"] / initial["word_count"] * 100)
            if initial["word_count"]
            else None
        )
        http_metadata = request_http_metadata(
            status_code=status_code,
            headers=response_headers,
            redirect_chain=redirect_chain,
        )
        rate_limited = http_metadata["outcome"] == "rate_limited"
        navigation_succeeded = status_code == 200

        issues: list[dict[str, str]] = []
        score = 100
        if mode == "browser_fallback":
            issues.append(
                issue(
                    "browser_fallback_mode",
                    "medium",
                    "渲染模式使用普通浏览器 UA 对照",
                    "模拟 Googlebot 请求被 WAF 拦截，本次渲染用于判断 CSR/SSR，不代表真实 Googlebot 渲染结果。",
                    "通过 Search Console URL Inspection 查看真实 Googlebot 的抓取响应与渲染 DOM。",
                )
            )
        if rate_limited:
            retry_after_seconds = http_metadata["retry_after_seconds"]
            retry_detail = (
                f"响应要求等待约 {retry_after_seconds} 秒后再试。"
                if retry_after_seconds is not None
                else "响应未提供可解析的 Retry-After。"
            )
            score -= 30
            issues.append(
                issue(
                    "render_rate_limited",
                    "high",
                    "模拟渲染请求被限流，无法判断页面状态",
                    (
                        f"无头 Chromium 主文档返回 HTTP 429；{retry_detail}"
                        "该响应来自当前测试服务器 IP，发生在页面路由判断之前，"
                        "不能据此认定目标页面本身返回 429。"
                    ),
                    (
                        "按 Retry-After 间隔后重新检测，并降低同一域名的测试频率；"
                        "真实 Googlebot 状态请使用 Search Console URL Inspection 确认。"
                    ),
                )
            )
        elif not navigation_succeeded:
            score -= 45
            issues.append(
                issue(
                    "render_http_status",
                    "critical",
                    "渲染导航未返回 HTTP 200",
                    f"主文档最终状态为 {status_code or 'unknown'}。",
                    "检查初始状态、重定向链和最终响应，修复 4xx、5xx 或网络错误。",
                )
            )
        if navigation_succeeded and not rendered["title"]:
            score -= 10
            issues.append(issue("rendered_title_missing", "high", "渲染后仍缺少标题", "渲染 DOM 中没有 title。", "确保渲染完成后 DOM 中存在稳定的 title。"))
        if navigation_succeeded and rendered["word_count"] < 50:
            score -= 25
            issues.append(issue("rendered_content_thin", "high", "渲染后核心内容仍过少", f"渲染后约 {rendered['word_count']} 个词/字符单元。", "检查 API 请求、客户端路由、鉴权、懒加载与 JS 异常。"))
        if (
            navigation_succeeded
            and initial["word_count"] >= 50
            and rendered["word_count"] < initial["word_count"] * 0.6
        ):
            score -= 20
            issues.append(issue("content_lost_after_render", "high", "渲染后丢失大量正文", f"渲染后只保留初始内容的约 {content_retention}%。", "检查 hydration 是否覆盖或移除了服务端输出内容。"))
        if navigation_succeeded and (page_errors or console_errors):
            score -= min(20, 5 + len(page_errors) * 5)
            issues.append(issue("javascript_errors", "high" if page_errors else "medium", "渲染期间出现 JavaScript 错误", f"捕获 {len(page_errors)} 个页面异常和 {len(console_errors)} 个 console error。", "修复首屏执行错误，并在接近 Googlebot 的无头浏览器环境中回归测试。"))
        if navigation_succeeded and (failed_resources or http_errors):
            score -= min(15, max(5, (len(failed_resources) + len(http_errors)) // 2))
            issues.append(issue("resource_failures", "medium", "部分渲染资源加载失败", f"{len(failed_resources)} 个网络失败，{len(http_errors)} 个 HTTP 4xx/5xx。", "确保核心 JS、CSS、API 和字体资源允许 Googlebot 访问并稳定返回。"))
        if navigation_succeeded and timed_out:
            score -= 10
            issues.append(issue("network_idle_timeout", "medium", "页面未及时进入网络空闲", "页面持续发起请求或渲染耗时过长。", "减少首屏长连接、重复请求与阻塞脚本，让核心内容更早稳定。"))
        if navigation_succeeded and blocked_private_resources:
            score -= 5
            issues.append(issue("private_resources", "medium", "页面引用了不可公开访问的资源", f"安全策略阻止了 {len(blocked_private_resources)} 个私有/本地网络资源。", "让渲染所需资源通过公开 HTTPS URL 提供。"))

        score = max(0, min(100, score))
        navigation_check_status = (
            "pass"
            if navigation_succeeded
            else "warning"
            if rate_limited
            else "fail"
        )
        unavailable_detail = (
            (
                f"HTTP 429，建议等待 {http_metadata['retry_after_seconds']} 秒后重试；"
                "本次不评估渲染后内容"
            )
            if rate_limited and http_metadata["retry_after_seconds"] is not None
            else "HTTP 429；本次不评估渲染后内容"
            if rate_limited
            else f"HTTP {status_code or 'unknown'}；本次不评估渲染后内容"
        )
        checks = [
            {
                "key": "render_mode",
                "label": "渲染身份",
                "status": "warning" if mode == "browser_fallback" else "pass",
                "detail": (
                    "普通浏览器 UA 对照模式；用于渲染方式诊断"
                    if mode == "browser_fallback"
                    else "Googlebot Smartphone UA 模拟模式"
                ),
            },
            {
                "key": "render_status",
                "label": "主文档成功渲染",
                "status": navigation_check_status,
                "detail": (
                    f"HTTP {status_code or 'unknown'}，总耗时 {elapsed_ms} ms"
                    if navigation_succeeded
                    else unavailable_detail
                ),
            },
            {
                "key": "rendered_content",
                "label": "渲染后有核心内容",
                "status": (
                    "pass"
                    if navigation_succeeded and rendered["word_count"] >= 50
                    else "fail"
                    if navigation_succeeded
                    else "warning"
                ),
                "detail": (
                    f"约 {rendered['word_count']} 个词/字符单元，变化 {word_delta:+d}"
                    if navigation_succeeded
                    else unavailable_detail
                ),
            },
            {
                "key": "javascript",
                "label": "JavaScript 无致命异常",
                "status": (
                    "pass"
                    if navigation_succeeded and not page_errors
                    else "fail"
                    if navigation_succeeded
                    else "warning"
                ),
                "detail": (
                    f"{len(page_errors)} 个页面异常，{len(console_errors)} 个 console error"
                    if navigation_succeeded
                    else unavailable_detail
                ),
            },
            {
                "key": "resources",
                "label": "核心资源可加载",
                "status": (
                    "pass"
                    if navigation_succeeded and not failed_resources and not http_errors
                    else "warning"
                ),
                "detail": (
                    f"{len(failed_resources) + len(http_errors)} 个异常资源"
                    if navigation_succeeded
                    else unavailable_detail
                ),
            },
        ]
        return {
            "service": "google_render",
            "status": status_from_issues(issues, score=score),
            "score": score,
            "simulated": True,
            "available": True,
            "engine": "Playwright Chromium",
            "mode": mode,
            "user_agent": effective_user_agent,
            "googlebot_equivalent": mode == "googlebot",
            "request": {
                "requested_url": normalized,
                "final_url": final_url,
                "status_code": status_code,
                **http_metadata,
                "redirect_count": len(redirect_chain),
                "redirect_chain": redirect_chain,
                "render_time_ms": elapsed_ms,
                "network_idle_timed_out": timed_out,
            },
            "comparison": {
                "initial_word_count": initial["word_count"],
                "rendered_word_count": rendered["word_count"],
                "word_delta": word_delta,
                "initial_internal_links": initial["internal_link_count"],
                "rendered_internal_links": rendered["internal_link_count"],
                "link_delta": link_delta,
                "content_retention_percent": content_retention,
                "title_before": initial["title"],
                "title_after": rendered["title"],
                "h1_before": initial["h1"],
                "h1_after": rendered["h1"],
            },
            "rendered_content": {
                key: value for key, value in rendered.items() if key != "visible_text"
            },
            "diagnostics": {
                "page_errors": page_errors,
                "console_errors": console_errors,
                "failed_resources": failed_resources,
                "http_errors": http_errors,
                "blocked_private_resources": blocked_private_resources,
            },
            "checks": checks,
            "issues": issues,
        }

    @staticmethod
    def _skipped(code: str, detail: str) -> dict[str, Any]:
        return {
            "service": "google_render",
            "status": "skipped",
            "score": None,
            "simulated": True,
            "available": code not in {
                "renderer_unavailable",
                "renderer_disabled",
                "renderer_launch_failed",
            },
            "engine": "Playwright Chromium",
            "checks": [],
            "issues": [
                issue(
                    code,
                    "high" if code == "robots_blocked" else "medium",
                    "Google Render 未执行",
                    detail,
                    "先解决抓取限制或启用服务器渲染能力后重新测试。",
                )
            ],
        }
