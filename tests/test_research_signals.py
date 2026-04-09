import asyncio

from app.models.discovery import (
    BacklinkOverviewResult,
    DiscoveryResult,
    FetchMetadata,
    HomepageExtract,
    KeyPages,
    LlmsResult,
    PageProfile,
    RobotsResult,
    SitemapResult,
    SiteSignals,
)
from app.services.audit.content import ContentService
from app.services.audit.schema import SchemaService
from app.services.audit.technical import TechnicalService


def _base_discovery() -> DiscoveryResult:
    homepage = HomepageExtract(
        title="Example Battery Backup",
        meta_description="Example backup system",
        canonical="https://example.com/backup",
        lang="en",
        viewport="width=device-width, initial-scale=1",
        h1="Example Backup System",
        headings=[
            {"level": "h1", "text": "Example Backup System"},
            {"level": "h2", "text": "How it works"},
            {"level": "h2", "text": "FAQ"},
        ],
        internal_links=[{"url": "https://example.com/specs", "text": "battery backup specifications"}],
        external_links=[{"url": "https://energy.gov/guide", "text": "Department of Energy guide"}],
        json_ld_blocks=[],
        open_graph={"og:title": "Example"},
        twitter_cards={"twitter:title": "Example"},
        word_count=520,
        html_length=6400,
        text_excerpt="Example backup excerpt",
    )
    homepage_profile = PageProfile(
        page_type="homepage",
        final_url="https://example.com/backup",
        title="Example Battery Backup",
        meta_description="Example backup system",
        canonical="https://example.com/backup",
        lang="en",
        headings=homepage.headings,
        word_count=520,
        has_faq=True,
        has_author=True,
        has_publish_date=True,
        has_quantified_data=True,
        has_reference_section=True,
        has_inline_citations=True,
        has_tldr=True,
        has_update_log=True,
        answer_first=True,
        heading_quality_score=92,
        information_density_score=80,
        chunk_structure_score=76,
        internal_link_count=4,
        external_link_count=2,
        descriptive_internal_link_ratio=0.9,
        descriptive_external_link_ratio=1.0,
        json_ld_summary={
            "json_ld_present": True,
            "types": ["Corporation", "FAQPage", "BreadcrumbList", "Article"],
            "has_organization": True,
            "has_local_business": False,
            "has_article": True,
            "has_faq_page": True,
            "has_service": False,
            "has_website": False,
            "has_product": False,
            "has_defined_term": False,
            "has_offer": False,
            "has_breadcrumb_list": True,
            "has_date_published": True,
            "has_date_modified": True,
            "visible_alignment_score": 88,
            "entity_id_count": 2,
            "relation_count": 4,
            "same_as": ["https://linkedin.com/company/example"],
        },
        entity_signals=SiteSignals(company_name_detected=True),
        text_excerpt="Example backup excerpt",
    )
    article_profile = PageProfile(
        page_type="article",
        final_url="https://example.com/blog/grid-outage-guide",
        title="Grid outage guide",
        word_count=980,
        has_author=True,
        has_publish_date=True,
        has_quantified_data=True,
        has_reference_section=True,
        has_inline_citations=True,
        has_tldr=True,
        answer_first=True,
        heading_quality_score=88,
        information_density_score=82,
        chunk_structure_score=78,
        internal_link_count=5,
        external_link_count=3,
        descriptive_internal_link_ratio=0.85,
        descriptive_external_link_ratio=0.9,
        json_ld_summary=homepage_profile.json_ld_summary,
        entity_signals=SiteSignals(),
    )
    return DiscoveryResult(
        url="https://example.com/backup",
        normalized_url="https://example.com/backup",
        final_url="https://example.com/backup",
        site_root_url="https://example.com",
        scope_root_url="https://example.com/",
        domain="example.com",
        fetch=FetchMetadata(
            final_url="https://example.com/backup",
            status_code=200,
            headers={"etag": "abc123", "last-modified": "Tue, 11 Feb 2025 10:00:00 GMT"},
            response_time_ms=220,
        ),
        homepage=homepage,
        robots=RobotsResult(url="https://example.com/robots.txt", exists=True, has_sitemap_directive=True),
        sitemap=SitemapResult(url="https://example.com/sitemap.xml", exists=True),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=True, content_preview="Example", content_length=320),
        business_type="saas",
        key_pages=KeyPages(
            about="https://example.com/about",
            service="https://example.com/service",
            contact="https://example.com/contact",
            article="https://example.com/blog/grid-outage-guide",
        ),
        schema_summary={
            "json_ld_present": True,
            "types": ["Corporation", "FAQPage", "BreadcrumbList", "Article"],
            "has_organization": True,
            "has_local_business": False,
            "has_article": True,
            "has_faq_page": True,
            "has_service": False,
            "has_website": False,
            "has_product": False,
            "has_defined_term": False,
            "has_offer": False,
            "has_breadcrumb_list": True,
            "has_date_published": True,
            "has_date_modified": True,
            "avg_visible_alignment_score": 88,
            "entity_id_count": 2,
            "relation_count": 4,
            "same_as": ["https://linkedin.com/company/example"],
        },
        site_signals=SiteSignals(
            company_name_detected=True,
            phone_detected=True,
            email_detected=True,
            same_as_detected=True,
        ),
        backlinks=BacklinkOverviewResult(available=False),
        page_profiles={"homepage": homepage_profile, "article": article_profile},
    )


def test_content_service_surfaces_evidence_and_link_context_signals() -> None:
    service = ContentService()
    result = asyncio.run(service.audit("https://example.com/backup", _base_discovery()))

    assert result.findings["has_reference_section_any"] is True
    assert result.findings["has_inline_citations_any"] is True
    assert result.findings["average_link_context_score"] >= 70


def test_schema_service_rewards_machine_dates_and_alignment() -> None:
    service = SchemaService()
    result = asyncio.run(service.audit("https://example.com/backup", _base_discovery()))

    assert result.checks["has_date_published"] is True
    assert result.checks["has_date_modified"] is True
    assert result.checks["visible_alignment_score"] >= 60
    assert result.structured_data_score >= 55


def test_technical_service_reports_revalidation_and_unique_h1() -> None:
    service = TechnicalService()
    result = asyncio.run(service.audit("https://example.com/backup", _base_discovery()))

    assert result.checks["unique_h1"] is True
    assert result.checks["revalidation_headers"]["etag"] is True
    assert result.findings["freshness_signal_score"] >= 60
