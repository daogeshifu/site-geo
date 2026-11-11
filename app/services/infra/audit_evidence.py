"""Collect one bounded set of raw page evidence for both SEO and GEO."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.models.discovery import DiscoveryResult, PageProfile
from app.services.infra.page_sources import capture_page_metadata, read_page_source
from app.utils.fetcher import fetch_url
from app.utils.url_classifier import classify_url_type
from app.utils.url_utils import is_internal_url, normalize_url


@dataclass
class PageEvidence:
    url: str
    final_url: str
    page_type: str
    html: str | None = None
    status_code: int | None = None
    response_time_ms: int | None = None
    response_headers: dict = field(default_factory=dict)
    source_key: str | None = None
    source_truncated: bool = False
    fetched_at: str | None = None
    error: str | None = None
    reused: bool = False
    rendered_html: str | None = None
    render_note: str | None = None

    def metadata(self) -> dict:
        return {name: getattr(self, name) for name in (
            "status_code", "response_time_ms", "response_headers", "source_key",
            "source_truncated", "fetched_at",
        )}


def sample_candidates(discovery: DiscoveryResult, max_pages: int) -> list[tuple[str, str, PageProfile | None]]:
    """Round-robin page types; failures remain in the sample denominator."""
    candidates: dict[str, tuple[str, str, PageProfile | None]] = {}
    scope = discovery.scope_root_url or discovery.final_url

    def add(url: str, page_type: str = "page", profile: PageProfile | None = None) -> None:
        try:
            normalized = normalize_url(url)
        except ValueError:
            return
        if not is_internal_url(scope, normalized):
            return
        kind = {"blog": "article", "docs": "documentation", "landing": "service"}.get(
            page_type, page_type,
        )
        if kind == "page":
            kind = classify_url_type(normalized)
            kind = {"blog": "article", "docs": "documentation", "landing": "service"}.get(kind, kind)
            if kind == "page" and any(segment in urlparse(normalized).path.split("/") for segment in ("tools", "tool", "calculator")):
                kind = "tool"
        previous = candidates.get(normalized)
        if previous is None or (profile is not None and previous[2] is None):
            candidates[normalized] = (kind, normalized, profile)

    for key, profile in discovery.page_profiles.items():
        add(profile.final_url, profile.page_type or key, profile)
    add(discovery.final_url, "homepage")
    for profile in discovery.additional_page_profiles:
        add(profile.final_url, profile.page_type, profile)
    for kind in ("about", "service", "contact", "article", "case_study"):
        url = getattr(discovery.key_pages, kind, None)
        if url:
            add(url, kind)
    for link in discovery.homepage.internal_links:
        add(link.url)
    for url in discovery.sitemap.discovered_urls:
        add(url)
    groups: dict[str, list] = {}
    for item in candidates.values():
        groups.setdefault(item[0], []).append(item)
    selected = []
    while groups and len(selected) < max_pages:
        for kind in list(groups):
            selected.append(groups[kind].pop(0))
            if not groups[kind]:
                del groups[kind]
            if len(selected) >= max_pages:
                break
    return selected


async def collect_page_evidence(discovery: DiscoveryResult, max_pages: int) -> list[PageEvidence]:
    candidates = sample_candidates(discovery, max_pages)
    semaphore = asyncio.Semaphore(max(1, settings.discovery_fetch_concurrency))
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout_seconds), follow_redirects=True,
        headers={"User-Agent": settings.default_user_agent},
    ) as client:
        async def collect(kind, url, profile):
            item = PageEvidence(url=url, final_url=url, page_type=kind)
            if profile and profile.source_key:
                source = await read_page_source(profile.source_key)
                if source is not None and profile.status_code is not None:
                    item.html = source
                    item.final_url = profile.final_url
                    for name in item.metadata():
                        setattr(item, name, getattr(profile, name))
                    item.reused = True
                    return item
            async with semaphore:
                try:
                    response = await fetch_url(url, client=client)
                    item.final_url = response.final_url
                    if not is_internal_url(discovery.scope_root_url or discovery.final_url, item.final_url):
                        item.error = "Redirect left the audited host or language scope."
                        return item
                    item.html = response.text
                    for name, value in (await capture_page_metadata(response)).items():
                        setattr(item, name, value)
                except Exception as exc:
                    item.error = str(exc)
            return item

        return list(await asyncio.gather(*(collect(*item) for item in candidates)))
