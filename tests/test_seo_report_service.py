from app.models.audit import (
    SeoAuditResult,
    SeoCheckResult,
    SeoDimensionResult,
    SeoIssueResult,
    SeoRoadmapItem,
    SeoSamplePageResult,
    SeoSummaryResult,
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
from app.services.reporting.seo_report import SeoReportService


def test_seo_report_contains_core_sections() -> None:
    service = SeoReportService()
    discovery = DiscoveryResult(
        url="https://example.com",
        normalized_url="https://example.com/",
        final_url="https://example.com/",
        site_root_url="https://example.com",
        scope_root_url="https://example.com",
        domain="example.com",
        fetch=FetchMetadata(final_url="https://example.com/", status_code=200, headers={}, response_time_ms=120),
        homepage=HomepageExtract(title="Example", meta_description="Example desc", lang="en"),
        robots=RobotsResult(url="https://example.com/robots.txt", exists=True),
        sitemap=SitemapResult(url="https://example.com/sitemap.xml", exists=True, discovered_urls=["https://example.com/"]),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False),
        business_type="agency",
        key_pages=KeyPages(service="https://example.com/services"),
        schema_summary={},
        site_signals=SiteSignals(company_name_detected=True),
    )
    seo = SeoAuditResult(
        score=78,
        overall_score=78,
        status="good",
        dimensions={
            "technical": SeoDimensionResult(key="technical", label="Technical SEO", weight=0.22, score=80, status="good"),
            "content_quality": SeoDimensionResult(key="content_quality", label="Content Quality", weight=0.23, score=74, status="good"),
        },
        weighted_scores={
            "technical": {"raw_score": 80, "raw_weight": 0.22, "weighted_value": 18.53},
            "content_quality": {"raw_score": 74, "raw_weight": 0.23, "weighted_value": 17.92},
        },
        coverage_checks=[
            SeoCheckResult(id="CHK-001", category="Technical SEO", check="robots", status="pass", summary="ok", evidence="robots.txt"),
            SeoCheckResult(id="CHK-002", category="On-Page SEO", check="title", status="fail", summary="missing title", evidence="homepage"),
        ],
        issues_table=[
            SeoIssueResult(
                issue_id="P-001",
                priority="P0",
                severity="critical",
                category="Technical SEO",
                scope="sitewide",
                description="Canonical mismatch",
                recommendation="Fix canonical",
            )
        ],
        roadmap=[
            SeoRoadmapItem(
                phase="0-30",
                priority="P0",
                task="Fix canonical",
                related_issue_ids=["P-001"],
                acceptance_criteria="Canonical is self-referencing",
            )
        ],
        sampled_pages=[
            SeoSamplePageResult(
                url="https://example.com/",
                page_type="homepage",
                status_code=200,
                final_url="https://example.com/",
                title="Example",
                title_length=7,
                meta_description="Example desc",
                meta_description_length=12,
                h1_count=1,
                alt_coverage_ratio=1.0,
            )
        ],
        coverage_summary={"total_checks": 2, "passed_checks": 1, "failed_checks": 1, "na_checks": 0},
        measurements={"sampled_url_count": 1},
        supporting_scores={"technical_score": 80},
        findings={"top_issues": ["Canonical mismatch"]},
        issues=["Canonical mismatch"],
        recommendations=["Fix canonical"],
    )
    summary = SeoSummaryResult(
        overall_score=78,
        status="good",
        summary="Example SEO summary",
        top_issues=["Canonical mismatch"],
        quick_wins=["Fix canonical"],
        coverage_summary={"total_checks": 2, "failed_checks": 1},
    )

    markdown = service.render_markdown(
        url="https://example.com",
        discovery=discovery,
        seo=seo,
        summary=summary,
    )

    for heading in [
        "# Google SEO Audit Report: example.com",
        "## Executive Summary",
        "## Score Dashboard",
        "## Coverage Checklist",
        "## Issue Backlog",
        "## Dimension Analysis",
        "## Sampled Pages",
        "## 30-60-90 Roadmap",
    ]:
        assert heading in markdown
