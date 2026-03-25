from app.models.audit import (
    ContentAuditResult,
    PageDiagnosticResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import (
    DiscoveryResult,
    FetchMetadata,
    HomepageExtract,
    KeyPages,
    LlmsResult,
    RobotsResult,
    SitemapResult,
    SiteSignals,
)
from app.services.report_service import ReportService
from app.services.cache_service import CacheService
from app.utils.url_utils import get_scope_root, is_internal_url, is_likely_homepage_url


def test_homepage_detection_accepts_locale_homepages() -> None:
    assert is_likely_homepage_url("https://example.com/")
    assert is_likely_homepage_url("https://example.com/en")
    assert is_likely_homepage_url("https://example.com/zh-cn/")
    assert not is_likely_homepage_url("https://example.com/products/widget")


def test_scope_boundaries_respect_host_and_locale_prefix() -> None:
    assert get_scope_root("https://www.ecoflow.com/de/") == "https://www.ecoflow.com/de/"
    assert get_scope_root("https://www.ecoflow.com/de/products/delta-2") == "https://www.ecoflow.com/de/"
    assert get_scope_root("https://de.ecoflow.com/") == "https://de.ecoflow.com/"

    assert is_internal_url("https://www.ecoflow.com/de/", "https://www.ecoflow.com/de/products/delta-2")
    assert not is_internal_url("https://www.ecoflow.com/de/", "https://www.ecoflow.com/fr/products/delta-2")
    assert not is_internal_url("https://www.ecoflow.com/de/", "https://de.ecoflow.com/products/delta-2")


def test_cache_key_changes_with_scope() -> None:
    service = CacheService(cache_dir=".cache/test-audits", ttl_days=7)
    de_path_key, _, _ = service.build_cache_key("https://www.ecoflow.com/de/", "standard", None)
    fr_path_key, _, _ = service.build_cache_key("https://www.ecoflow.com/fr/", "standard", None)
    de_subdomain_key, _, _ = service.build_cache_key("https://de.ecoflow.com/", "standard", None)

    assert de_path_key != fr_path_key
    assert de_path_key != de_subdomain_key


def test_report_renders_page_diagnostics_and_notices() -> None:
    discovery = DiscoveryResult(
        url="https://example.com/products/widget",
        normalized_url="https://example.com/products/widget",
        final_url="https://example.com/products/widget",
        site_root_url="https://example.com",
        domain="example.com",
        fetch=FetchMetadata(final_url="https://example.com/products/widget", status_code=200, headers={}, response_time_ms=120),
        homepage=HomepageExtract(title="Widget", lang="en"),
        robots=RobotsResult(url="https://example.com/robots.txt", exists=True),
        sitemap=SitemapResult(url="https://example.com/sitemap.xml", exists=True),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False),
        business_type="saas",
        key_pages=KeyPages(),
        schema_summary={},
        site_signals=SiteSignals(),
        input_is_likely_homepage=False,
        input_scope_warning="Input URL does not look like a homepage.",
        full_audit_enabled=True,
        profiled_page_count=9,
        site_snapshot_version="snapshot-v3",
    )
    summary = SummaryResult(
        composite_geo_score=60,
        status="fair",
        summary="Example summary",
        notices=["Non-homepage input detected: Input URL does not look like a homepage."],
    )
    service = ReportService()
    markdown = service.render_markdown(
        url="https://example.com/products/widget",
        discovery=discovery,
        visibility=VisibilityAuditResult(score=60, status="fair", ai_visibility_score=60, brand_authority_score=60),
        technical=TechnicalAuditResult(score=60, status="fair", technical_score=60),
        content=ContentAuditResult(
            score=60,
            status="fair",
            content_score=60,
            experience_score=60,
            expertise_score=60,
            authoritativeness_score=60,
            trustworthiness_score=60,
        ),
        schema_result=SchemaAuditResult(score=60, status="fair", structured_data_score=60),
        platform=PlatformAuditResult(score=60, status="fair", platform_optimization_score=60, platform_scores={}),
        summary=summary,
        page_diagnostics=[
            PageDiagnosticResult(
                url="https://example.com/products/widget",
                page_type="product",
                source="extended",
                overall_score=71,
                status="good",
                citability_score=78,
                content_score=70,
                technical_score=68,
                schema_score=55,
            )
        ],
    )
    assert "## Page Diagnostics (Full Audit)" in markdown
    assert "Non-homepage input detected" in markdown
