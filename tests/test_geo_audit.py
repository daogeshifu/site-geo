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
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False),
    )


def evidence(url="https://example.com/", html=HTML, kind="homepage", **kwargs):
    return PageEvidence(url=url, final_url=url, page_type=kind, html=html, status_code=200,
        response_headers={"content-type": "text/html"}, **kwargs)


def audit(items, source=None):
    return asyncio.run(GeoAuditService().audit("https://example.com/", source or discovery(), page_evidence=items, feedback_lang="zh"))


def check(page, rule):
    return next(c for d in page.dimensions.values() for c in d.checks if c.id == rule)


def test_scoring_definition_is_unique_and_normalized():
    assert len({row[0] for row in RULES}) == len(RULES) == 23
    assert sum(row[2] for row in RULES) == 100
    for key, (points, *_rest) in DIMENSIONS.items():
        assert sum(row[2] for row in RULES if row[1] == key) == points


def test_new_geo_is_invariant_to_external_and_social_signals(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    baseline = audit([evidence()], source)
    source.backlinks = BacklinkOverviewResult(available=True, authority_score=100, referring_domains=99999)
    source.llms.exists = True
    changed = HTML.replace('</head>', '<meta property="og:title" content="Great"><meta name="twitter:card" content="summary"></head>')
    item = evidence(html=changed)
    item.response_headers.update({"strict-transport-security": "max-age=31536000", "last-modified": "Wed, 11 Nov 2026 00:00:00 GMT"})
    result = audit([item], source)
    assert result.score == baseline.score
    assert result.score_range == baseline.score_range
    assert result.coverage["evidence_coverage"] == baseline.coverage["evidence_coverage"]
    assert "citation_probability" not in result.model_dump()


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


def test_combo_and_pure_geo_share_engine_but_never_scores(monkeypatch):
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
    async def seo(*args, **kwargs):
        received.append(("seo", kwargs["page_evidence"]))
        return SimpleNamespace(overall_score=99, model_dump=lambda **kw: {"overall_score": 99})
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    monkeypatch.setattr(service.discovery_service, "discover", discover)
    monkeypatch.setattr(module, "collect_page_evidence", collect)
    monkeypatch.setattr(service.geo_audit_service, "audit", geo)
    monkeypatch.setattr(service.seo_audit_service, "audit", seo)
    monkeypatch.setattr(service.seo_audit_service, "summarize", lambda *a, **kw: SimpleNamespace(model_dump=lambda **kw: {"overall_score": 99}))
    def task(kind):
        order = service._step_order_for(kind)
        now = datetime.now(timezone.utc)
        return AuditTask(task_id=kind, url=source.url, normalized_url=source.url, domain=source.domain, cache_key=kind,
            task_type=kind, created_at=now, updated_at=now, step_order=order, steps={key: TaskStep(name=key) for key in order})
    pure = asyncio.run(service._run_site_geo_task(task("site_geo_only_audit")))
    combo = asyncio.run(service._run_site_geo_task(task("site_geo_audit")))
    assert pure["geo"]["score"] == combo["geo"]["score"]
    assert "seo" not in pure and combo["seo"]["overall_score"] == 99
    assert combo["summary"]["combined_score"] is None
    assert combo["summary"]["seo_score"] == 99
    assert ("backlinks", False) in received and ("backlinks", True) in received
    assert all(item is shared for name, item in received if name in {"geo", "seo"})


def test_docs_and_frontend_describe_the_actual_new_rules():
    client = TestClient(app)
    html = client.get("/").text
    soup = BeautifulSoup(html, "html.parser")
    options = soup.select("#task-type option")
    assert options[0]["value"] == "site_geo_only_audit"
    assert options[0].has_attr("selected")
    assert "网站 SEO+GEO 审计" in options[2].text
    assert "<<<<<<<" not in html
    docs = BeautifulSoup(client.get("/api-doc").text, "html.parser")
    actual = {node["data-geo-check"]: int(node["data-points"]) for node in docs.select("[data-geo-check]")}
    assert actual == {row[0]: row[2] for row in RULES}
    assert "不平均" in docs.text
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
        assert payload["result"]["geo"]["scoring_version"] == "onsite-geo-v1"
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
    ("site_geo_only_audit", 6, 23), ("site_seo_audit", 6, 26), ("site_geo_audit", 12, 49),
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
        actual_dimensions = sum(len(result[key]["dimensions"]) for key in ("seo", "geo") if key in result)
        actual_checks = len(result.get("seo", {}).get("coverage_checks", [])) + sum(
            len(d["checks"]) for d in result.get("geo", {}).get("dimensions", {}).values())
        assert (actual_dimensions, actual_checks) == (dimension_count, check_count)
        if task_type != "site_seo_audit":
            assert result["geo"]["readiness_status"] == "blocked"
            assert result["geo"]["coverage"]["unknown_checks"] > 0
        if task_type == "site_geo_audit":
            assert result["summary"]["combined_score"] is None
            assert result["seo_summary"]["overall_score"] == result["seo"]["overall_score"]

        report = client.get(f"/api/v1/tasks/{task_id}/report")
        assert report.status_code == 200
        for check_id in ("GEO-023", "CHK-026") if task_type == "site_geo_audit" else (
            ("CHK-026",) if task_type == "site_seo_audit" else ("GEO-023",)
        ):
            assert check_id in report.text
        if "geo" in result:
            for heading in ("Complete GEO checklist", "Verification queue", "Recommendations", "Platform retrieval policies"):
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
                assert result["scoring_version"] == "onsite-geo-v1"
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


def test_combined_export_rebuilds_missing_historical_seo_summary(monkeypatch):
    from app.services.reporting.geo_report import render_geo_report

    async def variants(*args, **kwargs):
        return {"http_to_https": True, "non_www_to_preferred": True, "www_to_preferred": True}

    monkeypatch.setattr(SeoAuditService, "_probe_variants", variants)
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    source = discovery()
    geo = audit([evidence()], source).model_dump(mode="json")
    seo = asyncio.run(SeoAuditService().audit(source.url, source, page_evidence=[evidence()])).model_dump(mode="json")
    markdown = render_geo_report({"url": source.url, "geo": geo, "seo": seo, "discovery": source.model_dump(mode="json")})
    assert "GEO-023" in markdown and "CHK-026" in markdown
    assert "Verification queue" in markdown
