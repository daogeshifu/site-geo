import asyncio
import copy
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.main import app
from app.models.discovery import (
    BacklinkOverviewResult, DiscoveryResult, FetchMetadata, HomepageExtract,
    KeyPages, LlmsResult, PageProfile, RobotsResult, SitemapResult,
)
from app.models.task import AuditTask, TaskAuditRequest, TaskStep
from app.services.audit.geo import DIMENSIONS, RULES, GeoAuditService, main_document
from app.services.audit.seo import SeoAuditService
from app.services.infra.audit_evidence import PageEvidence, collect_page_evidence, sample_candidates
from app.services.infra.cache import CacheService
from app.services.orchestration.tasks import TaskService
from app.utils.robots_parser import inspect_robot_path
from app.utils.llms_parser import inspect_llms, inspect_llms_structure


HTML = '''<!doctype html><html lang="en"><head><title>Example widget guide</title></head>
<body><nav><a href="/about">About</a><a href="/docs/widget">Widget guide</a></nav>
<main><h1>Example widget guide</h1><p>Example widget guide explains setup and operation.</p>
<h2>Setup</h2><ol><li>Connect the widget.</li><li>Start the widget.</li></ol>
<p>Maintained by the Example technical team.</p></main></body></html>'''


def discovery():
    return DiscoveryResult(
        url="https://example.com/", normalized_url="https://example.com/", final_url="https://example.com/",
        scope_root_url="https://example.com/", domain="example.com", business_type="saas",
        fetch=FetchMetadata(final_url="https://example.com/", status_code=200, response_time_ms=100),
        homepage=HomepageExtract(title="Example", internal_links=[{"url": "https://example.com/docs/widget", "text": "Guide"}]),
        key_pages=KeyPages(), robots=RobotsResult(url="https://example.com/robots.txt", exists=True, status_code=200,
            raw_text="User-agent: *\nAllow: /\nUser-agent: GPTBot\nDisallow: /\n"),
        sitemap=SitemapResult(exists=True, discovered_urls=["https://example.com/", "https://example.com/docs/widget"]),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False, status_code=404),
    )


def evidence(url="https://example.com/", html=HTML, kind="homepage", **kwargs):
    kwargs.setdefault("response_time_ms", 100)
    return PageEvidence(url=url, final_url=url, page_type=kind, html=html, status_code=200,
        response_headers={"content-type": "text/html"}, **kwargs)


def audit(items, source=None):
    return asyncio.run(GeoAuditService().audit("https://example.com/", source or discovery(), page_evidence=items, feedback_lang="zh"))


def check(page, rule):
    return next(c for d in page.dimensions.values() for c in d.checks if c.id == rule)


def test_scoring_definition_is_unique_and_normalized():
    assert len({row[0] for row in RULES}) == len(RULES) == 26
    assert sum(row[2] for row in RULES) == 100
    for key, (points, *_rest) in DIMENSIONS.items():
        assert sum(row[2] for row in RULES if row[1] == key) == points


def test_new_geo_is_invariant_to_external_and_social_signals(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    baseline = audit([evidence()], source)
    source.backlinks = BacklinkOverviewResult(available=True, authority_score=100, referring_domains=99999)
    changed = HTML.replace('</head>', '<meta property="og:title" content="Great"><meta name="twitter:card" content="summary"></head>')
    item = evidence(html=changed)
    item.response_headers.update({"strict-transport-security": "max-age=31536000", "last-modified": "Wed, 11 Nov 2026 00:00:00 GMT"})
    result = audit([item], source)
    assert result.score == baseline.score
    assert result.score_range == baseline.score_range
    assert result.coverage["evidence_coverage"] == baseline.coverage["evidence_coverage"]
    assert "citation_probability" not in result.model_dump()


def test_llms_structure_and_speed_contribute_to_the_geo_score(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    missing = audit([evidence()], source)
    text = "# Example\n\n> Official widget documentation.\n\n## Guides\n- [Setup](/docs/widget): Connect a widget.\n"
    source.llms = LlmsResult(url="https://example.com/llms.txt", exists=True, status_code=200,
        structure_checks=inspect_llms_structure(text, "https://example.com/llms.txt"))
    complete = audit([evidence()], source)
    assert check(complete.pages[0], "GEO-024").value == 1
    assert complete.score > missing.score
    slow = audit([evidence(response_time_ms=5001)], source)
    assert check(slow.pages[0], "GEO-025").value == 0
    assert slow.score < complete.score
    assert complete.scoring_version == "onsite-geo-v2"
    assert "llms_txt" not in complete.auxiliary


@pytest.mark.parametrize("status,exists,text,expected", [
    (404, False, "", 0), (500, False, "", None), (429, False, "", None),
    (None, False, "", None), (200, True, "", 0),
    (200, True, "<html><head><title>Not found</title></head><body>Fallback</body></html>", 0),
    (200, True, "Plain text without navigation", 1 / 3),
    (200, True, "# Example\n\nOfficial documentation.\n", 2 / 3),
])
def test_llms_missing_unverified_and_partial_files_stay_distinct(monkeypatch, status, exists, text, expected):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    source.llms = LlmsResult(url="https://example.com/llms.txt", exists=exists, status_code=status,
        structure_checks=inspect_llms_structure(text, "https://example.com/llms.txt"))
    item = check(audit([evidence()], source).pages[0], "GEO-024")
    assert item.value == expected
    assert item.status == ("unknown" if expected is None else "fail" if expected == 0 else "partial")


def test_llms_parser_uses_the_complete_file_and_rejects_html_fallback(monkeypatch):
    from app.utils import llms_parser as module
    text = "# Example\n\nOfficial documentation.\n\n" + "Description. " * 80 + "\n## Guides\n- [Setup](/docs/widget)\n"
    response = SimpleNamespace(status_code=200, final_url="https://example.com/llms.txt",
                               text=text, headers={"content-type": "text/plain"})
    async def fetch(*args, **kwargs):
        return response
    monkeypatch.setattr(module, "fetch_url", fetch)
    result = asyncio.run(inspect_llms("https://example.com/"))
    assert "[Setup]" not in result.content_preview
    assert all(result.structure_checks.values())
    response.headers["content-type"] = "text/html"
    assert asyncio.run(inspect_llms("https://example.com/")).structure_checks["readable_text"] is False
    for target in ("#intro", "javascript:alert(1)", "https://other.example/docs", "/llms.txt", "http://[invalid"):
        assert inspect_llms_structure(f"# Example\n\nSummary.\n- [Link]({target})", result.url)["internal_navigation"] is False


@pytest.mark.parametrize("already_inspected", [False, True])
def test_discovery_upgrades_only_old_preview_only_llms_snapshots(monkeypatch, already_inspected):
    from app.services.discovery import discovery as module
    source = discovery()
    text = "# Example\n\nOfficial guide.\n- [Guide](/docs/widget)\n"
    full = LlmsResult(url=source.llms.url, exists=True, status_code=200,
                      structure_checks=inspect_llms_structure(text, source.llms.url))
    source.llms = full if already_inspected else LlmsResult(url=source.llms.url, exists=True, status_code=200)
    calls = []
    async def resolve(*args):
        return {"response": SimpleNamespace(final_url=source.final_url)}
    async def site(*args):
        return SimpleNamespace(site_id=1)
    async def cached(*args, **kwargs):
        return source
    async def inspect(url, **kwargs):
        calls.append(url)
        return full
    service = module.DiscoveryService()
    service.asset_store = SimpleNamespace(available=True, ensure_site=site, load_cached_discovery=cached)
    monkeypatch.setattr(service, "_resolve_target_scope", resolve)
    monkeypatch.setattr(module, "inspect_llms", inspect)
    result = asyncio.run(service.discover(source.url, include_backlinks=False))
    assert result.llms.structure_checks == full.structure_checks
    assert calls == ([] if already_inspected else [source.final_url])


@pytest.mark.parametrize("elapsed,value", [
    (0, 1), (800, 1), (801, .75), (1500, .75), (1501, .5),
    (3000, .5), (3001, .25), (5000, .25), (5001, 0), (None, None), (-1, None),
])
def test_html_loading_speed_uses_observed_timing_and_documented_boundaries(monkeypatch, elapsed, value):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    item = check(audit([evidence(response_time_ms=elapsed)]).pages[0], "GEO-025")
    assert item.value == value
    assert item.evidence_type == "http_timing"
    assert item.evidence["browser_load_and_core_web_vitals_measured"] is False
    if value is None:
        assert item.status == "unknown"


@pytest.mark.parametrize("path,value", [
    ("/docs/widget", 1), ("/docs/widget.html", 1), ("/docs/widget?utm_source=mail&gclid=1", 1),
    ("/docs/widget#setup", 1), ("/index.php", .5), ("/docs/widget?id=7", .5),
    ("/docs/widget?lang=zh", .5), ("/docs/widget?sessionid=secret", 0),
    ("/docs/widget;jsessionid=secret", 0), ("/#/docs/widget", 0), ("/#!/docs/widget", 0),
])
def test_url_static_style_distinguishes_clean_paths_tracking_and_dynamic_routes(monkeypatch, path, value):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    item = check(audit([evidence("https://example.com" + path)]).pages[0], "GEO-026")
    assert item.value == value
    assert item.max_points == 2
    assert item.blocker is False


def test_hash_routing_is_detected_after_http_has_removed_the_fragment(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    html = HTML.replace('<main>', '<main><a href="#/docs/widget">Widget route</a>')
    result = audit([evidence(html=html)])
    item = check(result.pages[0], "GEO-026")
    assert item.value == 0
    assert item.evidence["hash_route_links"] == ["https://example.com/#/docs/widget"]


def test_robots_uses_deep_paths_and_separates_training():
    robots = discovery().robots
    assert all(inspect_robot_path(robots, "https://example.com/docs/widget").values())
    robots.raw_text = "User-agent: *\nDisallow: /docs/*\nAllow: /docs/public$\n"
    assert all(inspect_robot_path(robots, "https://example.com/").values())
    assert not any(inspect_robot_path(robots, "https://example.com/docs/private").values())
    assert all(inspect_robot_path(robots, "https://example.com/docs/public").values())
    assert not any(inspect_robot_path(robots, "https://example.com/docs/public/extra").values())
    robots.raw_text = "User-agent: *\nDisallow:\n"
    assert all(inspect_robot_path(robots, "https://example.com/deep").values())
    robots.raw_text = None
    assert all(v is None for v in inspect_robot_path(robots, "https://example.com/docs/private").values())


def test_blockers_survive_a_high_score_and_are_scoped(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    source.robots.raw_text = "User-agent: *\nAllow: /\nUser-agent: OAI-SearchBot\nDisallow: /docs/\n"
    item = evidence("https://example.com/docs/widget", kind="documentation")
    result = audit([evidence(), item], source)
    assert result.readiness_status == "blocked"
    assert result.coverage["blocked_pages"] == 1
    assert result.blockers[0]["url"] == item.url
    assert result.blockers[0]["evidence"]["policies"]["Googlebot"] is True


def test_nav_scripts_and_hidden_copy_are_not_core_content(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    html = '<html><head><title>Excellent content</title></head><body><nav>Links</nav><main><script>Real body</script><p hidden>Hidden body</p></main><footer>Long footer</footer></body></html>'
    assert main_document(html)[2] == ""
    result = audit([evidence(html=html)])
    assert check(result.pages[0], "GEO-009").status == "fail"
    assert result.readiness_status == "blocked"
    # A short, meaningful response is not failed by an arbitrary word threshold.
    result = audit([evidence(html='<html lang="en"><head><title>Reset</title></head><body><main><h1>Reset</h1><p>Press reset.</p></main></body></html>')])
    assert check(result.pages[0], "GEO-009").status == "pass"


@pytest.mark.parametrize("landmark", ["main", "article", 'div role="main"'])
def test_content_survives_navigation_repaired_around_it(monkeypatch, landmark):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    tag = landmark.split()[0]
    # An unclosed navigation div makes lxml place the later content inside nav.
    html = (
        '<html><body><header><nav><div><a href="/">Navigation</a></nav></header>'
        f'<{landmark}><h1>Widget</h1><p>Press reset.</p>'
        f'<nav>Contents</nav><aside>Related pages</aside><footer>Copyright</footer></{tag}>'
        '</body></html>'
    )
    assert main_document(html)[2] == "Widget Press reset."
    result = audit([evidence(html=html)])
    extraction = check(result.pages[0], "GEO-009")
    assert extraction.status == "pass"
    assert extraction.blocker is False
    assert not any(blocker["check_id"] == "GEO-009" for blocker in result.blockers)


@pytest.mark.parametrize("hidden", ["hidden", 'aria-hidden="true"', 'style="display:none"'])
def test_hidden_content_in_navigation_is_not_rescued(monkeypatch, hidden):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    html = (
        '<html><body><nav>Navigation'
        f'<div {hidden}><main><h1>Hidden content</h1></main></div>'
        '</nav></body></html>'
    )
    assert main_document(html)[2] == ""
    result = audit([evidence(html=html)])
    assert check(result.pages[0], "GEO-009").status == "fail"


def test_body_fallback_still_excludes_navigation():
    html = '<html><body><nav>Navigation</nav><p>Visible body.</p><footer>Copyright</footer></body></html>'
    assert main_document(html)[2] == "Visible body."


def test_nested_styled_hidden_content_does_not_break_extraction():
    html = (
        '<html><body><main><div style="display:none">'
        '<p style="color:red">Hidden content</p></div><p>Visible body.</p></main></body></html>'
    )
    assert main_document(html)[2] == "Visible body."


def test_unknown_and_not_applicable_are_distinct_and_reported(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    result = audit([evidence()])
    page = result.pages[0]
    assert check(page, "GEO-004").status == "unknown"
    assert check(page, "GEO-011").status == "unknown"
    assert check(page, "GEO-019").status == "na"
    assert check(page, "GEO-020").status == "unknown"
    assert result.provisional is True
    assert result.readiness_status == "unverified"
    assert 0 < result.coverage["evidence_coverage"] < 1
    assert result.score_range[0] <= result.score <= result.score_range[1]


def test_sampling_and_aggregation_do_not_use_best_page(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    good = evidence("https://example.com/docs/good", kind="documentation")
    poor = evidence("https://example.com/docs/poor", html='<html><body><main>Loading</main></body></html>', kind="documentation")
    baseline = audit([copy.deepcopy(good)])
    result = audit([good, poor])
    assert result.score < baseline.score
    assert result.coverage["sampled_pages"] == 2
    assert result.coverage["sample_weights"][good.url] == .5
    assert result.coverage["total_site_pages"] is None
    failure = evidence("https://example.com/docs/missing", html=None, kind="documentation", error="timeout")
    failure.status_code = None
    failed = audit([evidence(), failure])
    assert failed.coverage["sampled_pages"] == 2
    assert failed.coverage["fetched_pages"] == 1
    assert failed.coverage["blocked_pages"] == 1


def test_render_errors_are_unknown_and_not_a_fake_comparison(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", True)
    async def denied(*args, **kwargs):
        return {"available": True, "request": {"status_code": 429}, "rendered_html": {"html": HTML}}
    service = GeoAuditService()
    monkeypatch.setattr(service.renderer, "test", denied)
    result = asyncio.run(service.audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    assert check(result.pages[0], "GEO-011").status == "unknown"
    async def rendered(*args, **kwargs):
        return {"available": True, "request": {"status_code": 200}, "rendered_html": {"html": HTML}}
    monkeypatch.setattr(service.renderer, "test", rendered)
    result = asyncio.run(service.audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    assert check(result.pages[0], "GEO-011").value == 1


def test_shared_evidence_reuses_captured_sources_and_retains_failures(monkeypatch):
    from app.services.infra import audit_evidence as module
    source = discovery()
    source.page_profiles = {"homepage": PageProfile(page_type="homepage", final_url=source.final_url, source_key="a" * 64, status_code=200)}
    async def read(key):
        return HTML
    requests = []
    async def fetch(url, **kwargs):
        requests.append(url)
        raise RuntimeError("network timeout")
    monkeypatch.setattr(module, "read_page_source", read)
    monkeypatch.setattr(module, "fetch_url", fetch)
    results = asyncio.run(collect_page_evidence(source, 8))
    assert len(results) == 2
    assert results[0].reused is True
    assert requests == ["https://example.com/docs/widget"]
    assert results[1].error == "network timeout"


def test_deep_documents_can_be_discovered_through_observed_link_chains(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    source.sitemap.discovered_urls = []
    parent = evidence("https://example.com/docs/widget", html=HTML.replace('</main>', '<a href="/docs/deep">Deep guide</a></main>'), kind="documentation")
    deep = evidence("https://example.com/docs/deep", kind="documentation")
    orphan = evidence("https://example.com/docs/orphan", kind="documentation")
    result = audit([parent, deep, orphan], source)
    assert check(result.pages[1], "GEO-006").status == "pass"
    assert check(result.pages[2], "GEO-006").status == "fail"


def test_hidden_inline_copy_and_unsupported_content_are_not_verified_body(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    assert main_document('<html><body><main><p style="display:none">hidden</p></main></body></html>')[2] == ""
    item = evidence(html='{"name":"Example"}')
    item.response_headers["content-type"] = "application/json"
    result = audit([item])
    assert check(result.pages[0], "GEO-009").status == "unknown"


def test_cache_and_task_routing_separate_three_task_types(tmp_path):
    cache = CacheService(cache_dir=str(tmp_path))
    keys = {cache.build_cache_key("https://example.com", "standard", task_type=kind)[0]
            for kind in ("site_geo_only_audit", "site_geo_audit", "site_seo_audit")}
    assert len(keys) == 3
    assert cache.build_cache_key("https://example.com", "standard", max_pages=5)[0] != cache.build_cache_key("https://example.com", "standard", max_pages=8)[0]
    assert TaskAuditRequest(url="https://example.com", task_type="site_geo_only_audit").task_type == "site_geo_only_audit"
    assert TaskAuditRequest(url="https://example.com").task_type == "site_seo_audit"
    assert TaskService()._step_order_for("site_geo_only_audit") == ["discovery", "geo", "observation", "summary"]


def test_sgeo_uses_shared_evidence_and_its_own_rubric_without_running_seo(monkeypatch):
    from app.services.orchestration import tasks as module
    service = TaskService()
    source = discovery()
    shared = [evidence()]
    received = []
    async def discover(*args, **kwargs):
        received.append(("backlinks", kwargs["include_backlinks"]))
        return source
    async def collect(*args):
        return shared
    original = service.geo_audit_service.audit
    async def geo(*args, **kwargs):
        received.append(("geo", kwargs["page_evidence"]))
        return await original(*args, **kwargs)
    original_sgeo = service.sgeo_audit_service.audit
    async def sgeo(*args, **kwargs):
        received.append(("sgeo", kwargs["page_evidence"]))
        return await original_sgeo(*args, **kwargs)
    async def seo(*args, **kwargs):
        raise AssertionError("SGEO must not run a second complete SEO scoring engine")
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    monkeypatch.setattr(service.discovery_service, "discover", discover)
    monkeypatch.setattr(module, "collect_page_evidence", collect)
    monkeypatch.setattr(service.geo_audit_service, "audit", geo)
    monkeypatch.setattr(service.seo_audit_service, "audit", seo)
    monkeypatch.setattr(service.sgeo_audit_service, "audit", sgeo)
    def task(kind):
        order = service._step_order_for(kind)
        now = datetime.now(timezone.utc)
        return AuditTask(task_id=kind, url=source.url, normalized_url=source.url, domain=source.domain, cache_key=kind,
            task_type=kind, created_at=now, updated_at=now, step_order=order, steps={key: TaskStep(name=key) for key in order})
    pure = asyncio.run(service._run_site_geo_task(task("site_geo_only_audit")))
    combo = asyncio.run(service._run_site_geo_task(task("site_geo_audit")))
    assert pure["geo"]["scoring_version"] == "onsite-geo-v2"
    assert combo["sgeo"]["scoring_version"] == "onsite-sgeo-v1"
    assert "seo" not in combo and "geo" not in combo and "seo_summary" not in combo
    assert combo["summary"]["combined_score"] == combo["sgeo"]["score"]
    assert combo["summary"]["sgeo_score"] == combo["sgeo"]["score"]
    assert "seo_score" not in combo["summary"] and "geo_score" not in combo["summary"]
    assert all(value is False for name, value in received if name == "backlinks")
    assert all(item is shared for name, item in received if name in {"geo", "sgeo"})


def test_docs_and_frontend_describe_the_actual_new_rules():
    client = TestClient(app)
    html = client.get("/").text
    soup = BeautifulSoup(html, "html.parser")
    options = soup.select("#task-type option")
    assert options[0]["value"] == "site_geo_only_audit"
    assert options[0].has_attr("selected")
    assert "网站 SGEO 诊断" in options[2].text
    assert "<<<<<<<" not in html
    docs = BeautifulSoup(client.get("/api-doc").text, "html.parser")
    actual = {node["data-geo-check"]: int(node["data-points"]) for node in docs.select("[data-geo-check]")}
    assert actual == {row[0]: row[2] for row in RULES}
    for key, (_, zh, _) in DIMENSIONS.items():
        assert docs.select_one(f"#geo-{key}-title").get_text() == zh
    assert docs.select_one('[data-geo-check="GEO-001"] .scoring-rule-label').get_text() == "HTTP / HTTPS"
    assert docs.select_one('[data-geo-check="GEO-023"] .scoring-rule-label').get_text() == "JSON-LD / Schema.org"
    assert not any("GEO-" in node.get_text() for node in docs.select("[data-geo-check]"))
    assert "SGEO 评分规则" in docs.text
    assert "combined_score" in docs.text
    assert "/api/v1/audit/geo" in docs.text
    assert "结构代理" in docs.text
    schema = client.get("/openapi.json").json()
    assert "/api/v1/audit/geo" in schema["paths"]
    assert "site_geo_only_audit" in schema["components"]["schemas"]["TaskAuditRequest"]["properties"]["task_type"]["enum"]


def test_real_seo_engine_consumes_shared_pages_without_refetch(monkeypatch):
    from app.services.audit import seo as module
    service = SeoAuditService()
    async def no_fetch(*args, **kwargs):
        raise AssertionError("Shared audit page must not be fetched again")
    async def variants(*args):
        return {"http_to_https": True, "non_www_to_preferred": True, "www_to_preferred": True}
    monkeypatch.setattr(module, "fetch_url", no_fetch)
    monkeypatch.setattr(service, "_probe_variants", variants)
    result = asyncio.run(service.audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    assert len(result.coverage_checks) == 26
    assert result.sampled_pages[0].url == "https://example.com/"
    assert result.sampled_pages[0].status_code == 200
    assert 0 <= result.overall_score <= 100


def test_geo_api_task_lifecycle_report_and_source_inventory(monkeypatch, tmp_path):
    from app.api.routes.tasks import task_service
    from app.services.orchestration import tasks as module
    source = discovery()
    async def discover(*args, **kwargs):
        assert kwargs["include_backlinks"] is False
        return source
    async def collect(*args):
        return [evidence(source_key="b" * 64, fetched_at="2026-11-11T00:00:00+00:00")]
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    monkeypatch.setattr(task_service, "asset_store", SimpleNamespace(available=False, backend="file"))
    monkeypatch.setattr(task_service, "cache_service", CacheService(cache_dir=str(tmp_path)))
    monkeypatch.setattr(task_service.discovery_service, "discover", discover)
    monkeypatch.setattr(module, "collect_page_evidence", collect)
    monkeypatch.setitem(settings.__dict__, "demo_access_token", "geo-lifecycle-test-token")
    with TestClient(app, headers={"X-API-Token": "geo-lifecycle-test-token"}) as client:
        response = client.post("/api/v1/tasks/audit", json={"url": source.url, "task_type": "site_geo_only_audit", "force_refresh": True})
        assert response.status_code == 200
        task_id = response.json()["data"]["task_id"]
        for _ in range(30):
            payload = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            if payload["status"] in {"completed", "failed"}:
                break
            time.sleep(.01)
        assert payload["status"] == "completed", payload.get("error")
        assert payload["progress_percent"] == 100
        assert payload["step_order"] == ["discovery", "geo", "observation", "summary"]
        assert payload["result"]["geo"]["scoring_version"] == "onsite-geo-v2"
        assert "seo" not in payload["result"]
        report = client.get(f"/api/v1/tasks/{task_id}/report")
        assert report.status_code == 200
        assert "GEO-009" in report.text
        assert "unknown" in report.text
        assert "no averaged combined score" in report.text
        from app.services.reporting.site_pages import task_site_pages
        inventory = task_site_pages(task_service.tasks[task_id])
        assert any(page.get("source_key") == "b" * 64 for page in inventory)


@pytest.mark.parametrize("task_type,dimension_count,check_count", [
    ("site_geo_only_audit", 6, 26), ("site_seo_audit", 6, 26), ("site_geo_audit", 6, 30),
])
def test_v1_task_results_reports_and_cache_keep_all_diagnostic_dimensions(
    monkeypatch, tmp_path, task_type, dimension_count, check_count
):
    """Exercise actual engines through v1, replacing only network evidence."""
    from app.api.routes.tasks import task_service
    from app.services.orchestration import tasks as task_module
    from app.services.audit import seo as seo_module

    source = discovery()
    source.robots.raw_text = "User-agent: *\nAllow: /\nUser-agent: OAI-SearchBot\nDisallow: /docs/\n"

    async def discover(*args, **kwargs):
        return source

    async def collect(*args, **kwargs):
        return [evidence(), evidence("https://example.com/docs/widget", kind="documentation")]

    async def variants(*args, **kwargs):
        return {"http_to_https": True, "non_www_to_preferred": True, "www_to_preferred": True}

    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    monkeypatch.setitem(settings.__dict__, "demo_access_token", "diagnostic-contract-token")
    monkeypatch.setattr(task_service, "asset_store", SimpleNamespace(available=False, backend="file"))
    monkeypatch.setattr(task_service, "cache_service", CacheService(cache_dir=str(tmp_path)))
    monkeypatch.setattr(task_service.discovery_service, "discover", discover)
    monkeypatch.setattr(task_module, "collect_page_evidence", collect)
    monkeypatch.setattr(seo_module, "collect_page_evidence", collect)
    monkeypatch.setattr(SeoAuditService, "_probe_variants", variants)

    with TestClient(app, headers={"X-API-Token": "diagnostic-contract-token"}) as client:
        request = {"url": source.url, "task_type": task_type, "feedback_lang": "zh"}
        response = client.post("/api/v1/tasks/audit", json=request)
        assert response.status_code == 200
        task_id = response.json()["data"]["task_id"]
        for _ in range(100):
            task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
            if task["status"] in {"completed", "failed"}:
                break
            time.sleep(.01)
        assert task["status"] == "completed", task.get("error")
        result = task["result"]
        actual_dimensions = sum(len(result[key]["dimensions"]) for key in ("seo", "geo", "sgeo") if key in result)
        actual_checks = len(result.get("seo", {}).get("coverage_checks", [])) + sum(
            len(d["checks"]) for key in ("geo", "sgeo") for d in result.get(key, {}).get("dimensions", {}).values())
        assert (actual_dimensions, actual_checks) == (dimension_count, check_count)
        if task_type != "site_seo_audit":
            readiness = result.get("sgeo") or result["geo"]
            assert readiness["readiness_status"] == "blocked"
            assert readiness["coverage"]["unknown_checks"] > 0
        if task_type == "site_geo_audit":
            assert result["summary"]["combined_score"] == result["sgeo"]["score"]
            assert result["summary"]["sgeo_score"] == result["sgeo"]["score"]
            assert not {"seo", "geo", "seo_summary"} & result.keys()

        report = client.get(f"/api/v1/tasks/{task_id}/report")
        assert report.status_code == 200
        for check_id in ("SGEO-026", "SGEO-030") if task_type == "site_geo_audit" else (
            ("CHK-026",) if task_type == "site_seo_audit" else ("GEO-026",)
        ):
            assert check_id in report.text
        if "geo" in result or "sgeo" in result:
            for heading in (f"Complete {'SGEO' if 'sgeo' in result else 'GEO'} checklist", "Verification queue", "Recommendations", "Platform retrieval policies"):
                assert heading in report.text
        cached = client.post("/api/v1/tasks/audit", json=request).json()["data"]
        assert cached["cached"] is True
        assert cached["result"] == result


def test_v1_sync_and_historical_module_contracts_still_work(monkeypatch):
    from app.services.audit import seo as seo_module, geo as geo_module

    async def collect(*args, **kwargs):
        return [evidence()]

    async def variants(*args, **kwargs):
        return {"http_to_https": True, "non_www_to_preferred": True, "www_to_preferred": True}

    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    monkeypatch.setitem(settings.__dict__, "demo_access_token", "legacy-contract-token")
    monkeypatch.setattr(seo_module, "collect_page_evidence", collect)
    monkeypatch.setattr(geo_module, "collect_page_evidence", collect)
    monkeypatch.setattr(SeoAuditService, "_probe_variants", variants)
    request = {"url": "https://example.com/", "discovery": discovery().model_dump(mode="json")}
    with TestClient(app, headers={"X-Demo-Token": "legacy-contract-token"}) as client:
        for module in ("visibility", "technical", "content", "schema", "platform", "seo", "geo", "full"):
            response = client.post(f"/api/v1/audit/{module}", json=request)
            assert response.status_code == 200, (module, response.text)
            result = response.json()["data"]
            if module == "full":
                assert result["summary"]["scoring_version"] == "geo-audit-v3"
                assert {"visibility", "technical", "content", "schema", "platform", "summary"} <= result.keys()
            elif module == "geo":
                assert result["scoring_version"] == "onsite-geo-v2"
                assert len(result["dimensions"]) == 6
            elif module == "seo":
                assert len(result["coverage_checks"]) == 26
            else:
                assert "score" in result and "status" in result


@pytest.mark.parametrize("endpoint", ["tasks/audit", "audit/seo", "audit/geo", "audit/full"])
def test_invalid_site_parameters_return_json_422_instead_of_500(monkeypatch, endpoint):
    monkeypatch.setitem(settings.__dict__, "demo_access_token", "validation-contract-token")
    with TestClient(app, headers={"Authorization": "Bearer validation-contract-token"}) as client:
        response = client.post(f"/api/v1/{endpoint}", json={"url": "https://example.com/", "max_pages": 3})
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert "Site scope requires max_pages >= 5" in response.json()["errors"][0]["ctx"]["error"]


def test_combined_export_regroups_historical_page_evidence_as_sgeo(monkeypatch):
    from app.services.reporting.geo_report import render_geo_report

    async def variants(*args, **kwargs):
        return {"http_to_https": True, "non_www_to_preferred": True, "www_to_preferred": True}

    monkeypatch.setattr(SeoAuditService, "_probe_variants", variants)
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    geo = audit([evidence()], source).model_dump(mode="json")
    seo = asyncio.run(SeoAuditService().audit(source.url, source, page_evidence=[evidence()])).model_dump(mode="json")
    markdown = render_geo_report({"url": source.url, "geo": geo, "seo": seo, "discovery": source.model_dump(mode="json")})
    assert all(key in markdown for key in ("SGEO-024", "SGEO-025", "SGEO-026", "SGEO-030"))
    assert "CHK-026" not in markdown
    assert "Complete SGEO checklist" in markdown
    assert "Verification queue" in markdown
