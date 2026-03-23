from __future__ import annotations

from collections import deque
from xml.etree import ElementTree

import httpx

from app.core.config import settings
from app.models.discovery import SitemapResult
from app.utils.fetcher import fetch_url
from app.utils.url_utils import get_site_root


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        return [], []

    tag = _strip_ns(root.tag)
    urls: list[str] = []
    sitemap_indexes: list[str] = []

    if tag == "urlset":
        for node in root.findall(".//{*}loc"):
            if node.text:
                urls.append(node.text.strip())
    elif tag == "sitemapindex":
        for node in root.findall(".//{*}loc"):
            if node.text:
                sitemap_indexes.append(node.text.strip())

    return urls, sitemap_indexes


async def inspect_sitemap(
    base_url: str,
    client: httpx.AsyncClient | None = None,
    candidate_urls: list[str] | None = None,
) -> SitemapResult:
    default_candidates = [
        f"{get_site_root(base_url)}/sitemap.xml",
        f"{get_site_root(base_url)}/sitemap_index.xml",
    ]
    merged_candidates = (candidate_urls or []) + default_candidates
    pending = deque(dict.fromkeys(merged_candidates))
    visited: set[str] = set()
    discovered_urls: list[str] = []
    primary_url: str | None = None
    status_code: int | None = None
    sitemap_index_count = 0

    while pending and len(discovered_urls) < settings.max_sitemap_urls:
        current_url = pending.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        try:
            response = await fetch_url(current_url, client=client)
        except Exception:
            continue

        if response.status_code >= 400:
            status_code = response.status_code
            continue

        primary_url = primary_url or current_url
        status_code = response.status_code
        urls, nested_sitemaps = _parse_sitemap_xml(response.text)
        if urls:
            for item in urls:
                if item not in discovered_urls:
                    discovered_urls.append(item)
                if len(discovered_urls) >= settings.max_sitemap_urls:
                    break

        if nested_sitemaps and sitemap_index_count < settings.max_sitemap_indexes:
            sitemap_index_count += 1
            for item in nested_sitemaps:
                if item not in visited:
                    pending.append(item)

    return SitemapResult(
        url=primary_url,
        exists=primary_url is not None,
        status_code=status_code,
        discovered_urls=discovered_urls[: settings.max_sitemap_urls],
        total_urls_sampled=len(discovered_urls[: settings.max_sitemap_urls]),
    )
