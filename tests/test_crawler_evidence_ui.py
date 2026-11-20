"""Chromium exercises the real templates, modules and test API against a controlled website."""

from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from app.api import demo_access
from app.main import app
from app.services.crawlers import http as crawler_http
from app.services.crawlers import simulation
from app.services.crawlers.catalog import PLATFORMS
from app.services.google_crawler.common import inspect_html


UI = "https://console.test"
SITE = "https://origin.example"
TOKEN = "ui-test-credential"
HTML = '<title>示例页面</title><body><h1>现场记录</h1><p>网页正文 &lt;tag&gt;</p><script>bad()</script></body>'
RENDERED = "<title>渲染标题</title><body>执行脚本后的正文</body>"


def website(request):
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /private")
    if path == "/redirect":
        return httpx.Response(302, headers={"Location": "/private"})
    if path == "/slow":
        raise httpx.ReadTimeout("timed out", request=request)
    if path == "/rate":
        return httpx.Response(429, headers={"Retry-After": "60"}, text="稍后重试")
    if path == "/binary":
        return httpx.Response(200, content=b"\x00\xff", headers={"Content-Type": "application/octet-stream"})
    if path == "/empty":
        return httpx.Response(204)
    if path == "/plain":
        return httpx.Response(200, text="纯文本样本")
    return httpx.Response(200, text=HTML, headers={"Content-Type": "text/html; charset=utf-8", "Set-Cookie": "hidden=1"})


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as engine:
        if not Path(engine.chromium.executable_path).is_file():
            pytest.skip("Chromium is required for crawler UI coverage")
        browser = engine.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser, monkeypatch):
    async def offline_url(url):
        assert urlsplit(url).hostname == "origin.example"
        return url

    async def capture(_self, url, *, user_agent, **options):
        content = inspect_html(RENDERED, url)
        return {
            "status": "passed",
            "request": {
                "status_code": 200, "final_url": url, "render_time_ms": 12,
                "headers": {"User-Agent": user_agent}, "response_headers": {"content-type": "text/html"},
            },
            "rendered_content": content,
            "rendered_html": {"html": RENDERED, "html_bytes": len(RENDERED.encode())},
        }

    monkeypatch.setattr(demo_access, "get_demo_access_tokens", lambda: (TOKEN,))
    monkeypatch.setattr(demo_access.demo_token_store, "log_usage", lambda _: None)
    monkeypatch.setattr(demo_access.demo_token_store, "resolve_token", lambda *args, **kwargs: None)
    monkeypatch.setattr(crawler_http, "normalize_public_url", offline_url)
    monkeypatch.setattr(simulation, "normalize_public_url", offline_url)
    make_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: make_client(transport=httpx.MockTransport(website), **kw))
    monkeypatch.setattr(simulation.GoogleRenderService, "capture", capture)

    client = TestClient(app)

    def serve(route):
        req = route.request
        path = urlsplit(req.url).path
        headers = {k: v for k, v in req.headers.items() if k in {"content-type", "x-api-token"}}
        response = client.request(req.method, path, headers=headers, content=req.post_data_buffer)
        route.fulfill(status=response.status_code, body=response.content, content_type=response.headers["content-type"])

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.route(UI + "/**", serve)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    client.close()
    assert not errors


def run(page, path="/page"):
    page.locator("#test-url").fill(SITE + path)
    page.locator("#demo-token").fill(TOKEN)
    page.get_by_role("button", name="开始测试").click()
    expect(page.locator("#run-state")).to_contain_text("测试结果")


def test_all_platforms_show_actual_headers_content_and_supported_stages(page):
    for platform in PLATFORMS:
        page.goto(UI + "/crawler-test/" + platform.id)
        raw = page.locator("#panel-spider")
        expect(raw.locator(".header-origin")).to_have_text("预设字段")
        run(page)
        expect(raw.locator(".header-origin")).to_have_text("网页请求 · 实测")
        expect(raw.locator(".request-data dd").first).to_have_text(platform.agents[0].user_agent)
        expect(raw.locator(".request-data")).to_contain_text("origin.example")
        expect(raw.locator(".page-title")).to_have_text("示例页面")
        expect(raw.locator(".excerpt p")).to_have_text("现场记录 网页正文 <tag>")
        expect(raw.locator(".content-facts dd").first).to_have_text(str(len("现场记录 网页正文 <tag>")))
        expect(raw.locator(".metrics dd").first).to_have_text("200")
        expect(raw.locator(".record >> text=Set-Cookie")).to_have_count(0)
        rendered = page.locator("#panel-render")
        if platform.render:
            expect(rendered.locator(".request-data dd").first).to_have_text(platform.render.user_agent)
            expect(rendered.locator(".excerpt p")).to_have_text("执行脚本后的正文")
        else:
            expect(rendered).to_have_count(0)


def test_switch_profile_and_platform_keep_url_and_discard_previous_evidence(page):
    page.goto(UI + "/crawler-test")
    page.locator('a[href="/crawler-test/openai"]').click()
    run(page)
    details = page.locator("#panel-spider .content-pane details")
    details.locator("summary").focus()
    page.keyboard.press("Enter")
    expect(details.locator("pre")).to_have_text(HTML)
    page.locator("#agent-select").select_option("GPTBot")
    expect(page.locator(".header-origin")).to_have_text("预设字段")
    expect(page.locator(".request-data dd").first).to_contain_text("GPTBot")
    expect(page.locator(".page-title")).to_have_count(0)
    run(page)
    expect(page.locator(".request-data dd").first).to_contain_text("GPTBot")
    page.locator("#platform-select").select_option("x")
    expect(page.locator("#test-url")).to_have_value(SITE + "/page")
    expect(page.locator(".stage-status")).to_have_text("待测试")
    expect(page.locator(".request-data dd").first).to_contain_text("Twitterbot")


def test_empty_error_and_interrupted_results_keep_the_source_of_headers(page):
    page.goto(UI + "/crawler-test/x")
    panel = page.locator("#panel-spider")
    for path, expected_origin, expected_content in [
        ("/private", "robots.txt 请求 · 实测", "禁止抓取当前路径"),
        ("/redirect", "最近响应 · 实测", "未取得网页正文"),
        ("/slow", "网页请求 · 已尝试", "响应超时"),
        ("/rate", "网页请求 · 实测", "稍后重试"),
        ("/empty", "网页请求 · 实测", "正文为 0 字节"),
        ("/binary", "网页请求 · 实测", "无文本预览"),
        ("/plain", "网页请求 · 实测", "纯文本样本"),
    ]:
        run(page, path)
        expect(panel.locator(".header-origin")).to_have_text(expected_origin)
        expect(panel.locator(".content-data")).to_contain_text(expected_content)
        if path in {"/private", "/slow"}:
            expect(panel.locator(".stage-summary")).to_be_hidden()
        if path == "/redirect":
            expect(panel.locator(".metrics dd").first).to_have_text("302")
        if path == "/rate":
            expect(panel.locator(".content-origin")).to_have_text("错误响应")
            expect(panel.locator(".stage-supplement")).to_contain_text("Retry-After")


def test_form_keyboard_recovery_and_narrow_layout(page):
    page.set_viewport_size({"width": 320, "height": 700})
    page.goto(UI + "/crawler-test/openai")
    url = page.get_by_label("网页地址")
    url.focus()
    page.keyboard.press("Enter")
    expect(url).to_be_focused()
    expect(url).to_have_attribute("aria-invalid", "true")
    url.fill(SITE + "/page")
    token = page.get_by_label("访问 Token", exact=True)
    token.fill("invalid")
    page.get_by_label("显示访问 Token").check()
    expect(token).to_have_attribute("type", "text")
    page.get_by_role("button", name="开始测试").click()
    expect(token).to_be_focused()
    expect(token).to_have_attribute("type", "password")
    expect(page.get_by_role("alert")).to_contain_text("Token 无效")
    run(page)
    request = page.locator(".request-pane").bounding_box()
    content = page.locator(".content-pane").bounding_box()
    assert content["y"] >= request["y"] + request["height"] - 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_switch_during_pending_request_discards_late_result(page):
    page.goto(UI + "/crawler-test/openai")
    pending = []
    page.route("**/api/v1/crawler/test", lambda route: pending.append(route))
    page.locator("#test-url").fill(SITE + "/page")
    page.locator("#demo-token").fill(TOKEN)
    page.locator("#run-test").click()
    expect(page.locator("#run-test")).to_be_disabled()
    expect(page.locator(".stage-status")).to_have_text("测试中")
    expect(page.locator(".header-origin")).to_have_text("预设字段")
    page.locator("#agent-select").select_option("GPTBot")
    expect(page.locator("#run-test")).to_be_enabled()
    pending[0].fulfill(status=503, json={"success": False, "message": "过期的请求"})
    page.unroute("**/api/v1/crawler/test")
    expect(page.locator(".stage-status")).to_have_text("待测试")
    expect(page.get_by_role("alert")).to_be_hidden()
    run(page)
    expect(page.locator(".request-data dd").first).to_contain_text("GPTBot")
