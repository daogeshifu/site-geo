from app.models.discovery import BacklinkOverviewResult, KeyPages, LlmsResult, SiteSignals
from app.services.discovery.backlinks import BacklinkService
from app.utils.heuristics import assess_llms_effectiveness, calculate_brand_authority


def test_backlink_service_parses_semrush_csv_payload() -> None:
    service = BacklinkService()
    payload = service._parse_payload(
        "ascore;backlinks_num;domains_num;ips_num;ipclass_c_num;follows_num;nofollows_num\n"
        "42;1200;88;66;40;720;480\n"
    )
    assert payload["ascore"] == "42"
    assert payload["domains_num"] == "88"


def test_llms_effectiveness_rewards_brand_and_guidance() -> None:
    llms = LlmsResult(
        url="https://example.com/llms.txt",
        exists=True,
        status_code=200,
        content_preview="# Example Co\n## Services\nWe provide SEO services.\nPreferred citation: canonical URL.\nContact support@example.com",
        content_length=420,
    )
    quality = assess_llms_effectiveness(llms, company_name="Example Co", business_type="agency")
    assert quality["score"] >= 80
    assert quality["signals"]["mentions_brand"] is True
    assert quality["signals"]["includes_guidance"] is True


def test_brand_authority_renormalizes_when_backlinks_are_unavailable() -> None:
    score = calculate_brand_authority(
        signals=SiteSignals(
            company_name_detected=True,
            phone_detected=True,
            email_detected=True,
            same_as_detected=True,
            detected_company_name="Example Co",
            homepage_brand_mentions=3,
        ),
        homepage={
            "title": "Example Co | GEO Services",
            "meta_description": "Example Co helps brands grow.",
            "h1": "Example Co GEO Services",
        },
        llms=LlmsResult(
            url="https://example.com/llms.txt",
            exists=True,
            content_preview="Example Co services and citation guidance",
            content_length=300,
        ),
        key_pages=KeyPages(about="https://example.com/about", contact="https://example.com/contact"),
        schema_summary={"same_as": ["https://linkedin.com/company/example"], "has_organization": True},
        primary_domain="example.com",
        sitemap_urls=["https://example.com/sitemap.xml"],
        backlinks=BacklinkOverviewResult(available=False, error="Semrush API key not configured."),
    )
    assert score["score"] >= 60
    assert score["components"]["backlink_quality"]["score"] is None
