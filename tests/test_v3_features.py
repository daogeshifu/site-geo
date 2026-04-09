import asyncio

from app.core.exceptions import AppError
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
from app.services.reporting.report import ReportService
from app.services.infra.cache import CacheService
from app.services.discovery.discovery import DiscoveryService
from app.services.audit.summarizer import SummarizerService
from app.utils.fetcher import FetchedResponse
from app.utils.url_utils import entry_url_candidates, get_scope_root, is_internal_url, is_likely_homepage_url
from app.utils.localization import localize_payload


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


def test_entry_url_candidates_cover_www_and_http_variants() -> None:
    assert entry_url_candidates("idtcpack.com") == [
        "https://idtcpack.com/",
        "https://www.idtcpack.com/",
        "http://idtcpack.com/",
        "http://www.idtcpack.com/",
    ]
    assert entry_url_candidates("https://idtcpack.com") == [
        "https://idtcpack.com/",
        "https://www.idtcpack.com/",
        "http://idtcpack.com/",
        "http://www.idtcpack.com/",
    ]


def test_cache_key_changes_with_scope() -> None:
    service = CacheService(cache_dir=".cache/test-audits", ttl_days=7)
    de_path_key, _, _ = service.build_cache_key("https://www.ecoflow.com/de/", "standard", None)
    fr_path_key, _, _ = service.build_cache_key("https://www.ecoflow.com/fr/", "standard", None)
    de_subdomain_key, _, _ = service.build_cache_key("https://de.ecoflow.com/", "standard", None)

    assert de_path_key != fr_path_key
    assert de_path_key != de_subdomain_key


def test_localize_payload_translates_known_messages_to_zh() -> None:
    payload = {
        "issues": ["robots.txt blocks one or more major AI crawlers."],
        "recommendations": ["Add FAQ sections to commercial pages and high-intent landing pages."],
    }
    localized = localize_payload(payload, "zh")
    assert localized["issues"][0] == "robots.txt 阻止了一个或多个主要 AI 爬虫。"
    assert localized["recommendations"][0] == "在商业页和高意向落地页增加 FAQ 模块。"


def test_localize_payload_translates_schema_requirements_and_observation_text() -> None:
    payload = {
        "schema": {
            "missing_schema_recommendations": [
                "Add Organization schema with name, url, logo, contactPoint, and sameAs.",
                "Add WebSite schema with SearchAction where relevant.",
                "Model proprietary technologies or frameworks with DefinedTerm and stable @id values.",
            ]
        },
        "observation": {
            "summary": "Optional observation data is available and classified as advanced measurement maturity.",
            "highlights": [
                "Observed 123 AI-attributed sessions in the uploaded data.",
                "Top observed AI source: ChatGPT (88 sessions).",
            ],
            "data_gaps": [
                "GA4 AI traffic totals were not provided.",
                "No citation observation samples were provided.",
            ],
        },
    }
    localized = localize_payload(payload, "zh")
    assert localized["schema"]["missing_schema_recommendations"][0] == "添加 Organization Schema，并包含 name、url、logo、contactPoint 和 sameAs。"
    assert localized["schema"]["missing_schema_recommendations"][1] == "在适用场景下添加带 SearchAction 的 WebSite Schema。"
    assert localized["schema"]["missing_schema_recommendations"][2] == "使用 DefinedTerm 和稳定的 @id 来描述自有技术、方法论或框架。"
    assert localized["observation"]["summary"] == "已提供可选 observation 数据，当前 measurement maturity 为 advanced。"
    assert localized["observation"]["highlights"][0] == "上传数据中观测到 123 个 AI 归因 sessions。"
    assert localized["observation"]["highlights"][1] == "观测到的首要 AI 来源：ChatGPT（88 个 sessions）。"
    assert localized["observation"]["data_gaps"][0] == "未提供 GA4 AI 流量总量。"
    assert localized["observation"]["data_gaps"][1] == "未提供引用观测样本。"


def test_discovery_entry_fetch_falls_back_to_www_variant(monkeypatch) -> None:
    service = DiscoveryService()
    attempted_urls: list[str] = []

    async def fake_fetch_url(url: str, client=None, method: str = "GET") -> FetchedResponse:
        attempted_urls.append(url)
        if url == "https://idtcpack.com/":
            raise AppError(502, "fetch failed", "tls mismatch")
        if url == "https://www.idtcpack.com/":
            return FetchedResponse(
                final_url="https://www.idtcpack.com/",
                status_code=200,
                headers={},
                text="<html></html>",
                response_time_ms=42,
            )
        raise AssertionError(f"Unexpected candidate URL: {url}")

    monkeypatch.setattr("app.services.discovery.discovery.fetch_url", fake_fetch_url)

    response = asyncio.run(service._fetch_entry_response(client=None, url="https://idtcpack.com"))
    assert response.final_url == "https://www.idtcpack.com/"
    assert attempted_urls == ["https://idtcpack.com/", "https://www.idtcpack.com/"]


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


def test_summarizer_uses_english_dimension_keys() -> None:
    service = SummarizerService()
    discovery = DiscoveryResult(
        url="https://example.com/",
        normalized_url="https://example.com/",
        final_url="https://example.com/",
        site_root_url="https://example.com",
        scope_root_url="https://example.com/",
        domain="example.com",
        fetch=FetchMetadata(final_url="https://example.com/", status_code=200, headers={}, response_time_ms=120),
        homepage=HomepageExtract(title="Example", lang="en"),
        robots=RobotsResult(url="https://example.com/robots.txt", exists=True),
        sitemap=SitemapResult(url="https://example.com/sitemap.xml", exists=True),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False),
        business_type="saas",
        key_pages=KeyPages(),
        schema_summary={},
        site_signals=SiteSignals(),
    )
    summary = asyncio.run(
        service.summarize(
            url="https://example.com/",
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
            schema=SchemaAuditResult(score=60, status="fair", structured_data_score=60),
            platform=PlatformAuditResult(score=60, status="fair", platform_optimization_score=60, platform_scores={}),
            feedback_lang="zh",
        )
    )
    assert "AI Citability & Visibility" in summary.dimensions
    assert summary.dimensions["AI Citability & Visibility"]["display_name"] == "AI 可见性"
    assert summary.metric_definitions[0].name == "AI Citability & Visibility"

    localized = localize_payload(summary.model_dump(), "zh")
    assert "AI Citability & Visibility" in localized["dimensions"]
    assert localized["dimensions"]["AI Citability & Visibility"]["display_name"] == "AI 可见性"
    assert localized["metric_definitions"][0]["name"] == "AI 可见性"
    assert localized["metric_definitions"][-1]["name"] == "观测层"
    assert localized["metric_definitions"][0]["formula"] == "爬虫可达性 + 可引用结构 + llms 指引 + 基础实体存在"
