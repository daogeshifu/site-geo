from __future__ import annotations

import httpx
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.services.crawlers import http as crawler_http
from app.services.crawlers import simulation
from app.services.crawlers.catalog import BY_ID, GROUPS, PLATFORMS
from app.services.crawlers.http import MAX_HTML_BYTES

client = TestClient(app)
TARGET = "https://sample.example/page"
HTML = '<title>测试页面</title><meta name="googlebot" content="noindex"><h1>原始响应</h1>'


def use_site(monkeypatch, handler):
    """Record real outgoing HTTPX requests; no DNS or Internet required."""
    requests = []

    def recording_handler(request):
        requests.append(request)
        return handler(request)

    async def normalized(url):
        return url

    transport = httpx.MockTransport(recording_handler)
    make_client = httpx.AsyncClient
    monkeypatch.setattr(crawler_http, "normalize_public_url", normalized)
    monkeypatch.setattr(simulation, "normalize_public_url", normalized)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: make_client(transport=transport, **kwargs))
    return requests


def open_site(request):
    if request.url.path == "/robots.txt":
        return httpx.Response(404)
    return httpx.Response(200, headers={"Content-Type": "text/html; charset=utf-8"}, text=HTML)


def test_directory_detail_and_navigation_agree_on_platforms():
    directory = BeautifulSoup(client.get("/crawler-test").text, "html.parser")
    assert [h.get_text(strip=True) for h in directory.select(".platform-group h2")] == list(GROUPS)
    assert {a["href"] for a in directory.select(".platform-link")} == {
        f"/crawler-test/{p.id}" for p in PLATFORMS
    }
    for platform in PLATFORMS:
        detail = BeautifulSoup(client.get(f"/crawler-test/{platform.id}").text, "html.parser")
        assert detail.select_one("#platform-select option[selected]")["value"] == platform.id
        assert detail.select_one("#panel-spider")
        assert bool(detail.select_one("#panel-render")) == bool(platform.render)
        assert not detail.select_one("#checklist-body")
        assert platform.sources[0][1] in [link["href"] for link in detail.select(".sources a")]
    assert client.get("/crawler-test/unknown").status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platform,agent", [(p.id, agent.token) for p in PLATFORMS if p.render is None for agent in p.agents]
)
async def test_spider_only_sends_selected_identity(monkeypatch, platform, agent):
    requests = use_site(monkeypatch, open_site)
    expected = BY_ID[platform].agent(agent)
    data = await simulation.simulate(TARGET, platform, agent)
    assert "render" not in data
    assert [r.url.path for r in requests] == ["/robots.txt", "/page"]
    assert requests[0].headers["User-Agent"] == expected.headers(robots=True)["User-Agent"]
    assert requests[1].headers["User-Agent"] == expected.user_agent
    for name, value in expected.page_headers:
        assert requests[1].headers[name] == value
    assert "Range" not in requests[0].headers
    spider = data["spider"]
    assert spider["raw_html"] == HTML
    assert spider["request"]["headers"]["User-Agent"] == requests[1].headers["User-Agent"]
    assert spider["robots"]["token"] == agent
    assert ("noindex" in spider["content"]["directives"]) == (agent == "Googlebot")


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["google", "baidu", "bing"])
async def test_supported_renderer_receives_own_agent_and_original_html(monkeypatch, platform):
    def site(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<h1>Initial</h1>")

    use_site(monkeypatch, site)

    async def capture(self, url, **options):
        assert url == TARGET
        assert options["user_agent"] == BY_ID[platform].render.user_agent
        assert options["initial_html"] == "<h1>Initial</h1>"
        return {"status": "passed", "rendered_html": {"html": "<h1>Rendered</h1>"}}

    monkeypatch.setattr(simulation.GoogleRenderService, "capture", capture)
    data = await simulation.simulate(TARGET, platform)
    assert data["spider"]["raw_html"] != data["render"]["rendered_html"]["html"]


@pytest.mark.asyncio
async def test_redirect_checks_selected_robots_before_fetching_new_path(monkeypatch):
    def site(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: OAI-SearchBot\nDisallow: /private/*\nUser-agent: *\nAllow: /"
            )
        assert request.url.path == "/page"
        return httpx.Response(302, headers={"Location": "https://other.example/private/test"})

    requests = use_site(monkeypatch, site)
    data = await simulation.simulate(TARGET, "openai")
    assert [r.url.path for r in requests] == ["/robots.txt", "/page", "/robots.txt"]
    assert requests[-1].url.host == "other.example"
    assert data["spider"]["status"] == "skipped"
    assert data["spider"]["robots"]["target"].endswith("/private/test")
    assert data["spider"]["robots"]["allowed"] is False
    receipts = data["spider"]["observed_responses"]
    assert [entry["status_code"] for entry in receipts] == [302]
    assert receipts[0]["url"] == TARGET
    assert receipts[0]["headers"]["User-Agent"] == BY_ID["openai"].agents[0].user_agent
    assert "request" not in data["spider"]


@pytest.mark.asyncio
async def test_google_extended_is_separate_from_fetch_identity(monkeypatch):
    def site(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: Google-Extended\nDisallow: /\nUser-agent: Googlebot\nAllow: /"
            )
        return open_site(request)

    requests = use_site(monkeypatch, site)
    data = await simulation.simulate(TARGET, "gemini")
    rules = data["spider"]["robots"]
    assert rules["allowed"] and rules["content_use"]["allowed"] is False
    assert all("Google-Extended" not in r.headers["User-Agent"] for r in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429])
async def test_http_denial_is_returned_without_substitution(monkeypatch, status):
    def site(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            status, headers={"Retry-After": "60", "Content-Type": "text/html"}, text="blocked"
        )

    requests = use_site(monkeypatch, site)
    data = await simulation.simulate(TARGET, "google")
    assert len(requests) == 2
    assert data["spider"]["request"]["status_code"] == status
    assert data["spider"]["raw_html"] == "blocked"
    assert data["render"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_response_capture_caps_decompressed_bytes(monkeypatch):
    def site(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200, headers={"content-type": "text/plain"}, content=b"x" * (MAX_HTML_BYTES + 5)
        )

    use_site(monkeypatch, site)
    spider = (await simulation.simulate(TARGET, "x"))["spider"]
    assert spider["truncated"]
    assert len(spider["raw_html"]) == spider["request"]["size_bytes"] == MAX_HTML_BYTES


@pytest.mark.asyncio
async def test_unknown_platform_and_agent_fail_before_fetch():
    for platform, agent in [("missing", None), ("openai", "Twitterbot")]:
        with pytest.raises(AppError) as error:
            await simulation.simulate(TARGET, platform, agent)
        assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_renderer_failure_preserves_spider_evidence(monkeypatch):
    use_site(monkeypatch, open_site)

    async def crash(self, url, **options):
        raise RuntimeError("browser exited")

    monkeypatch.setattr(simulation.GoogleRenderService, "capture", crash)
    data = await simulation.simulate(TARGET, "google")
    assert data["spider"]["raw_html"] == HTML
    assert data["render"]["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["ftp://example.com/page", "https://example.com:invalid/"])
async def test_invalid_fetch_address_gets_client_error(url):
    with pytest.raises(AppError) as error:
        await simulation.simulate(url, "openai")
    assert error.value.status_code == 400
