from app.models.audit import (
    ContentPageAnalysis,
    PageContentAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.services.page_content_audit_service import PageContentAuditService


def test_page_content_summary_uses_skill_breakdown() -> None:
    discovery = DiscoveryResult.model_validate(
        {
            "url": "https://example.com/blog/post",
            "normalized_url": "https://example.com/blog/post",
            "final_url": "https://example.com/blog/post",
            "site_root_url": "https://example.com",
            "scope_root_url": "https://example.com",
            "domain": "example.com",
            "fetch": {
                "final_url": "https://example.com/blog/post",
                "status_code": 200,
                "headers": {"content-type": "text/html"},
                "response_time_ms": 180,
            },
            "homepage": {
                "title": "Example blog post",
                "meta_description": "Example description",
                "canonical": "https://example.com/blog/post",
                "lang": "en",
                "viewport": "width=device-width, initial-scale=1",
                "h1": "Example blog post",
                "headings": [{"level": "h1", "text": "Example blog post"}],
                "hreflang": [],
                "internal_links": [],
                "external_links": [],
                "images": [],
                "scripts": [],
                "stylesheets": [],
                "json_ld_blocks": [],
                "open_graph": {},
                "twitter_cards": {},
                "word_count": 900,
                "html_length": 6000,
                "text_excerpt": "Example excerpt",
            },
            "robots": {"url": "https://example.com/robots.txt", "exists": True},
            "sitemap": {"exists": True, "discovered_urls": [], "total_urls_sampled": 0},
            "llms": {"url": "https://example.com/llms.txt", "exists": False},
            "business_type": "media",
            "key_pages": {},
        }
    )
    content_result = PageContentAuditResult(
        score=76,
        status="good",
        module_key="content",
        page_content_score=74,
        geo_readiness_score=78,
        on_page_seo_score=72,
        schema_support_score=70,
        experience_score=71,
        expertise_score=77,
        authoritativeness_score=73,
        trustworthiness_score=75,
        findings={"llm_summary": "Strong page with a few citation gaps."},
        issues=["Missing FAQ schema", "Add more source citations"],
        strengths=["Answer-first opening detected"],
        recommendations=["Add FAQPage schema", "Add inline citations"],
        checks={},
        geo_factors={"clear_definitions": 80, "source_citations": 45},
        on_page_checks={},
        schema_checks={},
        target_page=ContentPageAnalysis(
            url="https://example.com/blog/post",
            page_type="article",
            title="Example blog post",
            word_count=900,
        ),
        core_checks=[],
        skill_lenses=[],
    )

    summary = PageContentAuditService().summarize(discovery, content_result, feedback_lang="en")

    assert summary.overall_score == 76
    assert summary.summary == "Strong page with a few citation gaps."
    assert summary.applied_skills == ["geo-content-optimizer", "on-page-seo-auditor"]
    assert summary.score_breakdown["page_content_score"] == 74
    assert summary.top_issues == ["Missing FAQ schema", "Add more source citations"]
    assert summary.quick_wins == ["Add FAQPage schema", "Add inline citations"]
