import asyncio
import copy
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.main import app
from app.models.sgeo import SGEO_SCORING_VERSION
from app.models.task import AuditTask
from app.services.audit.geo import GeoAuditService
from app.services.audit.sgeo import DIMENSIONS, RULES, SgeoAuditService
from app.services.infra.audit_evidence import PageEvidence
from app.services.infra.cache import CacheService
from app.services.orchestration.tasks import TaskService
from app.services.reporting.geo_report import render_geo_report
from test_geo_audit import discovery, evidence, HTML


@pytest.fixture(autouse=True)
def disable_browser_measurements(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)


def audit(items=None):
    return asyncio.run(SgeoAuditService().audit("https://example.com/", discovery(),
        page_evidence=items if items is not None else [evidence()], feedback_lang="zh"))


def checks(result):
    return {c.id: c for d in result.dimensions.values() for c in d.checks}


def page_checks(result, index=0):
    return {c.id: c for d in result.pages[index].dimensions.values() for c in d.checks}


def test_sgeo_rubric_has_thirty_uniquely_owned_checks_and_one_hundred_points():
    assert len(RULES) == len({row[0] for row in RULES}) == 30
    assert sum(row[2] for row in RULES) == 100
    assert sum(row[0] for row in DIMENSIONS.values()) == 100
    for key, (weight, *_rest) in DIMENSIONS.items():
        assert sum(row[2] for row in RULES if row[1] == key) == weight
    result = audit()
    assert result.scoring_version == SGEO_SCORING_VERSION
    assert len(result.dimensions) == 6
    assert set(checks(result)) == {f"SGEO-{i:03}" for i in range(1, 31)}
    assert sum(d.weight for d in result.dimensions.values()) == pytest.approx(1)


def test_sgeo_reweights_observations_without_using_any_geo_score_or_dimension_total():
    geo = asyncio.run(GeoAuditService().audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    service = SgeoAuditService()
    expected = service.build(geo)
    geo.score = 0
    geo.score_range = [0, 0]
    for dimension in geo.dimensions.values():
        dimension.score, dimension.earned_points = 0, 0
    for page in geo.pages:
        page.score = 0
        for dimension in page.dimensions.values():
            dimension.score, dimension.earned_points = 0, 0
    actual = service.build(geo)
    assert actual.score == expected.score
    assert actual.score_range == expected.score_range
    assert actual.dimensions == expected.dimensions
    assert actual.score != 0


def test_metadata_and_mobile_evidence_change_the_same_unified_score():
    baseline = audit()
    improved_html = HTML.replace('</head>', '<meta name="description" content="A clear widget setup guide"><meta name="viewport" content="width=device-width, initial-scale=1"></head>')
    improved = audit([evidence(html=improved_html)])
    assert improved.score > baseline.score
    assert page_checks(baseline)["SGEO-021"].value == pytest.approx(2 / 3)
    assert page_checks(improved)["SGEO-021"].status == "pass"
    assert page_checks(baseline)["SGEO-027"].status == "fail"
    assert page_checks(improved)["SGEO-027"].status == "pass"
    assert page_checks(improved)["SGEO-027"].evidence["actual_mobile_layout_measured"] is False
    assert all(c.impact and c.recommendation and c.acceptance_criteria for c in checks(improved).values())
    assert improved.pages[0].title == 'Example widget guide'
    assert improved.pages[0].meta_description == 'A clear widget setup guide'
    assert improved.pages[0].h1_count == 1
    assert improved.pages[0].noindex_detected is False


def test_failed_fetches_remain_in_sample_and_are_not_treated_as_passing_content():
    failed = PageEvidence(url="https://example.com/docs/widget", final_url="https://example.com/docs/widget",
        page_type="documentation", error="timeout")
    result = audit([evidence(), failed])
    assert len(result.pages) == 2
    assert result.status == result.readiness_status == "blocked"
    assert result.coverage["blocked_pages"] == 1
    assert page_checks(result, 1)["SGEO-001"].status == "fail"
    for key in ("SGEO-021", "SGEO-027", "SGEO-028", "SGEO-029", "SGEO-030"):
        assert page_checks(result, 1)[key].status == "unknown"
    assert result.coverage["evidence_coverage"] < 1
    assert result.score_range[0] <= result.score <= result.score_range[1]


def test_a_blocker_is_reported_even_when_the_measured_score_is_high():
    source = discovery()
    source.robots.raw_text = "User-agent: OAI-SearchBot\nDisallow: /\n"
    result = asyncio.run(SgeoAuditService().audit(source.url, source, page_evidence=[evidence()]))
    assert result.score > 50
    assert result.readiness_status == "blocked"
    assert result.blockers[0]["check_id"] == "SGEO-002"
    assert checks(result)["SGEO-002"].blocker


def test_unknown_and_inapplicable_checks_are_distinct_and_do_not_invent_findings():
    result = audit()
    assert page_checks(result)["SGEO-029"].status == "na"
    assert page_checks(result)["SGEO-030"].status == "na"
    for key in ("SGEO-004", "SGEO-011", "SGEO-020"):
        assert page_checks(result)[key].status == "unknown"
        assert checks(result)[key].label not in result.issues
    assert result.provisional is True
    assert audit([]).score is None
    assert audit([]).score_range == [0, 100]


def test_payload_uses_utf8_bytes_and_truncation_preserves_unknown_state():
    html = HTML + '<!--' + '中' * 90000 + '-->'
    result = audit([evidence(html=html)])
    measured = page_checks(result)["SGEO-028"]
    assert measured.evidence["html_bytes"] == len(html.encode('utf-8'))
    assert measured.status == "partial"
    truncated = audit([evidence(html=html, source_truncated=True)])
    assert page_checks(truncated)["SGEO-028"].status == "unknown"
    assert page_checks(truncated)["SGEO-029"].status == "unknown"
    assert page_checks(truncated)["SGEO-030"].status == "unknown"


@pytest.mark.parametrize("attributes,expected", [
    ('src="/hero.png" fetchpriority="high"', "pass"),
    ('src="/hero.png" fetchpriority="high" loading="lazy"', "fail"),
    ('src="/hero.png" fetchpriority="HIGH" loading="LAZY"', "fail"),
    ('data-src="/hidden.png"', "fail"),
])
def test_image_policy_does_not_require_eager_images_to_be_lazy(attributes, expected):
    result = audit([evidence(html=HTML.replace('</main>', f'<img {attributes} alt="Widget"></main>'))])
    assert page_checks(result)["SGEO-029"].status == expected


@pytest.mark.parametrize("attributes,expected", [
    ('hreflang="en-GB" href="/en/"', 'pass'),
    ('hreflang="x-default" href="/"', 'pass'),
    ('hreflang="not a language" href="/en/"', 'fail'),
    ('hreflang="en"', 'fail'),
])
def test_alternate_links_check_declared_language_and_url_without_claiming_reciprocity(attributes, expected):
    result = audit([evidence(html=HTML.replace('</head>', f'<link rel="alternate" {attributes}></head>'))])
    check = page_checks(result)["SGEO-030"]
    assert check.status == expected
    assert check.evidence["reciprocal_links_verified"] is False


def test_duplicate_metadata_is_one_shared_check_and_redirect_aliases_are_not_duplicates():
    geo = asyncio.run(GeoAuditService().audit("https://example.com/", discovery(), page_evidence=[
        evidence(), evidence("https://example.com/docs/widget", kind="documentation")]))
    signals = {p.url: {"title": "Same title", "meta_description": "Same description", "lang": "en"} for p in geo.pages}
    result = SgeoAuditService().build(geo, signals=signals)
    assert page_checks(result)["SGEO-021"].value == pytest.approx(1 / 3)
    assert page_checks(result)["SGEO-021"].evidence["duplicate_title"] is True
    geo.pages[1].final_url = geo.pages[0].final_url
    aliases = SgeoAuditService().build(geo, signals=signals)
    assert page_checks(aliases)["SGEO-021"].status == "pass"


def test_more_pages_of_one_type_do_not_overweight_that_type():
    base = asyncio.run(GeoAuditService().audit("https://example.com/", discovery(), page_evidence=[
        evidence(), evidence("https://example.com/docs/widget", kind="documentation", response_time_ms=5000)]))
    service = SgeoAuditService()
    before = service.build(base)
    for i in range(3):
        base.pages.append(base.pages[1].model_copy(deep=True, update={"url": f"https://example.com/docs/copy-{i}"}))
    after = service.build(base)
    assert after.score == before.score
    assert after.score_range == before.score_range


def test_legacy_upgrade_and_export_preserve_saved_scores_and_leave_new_measurements_unknown():
    geo = asyncio.run(GeoAuditService().audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    payload = {"url": discovery().url, "geo": geo.model_dump(mode="json"), "seo": {"overall_score": 99}}
    original = copy.deepcopy(payload)
    upgraded = SgeoAuditService().upgrade_legacy_payload(payload, feedback_lang="zh")
    assert payload == original
    assert upgraded["sgeo"]["score"] != 99
    assert upgraded["seo"]["overall_score"] == 99
    assert upgraded["summary"]["sgeo_score"] == upgraded["sgeo"]["score"]
    for dimension in upgraded["sgeo"]["dimensions"].values():
        for check in dimension["checks"]:
            if check["id"] in {"SGEO-021", "SGEO-027", "SGEO-028", "SGEO-029", "SGEO-030"}:
                assert check["status"] == "unknown"
    markdown = render_geo_report(payload)
    assert "Complete SGEO checklist" in markdown
    assert "SGEO-030" in markdown
    assert "# SEO" not in markdown and "GEO score:" not in markdown.replace("SGEO score:", "")
    assert payload == original


def test_task_reads_upgrade_legacy_reports_without_mutating_the_stored_task():
    geo = asyncio.run(GeoAuditService().audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    service = TaskService()
    now = datetime.now(timezone.utc)
    task = AuditTask(task_id="old", task_type="site_geo_audit", url="https://example.com/", normalized_url="https://example.com/",
        domain="example.com", cache_key="old", created_at=now, updated_at=now, status="completed",
        result={"geo": geo.model_dump(), "seo": {"overall_score": 99}})
    service.tasks["old"] = task
    view = asyncio.run(service.get_task("old"))
    assert "sgeo" in view.result
    assert "sgeo" not in service.tasks["old"].result


def test_page_inventory_keeps_sgeo_metadata_without_overlaying_historical_seo_sources():
    from app.services.reporting.site_pages import task_site_pages
    from types import SimpleNamespace
    result = audit()
    payload = {"sgeo": result.model_dump(mode="json"), "discovery": discovery().model_dump(mode="json"),
        "seo": {"sampled_pages": [{"url": "https://example.com/", "title": "Old SEO title"}]}}
    inventory = task_site_pages(SimpleNamespace(result=payload, steps={}, url="https://example.com/"))
    homepage = next(page for page in inventory if page["url"] == 'https://example.com/')
    assert homepage['title'] == 'Example widget guide'
    assert homepage['h1_count'] == 1
    assert homepage['discovery_source'] == 'sgeo_sample'


def test_a_legacy_viewport_presence_flag_does_not_verify_its_device_width_value():
    geo = asyncio.run(GeoAuditService().audit("https://example.com/", discovery(), page_evidence=[evidence()]))
    result = SgeoAuditService().build(geo, signals={'https://example.com/': {'viewport_present': True}})
    check = page_checks(result)['SGEO-027']
    assert check.status == 'unknown'
    assert check.evidence['viewport_present'] is True


def test_sgeo_version_only_invalidates_sgeo_cache_keys(monkeypatch, tmp_path):
    from app.services.infra import cache as module
    cache = CacheService(cache_dir=str(tmp_path))
    kinds = ("site_geo_audit", "site_geo_only_audit", "site_seo_audit")
    before = {kind: cache.build_cache_key("https://example.com/", "standard", task_type=kind)[0] for kind in kinds}
    monkeypatch.setattr(module, "SGEO_SCORING_VERSION", "next-sgeo-version")
    after = {kind: cache.build_cache_key("https://example.com/", "standard", task_type=kind)[0] for kind in kinds}
    assert before["site_geo_audit"] != after["site_geo_audit"]
    assert before["site_geo_only_audit"] == after["site_geo_only_audit"]
    assert before["site_seo_audit"] == after["site_seo_audit"]


def test_scoring_documentation_matches_live_sgeo_rule_registry():
    docs = BeautifulSoup(TestClient(app).get('/api-doc').text, 'html.parser')
    assert {node['data-sgeo-check']: int(node['data-points']) for node in docs.select('[data-sgeo-check]')} == {r[0]: r[2] for r in RULES}
    for key, (weight, zh, _) in DIMENSIONS.items():
        card = docs.select_one(f'[data-sgeo-dimension="{key}"]')
        assert card.select_one('h3').text == zh
        assert int(card['data-weight']) == weight
    assert docs.select_one('#sgeo-scoring')
