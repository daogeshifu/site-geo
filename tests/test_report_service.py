from app.models.audit import (
    ContentAuditResult,
    PlatformAuditDetail,
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
from app.services.reporting.report import ReportService


def test_report_contains_reference_sections() -> None:
    service = ReportService()
    discovery = DiscoveryResult(
        url="https://example.com",
        normalized_url="https://example.com/",
        final_url="https://example.com/",
        domain="example.com",
        fetch=FetchMetadata(final_url="https://example.com/", status_code=200, headers={}, response_time_ms=100),
        homepage=HomepageExtract(title="Example Co", meta_description="Example description", lang="en"),
        robots=RobotsResult(url="https://example.com/robots.txt", exists=True),
        sitemap=SitemapResult(url="https://example.com/sitemap.xml", exists=True),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False),
        business_type="agency",
        key_pages=KeyPages(about="https://example.com/about", service="https://example.com/services"),
        schema_summary={},
        site_signals=SiteSignals(company_name_detected=True),
    )
    visibility = VisibilityAuditResult(score=50, status="fair", ai_visibility_score=50, brand_authority_score=40)
    technical = TechnicalAuditResult(score=45, status="fair", technical_score=45)
    content = ContentAuditResult(
        score=55,
        status="fair",
        content_score=55,
        experience_score=50,
        expertise_score=60,
        authoritativeness_score=45,
        trustworthiness_score=65,
    )
    schema_result = SchemaAuditResult(score=20, status="critical", structured_data_score=20)
    platform = PlatformAuditResult(
        score=35,
        status="poor",
        platform_optimization_score=35,
        platform_scores={
            "google_ai_overviews": PlatformAuditDetail(platform_score=35, primary_gap="Missing schema"),
        },
    )
    summary = SummaryResult(
        composite_geo_score=42,
        status="poor",
        weighted_scores={
            "AI Citability & Visibility": {"raw_score": 50, "weight": 0.25, "weighted_value": 12.5},
            "Brand Authority Signals": {"raw_score": 40, "weight": 0.20, "weighted_value": 8.0},
            "Content Quality & E-E-A-T": {"raw_score": 55, "weight": 0.20, "weighted_value": 11.0},
            "Technical Foundations": {"raw_score": 45, "weight": 0.15, "weighted_value": 6.75},
            "Structured Data": {"raw_score": 20, "weight": 0.10, "weighted_value": 2.0},
            "Platform Optimization": {"raw_score": 35, "weight": 0.10, "weighted_value": 3.5},
        },
        summary="Example summary",
        top_issues=["technical: Missing sitemap"],
        quick_wins=["Add sitemap.xml"],
    )
    markdown = service.render_markdown(
        url="https://example.com",
        discovery=discovery,
        visibility=visibility,
        technical=technical,
        content=content,
        schema_result=schema_result,
        platform=platform,
        summary=summary,
    )
    for heading in [
        "## Executive Summary",
        "## Score Dashboard",
        "## AI Platform Readiness",
        "## Critical Findings",
        "## Strengths to Build On",
        "## E-E-A-T Assessment",
        "## Technical Audit Summary",
        "## Prioritized Action Plan",
        "## Implementation Roadmap",
        "## Projected Score After Full Implementation",
        "## Appendix: Site Facts",
    ]:
        assert heading in markdown
