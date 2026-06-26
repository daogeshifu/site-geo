from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.models.audit import (
    ActionPlanItem,
    SeoAuditResult,
    SeoCheckResult,
    SeoDimensionResult,
    SeoIssueResult,
    SeoRoadmapItem,
    SeoSamplePageResult,
    SeoSummaryResult,
)
from app.models.requests import LLMConfig
from app.services.audit.base import AuditBaseService
from app.services.audit.content import ContentService
from app.services.audit.schema import SchemaService
from app.services.audit.scoring import ScoringService
from app.services.audit.technical import TechnicalService
from app.services.audit.visibility import VisibilityService
from app.utils.fetcher import fetch_url
from app.utils.html_parser import parse_html
from app.utils.url_utils import normalize_url


class SeoAuditService(AuditBaseService):
    """Google SEO audit service built on top of the shared discovery snapshot."""

    RAW_WEIGHTS = {
        "technical": 0.22,
        "content_quality": 0.23,
        "on_page": 0.20,
        "schema": 0.10,
        "performance": 0.10,
        "ai_search": 0.10,
    }

    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()
        self.technical_service = TechnicalService(self.discovery_service)
        self.content_service = ContentService(self.discovery_service)
        self.schema_service = SchemaService(self.discovery_service)
        self.visibility_service = VisibilityService(self.discovery_service)

    def _t(self, feedback_lang: str, zh_text: str, en_text: str) -> str:
        return zh_text if feedback_lang == "zh" else en_text

    def _weight_total(self) -> float:
        return sum(self.RAW_WEIGHTS.values()) or 1.0

    def _weighted_score(self, scores: dict[str, int]) -> tuple[int, dict[str, Any]]:
        total_weight = self._weight_total()
        weighted_scores: dict[str, Any] = {}
        total = 0.0
        for key, raw_weight in self.RAW_WEIGHTS.items():
            raw_score = self.scoring.clamp_score(scores.get(key, 0))
            normalized_weight = raw_weight / total_weight
            weighted_value = round(raw_score * normalized_weight, 2)
            total += weighted_value
            weighted_scores[key] = {
                "raw_score": raw_score,
                "raw_weight": raw_weight,
                "normalized_weight": round(normalized_weight, 4),
                "weighted_value": weighted_value,
            }
        return self.scoring.clamp_score(total), weighted_scores

    def _sample_urls(self, discovery, max_pages: int) -> list[tuple[str, str]]:
        seen: set[str] = set()
        sampled: list[tuple[str, str]] = []

        def add(page_type: str, url: str | None) -> None:
            if not url:
                return
            normalized = normalize_url(url)
            if normalized in seen:
                return
            seen.add(normalized)
            sampled.append((page_type, normalized))

        for page_type, profile in discovery.page_profiles.items():
            add(page_type, profile.final_url)
        for profile in discovery.additional_page_profiles:
            add(profile.page_type or "page", profile.final_url)
        for url in discovery.sitemap.discovered_urls[:max_pages]:
            add("sitemap", url)
        return sampled[:max_pages]

    def _extract_meta_robots(self, soup: BeautifulSoup) -> str:
        values = []
        for tag in soup.find_all("meta", attrs={"name": re.compile(r"^robots$", re.I)}):
            content = (tag.get("content") or "").strip()
            if content:
                values.append(content.lower())
        return ", ".join(values)

    def _detect_analytics(self, soup: BeautifulSoup, html: str) -> dict[str, bool]:
        lowered = (html or "").lower()
        has_ga4 = (
            "googletagmanager.com/gtag/js" in lowered
            or "gtag(" in lowered
            or bool(re.search(r"\bG-[A-Z0-9]{4,}\b", html or ""))
        )
        has_gtm = "googletagmanager.com/gtm.js" in lowered or bool(re.search(r"\bGTM-[A-Z0-9]{4,}\b", html or ""))
        has_gsc_verification = bool(
            soup.find("meta", attrs={"name": re.compile(r"^google-site-verification$", re.I)})
        )
        return {
            "ga4": has_ga4,
            "gtm": has_gtm,
            "gsc_verification": has_gsc_verification,
        }

    def _nofollow_internal_links(self, soup: BeautifulSoup, base_url: str) -> int:
        host = urlparse(base_url).netloc
        count = 0
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href:
                continue
            absolute = href if href.startswith("http") else ""
            if absolute and urlparse(absolute).netloc and urlparse(absolute).netloc != host:
                continue
            rel_values = [item.lower() for item in (link.get("rel") or [])]
            if "nofollow" in rel_values:
                count += 1
        return count

    async def _fetch_sample_pages(self, discovery, *, max_pages: int) -> list[SeoSamplePageResult]:
        sampled = self._sample_urls(discovery, max_pages)
        if not sampled:
            return []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        ) as client:
            async def worker(page_type: str, url: str) -> SeoSamplePageResult | None:
                try:
                    response = await fetch_url(url, client=client)
                except Exception:
                    return None
                parsed = parse_html(response.final_url, response.text, scope_url=discovery.scope_root_url)
                soup = BeautifulSoup(response.text or "", "lxml")
                meta_robots = self._extract_meta_robots(soup)
                noindex_detected = "noindex" in meta_robots or "noindex" in (
                    response.headers.get("x-robots-tag", "").lower()
                )
                images = parsed["images"]
                image_count = len(images)
                alt_count = sum(1 for image in images if (image.get("alt") or "").strip())
                lazy_count = sum(1 for image in images if (image.get("loading") or "").lower() == "lazy")
                h1_count = sum(1 for heading in parsed["headings"] if heading["level"] == "h1")
                return SeoSamplePageResult(
                    url=url,
                    page_type=page_type,
                    status_code=response.status_code,
                    final_url=response.final_url,
                    redirected=normalize_url(response.final_url) != normalize_url(url),
                    title=parsed["title"],
                    title_length=len(parsed["title"] or ""),
                    meta_description=parsed["meta_description"],
                    meta_description_length=len(parsed["meta_description"] or ""),
                    canonical=parsed["canonical"],
                    lang=parsed["lang"],
                    viewport_present=bool(parsed["viewport"]),
                    h1_count=h1_count,
                    word_count=parsed["word_count"],
                    html_length=parsed["html_length"],
                    image_count=image_count,
                    alt_coverage_ratio=round((alt_count / image_count), 2) if image_count else 1.0,
                    lazyload_ratio=round((lazy_count / image_count), 2) if image_count else 1.0,
                    noindex_detected=noindex_detected,
                    nofollow_internal_links=self._nofollow_internal_links(soup, response.final_url),
                    open_graph_present=bool(parsed["open_graph"]),
                    twitter_card_present=bool(parsed["twitter_cards"]),
                )

            results = await asyncio.gather(
                *(worker(page_type, url) for page_type, url in sampled),
                return_exceptions=True,
            )
        return [item for item in results if isinstance(item, SeoSamplePageResult)]

    async def _probe_variants(self, final_url: str) -> dict[str, bool]:
        parsed = urlparse(final_url)
        host = parsed.netloc
        scheme = parsed.scheme or "https"
        bare_host = host[4:] if host.startswith("www.") else host
        www_host = host if host.startswith("www.") else f"www.{host}"
        preferred_host = host
        candidates = {
            "http_to_https": f"http://{preferred_host}/",
            "non_www_to_preferred": f"{scheme}://{bare_host}/",
            "www_to_preferred": f"{scheme}://{www_host}/",
        }
        results = {key: True for key in candidates}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        ) as client:
            for key, candidate in candidates.items():
                try:
                    response = await fetch_url(candidate, client=client)
                except Exception:
                    results[key] = False
                    continue
                normalized_final = normalize_url(response.final_url)
                results[key] = normalized_final.startswith(normalize_url(f"{scheme}://{preferred_host}/"))
        return results

    def _build_checks(
        self,
        *,
        feedback_lang: str,
        discovery,
        technical,
        content,
        schema_result,
        visibility,
        samples: list[SeoSamplePageResult],
        homepage_analytics: dict[str, bool],
        variant_results: dict[str, bool],
    ) -> list[dict[str, Any]]:
        sample_count = len(samples) or 1
        error_pages = [page for page in samples if page.status_code >= 400]
        redirected_pages = [page for page in samples if page.redirected]
        canonical_mismatches = [
            page for page in samples
            if page.canonical and normalize_url(page.canonical) != normalize_url(page.final_url)
        ]
        missing_titles = [page for page in samples if not page.title]
        title_length_issues = [page for page in samples if page.title and not 45 <= page.title_length <= 65]
        missing_meta = [page for page in samples if not page.meta_description]
        meta_length_issues = [page for page in samples if page.meta_description and not 80 <= page.meta_description_length <= 170]
        heading_issues = [page for page in samples if page.h1_count != 1]
        lang_issues = [page for page in samples if not page.lang]
        alt_issues = [page for page in samples if page.alt_coverage_ratio < 0.8]
        noindex_pages = [page for page in samples if page.noindex_detected]
        oversized_html = [page for page in samples if page.html_length > 250000]
        internal_nofollow = [page for page in samples if page.nofollow_internal_links > 0]
        url_structure_issues = [
            page for page in samples
            if any(token in page.url for token in ["?", "_"]) or page.url.lower() != page.url or len(page.url) > 110
        ]
        hreflang_applicable = bool(discovery.homepage.hreflang or discovery.requested_target_locale)
        sitemap_https_ok = bool(discovery.sitemap.discovered_urls) and all(
            item.startswith("https://") for item in discovery.sitemap.discovered_urls[: min(50, len(discovery.sitemap.discovered_urls))]
        )
        sitemap_clean = all(
            "?" not in item and "#" not in item and item.lower() == item
            for item in discovery.sitemap.discovered_urls[: min(50, len(discovery.sitemap.discovered_urls))]
        ) if discovery.sitemap.discovered_urls else False
        checks = [
            {
                "id": "CHK-001",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "robots.txt 配置正确并声明本站 sitemap", "robots.txt is valid and points to the site sitemap"),
                "passed": discovery.robots.exists and discovery.robots.has_sitemap_directive,
                "summary": self._t(feedback_lang, "robots.txt 存在且包含 Sitemap 指令。", "robots.txt exists and exposes a Sitemap directive."),
                "failure": self._t(feedback_lang, "robots.txt 缺失或未声明 sitemap。", "robots.txt is missing or does not declare the sitemap."),
                "evidence": discovery.robots.url,
                "impact": self._t(feedback_lang, "影响抓取入口与站点规范发现。", "Impacts crawler discovery and crawl governance."),
                "severity": "high",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "补齐 robots.txt 并声明首选 sitemap URL。", "Publish robots.txt and include the preferred sitemap URL."),
                "effort": self._t(feedback_lang, "1-2 hours", "1-2 hours"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-002",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "XML Sitemap 存在、全 HTTPS、无脏数据", "XML sitemap exists, uses HTTPS, and stays clean"),
                "passed": discovery.sitemap.exists and sitemap_https_ok and sitemap_clean,
                "summary": self._t(feedback_lang, "sitemap 已覆盖核心页面，URL 协议与格式基本一致。", "The sitemap covers core URLs with clean HTTPS entries."),
                "failure": self._t(feedback_lang, "sitemap 缺失、存在非 HTTPS URL，或带参数/大小写脏数据。", "The sitemap is missing, contains non-HTTPS URLs, or includes dirty parameterized entries."),
                "evidence": discovery.sitemap.url or discovery.robots.url,
                "impact": self._t(feedback_lang, "可能导致抓取、规范化和收录信号混乱。", "Can confuse crawling, canonicalization, and indexing signals."),
                "severity": "high",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "清理 sitemap，统一为首选 HTTPS 规范 URL，并移除参数页。", "Clean the sitemap, keep only preferred HTTPS canonicals, and remove parameterized URLs."),
                "effort": self._t(feedback_lang, "2-4 hours", "2-4 hours"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-003",
                "category": "Measurement",
                "check": self._t(feedback_lang, "GA4 / GSC 部署可识别", "GA4 / GSC deployment is detectable"),
                "passed": homepage_analytics["ga4"] and homepage_analytics["gsc_verification"],
                "summary": self._t(feedback_lang, "首页可识别到 GA4 与 GSC 验证信号。", "Homepage shows detectable GA4 and GSC verification signals."),
                "failure": self._t(feedback_lang, "未同时识别到 GA4 与 GSC 验证信号。", "GA4 and GSC verification were not both detected."),
                "evidence": self._t(feedback_lang, "Homepage HTML scripts/meta", "Homepage HTML scripts/meta"),
                "impact": self._t(feedback_lang, "影响测量闭环与后续 SEO 追踪。", "Weakens measurement coverage and ongoing SEO validation."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "补齐 GA4 与 GSC 验证，并确认转化事件映射。", "Install GA4 and GSC verification and confirm conversion event mapping."),
                "effort": self._t(feedback_lang, "1-3 hours", "1-3 hours"),
                "difficulty": "low",
                "owner": "Marketing Ops",
            },
            {
                "id": "CHK-004",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "HTTPS 全站启用，HTTP 自动 301 到 HTTPS", "HTTPS is enforced with HTTP redirected to HTTPS"),
                "passed": technical.checks.get("https") and variant_results.get("http_to_https", False),
                "summary": self._t(feedback_lang, "站点已使用 HTTPS 并对 HTTP 变体做统一跳转。", "The site enforces HTTPS and normalizes HTTP variants."),
                "failure": self._t(feedback_lang, "HTTPS 未完全统一，或 HTTP 变体未可靠跳转。", "HTTPS is not fully normalized or HTTP variants do not redirect reliably."),
                "evidence": discovery.final_url,
                "impact": self._t(feedback_lang, "削弱规范化与用户信任，可能造成重复 URL。", "Can fragment canonical signals and reduce user trust."),
                "severity": "critical",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "配置 301 到首选 HTTPS 主域，并同步 canonical / sitemap。", "301 redirect all variants to the preferred HTTPS host and align canonical/sitemap signals."),
                "effort": self._t(feedback_lang, "2-6 hours", "2-6 hours"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-005",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "www / 非 www 统一到首选域", "www / non-www variants resolve to the preferred host"),
                "passed": variant_results.get("non_www_to_preferred", False) and variant_results.get("www_to_preferred", False),
                "summary": self._t(feedback_lang, "主域变体已统一到首选 hostname。", "Host variants resolve to the preferred hostname."),
                "failure": self._t(feedback_lang, "www 与非 www 之间仍存在分裂或重定向不稳定。", "www and non-www variants are still split or unstable."),
                "evidence": discovery.site_root_url,
                "impact": self._t(feedback_lang, "可能造成链路权重分散与收录重复。", "Can split link equity and create duplicate indexing signals."),
                "severity": "high",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "将所有 host 变体 301 到首选主域。", "301 redirect every hostname variant to the preferred host."),
                "effort": self._t(feedback_lang, "1-3 hours", "1-3 hours"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-006",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "URL 结构简短、语义化、小写、无冗余参数", "URL structure is short, semantic, lowercase, and clean"),
                "passed": not url_structure_issues,
                "summary": self._t(feedback_lang, "采样 URL 结构整体可读且规整。", "Sampled URLs are readable and consistently structured."),
                "failure": self._t(feedback_lang, "采样 URL 存在参数、下划线、大写或过长问题。", "Sampled URLs include parameters, underscores, uppercase characters, or overly long paths."),
                "evidence": ", ".join(page.url for page in url_structure_issues[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响可读性、规范化和主题聚合。", "Hurts readability, canonicalization, and topical clustering."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "统一 URL 命名规范，压缩路径层级并避免参数收录。", "Standardize URL naming, shorten deep paths, and avoid indexable parameter URLs."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "medium",
                "owner": "SEO + Engineering",
            },
            {
                "id": "CHK-007",
                "category": "Schema",
                "check": self._t(feedback_lang, "页面类型对应的 Schema 已部署", "Page-type schema coverage is in place"),
                "passed": schema_result.structured_data_score >= 70,
                "summary": self._t(feedback_lang, "结构化数据覆盖与实体信号基础较完整。", "Structured data coverage and entity signals are broadly in place."),
                "failure": self._t(feedback_lang, "Schema 覆盖偏弱，缺少关键页型标记或 sameAs/@id 支撑。", "Schema coverage is weak and misses key page types or sameAs/@id support."),
                "evidence": ", ".join(schema_result.schema_types[:6]) or "JSON-LD not detected",
                "impact": self._t(feedback_lang, "削弱 Google 对实体、内容类型与富结果的理解。", "Reduces Google's understanding of entities, page type, and rich result eligibility."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "按页型补齐 Organization / WebSite / Service / Article / FAQPage / Product / BreadcrumbList。", "Add Organization / WebSite / Service / Article / FAQPage / Product / BreadcrumbList by page type."),
                "effort": self._t(feedback_lang, "1-3 days", "1-3 days"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-008",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "采样页面 HTTP 状态正常，无 4xx/5xx 或明显重定向链", "Sampled pages return healthy HTTP statuses without obvious redirect issues"),
                "passed": not error_pages and len(redirected_pages) <= max(1, sample_count // 3),
                "summary": self._t(feedback_lang, "采样页面状态码稳定。", "Sampled pages return stable HTTP statuses."),
                "failure": self._t(feedback_lang, "采样页面存在 4xx/5xx 或较多重定向。", "Sampled pages contain 4xx/5xx responses or too many redirects."),
                "evidence": ", ".join(f"{page.url} ({page.status_code})" for page in error_pages[:3]) or ", ".join(page.url for page in redirected_pages[:3]),
                "impact": self._t(feedback_lang, "影响抓取效率、权重传递和页面可访问性。", "Hurts crawl efficiency, signal consolidation, and page accessibility."),
                "severity": "critical",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "修复错误页并压缩重定向层级，核心页保持 200 直达。", "Fix error pages and collapse redirects so core URLs resolve directly with 200 responses."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-009",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "移动端基础适配正常", "Mobile basics are correctly configured"),
                "passed": bool(discovery.homepage.viewport),
                "summary": self._t(feedback_lang, "首页声明了 viewport。", "Homepage declares a viewport."),
                "failure": self._t(feedback_lang, "首页缺少 viewport，移动端适配信号不足。", "Homepage is missing a viewport declaration."),
                "evidence": discovery.final_url,
                "impact": self._t(feedback_lang, "影响移动端可用性与移动优先索引。", "Weakens mobile usability and mobile-first indexing."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "补充标准 viewport，并复核移动端交互与排版。", "Add a standard viewport and verify mobile interaction and layout."),
                "effort": self._t(feedback_lang, "1-4 hours", "1-4 hours"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-010",
                "category": "Performance",
                "check": self._t(feedback_lang, "核心页面性能与资源负担可控", "Core pages show acceptable performance and resource weight"),
                "passed": technical.technical_score >= 65 and technical.findings.get("response_time_ms", 9999) <= 1500 and not oversized_html,
                "summary": self._t(feedback_lang, "服务器响应、渲染阻塞和页面体量整体可控。", "Server response, render blocking, and page weight look manageable."),
                "failure": self._t(feedback_lang, "响应偏慢、阻塞资源较多或 HTML 体量过大。", "Responses are slow, render-blocking risk is elevated, or HTML payloads are too large."),
                "evidence": self._t(feedback_lang, f"response_time_ms={technical.findings.get('response_time_ms', '-')}", f"response_time_ms={technical.findings.get('response_time_ms', '-')}"),
                "impact": self._t(feedback_lang, "拖累抓取效率、用户体验与转化。", "Hurts crawl efficiency, UX, and conversion performance."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "优先优化首屏资源、压缩 HTML/图片并延迟非关键 JS。", "Optimize above-the-fold resources, reduce HTML/image weight, and defer non-critical JS."),
                "effort": self._t(feedback_lang, "1-5 days", "1-5 days"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-011",
                "category": "International SEO",
                "check": self._t(feedback_lang, "hreflang 与目标语言版本一致", "hreflang coverage matches the target locale"),
                "passed": (not hreflang_applicable) or technical.checks.get("hreflang_target_present", False),
                "status": "na" if not hreflang_applicable else None,
                "summary": self._t(feedback_lang, "多语言信号与目标语言范围保持一致。", "Multilingual signals line up with the requested locale scope."),
                "failure": self._t(feedback_lang, "hreflang 缺失或未覆盖目标语言版本。", "hreflang is missing or does not cover the requested locale."),
                "evidence": ", ".join(discovery.homepage.hreflang[:6]) or discovery.final_url,
                "impact": self._t(feedback_lang, "可能造成语言版本错配与国际收录波动。", "Can cause locale mismatch and unstable international indexing."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "补齐 hreflang/x-default，并确保 canonical 落在同一语言集合。", "Add hreflang/x-default and keep canonical URLs inside the same locale cluster."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-012",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "Noindex 未误伤应收录核心页面", "Noindex is not accidentally blocking core indexable pages"),
                "passed": not noindex_pages,
                "summary": self._t(feedback_lang, "采样核心页未发现 noindex。", "No sampled core page is accidentally marked noindex."),
                "failure": self._t(feedback_lang, "采样核心页检测到 noindex。", "A sampled core page is marked noindex."),
                "evidence": ", ".join(page.final_url for page in noindex_pages[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "会直接阻断收录与自然流量。", "Directly blocks indexing and organic traffic."),
                "severity": "critical",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "移除核心页上的 noindex / X-Robots-Tag，并复核模板逻辑。", "Remove noindex / X-Robots-Tag from core pages and review template logic."),
                "effort": self._t(feedback_lang, "1-4 hours", "1-4 hours"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-013",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "JS 渲染不会遮蔽核心内容", "JavaScript rendering does not hide the main content"),
                "passed": technical.ssr_signal.get("score", 0) >= 60,
                "summary": self._t(feedback_lang, "HTML 初始内容量对抓取基本友好。", "Initial HTML content looks sufficiently crawler-friendly."),
                "failure": self._t(feedback_lang, "HTML 内容偏薄，疑似依赖前端渲染。", "Initial HTML is thin and appears overly dependent on client-side rendering."),
                "evidence": technical.ssr_signal.get("classification", "unknown"),
                "impact": self._t(feedback_lang, "可能导致抓取内容不全、渲染延迟和关键词信号损失。", "Can cause incomplete crawl content, delayed rendering, and weaker keyword signals."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "对关键模板采用 SSR/静态预渲染，确保正文、标题和链接在初始 HTML 中可见。", "Use SSR or pre-rendering on key templates so content, headings, and links are visible in the initial HTML."),
                "effort": self._t(feedback_lang, "2-10 days", "2-10 days"),
                "difficulty": "high",
                "owner": "Engineering",
            },
            {
                "id": "CHK-014",
                "category": "On-Page SEO",
                "check": self._t(feedback_lang, "Title 唯一、含主题词、长度合适", "Titles are unique, descriptive, and appropriately sized"),
                "passed": not missing_titles and len(title_length_issues) <= max(1, sample_count // 4),
                "summary": self._t(feedback_lang, "采样页 title 基本齐全。", "Sampled pages largely have usable title tags."),
                "failure": self._t(feedback_lang, "采样页存在 title 缺失或长度明显异常。", "Sampled pages are missing titles or show clear length issues."),
                "evidence": ", ".join(page.final_url for page in (missing_titles + title_length_issues)[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响主题理解、排名与 SERP CTR。", "Hurts topical clarity, ranking relevance, and SERP CTR."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "为核心模板建立唯一 title 模板，并控制在 45-65 字符。", "Create unique title patterns for core templates and keep them around 45-65 characters."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "medium",
                "owner": "SEO + Content",
            },
            {
                "id": "CHK-015",
                "category": "On-Page SEO",
                "check": self._t(feedback_lang, "Meta Description 唯一且长度合适", "Meta descriptions are present and reasonably sized"),
                "passed": not missing_meta and len(meta_length_issues) <= max(1, sample_count // 3),
                "summary": self._t(feedback_lang, "采样页 meta description 覆盖较完整。", "Sampled pages mostly have usable meta descriptions."),
                "failure": self._t(feedback_lang, "采样页存在 description 缺失或长度异常。", "Sampled pages are missing descriptions or have clear length issues."),
                "evidence": ", ".join(page.final_url for page in (missing_meta + meta_length_issues)[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响搜索结果摘要与点击率。", "Reduces search snippet quality and CTR."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "补齐描述并在 80-170 字符内突出价值点与 CTA。", "Write descriptions in the 80-170 character range with value proposition and CTA cues."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "low",
                "owner": "SEO + Content",
            },
            {
                "id": "CHK-016",
                "category": "On-Page SEO",
                "check": self._t(feedback_lang, "H 标签层级合理，核心页仅一个 H1", "Heading hierarchy is clean with a single H1 per page"),
                "passed": not heading_issues,
                "summary": self._t(feedback_lang, "采样页标题层级整体清晰。", "Sampled pages show a clean heading hierarchy."),
                "failure": self._t(feedback_lang, "采样页存在 H1 缺失、重复或层级混乱。", "Sampled pages are missing an H1, have multiple H1s, or show weak heading structure."),
                "evidence": ", ".join(f"{page.final_url} (H1={page.h1_count})" for page in heading_issues[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响页面主题传达与可读性。", "Weakens topical clarity and readability."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "每页保留唯一 H1，并让 H2/H3 体现信息分块。", "Keep a single H1 per page and use H2/H3 for structured sections."),
                "effort": self._t(feedback_lang, "1-2 days", "1-2 days"),
                "difficulty": "low",
                "owner": "Content + Engineering",
            },
            {
                "id": "CHK-017",
                "category": "Technical SEO",
                "check": self._t(feedback_lang, "Canonical 使用正确并与最终 URL 对齐", "Canonical tags align with the preferred final URLs"),
                "passed": technical.checks.get("canonical") and not canonical_mismatches,
                "summary": self._t(feedback_lang, "canonical 与最终 URL 基本一致。", "Canonical tags align with preferred final URLs."),
                "failure": self._t(feedback_lang, "canonical 缺失、协议错误或指向非首选 URL。", "Canonical tags are missing, use the wrong protocol, or point to non-preferred URLs."),
                "evidence": ", ".join(page.final_url for page in canonical_mismatches[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "会造成重复内容与规范化冲突。", "Creates duplicate content risk and canonical conflicts."),
                "severity": "high",
                "priority": "P0",
                "recommendation": self._t(feedback_lang, "核心页统一输出自引用 canonical，并与 sitemap/hreflang 同步。", "Use self-referencing canonicals on core pages and keep them aligned with sitemap/hreflang."),
                "effort": self._t(feedback_lang, "2-8 hours", "2-8 hours"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-018",
                "category": "International SEO",
                "check": self._t(feedback_lang, "HTML lang 属性正确", "HTML lang attributes are correctly set"),
                "passed": not lang_issues,
                "summary": self._t(feedback_lang, "采样页 lang 属性覆盖正常。", "Sampled pages expose language attributes consistently."),
                "failure": self._t(feedback_lang, "采样页存在 lang 缺失。", "Sampled pages are missing language attributes."),
                "evidence": ", ".join(page.final_url for page in lang_issues[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响语言识别、可访问性和国际化信号。", "Hurts language detection, accessibility, and international SEO signals."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "在所有模板上输出准确的 html lang。", "Set accurate html lang attributes across all templates."),
                "effort": self._t(feedback_lang, "1-4 hours", "1-4 hours"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-019",
                "category": "Image SEO",
                "check": self._t(feedback_lang, "图片具备描述性 alt 文本", "Images use descriptive alt text"),
                "passed": not alt_issues,
                "summary": self._t(feedback_lang, "采样页图片 alt 覆盖率整体正常。", "Sampled pages show acceptable alt-text coverage."),
                "failure": self._t(feedback_lang, "采样页图片 alt 覆盖率偏低。", "Sampled pages have weak alt-text coverage."),
                "evidence": ", ".join(f"{page.final_url} ({page.alt_coverage_ratio})" for page in alt_issues[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响图片搜索与可访问性。", "Hurts image SEO and accessibility."),
                "severity": "medium",
                "priority": "P2",
                "recommendation": self._t(feedback_lang, "为功能性与内容型图片补充描述性 alt。", "Add descriptive alt text to functional and content-driven images."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "low",
                "owner": "Content",
            },
            {
                "id": "CHK-020",
                "category": "On-Page SEO",
                "check": self._t(feedback_lang, "内部链接语义清晰且无异常 nofollow", "Internal linking is descriptive and avoids stray nofollow usage"),
                "passed": content.findings.get("average_link_context_score", 0) >= 55 and not internal_nofollow,
                "summary": self._t(feedback_lang, "内链锚文本与链接语义基础可用。", "Internal anchor text and linking context look usable."),
                "failure": self._t(feedback_lang, "内链锚文本偏泛，或采样页存在内部 nofollow。", "Internal anchor text is too generic or sampled pages contain internal nofollow links."),
                "evidence": ", ".join(page.final_url for page in internal_nofollow[:3]) or str(content.findings.get("average_link_context_score", 0)),
                "impact": self._t(feedback_lang, "降低主题传递和站内抓取效率。", "Weakens topical flow and internal crawl discovery."),
                "severity": "medium",
                "priority": "P2",
                "recommendation": self._t(feedback_lang, "优化锚文本语义，移除非必要的内部 nofollow。", "Improve anchor semantics and remove unnecessary internal nofollow usage."),
                "effort": self._t(feedback_lang, "1-3 days", "1-3 days"),
                "difficulty": "medium",
                "owner": "SEO + Content",
            },
            {
                "id": "CHK-021",
                "category": "Performance",
                "check": self._t(feedback_lang, "页面体量与 HTML 负担可控", "Page payload and HTML size are under control"),
                "passed": not oversized_html,
                "summary": self._t(feedback_lang, "采样页 HTML 体量没有明显超标。", "Sampled HTML payloads are within a reasonable range."),
                "failure": self._t(feedback_lang, "采样页 HTML 体量偏大。", "Sampled pages have oversized HTML payloads."),
                "evidence": ", ".join(f"{page.final_url} ({page.html_length})" for page in oversized_html[:3]) or discovery.final_url,
                "impact": self._t(feedback_lang, "影响渲染速度与资源下载效率。", "Hurts render speed and download efficiency."),
                "severity": "medium",
                "priority": "P2",
                "recommendation": self._t(feedback_lang, "减少冗余 DOM / 内联数据，压缩模板输出。", "Reduce redundant DOM and inline payloads and slim template output."),
                "effort": self._t(feedback_lang, "1-4 days", "1-4 days"),
                "difficulty": "medium",
                "owner": "Engineering",
            },
            {
                "id": "CHK-022",
                "category": "Performance",
                "check": self._t(feedback_lang, "图片懒加载与尺寸声明合理", "Images use lazy-loading and explicit dimensions"),
                "passed": technical.checks.get("image_optimization", {}).get("lazyload_ratio", 0) >= 0.5,
                "summary": self._t(feedback_lang, "图片加载策略具备基础优化。", "Image delivery shows baseline optimization."),
                "failure": self._t(feedback_lang, "图片懒加载或尺寸声明不足。", "Image lazy-loading or dimension declarations are insufficient."),
                "evidence": str(technical.checks.get("image_optimization", {})),
                "impact": self._t(feedback_lang, "拖累 LCP 和布局稳定性。", "Hurts LCP and layout stability."),
                "severity": "medium",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "关键图片压缩并补齐 width/height 与 lazy loading。", "Compress key images and add width/height plus lazy loading."),
                "effort": self._t(feedback_lang, "0.5-2 days", "0.5-2 days"),
                "difficulty": "low",
                "owner": "Engineering",
            },
            {
                "id": "CHK-023",
                "category": "Content Quality",
                "check": self._t(feedback_lang, "核心主题覆盖与页面深度足够", "Core topic coverage and page depth are sufficient"),
                "passed": content.content_score >= 65 and content.expertise_score >= 60,
                "summary": self._t(feedback_lang, "服务页/文章页已具备基础主题深度。", "Service and article pages show baseline topical depth."),
                "failure": self._t(feedback_lang, "服务页或文章页深度不足，主题覆盖偏浅。", "Service or article depth is too thin and topical coverage remains shallow."),
                "evidence": ", ".join(content.issues[:2]) or "content depth",
                "impact": self._t(feedback_lang, "限制关键词覆盖、排名能力和长尾拓展。", "Limits keyword reach, ranking ability, and long-tail expansion."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "扩展服务页与知识内容，围绕意图簇建立专题页面与 FAQ。", "Deepen service pages and knowledge content and build topic clusters with dedicated pages and FAQs."),
                "effort": self._t(feedback_lang, "1-4 weeks", "1-4 weeks"),
                "difficulty": "medium",
                "owner": "Content + SEO",
            },
            {
                "id": "CHK-024",
                "category": "Content Quality",
                "check": self._t(feedback_lang, "E-E-A-T 信号完整", "E-E-A-T signals are strong enough"),
                "passed": (
                    content.experience_score >= 60
                    and content.expertise_score >= 60
                    and content.authoritativeness_score >= 55
                    and content.trustworthiness_score >= 60
                ),
                "summary": self._t(feedback_lang, "作者、日期、案例、联系信息与证据基础较完整。", "Author, date, proof, contact, and expertise signals are broadly present."),
                "failure": self._t(feedback_lang, "E-E-A-T 信号仍偏弱，尤其是作者、日期、案例或权威证明。", "E-E-A-T remains weak, especially around authorship, dates, case evidence, or authority proof."),
                "evidence": self._t(feedback_lang, f"EEAT={content.experience_score}/{content.expertise_score}/{content.authoritativeness_score}/{content.trustworthiness_score}", f"EEAT={content.experience_score}/{content.expertise_score}/{content.authoritativeness_score}/{content.trustworthiness_score}"),
                "impact": self._t(feedback_lang, "影响质量评估、信任与高价值查询竞争力。", "Hurts quality evaluation, trust, and competitiveness on high-value queries."),
                "severity": "high",
                "priority": "P1",
                "recommendation": self._t(feedback_lang, "补齐作者页、更新时间、案例/数据与企业信任模块。", "Add author pages, update timestamps, case proof, and trust modules."),
                "effort": self._t(feedback_lang, "1-3 weeks", "1-3 weeks"),
                "difficulty": "medium",
                "owner": "Content + Brand",
            },
            {
                "id": "CHK-025",
                "category": "Content Quality",
                "check": self._t(feedback_lang, "页面具备引用、FAQ 与 answer-first 结构", "Pages expose citations, FAQ coverage, and answer-first structure"),
                "passed": content.findings.get("has_reference_section_any", False) and content.findings.get("has_answer_first_any", False),
                "summary": self._t(feedback_lang, "关键页面具备被摘要与引用的结构基础。", "Key pages are structured for extractability and citation."),
                "failure": self._t(feedback_lang, "引用区、FAQ 或 answer-first 结构不足。", "References, FAQ coverage, or answer-first structure is still weak."),
                "evidence": ", ".join(content.recommendations[:2]) or "citation structure",
                "impact": self._t(feedback_lang, "影响摘要式 SERP、AI 抽取与转化前置沟通。", "Weakens snippet extraction, AI reuse, and conversion-oriented answer blocks."),
                "severity": "medium",
                "priority": "P2",
                "recommendation": self._t(feedback_lang, "在核心页增加首段摘要、FAQ、来源区与可引用数据块。", "Add intro summaries, FAQs, references, and quotable proof blocks to core pages."),
                "effort": self._t(feedback_lang, "3-7 days", "3-7 days"),
                "difficulty": "medium",
                "owner": "Content",
            },
            {
                "id": "CHK-026",
                "category": "AI Search",
                "check": self._t(feedback_lang, "AI / GEO 可见性达到基础可用水平", "AI / GEO visibility reaches a usable baseline"),
                "passed": visibility.ai_visibility_score >= 60 and visibility.brand_authority_score >= 50,
                "summary": self._t(feedback_lang, "站点已具备基础的 AI 搜索与引用可见性。", "The site has baseline AI search visibility and reuse readiness."),
                "failure": self._t(feedback_lang, "AI 抓取、实体信号或可引用结构仍偏弱。", "AI crawler access, entity signals, or citation structure remains weak."),
                "evidence": self._t(feedback_lang, f"AI={visibility.ai_visibility_score}, Brand={visibility.brand_authority_score}", f"AI={visibility.ai_visibility_score}, Brand={visibility.brand_authority_score}"),
                "impact": self._t(feedback_lang, "影响 AI Overviews、ChatGPT、Perplexity 等新入口可见性。", "Reduces visibility across AI Overviews, ChatGPT, Perplexity, and similar surfaces."),
                "severity": "medium",
                "priority": "P2",
                "recommendation": self._t(feedback_lang, "放行 AI crawler，补齐 llms.txt、sameAs、FAQ 与证据型内容模块。", "Allow AI crawlers and add llms.txt, sameAs, FAQ, and proof-led content modules."),
                "effort": self._t(feedback_lang, "1-2 weeks", "1-2 weeks"),
                "difficulty": "medium",
                "owner": "SEO + Content",
            },
        ]
        for item in checks:
            if item.get("status") == "na":
                continue
            item["status"] = "pass" if item["passed"] else "fail"
        return checks

    def _dimension_cards(
        self,
        *,
        feedback_lang: str,
        technical,
        content,
        schema_result,
        visibility,
        checks: list[dict[str, Any]],
        scores: dict[str, int],
    ) -> dict[str, SeoDimensionResult]:
        grouped_issues: dict[str, list[str]] = defaultdict(list)
        grouped_recommendations: dict[str, list[str]] = defaultdict(list)
        category_map = {
            "technical": {"Technical SEO", "International SEO"},
            "content_quality": {"Content Quality"},
            "on_page": {"On-Page SEO", "Image SEO"},
            "schema": {"Schema"},
            "performance": {"Performance"},
            "ai_search": {"AI Search"},
        }
        for item in checks:
            if item["status"] != "fail":
                continue
            for dimension_key, categories in category_map.items():
                if item["category"] in categories:
                    grouped_issues[dimension_key].append(item["failure"])
                    grouped_recommendations[dimension_key].append(item["recommendation"])
        eeat_average = self.scoring.clamp_score(
            (content.experience_score + content.expertise_score + content.authoritativeness_score + content.trustworthiness_score) / 4
        )
        dimension_inputs = {
            "technical": {
                "label": self._t(feedback_lang, "Technical SEO", "Technical SEO"),
                "summary": self._t(feedback_lang, "抓取、索引、规范化与站点结构信号。", "Crawling, indexing, canonicalization, and site-structure signals."),
                "highlights": technical.strengths[:3],
            },
            "content_quality": {
                "label": self._t(feedback_lang, "Content Quality", "Content Quality"),
                "summary": self._t(feedback_lang, "页面深度、主题覆盖与 E-E-A-T 信号。", "Page depth, topical coverage, and E-E-A-T signals."),
                "highlights": [self._t(feedback_lang, f"E-E-A-T {eeat_average}/100", f"E-E-A-T {eeat_average}/100")] + content.strengths[:2],
            },
            "on_page": {
                "label": self._t(feedback_lang, "On-Page SEO", "On-Page SEO"),
                "summary": self._t(feedback_lang, "Title、描述、H 标签、图片与内链语义。", "Titles, descriptions, headings, images, and internal link semantics."),
                "highlights": [self._t(feedback_lang, "采样页模板级 On-Page 基础检查", "Template-level on-page checks across sampled pages")],
            },
            "schema": {
                "label": self._t(feedback_lang, "Schema", "Schema"),
                "summary": self._t(feedback_lang, "结构化数据覆盖、实体关系与机器可读一致性。", "Structured data coverage, entity relationships, and machine-readable consistency."),
                "highlights": schema_result.strengths[:3],
            },
            "performance": {
                "label": self._t(feedback_lang, "Core Web Vitals / Performance", "Core Web Vitals / Performance"),
                "summary": self._t(feedback_lang, "响应速度、阻塞资源、图片与页面体量。", "Response speed, blocking resources, images, and payload size."),
                "highlights": technical.strengths[:2],
            },
            "ai_search": {
                "label": self._t(feedback_lang, "AI Search / GEO", "AI Search / GEO"),
                "summary": self._t(feedback_lang, "AI 可抓取性、实体清晰度与可引用内容结构。", "AI crawlability, entity clarity, and citation-ready content structure."),
                "highlights": visibility.strengths[:3],
            },
        }
        cards: dict[str, SeoDimensionResult] = {}
        for key, payload in dimension_inputs.items():
            score = self.scoring.clamp_score(scores[key])
            cards[key] = SeoDimensionResult(
                key=key,
                label=payload["label"],
                weight=self.RAW_WEIGHTS[key],
                score=score,
                status=self.scoring.status_from_score(score),
                summary=payload["summary"],
                highlights=payload["highlights"],
                issues=grouped_issues.get(key, [])[:4],
                recommendations=list(dict.fromkeys(grouped_recommendations.get(key, [])))[:4],
            )
        return cards

    def _coverage_results(self, checks: list[dict[str, Any]]) -> list[SeoCheckResult]:
        return [
            SeoCheckResult(
                id=item["id"],
                category=item["category"],
                check=item["check"],
                scope=item.get("scope", "sitewide"),
                status=item["status"],
                summary=item["summary"] if item["status"] == "pass" else item["failure"],
                evidence=item["evidence"],
                seo_impact=item["impact"],
                severity=item["severity"],
                priority=item["priority"],
            )
            for item in checks
        ]

    def _issue_results(self, checks: list[dict[str, Any]]) -> list[SeoIssueResult]:
        issues = []
        for index, item in enumerate([check for check in checks if check["status"] == "fail"], start=1):
            issues.append(
                SeoIssueResult(
                    issue_id=f"P-{index:03d}",
                    priority=item["priority"],
                    severity=item["severity"],
                    category=item["category"],
                    scope=item.get("scope", "sitewide"),
                    description=item["failure"],
                    evidence=item["evidence"],
                    seo_impact=item["impact"],
                    recommendation=item["recommendation"],
                    estimated_effort=item["effort"],
                    implementation_difficulty=item["difficulty"],
                    owner_team=item["owner"],
                    acceptance_criteria=item["recommendation"],
                )
            )
        return issues

    def _roadmap(self, issues: list[SeoIssueResult], feedback_lang: str) -> list[SeoRoadmapItem]:
        roadmap: list[SeoRoadmapItem] = []
        for issue in issues:
            if issue.priority == "P0":
                phase = "0-30"
                impact = self._t(feedback_lang, "Stop-loss: fix crawl, index, and canonical blockers.", "Stop-loss: fix crawl, index, and canonical blockers.")
            elif issue.category in {"Schema", "Content Quality", "On-Page SEO"}:
                phase = "31-60"
                impact = self._t(feedback_lang, "Build stronger landing pages, metadata, and structured content coverage.", "Build stronger landing pages, metadata, and structured content coverage.")
            else:
                phase = "61-90"
                impact = self._t(feedback_lang, "Compound trust, AI visibility, and long-tail quality signals.", "Compound trust, AI visibility, and long-tail quality signals.")
            roadmap.append(
                SeoRoadmapItem(
                    phase=phase,
                    priority=issue.priority,
                    task=issue.recommendation,
                    related_issue_ids=[issue.issue_id],
                    scope=issue.scope,
                    owner_team=issue.owner_team,
                    estimated_effort=issue.estimated_effort,
                    acceptance_criteria=issue.acceptance_criteria,
                    expected_impact=impact,
                )
            )
        return roadmap[:12]

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        feedback_lang: str = "en",
        target_locale: str | None = None,
        max_pages: int = 12,
    ) -> SeoAuditResult:
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(
            url,
            discovery,
            full_audit=max_pages > 5,
            max_pages=max_pages,
            target_locale=target_locale,
        )

        technical, content, schema_result, visibility = await asyncio.gather(
            self.technical_service.audit(url, resolved, mode=mode, llm_config=llm_config, target_locale=target_locale),
            self.content_service.audit(url, resolved, mode=mode, llm_config=llm_config, feedback_lang=feedback_lang, target_locale=target_locale),
            self.schema_service.audit(url, resolved, mode=mode, llm_config=llm_config, target_locale=target_locale),
            self.visibility_service.audit(url, resolved, mode=mode, llm_config=llm_config, feedback_lang=feedback_lang, target_locale=target_locale),
        )

        samples, variant_results = await asyncio.gather(
            self._fetch_sample_pages(resolved, max_pages=max_pages),
            self._probe_variants(resolved.final_url),
        )

        homepage_response = await fetch_url(resolved.final_url)
        homepage_soup = BeautifulSoup(homepage_response.text or "", "lxml")
        homepage_analytics = self._detect_analytics(homepage_soup, homepage_response.text)

        on_page_score = self.scoring.clamp_score(
            (
                25 if all(page.title for page in samples or [SeoSamplePageResult(url=url, title="x")]) else 0
            )
            + (
                20 if all(page.meta_description for page in samples or [SeoSamplePageResult(url=url, meta_description="x")]) else 0
            )
            + (20 if all(page.h1_count == 1 for page in samples or [SeoSamplePageResult(url=url, h1_count=1)]) else 0)
            + (15 if not any(page.alt_coverage_ratio < 0.8 for page in samples) else 0)
            + (20 if content.findings.get("average_link_context_score", 0) >= 55 else 0)
        )
        performance_score = self.scoring.clamp_score(
            technical.findings.get("response_time_ms", 3000) <= 300 and 100
            or technical.findings.get("response_time_ms", 3000) <= 800 and 78
            or technical.findings.get("response_time_ms", 3000) <= 1500 and 58
            or 35
        )
        performance_score = self.scoring.clamp_score(
            performance_score * 0.45
            + technical.render_blocking_risk.get("score", 0) * 0.25
            + technical.checks.get("image_optimization", {}).get("lazyload_ratio", 0) * 100 * 0.15
            + (100 if not any(page.html_length > 250000 for page in samples) else 55) * 0.15
        )
        content_quality_score = self.scoring.clamp_score(
            (
                content.content_score
                + content.experience_score
                + content.expertise_score
                + content.authoritativeness_score
                + content.trustworthiness_score
            ) / 5
        )
        ai_search_score = self.scoring.clamp_score(
            visibility.ai_visibility_score * 0.55
            + visibility.brand_authority_score * 0.15
            + schema_result.structured_data_score * 0.10
            + (100 if content.findings.get("has_answer_first_any", False) else 45) * 0.10
            + (100 if content.findings.get("has_reference_section_any", False) else 40) * 0.10
        )
        raw_scores = {
            "technical": technical.technical_score,
            "content_quality": content_quality_score,
            "on_page": on_page_score,
            "schema": schema_result.structured_data_score,
            "performance": performance_score,
            "ai_search": ai_search_score,
        }
        overall_score, weighted_scores = self._weighted_score(raw_scores)

        checks = self._build_checks(
            feedback_lang=feedback_lang,
            discovery=resolved,
            technical=technical,
            content=content,
            schema_result=schema_result,
            visibility=visibility,
            samples=samples,
            homepage_analytics=homepage_analytics,
            variant_results=variant_results,
        )
        coverage_checks = self._coverage_results(checks)
        issues_table = self._issue_results(checks)
        roadmap = self._roadmap(issues_table, feedback_lang)
        dimensions = self._dimension_cards(
            feedback_lang=feedback_lang,
            technical=technical,
            content=content,
            schema_result=schema_result,
            visibility=visibility,
            checks=checks,
            scores=raw_scores,
        )

        coverage_summary = {
            "total_checks": len(coverage_checks),
            "passed_checks": sum(1 for item in coverage_checks if item.status == "pass"),
            "failed_checks": sum(1 for item in coverage_checks if item.status == "fail"),
            "na_checks": sum(1 for item in coverage_checks if item.status == "na"),
        }
        measurements = {
            "sampled_url_count": len(samples),
            "response_time_ms": technical.findings.get("response_time_ms"),
            "render_blocking_risk": technical.findings.get("render_blocking_risk"),
            "security_headers_score": technical.findings.get("security_headers_score"),
            "schema_type_count": schema_result.findings.get("schema_type_count"),
            "same_as_count": schema_result.findings.get("same_as_count"),
            "ai_visibility_score": visibility.ai_visibility_score,
            "brand_authority_score": visibility.brand_authority_score,
            "eeat_average": content_quality_score,
            "analytics_detected": homepage_analytics,
        }
        top_issues = [item.description for item in issues_table[:5]]
        quick_wins = [item.recommendation for item in issues_table[:5]]
        processing_notes = [
            self._t(feedback_lang, "基于 discovery snapshot + 采样页面做站点级 SEO 诊断。", "Site-level SEO audit based on the discovery snapshot plus sampled pages."),
            self._t(feedback_lang, "性能维度目前使用响应时间、阻塞资源和页面体量启发式，不等同于真实 CrUX/PSI。", "Performance currently uses response-time, blocking-resource, and payload heuristics rather than live CrUX/PSI data."),
            self._t(feedback_lang, "竞品 SERP 与关键词地图未接入外部数据源时，报告以站内结构与内容信号为主。", "Without external SERP data, the report emphasizes on-site structure and content signals."),
        ]

        result = SeoAuditResult(
            score=overall_score,
            overall_score=overall_score,
            status=self.scoring.status_from_score(overall_score),
            findings={
                "top_issues": top_issues,
                "quick_wins": quick_wins,
            },
            issues=top_issues,
            strengths=list(dict.fromkeys(
                technical.strengths[:2] + content.strengths[:2] + schema_result.strengths[:2] + visibility.strengths[:2]
            ))[:8],
            recommendations=quick_wins,
            dimensions=dimensions,
            weighted_scores=weighted_scores,
            coverage_checks=coverage_checks,
            issues_table=issues_table,
            roadmap=roadmap,
            sampled_pages=samples,
            coverage_summary=coverage_summary,
            measurements=measurements,
            supporting_scores={
                "technical_score": technical.technical_score,
                "content_score": content.content_score,
                "schema_score": schema_result.structured_data_score,
                "ai_visibility_score": visibility.ai_visibility_score,
                "brand_authority_score": visibility.brand_authority_score,
                "on_page_score": on_page_score,
                "performance_score": performance_score,
                "content_quality_score": content_quality_score,
                "ai_search_score": ai_search_score,
            },
            processing_notes=processing_notes,
        )
        self.set_execution_metadata(result, mode, llm_config)
        result.llm_enhanced = any([
            technical.llm_enhanced,
            content.llm_enhanced,
            schema_result.llm_enhanced,
            visibility.llm_enhanced,
        ])
        result = self.finalize_audit_result(
            result,
            module_key="seo",
            input_pages=[item.url for item in samples] or [resolved.final_url],
            started_at=started_at,
            confidence=min(0.96, 0.62 + (len(samples) / max(max_pages, 1)) * 0.25),
        )
        return result

    def summarize(self, audit_result: SeoAuditResult, *, feedback_lang: str = "en") -> SeoSummaryResult:
        ordered_dimensions = sorted(audit_result.dimensions.values(), key=lambda item: item.score)
        top_issues = audit_result.issues[:5]
        quick_wins = audit_result.recommendations[:5]
        roadmap_by_phase: dict[str, list[SeoRoadmapItem]] = {"0-30": [], "31-60": [], "61-90": []}
        for item in audit_result.roadmap:
            roadmap_by_phase.setdefault(item.phase, []).append(item)
        actions = [
            ActionPlanItem(
                priority="high" if road.priority == "P0" else "medium" if road.priority == "P1" else "low",
                module=road.phase,
                action=road.task,
                rationale=road.expected_impact,
            )
            for road in audit_result.roadmap[:6]
        ]
        summary_text = self._t(
            feedback_lang,
            (
                f"站点当前 Google SEO 健康度为 {audit_result.overall_score}/100。"
                f"最大短板集中在 {ordered_dimensions[0].label if ordered_dimensions else 'Technical SEO'}"
                f"{f' 与 {ordered_dimensions[1].label}' if len(ordered_dimensions) > 1 else ''}。"
                "优先修复抓取/规范化阻断项，再推进页面级元数据、内容深度和结构化数据。"
            ),
            (
                f"The site currently scores {audit_result.overall_score}/100 for Google SEO health. "
                f"The biggest gaps are in {ordered_dimensions[0].label if ordered_dimensions else 'Technical SEO'}"
                f"{f' and {ordered_dimensions[1].label}' if len(ordered_dimensions) > 1 else ''}. "
                "Fix crawl and canonical blockers first, then deepen metadata, content quality, and structured data."
            ),
        )
        return SeoSummaryResult(
            overall_score=audit_result.overall_score,
            status=audit_result.status,
            audit_mode=audit_result.audit_mode,
            llm_enhanced=audit_result.llm_enhanced,
            llm_provider=audit_result.llm_provider,
            llm_model=audit_result.llm_model,
            summary=summary_text,
            score_breakdown={
                key: {
                    "label": value.label,
                    "score": value.score,
                    "weight": value.weight,
                }
                for key, value in audit_result.dimensions.items()
            },
            dimensions={key: value.model_dump() for key, value in audit_result.dimensions.items()},
            top_issues=top_issues,
            quick_wins=quick_wins,
            prioritized_action_plan=actions,
            coverage_summary=audit_result.coverage_summary,
            roadmap_by_phase=roadmap_by_phase,
            processing_notes=audit_result.processing_notes,
        )
