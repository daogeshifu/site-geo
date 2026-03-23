from __future__ import annotations

from app.models.discovery import DiscoveryResult
from app.utils.heuristics import calculate_brand_authority


class BrandAuthorityService:
    """Reserved service boundary for future standalone brand-authority audit APIs."""

    def assess(self, discovery: DiscoveryResult) -> dict:
        return calculate_brand_authority(
            signals=discovery.site_signals,
            homepage=discovery.homepage.model_dump(),
            llms=discovery.llms,
            key_pages=discovery.key_pages,
            schema_summary=discovery.schema_summary,
            primary_domain=discovery.domain,
            sitemap_urls=discovery.robots.sitemaps,
            backlinks=discovery.backlinks,
        )
