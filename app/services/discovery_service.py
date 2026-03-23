from __future__ import annotations

import asyncio

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.discovery import DiscoveryResult, FetchMetadata, HomepageExtract
from app.utils.fetcher import fetch_url
from app.utils.heuristics import detect_site_signals, infer_business_type, select_key_pages
from app.utils.html_parser import parse_html
from app.utils.llms_parser import inspect_llms
from app.utils.robots_parser import inspect_robots
from app.utils.schema_extractor import extract_schema_summary
from app.utils.sitemap_parser import inspect_sitemap
from app.utils.url_utils import normalize_url, registered_domain


class DiscoveryService:
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

            robots_result, llms_result = await asyncio.gather(
                inspect_robots(homepage_response.final_url, client=client),
                inspect_llms(homepage_response.final_url, client=client),
            )
            sitemap_result = await inspect_sitemap(
                homepage_response.final_url,
                client=client,
                candidate_urls=robots_result.sitemaps or None,
            )

        schema_summary = extract_schema_summary(parsed_homepage["json_ld_blocks"])
        candidate_urls = sitemap_result.discovered_urls + [
            item["url"] for item in parsed_homepage["internal_links"]
        ]
        key_pages = select_key_pages(candidate_urls)
        site_signals = detect_site_signals(
            text=parsed_homepage["text_content"],
            schema_summary=schema_summary,
            key_pages=key_pages,
            title=parsed_homepage["title"],
        )
        business_type = infer_business_type(
            parsed_homepage["title"],
            parsed_homepage["meta_description"],
            parsed_homepage["text_content"],
        )

        return DiscoveryResult(
            url=url,
            normalized_url=normalized_url,
            final_url=homepage_response.final_url,
            domain=registered_domain(homepage_response.final_url),
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
        )
