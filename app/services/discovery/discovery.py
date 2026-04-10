from __future__ import annotations

import asyncio

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.discovery import (
    DiscoveryResult,
    FetchMetadata,
    HomepageExtract,
    KeyPages,
    PageProfile,
    SiteSignals,
)
from app.services.discovery.backlinks import BacklinkService
from app.services.infra.site_assets import SiteAssetStore
from app.utils.fetcher import fetch_url
from app.utils.heuristics import detect_site_signals, infer_business_type, select_key_pages
from app.utils.html_parser import parse_html
from app.utils.llms_parser import inspect_llms
from app.utils.robots_parser import inspect_robots
from app.utils.schema_extractor import extract_schema_summary
from app.utils.sitemap_parser import inspect_sitemap
from app.utils.text_analyzer import (
    assess_link_context,
    contains_faq,
    estimate_information_density,
    evaluate_chunk_structure,
    evaluate_heading_quality,
    has_author_signals,
    has_inline_citations,
    has_publish_date,
    has_quantified_data,
    has_reference_section,
    has_tldr_summary,
    has_update_log,
    is_answer_first,
)
from app.utils.url_classifier import classify_url_type
from app.utils.url_utils import (
    entry_url_candidates,
    get_scope_root,
    get_site_root,
    is_internal_url,
    is_likely_homepage_url,
    normalize_url,
    registered_domain,
)


class DiscoveryService:
    """站点快照服务（snapshot-v3）：负责抓取并聚合首页、关键页、协议文件和实体信号。"""

    SNAPSHOT_VERSION = "snapshot-v3"
    EXTRA_PAGE_PATTERNS = {
        "product": ["product", "products", "item", "sku", "shop"],
        "faq": ["faq", "help", "support"],
        "documentation": ["docs", "documentation", "guide", "manual"],
        "comparison": ["compare", "comparison", "vs"],
    }

    def __init__(self) -> None:
        self.backlink_service = BacklinkService()
        self.asset_store = SiteAssetStore()

    def _build_page_profile(
        self,
        *,
        page_type: str,
        final_url: str,
        parsed: dict,
    ) -> PageProfile:
        """将 HTML 解析结果构建为 PageProfile 对象。"""
        schema_summary = extract_schema_summary(parsed["json_ld_blocks"], visible_text=parsed["text_content"])
        entity_signals = detect_site_signals(
            text=parsed["text_content"],
            schema_summary=schema_summary,
            key_pages=KeyPages(),
            title=parsed["title"],
        )
        heading_quality = evaluate_heading_quality(parsed["headings"])
        information_density = estimate_information_density(parsed["text_content"], parsed["headings"])
        chunk_structure = evaluate_chunk_structure(parsed["text_content"], parsed["headings"])
        link_context = assess_link_context(parsed["internal_links"], parsed["external_links"])
        return PageProfile(
            page_type=page_type,
            final_url=final_url,
            title=parsed["title"],
            meta_description=parsed["meta_description"],
            canonical=parsed["canonical"],
            lang=parsed["lang"],
            headings=parsed["headings"],
            word_count=parsed["word_count"],
            has_faq=contains_faq(parsed["text_content"], parsed["headings"]),
            has_author=has_author_signals(parsed["text_content"]),
            has_publish_date=has_publish_date(parsed["text_content"]),
            has_quantified_data=has_quantified_data(parsed["text_content"]),
            has_reference_section=has_reference_section(parsed["text_content"], parsed["headings"]),
            has_inline_citations=has_inline_citations(parsed["text_content"]),
            has_tldr=has_tldr_summary(parsed["text_content"], parsed["headings"]),
            has_update_log=has_update_log(parsed["text_content"], parsed["headings"]),
            answer_first=is_answer_first(parsed["text_content"]),
            heading_quality_score=heading_quality["score"],
            information_density_score=information_density["score"],
            chunk_structure_score=chunk_structure["score"],
            internal_link_count=link_context["internal_link_count"],
            external_link_count=link_context["external_link_count"],
            descriptive_internal_link_ratio=link_context["descriptive_internal_link_ratio"],
            descriptive_external_link_ratio=link_context["descriptive_external_link_ratio"],
            json_ld_summary=schema_summary,
            json_ld_blocks=parsed["json_ld_blocks"],
            entity_signals=entity_signals,
            text_excerpt=parsed["text_excerpt"],
        )

    def _aggregate_schema_summary(self, page_profiles: dict[str, PageProfile]) -> dict:
        """合并所有页面的 JSON-LD 块，生成全站 Schema 摘要。"""
        blocks: list[str] = []
        page_summaries: list[dict] = []
        for profile in page_profiles.values():
            blocks.extend(profile.json_ld_blocks)
            if profile.json_ld_summary:
                page_summaries.append(profile.json_ld_summary)

        aggregated = extract_schema_summary(blocks)
        if page_summaries:
            aggregated["has_date_published"] = aggregated["has_date_published"] or any(
                item.get("has_date_published") for item in page_summaries
            )
            aggregated["has_date_modified"] = aggregated["has_date_modified"] or any(
                item.get("has_date_modified") for item in page_summaries
            )
            aggregated["has_breadcrumb_list"] = aggregated["has_breadcrumb_list"] or any(
                item.get("has_breadcrumb_list") for item in page_summaries
            )
            aggregated["avg_visible_alignment_score"] = int(
                round(
                    sum(int(item.get("visible_alignment_score", 0)) for item in page_summaries)
                    / max(len(page_summaries), 1)
                )
            )
            aggregated["pages_with_machine_dates"] = sum(
                1 for item in page_summaries if item.get("has_date_published") or item.get("has_date_modified")
            )
        else:
            aggregated["avg_visible_alignment_score"] = 0
            aggregated["pages_with_machine_dates"] = 0
        return aggregated

    def _aggregate_site_signals(self, page_profiles: dict[str, PageProfile]) -> SiteSignals:
        """跨页面聚合实体信号。"""
        if not page_profiles:
            return SiteSignals()

        company_name = None
        homepage_mentions = 0
        merged = SiteSignals()
        for profile in page_profiles.values():
            signals = profile.entity_signals
            company_name = company_name or signals.detected_company_name
            homepage_mentions = max(homepage_mentions, signals.homepage_brand_mentions)
            merged.company_name_detected = merged.company_name_detected or signals.company_name_detected
            merged.address_detected = merged.address_detected or signals.address_detected
            merged.phone_detected = merged.phone_detected or signals.phone_detected
            merged.email_detected = merged.email_detected or signals.email_detected
            merged.awards_detected = merged.awards_detected or signals.awards_detected
            merged.certifications_detected = merged.certifications_detected or signals.certifications_detected
            merged.same_as_detected = merged.same_as_detected or signals.same_as_detected
        merged.detected_company_name = company_name
        merged.homepage_brand_mentions = homepage_mentions
        return merged

    def _merge_candidate_urls(self, *groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for url in group:
                if not url:
                    continue
                normalized = normalize_url(url)
                if normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged

    def _priority_for_url_type(self, url_type: str) -> int:
        if url_type == "homepage":
            return 0
        if url_type in {"about", "contact", "landing"}:
            return 10
        if url_type in {"blog", "product", "docs", "case_study", "faq"}:
            return 20
        return 50

    async def _load_or_fetch_page_profile(
        self,
        client: httpx.AsyncClient,
        page_type: str,
        page_url: str,
        *,
        scope_url: str,
        site_id: int | None = None,
        cached_snapshots: dict[str, PageProfile] | None = None,
        asset_stats: dict[str, int] | None = None,
        discovery_source: str = "unknown",
    ) -> PageProfile | None:
        """优先复用 MySQL 页面快照，否则执行网络抓取。"""
        normalized_url = normalize_url(page_url)
        cached_profile = (cached_snapshots or {}).get(normalized_url)
        if cached_profile:
            if asset_stats is not None:
                asset_stats["reused"] = asset_stats.get("reused", 0) + 1
            return cached_profile.model_copy(update={"page_type": page_type})

        try:
            response = await fetch_url(page_url, client=client)
        except Exception:
            return None
        if response.status_code >= 400:
            return None

        parsed = parse_html(response.final_url, response.text, scope_url=scope_url)
        profile = self._build_page_profile(page_type=page_type, final_url=response.final_url, parsed=parsed)
        if asset_stats is not None:
            asset_stats["fetched"] = asset_stats.get("fetched", 0) + 1
        if self.asset_store.enabled and site_id is not None:
            await self.asset_store.save_page_snapshot(
                site_id=site_id,
                page_url=normalized_url,
                final_url=response.final_url,
                url_type=page_type or classify_url_type(response.final_url),
                discovery_source=discovery_source,
                status_code=response.status_code,
                parsed=parsed,
                page_profile=profile,
                raw_html=response.text,
            )
            if cached_snapshots is not None:
                cached_snapshots[normalized_url] = profile
                cached_snapshots[normalize_url(response.final_url)] = profile
        return profile

    async def _collect_page_profiles(
        self,
        client: httpx.AsyncClient,
        targets: dict[str, tuple[str, str]],
        *,
        scope_url: str,
        site_id: int | None = None,
        cached_snapshots: dict[str, PageProfile] | None = None,
        asset_stats: dict[str, int] | None = None,
        source_map: dict[str, str] | None = None,
    ) -> dict[str, PageProfile]:
        """限制并发地抓取或复用一批页面画像。"""
        if not targets:
            return {}
        semaphore = asyncio.Semaphore(max(1, settings.discovery_fetch_concurrency))
        results: dict[str, PageProfile] = {}

        async def worker(target_key: str, page_type: str, page_url: str) -> tuple[str, PageProfile | None]:
            async with semaphore:
                profile = await self._load_or_fetch_page_profile(
                    client,
                    page_type,
                    page_url,
                    scope_url=scope_url,
                    site_id=site_id,
                    cached_snapshots=cached_snapshots,
                    asset_stats=asset_stats,
                    discovery_source=(source_map or {}).get(normalize_url(page_url), "candidate"),
                )
                return target_key, profile

        futures = [
            asyncio.create_task(worker(target_key, page_type, page_url))
            for target_key, (page_type, page_url) in targets.items()
        ]
        for future in asyncio.as_completed(futures):
            target_key, profile = await future
            if profile is not None:
                results[target_key] = profile
        return results

    def _infer_additional_page_type(self, url: str) -> str:
        lowered = url.lower()
        for page_type, keywords in self.EXTRA_PAGE_PATTERNS.items():
            if any(keyword in lowered for keyword in keywords):
                return page_type
        return "page"

    def _full_audit_candidates(self, base_url: str, candidate_urls: list[str], existing_urls: set[str], max_pages: int) -> list[str]:
        """筛选 full audit 模式下的额外页面候选。"""
        deduped: list[str] = []
        for url in candidate_urls:
            if not url or url in existing_urls:
                continue
            if not is_internal_url(base_url, url):
                continue
            lowered = url.lower()
            if any(token in lowered for token in ["/tag/", "/author/", "/category/", "/page/", "utm_", "#"]):
                continue
            deduped.append(url)
        ordered = sorted(dict.fromkeys(deduped), key=lambda item: (len(item), item))
        return ordered[:max_pages]

    async def _fetch_entry_response(self, client: httpx.AsyncClient, url: str):
        """抓取入口页面，支持常见域名/协议变体回退。"""
        attempts: list[dict] = []
        last_error: AppError | None = None
        for candidate in entry_url_candidates(url):
            try:
                response = await fetch_url(candidate, client=client)
            except AppError as exc:
                last_error = exc
                attempts.append({"url": candidate, "error": str(exc.errors or exc.message)})
                continue
            if response.status_code < 400:
                return response
            attempts.append({"url": candidate, "status_code": response.status_code})

        raise AppError(
            502,
            "failed to fetch homepage",
            {
                "url": normalize_url(url),
                "attempts": attempts,
                "last_error": str(last_error.errors or last_error.message) if last_error else None,
            },
        )

    async def discover(self, url: str, *, full_audit: bool = False, max_pages: int = 12, force_refresh: bool = False) -> DiscoveryResult:
        """执行完整的站点快照发现流程。"""
        try:
            normalized_url = normalize_url(url)
        except ValueError as exc:
            raise AppError(400, "invalid URL", str(exc)) from exc

        initial_site = await self.asset_store.ensure_site(normalized_url) if self.asset_store.available else None
        if self.asset_store.available and initial_site and force_refresh:
            await self.asset_store.clear_site_content(initial_site.site_id)
        if self.asset_store.available and initial_site and not force_refresh:
            cached_discovery = await self.asset_store.load_cached_discovery(
                initial_site.site_id,
                full_audit=full_audit,
                max_pages=max_pages,
            )
            if cached_discovery:
                return cached_discovery

        asset_stats = {"reused": 0, "fetched": 0}
        source_map: dict[str, str] = {}
        cached_snapshots: dict[str, PageProfile] = {}
        actual_site = initial_site

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        ) as client:
            homepage_response = await self._fetch_entry_response(client, normalized_url)
            scope_root_url = get_scope_root(homepage_response.final_url)
            parsed_homepage = parse_html(homepage_response.final_url, homepage_response.text, scope_url=scope_root_url)

            if self.asset_store.available:
                actual_site = await self.asset_store.ensure_site(homepage_response.final_url)
                if self.asset_store.available and actual_site and force_refresh:
                    await self.asset_store.clear_site_content(actual_site.site_id)
                if self.asset_store.available and actual_site and not force_refresh and (not initial_site or actual_site.site_id != initial_site.site_id):
                    redirected_cached = await self.asset_store.load_cached_discovery(
                        actual_site.site_id,
                        full_audit=full_audit,
                        max_pages=max_pages,
                    )
                    if redirected_cached:
                        return redirected_cached
                if actual_site:
                    cached_snapshots = await self.asset_store.load_snapshot_map(actual_site.site_id)
                    stored_urls = await self.asset_store.load_site_urls(actual_site.site_id)
                    for row in stored_urls:
                        source_map[row.normalized_url] = row.discovery_source
                else:
                    stored_urls = []
            else:
                stored_urls = []

            target_domain = registered_domain(homepage_response.final_url)
            site_root_url = get_site_root(homepage_response.final_url)
            input_is_likely_homepage = is_likely_homepage_url(homepage_response.final_url)
            robots_result, llms_result, backlinks_result = await asyncio.gather(
                inspect_robots(homepage_response.final_url, client=client),
                inspect_llms(homepage_response.final_url, client=client),
                self.backlink_service.fetch_overview(target_domain, client=client),
            )
            sitemap_result = await inspect_sitemap(
                homepage_response.final_url,
                client=client,
                candidate_urls=robots_result.sitemaps or None,
            )

            homepage_link_urls = [item["url"] for item in parsed_homepage["internal_links"]]
            for item in sitemap_result.discovered_urls:
                source_map[normalize_url(item)] = "sitemap"
            for item in homepage_link_urls:
                source_map.setdefault(normalize_url(item), "internal_links")

            known_urls = [row.final_url or row.normalized_url for row in stored_urls]
            candidate_urls = self._merge_candidate_urls(known_urls, sitemap_result.discovered_urls, homepage_link_urls)
            scoped_candidate_urls = [item for item in candidate_urls if is_internal_url(scope_root_url, item)]
            key_pages = select_key_pages(scoped_candidate_urls)

            homepage_profile = self._build_page_profile(
                page_type="homepage",
                final_url=homepage_response.final_url,
                parsed=parsed_homepage,
            )
            page_profiles: dict[str, PageProfile] = {"homepage": homepage_profile}
            asset_stats["fetched"] += 1
            if self.asset_store.available and actual_site:
                await self.asset_store.save_page_snapshot(
                    site_id=actual_site.site_id,
                    page_url=homepage_response.final_url,
                    final_url=homepage_response.final_url,
                    url_type="homepage",
                    discovery_source="entry",
                    status_code=homepage_response.status_code,
                    parsed=parsed_homepage,
                    page_profile=homepage_profile,
                    raw_html=homepage_response.text,
                )
                cached_snapshots[normalize_url(homepage_response.final_url)] = homepage_profile
                source_map[normalize_url(homepage_response.final_url)] = "entry"

            snapshot_targets = {
                page_type: (page_type, page_url)
                for page_type, page_url in {
                    "about": key_pages.about,
                    "service": key_pages.service,
                    "article": key_pages.article,
                    "case_study": key_pages.case_study,
                }.items()
                if page_url
            }
            page_profiles.update(
                await self._collect_page_profiles(
                    client,
                    snapshot_targets,
                    scope_url=scope_root_url,
                    site_id=actual_site.site_id if actual_site else None,
                    cached_snapshots=cached_snapshots,
                    asset_stats=asset_stats,
                    source_map=source_map,
                )
            )

            additional_page_profiles: list[PageProfile] = []
            if full_audit:
                existing_urls = {profile.final_url for profile in page_profiles.values()}
                extra_needed = max(0, max_pages - len(page_profiles))
                extra_candidates = self._full_audit_candidates(
                    scope_root_url,
                    scoped_candidate_urls,
                    existing_urls,
                    extra_needed,
                )
                if extra_candidates:
                    extra_targets = {
                        candidate: (self._infer_additional_page_type(candidate), candidate)
                        for candidate in extra_candidates
                    }
                    extra_profiles = await self._collect_page_profiles(
                        client,
                        extra_targets,
                        scope_url=scope_root_url,
                        site_id=actual_site.site_id if actual_site else None,
                        cached_snapshots=cached_snapshots,
                        asset_stats=asset_stats,
                        source_map=source_map,
                    )
                    additional_page_profiles.extend(extra_profiles.values())

        if page_profiles.get("about"):
            key_pages.about = page_profiles["about"].final_url
        if page_profiles.get("service"):
            key_pages.service = page_profiles["service"].final_url
        if page_profiles.get("article"):
            key_pages.article = page_profiles["article"].final_url
        if page_profiles.get("case_study"):
            key_pages.case_study = page_profiles["case_study"].final_url

        combined_profiles = {**page_profiles}
        for index, profile in enumerate(additional_page_profiles, start=1):
            combined_profiles[f"additional_{index}"] = profile
        schema_summary = self._aggregate_schema_summary(combined_profiles)
        site_signals = self._aggregate_site_signals(combined_profiles)
        business_type = infer_business_type(
            parsed_homepage["title"],
            parsed_homepage["meta_description"],
            parsed_homepage["text_content"],
        )
        input_scope_warning = (
            "Input URL does not look like a homepage. GEO site-level scores may be directionally useful but can be biased "
            "because homepage-derived signals are being evaluated from a deeper page."
            if not input_is_likely_homepage
            else None
        )

        result = DiscoveryResult(
            url=url,
            normalized_url=normalized_url,
            final_url=homepage_response.final_url,
            site_root_url=site_root_url,
            scope_root_url=scope_root_url,
            domain=target_domain,
            fetch=FetchMetadata(
                final_url=homepage_response.final_url,
                status_code=homepage_response.status_code,
                headers=homepage_response.headers,
                response_time_ms=homepage_response.response_time_ms,
            ),
            homepage=HomepageExtract.model_validate(parsed_homepage),
            robots=robots_result,
            sitemap=sitemap_result,
            llms=llms_result,
            business_type=business_type,
            key_pages=key_pages,
            schema_summary=schema_summary,
            site_signals=site_signals,
            backlinks=backlinks_result,
            page_profiles=page_profiles,
            additional_page_profiles=additional_page_profiles,
            input_is_likely_homepage=input_is_likely_homepage,
            input_scope_warning=input_scope_warning,
            full_audit_enabled=full_audit,
            requested_max_pages=max_pages,
            profiled_page_count=len(page_profiles) + len(additional_page_profiles),
            site_snapshot_version=self.SNAPSHOT_VERSION,
        )

        if self.asset_store.available and actual_site:
            url_items: list[dict[str, str | int | None]] = []
            seen_urls: set[str] = set()

            def register_url(candidate_url: str, url_type: str | None = None, source: str | None = None) -> None:
                normalized_candidate = normalize_url(candidate_url)
                if normalized_candidate in seen_urls:
                    return
                seen_urls.add(normalized_candidate)
                resolved_type = url_type or classify_url_type(normalized_candidate)
                url_items.append(
                    {
                        "normalized_url": normalized_candidate,
                        "final_url": normalized_candidate,
                        "url_type": resolved_type,
                        "discovery_source": source or source_map.get(normalized_candidate) or "unknown",
                        "priority": self._priority_for_url_type(resolved_type),
                        "fetch_status": "success" if normalized_candidate in cached_snapshots else "pending",
                    }
                )

            register_url(homepage_response.final_url, "homepage", "entry")
            for candidate in scoped_candidate_urls:
                register_url(candidate, source=source_map.get(candidate))
            for page_type, profile in page_profiles.items():
                register_url(profile.final_url, "homepage" if page_type == "homepage" else page_type, source_map.get(profile.final_url))
            for profile in additional_page_profiles:
                register_url(profile.final_url, profile.page_type, source_map.get(profile.final_url))

            result.asset_summary = await self.asset_store.save_discovery(
                site_id=actual_site.site_id,
                discovery=result,
                url_items=url_items,
                reused_snapshot_count=asset_stats["reused"],
                fetched_snapshot_count=asset_stats["fetched"],
            )
        else:
            result.asset_summary.backend = "file"
            result.asset_summary.note = "MySQL asset storage is disabled; discovery uses live fetch plus file cache."

        return result
