from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import google_crawler as crawler_routes
from app.core.exceptions import AppError
from app.main import app
from app.services.google_crawler import browser_raw as browser_raw_module
from app.services.google_crawler import googlebot as googlebot_module
from app.services.google_crawler.browser_raw import (
    BrowserRawHtmlService,
    BrowserRawResponse,
)
from app.services.google_crawler.common import inspect_html
from app.services.google_crawler.googlebot import (
    GooglebotRun,
    GooglebotService,
    _HttpResult,
)
from app.services.google_crawler.overview import build_crawler_overview
from app.utils.public_url import normalize_public_url


client = TestClient(app)


def test_google_crawler_demo_page_is_available() -> None:
    response = client.get("/google-crawler-test")
    assert response.status_code == 200
    assert "Googlebot" in response.text
    assert "Google Render" in response.text
    assert "Overview" in response.text
    assert "页面渲染与 SEO 结论" in response.text


def test_inspect_html_extracts_indexable_content() -> None:
    result = inspect_html(
        """
        <html><head>
          <title>Example</title>
          <meta name="robots" content="index, follow">
          <link rel="canonical" href="/canonical">
        </head><body>
          <h1>Primary heading</h1>
          <a href="/one">One</a>
          <script>document.body.dataset.ready = "true"</script>
        </body></html>
        """,
        "https://example.com/page",
    )
    assert result["title"] == "Example"
    assert result["h1"] == "Primary heading"
    assert result["canonical"] == "https://example.com/canonical"
    assert result["directives"] == ["follow", "index"]
    assert result["internal_link_count"] == 1
    assert result["script_count"] == 1


@pytest.mark.asyncio
async def test_public_url_guard_rejects_localhost() -> None:
    with pytest.raises(AppError, match="Local network URLs"):
        await normalize_public_url("http://localhost:8023/private")


def test_combined_demo_endpoint_returns_two_tabs(monkeypatch: pytest.MonkeyPatch) -> None:
    googlebot_result = {
        "status": "passed",
        "score": 92,
        "request": {"final_url": "https://example.com/"},
        "crawlability": {"allowed": True},
        "access": {
            "browser_fallback_used": True,
            "fallback_user_agent": "Mozilla/5.0 Test Browser",
        },
    }
    render_options: dict[str, object] = {}

    async def fake_googlebot_run(url: str) -> GooglebotRun:
        return GooglebotRun(result=googlebot_result, html="<html><body>content</body></html>")

    async def fake_render_test(url: str, **options: object) -> dict:
        render_options.update(options)
        return {"status": "warning", "score": 74, "service": "google_render"}

    monkeypatch.setattr(crawler_routes.googlebot_service, "run", fake_googlebot_run)
    monkeypatch.setattr(crawler_routes.google_render_service, "test", fake_render_test)

    response = client.post(
        "/api/v1/demo/google-crawler/test",
        json={"url": "https://example.com/"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "warning"
    assert data["score"] == 83
    assert "overview" in data
    assert data["googlebot"]["score"] == 92
    assert data["google_render"]["score"] == 74
    assert render_options["mode"] == "browser_fallback"
    assert render_options["user_agent"] == "Mozilla/5.0 Test Browser"


def test_crawler_overview_identifies_server_rendered_page() -> None:
    overview = build_crawler_overview(
        {
            "status": "passed",
            "score": 96,
            "request": {"status_code": 200},
            "crawlability": {"allowed": True, "detail": "Googlebot allowed"},
            "indexability": {"indexable": True},
            "content": {"word_count": 240},
            "issues": [],
        },
        {
            "status": "passed",
            "score": 94,
            "request": {"status_code": 200},
            "comparison": {
                "initial_word_count": 240,
                "rendered_word_count": 258,
                "word_delta": 18,
            },
            "issues": [],
        },
    )

    assert overview["rendering"]["type"] == "server_rendered"
    assert overview["rendering"]["label"] == "服务端渲染 / 静态输出"
    assert overview["seo"]["status"] == "passed"
    assert overview["major_issues"] == []


def test_crawler_overview_flags_client_rendered_content_and_prioritizes_issues() -> None:
    overview = build_crawler_overview(
        {
            "status": "warning",
            "score": 72,
            "request": {"status_code": 200},
            "crawlability": {"allowed": True, "detail": "Googlebot allowed"},
            "indexability": {"indexable": True},
            "content": {"word_count": 12},
            "issues": [
                {
                    "code": "thin_initial_html",
                    "severity": "high",
                    "title": "初始 HTML 可见内容过少",
                    "detail": "核心内容依赖 JavaScript。",
                    "recommendation": "使用 SSR 或静态生成。",
                }
            ],
        },
        {
            "status": "warning",
            "score": 76,
            "request": {"status_code": 200},
            "comparison": {
                "initial_word_count": 12,
                "rendered_word_count": 320,
                "word_delta": 308,
            },
            "issues": [
                {
                    "severity": "medium",
                    "title": "部分渲染资源加载失败",
                    "detail": "发现异常资源。",
                    "recommendation": "修复异常资源。",
                }
            ],
        },
    )

    assert overview["rendering"]["type"] == "client_rendered"
    assert overview["rendering"]["status"] == "warning"
    assert overview["seo"]["status"] == "warning"
    assert overview["major_issues"][0]["source"] == "Googlebot"
    assert overview["major_issues"][0]["severity"] == "high"


def test_googlebot_access_challenge_recognizes_waf_response() -> None:
    response = _HttpResult(
        requested_url="https://example.com/",
        final_url="https://example.com/",
        status_code=446,
        headers={"server": "AkamaiGHost", "content-type": "text/html"},
        text="<h1>Access Denied</h1>",
        response_time_ms=12,
        redirect_chain=[],
        truncated=False,
    )

    assert GooglebotService._is_access_challenge(response) is True


@pytest.mark.asyncio
async def test_browser_raw_html_fetches_unrendered_html_and_validates_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = BrowserRawHtmlService(timeout_seconds=2)
    normalized_urls: list[str] = []
    responses = iter(
        [
            type(
                "Response",
                (),
                {
                    "status_code": 302,
                    "headers": {"location": "/final"},
                    "content": b"",
                    "encoding": "utf-8",
                    "url": "https://example.com/start",
                },
            )(),
            type(
                "Response",
                (),
                {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "content": b"<html><body><div id='app'></div></body></html>",
                    "encoding": "utf-8",
                    "url": "https://example.com/final",
                },
            )(),
        ]
    )

    async def fake_normalize(url: str) -> str:
        normalized_urls.append(url)
        return url

    def fake_request_once(url: str) -> object:
        del url
        return next(responses)

    monkeypatch.setattr(browser_raw_module, "normalize_public_url", fake_normalize)
    monkeypatch.setattr(service, "_request_once", fake_request_once)

    result = await service.fetch("https://example.com/start")

    assert result.status_code == 200
    assert result.final_url == "https://example.com/final"
    assert result.redirect_chain == [
        {
            "status_code": 302,
            "from": "https://example.com/start",
            "to": "https://example.com/final",
        }
    ]
    assert normalized_urls == [
        "https://example.com/start",
        "https://example.com/final",
    ]
    assert "<div id='app'>" in result.text


@pytest.mark.asyncio
async def test_googlebot_waf_challenge_uses_browser_control_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GooglebotService(timeout_seconds=2)

    async def fake_normalize(url: str) -> str:
        return url

    async def fake_fetch(
        url: str,
        *,
        client: object,
        validate_url: bool = True,
    ) -> _HttpResult:
        del validate_url
        del client
        return _HttpResult(
            requested_url=url,
            final_url=url,
            status_code=446,
            headers={"server": "AkamaiGHost", "content-type": "text/html"},
            text="<h1>Access Denied</h1>",
            response_time_ms=10,
            redirect_chain=[],
            truncated=False,
        )

    async def fake_browser_fetch(url: str) -> BrowserRawResponse:
        if url.endswith("/robots.txt"):
            return BrowserRawResponse(
                requested_url=url,
                final_url=url,
                status_code=200,
                headers={"content-type": "text/plain"},
                text="User-agent: Googlebot\nAllow: /\n",
                response_time_ms=8,
                redirect_chain=[],
                truncated=False,
            )
        return BrowserRawResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            headers={"content-type": "text/html"},
            text=(
                "<html><head><title>App</title><meta name='robots' content='all'>"
                "</head><body><h1>Browser content</h1><div id='app'></div>"
                "<script src='/app.js'></script></body></html>"
            ),
            response_time_ms=12,
            redirect_chain=[],
            truncated=False,
        )

    monkeypatch.setattr(googlebot_module, "normalize_public_url", fake_normalize)
    monkeypatch.setattr(service, "_fetch", fake_fetch)
    monkeypatch.setattr(service.browser_raw_service, "fetch", fake_browser_fetch)

    run = await service.run("https://example.com/app")

    assert run.result["request"]["status_code"] == 446
    assert run.result["control_request"]["status_code"] == 200
    assert run.result["access"]["state"] == "waf_challenge"
    assert run.result["access"]["browser_fallback_used"] is True
    assert run.result["access"]["control_transport"] == "curl_cffi_chrome"
    assert run.result["access"]["raw_html_source"] == "browser_control"
    assert run.result["crawlability"]["allowed"] is True
    assert run.result["indexability"]["indexable"] is None
    assert run.result["indexability"]["state"] == "unknown_googlebot_access"
    assert run.result["content"]["h1"] == "Browser content"
    assert "Browser content" in run.html


def test_crawler_overview_does_not_call_waf_challenge_not_indexable() -> None:
    overview = build_crawler_overview(
        {
            "status": "warning",
            "score": 73,
            "request": {"status_code": 446},
            "access": {
                "state": "waf_challenge",
                "detail": "模拟 Googlebot 被 WAF 拦截。",
            },
            "crawlability": {"allowed": True, "detail": "Googlebot rules allow /app/"},
            "indexability": {
                "indexable": None,
                "state": "unknown_googlebot_access",
                "noindex": False,
            },
            "issues": [
                {
                    "code": "googlebot_access_challenge",
                    "severity": "high",
                    "title": "模拟 Googlebot 请求被 WAF 或反爬策略拦截",
                    "detail": "Googlebot UA 返回 HTTP 446。",
                    "recommendation": "使用 Search Console 确认。",
                }
            ],
        },
        {
            "status": "warning",
            "score": 85,
            "mode": "browser_fallback",
            "request": {"status_code": 200},
            "comparison": {
                "initial_word_count": 12,
                "rendered_word_count": 320,
                "word_delta": 308,
            },
            "issues": [],
        },
    )

    assert overview["rendering"]["type"] == "client_rendered"
    assert overview["seo"]["status"] == "warning"
    assert overview["indexing"]["status"] == "warning"
    assert overview["indexing"]["label"] == "真实索引状态待确认"
    assert "不可索引" not in overview["summary"]
