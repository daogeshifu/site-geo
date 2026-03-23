from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HeadingItem(BaseModel):
    level: str
    text: str


class LinkItem(BaseModel):
    url: str
    text: str | None = None


class ImageItem(BaseModel):
    src: str
    alt: str | None = None
    loading: str | None = None
    width: str | None = None
    height: str | None = None


class ScriptItem(BaseModel):
    src: str | None = None
    is_inline: bool = False
    async_attr: bool = False
    defer_attr: bool = False
    type: str | None = None


class StylesheetItem(BaseModel):
    href: str
    media: str | None = None


class FetchMetadata(BaseModel):
    final_url: str
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    response_time_ms: int


class HomepageExtract(BaseModel):
    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    lang: str | None = None
    viewport: str | None = None
    h1: str | None = None
    headings: list[HeadingItem] = Field(default_factory=list)
    hreflang: list[str] = Field(default_factory=list)
    internal_links: list[LinkItem] = Field(default_factory=list)
    external_links: list[LinkItem] = Field(default_factory=list)
    images: list[ImageItem] = Field(default_factory=list)
    scripts: list[ScriptItem] = Field(default_factory=list)
    stylesheets: list[StylesheetItem] = Field(default_factory=list)
    json_ld_blocks: list[str] = Field(default_factory=list)
    open_graph: dict[str, str] = Field(default_factory=dict)
    twitter_cards: dict[str, str] = Field(default_factory=dict)
    word_count: int = 0
    html_length: int = 0
    text_excerpt: str = ""


class RobotsUserAgentRule(BaseModel):
    allowed: bool = True
    matched_user_agent: str = "*"


class RobotsResult(BaseModel):
    url: str
    exists: bool
    status_code: int | None = None
    allows_all: bool = True
    has_sitemap_directive: bool = False
    sitemaps: list[str] = Field(default_factory=list)
    user_agents: dict[str, RobotsUserAgentRule] = Field(default_factory=dict)
    raw_preview: str = ""


class SitemapResult(BaseModel):
    url: str | None = None
    exists: bool = False
    status_code: int | None = None
    discovered_urls: list[str] = Field(default_factory=list)
    total_urls_sampled: int = 0


class LlmsResult(BaseModel):
    url: str
    exists: bool
    status_code: int | None = None
    content_preview: str = ""
    content_length: int = 0
    effectiveness_score: int = 0
    signals: dict[str, bool] = Field(default_factory=dict)


class BacklinkOverviewResult(BaseModel):
    provider: str = "semrush"
    available: bool = False
    source: str | None = None
    target: str | None = None
    target_type: str = "root_domain"
    authority_score: int | None = None
    backlinks_num: int | None = None
    referring_domains: int | None = None
    referring_ips: int | None = None
    referring_ip_classes: int | None = None
    follow_ratio: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class SiteSignals(BaseModel):
    company_name_detected: bool = False
    address_detected: bool = False
    phone_detected: bool = False
    email_detected: bool = False
    awards_detected: bool = False
    certifications_detected: bool = False
    same_as_detected: bool = False
    detected_company_name: str | None = None
    homepage_brand_mentions: int = 0


class KeyPages(BaseModel):
    about: str | None = None
    service: str | None = None
    contact: str | None = None
    article: str | None = None
    case_study: str | None = None


class DiscoveryResult(BaseModel):
    url: str
    normalized_url: str
    final_url: str
    domain: str
    fetch: FetchMetadata
    homepage: HomepageExtract
    robots: RobotsResult
    sitemap: SitemapResult
    llms: LlmsResult
    business_type: str
    key_pages: KeyPages
    schema_summary: dict[str, Any] = Field(default_factory=dict)
    site_signals: SiteSignals = Field(default_factory=SiteSignals)
    backlinks: BacklinkOverviewResult = Field(default_factory=BacklinkOverviewResult)
