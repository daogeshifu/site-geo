from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import google_crawler as crawler_routes
from app.core.exceptions import AppError
from app.main import app
from app.services.google_crawler.common import inspect_html
from app.services.google_crawler.googlebot import GooglebotRun
from app.utils.public_url import normalize_public_url


client = TestClient(app)


def test_google_crawler_demo_page_is_available() -> None:
    response = client.get("/google-crawler-test")
    assert response.status_code == 200
    assert "Googlebot" in response.text
    assert "Google Render" in response.text


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
    assert data["googlebot"]["score"] == 92
    assert data["google_render"]["score"] == 74
