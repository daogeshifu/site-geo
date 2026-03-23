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
from app.services.backlink_service import BacklinkService
from app.utils.fetcher import fetch_url
from app.utils.heuristics import detect_site_signals, infer_business_type, select_key_pages
from app.utils.html_parser import parse_html
from app.utils.llms_parser import inspect_llms
from app.utils.robots_parser import inspect_robots
from app.utils.schema_extractor import extract_schema_summary
from app.utils.sitemap_parser import inspect_sitemap
from app.utils.text_analyzer import (
    contains_faq,
    estimate_information_density,
    evaluate_chunk_structure,
    evaluate_heading_quality,
    has_author_signals,
    has_publish_date,
    has_quantified_data,
    is_answer_first,
)
from app.utils.url_utils import normalize_url, registered_domain


class DiscoveryService:
    SNAPSHOT_VERSION = "snapshot-v2"

    def __init__(self) -> None:
        self.backlink_service = BacklinkService()

    def _build_page_profile(
        self,
        *,
        page_type: str,
        final_url: str,
        parsed: dict,
    ) -> PageProfile:
        schema_summary = extract_schema_summary(parsed["json_ld_blocks"])
        entity_signals = detect_site_signals(
            text=parsed["text_content"],
            schema_summary=schema_summary,
            key_pages=KeyPages(),
            title=parsed["title"],
        )
        heading_quality = evaluate_heading_quality(parsed["headings"])
        information_density = estimate_information_density(parsed["text_content"], parsed["headings"])
        chunk_structure = evaluate_chunk_structure(parsed["text_content"], parsed["headings"])
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
            answer_first=is_answer_first(parsed["text_content"]),
            heading_quality_score=heading_quality["score"],
            information_density_score=information_density["score"],
            chunk_structure_score=chunk_structure["score"],
            json_ld_summary=schema_summary,
            json_ld_blocks=parsed["json_ld_blocks"],
            entity_signals=entity_signals,
            text_excerpt=parsed["text_excerpt"],
        )

    def _aggregate_schema_summary(self, page_profiles: dict[str, PageProfile]) -> dict:
        blocks: list[str] = []
        for profile in page_profiles.values():
            blocks.extend(profile.json_ld_blocks)
        return extract_schema_summary(blocks)

    def _aggregate_site_signals(self, page_profiles: dict[str, PageProfile]) -> SiteSignals:
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

    async def _fetch_page_profile(
        self,
        client: httpx.AsyncClient,
        page_type: str,
        page_url: str,
    ) -> PageProfile | None:
        try:
            response = await fetch_url(page_url, client=client)
        except Exception:
            return None
        if response.status_code >= 400:
            return None
        parsed = parse_html(response.final_url, response.text)
        return self._build_page_profile(page_type=page_type, final_url=response.final_url, parsed=parsed)

    async def discover(self, url: str) -> DiscoveryResult:
        try:
            normalized_url = normalize_url(url)
        except ValueError as exc:
            raise AppError(400, "invalid URL", str(exc)) from exc

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        ) as client:
            homepage_response = await fetch_url(normalized_url, client=client)
            if homepage_response.status_code >= 400:
                raise AppError(
                    502,
                    "failed to fetch homepage",
                    {"url": normalized_url, "status_code": homepage_response.status_code},
                )
            parsed_homepage = parse_html(homepage_response.final_url, homepage_response.text)

            target_domain = registered_domain(homepage_response.final_url)
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

            candidate_urls = sitemap_result.discovered_urls + [
                item["url"] for item in parsed_homepage["internal_links"]
            ]
            key_pages = select_key_pages(candidate_urls)

            page_profiles: dict[str, PageProfile] = {
                "homepage": self._build_page_profile(
                    page_type="homepage",
                    final_url=homepage_response.final_url,
                    parsed=parsed_homepage,
                )
            }

            snapshot_targets = {
                "about": key_pages.about,
                "service": key_pages.service,
                "article": key_pages.article,
                "case_study": key_pages.case_study,
            }
            coroutines = {
                page_type: self._fetch_page_profile(client, page_type, page_url)
                for page_type, page_url in snapshot_targets.items()
                if page_url
            }
            if coroutines:
                results = await asyncio.gather(*coroutines.values(), return_exceptions=True)
                for page_type, result in zip(coroutines.keys(), results):
                    if isinstance(result, Exception) or result is None:
                        continue
                    page_profiles[page_type] = result

        if page_profiles.get("about"):
            key_pages.about = page_profiles["about"].final_url
        if page_profiles.get("service"):
            key_pages.service = page_profiles["service"].final_url
        if page_profiles.get("article"):
            key_pages.article = page_profiles["article"].final_url
        if page_profiles.get("case_study"):
            key_pages.case_study = page_profiles["case_study"].final_url

        schema_summary = self._aggregate_schema_summary(page_profiles)
        site_signals = self._aggregate_site_signals(page_profiles)
        business_type = infer_business_type(
            parsed_homepage["title"],
            parsed_homepage["meta_description"],
            parsed_homepage["text_content"],
        )

        return DiscoveryResult(
            url=url,
            normalized_url=normalized_url,
            final_url=homepage_response.final_url,
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
            site_snapshot_version=self.SNAPSHOT_VERSION,
        )
