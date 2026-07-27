from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import google_crawler as crawler_routes
from app.core.exceptions import AppError
from app.main import app
from app.services.google_crawler.common import inspect_html
from app.services.google_crawler.googlebot import GooglebotRun
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
    }

    async def fake_googlebot_run(url: str) -> GooglebotRun:
        return GooglebotRun(result=googlebot_result, html="<html><body>content</body></html>")

    async def fake_render_test(url: str, **_: object) -> dict:
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
    assert overview["rendering"]["status"] == "failed"
    assert overview["seo"]["status"] == "failed"
    assert overview["major_issues"][0]["source"] == "Googlebot"
    assert overview["major_issues"][0]["severity"] == "high"
