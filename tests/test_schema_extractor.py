from app.models.discovery import PageProfile, SiteSignals
from app.services.audit.page_diagnostics import PageDiagnosticsService
from app.utils.schema_extractor import extract_schema_summary


def test_extract_schema_summary_treats_corporation_as_organization() -> None:
    summary = extract_schema_summary(
        [
            '{"@context":"https://schema.org","@type":"Corporation","@id":"https://example.com/#org","sameAs":["https://linkedin.com/company/example"]}',
            '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","acceptedAnswer":{"@type":"Answer","text":"A"}}]}',
            '{"@context":"https://schema.org","@type":"BreadcrumbList"}',
        ]
    )

    assert summary["json_ld_present"] is True
    assert summary["has_organization"] is True
    assert summary["has_faq_page"] is True
    assert summary["same_as"] == ["https://linkedin.com/company/example"]
    assert "Corporation" in summary["types"]


def test_extract_schema_summary_captures_machine_dates_and_visible_alignment() -> None:
    summary = extract_schema_summary(
        [
            '{"@context":"https://schema.org","@type":"Article","headline":"Battery backup overview","datePublished":"2025-01-10","dateModified":"2025-02-11","description":"Battery backup overview"}'
        ],
        visible_text="Battery backup overview. Last updated 2025-02-11.",
    )

    assert summary["has_article"] is True
    assert summary["has_date_published"] is True
    assert summary["has_date_modified"] is True
    assert summary["visible_alignment_score"] >= 60


def test_extract_schema_summary_normalizes_type_urls_and_ignores_invalid_blocks() -> None:
    summary = extract_schema_summary(
        [
            'not-json',
            '{"@context":"https://schema.org","@type":["https://schema.org/ProductModel","http://schema.org/Offer"]}',
        ]
    )

    assert summary["json_ld_present"] is True
    assert summary["has_product"] is True
    assert summary["has_offer"] is True
    assert summary["types"] == ["Offer", "ProductModel"]


def test_page_diagnostics_schema_score_rewards_organization_subtypes() -> None:
    service = PageDiagnosticsService()
    profile = PageProfile(
        page_type="product",
        final_url="https://example.com/e10",
        json_ld_summary={
            "json_ld_present": True,
            "has_organization": True,
            "has_service": False,
            "has_article": False,
            "has_faq_page": True,
            "has_product": False,
            "has_defined_term": False,
            "same_as": ["https://linkedin.com/company/example"],
        },
        entity_signals=SiteSignals(),
    )

    assert service._schema_score(profile) == 53


def test_page_diagnostics_returns_full_issue_lists_with_category_details() -> None:
    service = PageDiagnosticsService()
    profile = PageProfile(
        page_type="article",
        final_url="https://example.com/research",
        word_count=120,
        headings=[],
        has_quantified_data=True,
        has_reference_section=False,
        has_inline_citations=False,
        has_tldr=False,
        has_publish_date=False,
        has_author=False,
        descriptive_internal_link_ratio=0.0,
        descriptive_external_link_ratio=0.0,
        title=None,
        meta_description=None,
        canonical=None,
        html_lang=None,
        json_ld_summary={"json_ld_present": True, "visible_alignment_score": 0},
        entity_signals=SiteSignals(),
    )

    result = service._diagnose_page("article", profile, source="core")

    assert result.issue_count == len(result.issues)
    assert len(result.issues) > 5
    assert "evidence" in result.issue_details
    assert "schema" in result.issue_details
    assert "freshness" in result.issue_details
    assert "citability" in result.recommendation_details
