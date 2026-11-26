from __future__ import annotations

from collections import deque
import re
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from app.core.config import settings
from app.models.discovery import SitemapResult
from app.utils.fetcher import fetch_url
from app.utils.url_utils import get_site_root

DIRTY_SITEMAP_URL_RE = re.compile(r"(?:[?&](?:utm_|sessionid|phpsessid|jsessionid|sid|replytocom)=|;jsessionid=|#)", re.I)


def _strip_ns(tag: str) -> str:
    """去除 XML 命名空间前缀（如 {http://www.sitemaps.org/schemas/sitemap/0.9}urlset → urlset）"""
    return tag.split("}", 1)[-1]


def _parse_sitemap_details(xml_text: str) -> tuple[list[str], list[str], int, bool]:
    """解析 Sitemap XML，返回 (URL 列表, 子 Sitemap 列表, 有效 lastmod 数量, 是否 XML 解析失败)"""
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        return [], [], 0, True

    tag = _strip_ns(root.tag)
    urls: list[str] = []
    sitemap_indexes: list[str] = []
    lastmod_count = 0

    if tag == "urlset":
        for entry in root.findall(".//{*}url"):
            loc = entry.find("{*}loc")
            if loc is not None and loc.text and loc.text.strip():
                urls.append(loc.text.strip())
                lastmod = entry.find("{*}lastmod")
                if lastmod is not None and lastmod.text and lastmod.text.strip():
                    lastmod_count += 1
        if not urls:
            for node in root.findall(".//{*}loc"):
                if node.text and node.text.strip():
                    urls.append(node.text.strip())
    elif tag == "sitemapindex":
        for entry in root.findall(".//{*}sitemap"):
            loc = entry.find("{*}loc")
            if loc is not None and loc.text and loc.text.strip():
                sitemap_indexes.append(loc.text.strip())
                lastmod = entry.find("{*}lastmod")
                if lastmod is not None and lastmod.text and lastmod.text.strip():
                    lastmod_count += 1
        if not sitemap_indexes:
            for node in root.findall(".//{*}loc"):
                if node.text and node.text.strip():
                    sitemap_indexes.append(node.text.strip())

    return urls, sitemap_indexes, lastmod_count, False


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """解析 Sitemap XML，返回 (URL 列表, 子 Sitemap 列表)"""
    urls, sitemap_indexes, _, _ = _parse_sitemap_details(xml_text)
    return urls, sitemap_indexes


async def inspect_sitemap(
    base_url: str,
    client: httpx.AsyncClient | None = None,
    candidate_urls: list[str] | None = None,
) -> SitemapResult:
    """发现并解析站点的 Sitemap，收集 URL 样本与质量指标"""
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
    invalid_xml = False
    has_sitemap_index = False
    lastmod_count = 0
    total_url_entries = 0

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
        urls, nested_sitemaps, entry_lastmod, parse_failed = _parse_sitemap_details(response.text)
        if parse_failed:
            invalid_xml = True
            continue

        if urls:
            total_url_entries += len(urls)
            lastmod_count += entry_lastmod
            for item in urls:
                if item not in discovered_urls:
                    discovered_urls.append(item)
                if len(discovered_urls) >= settings.max_sitemap_urls:
                    break

        if nested_sitemaps:
            has_sitemap_index = True
            if sitemap_index_count < settings.max_sitemap_indexes:
                sitemap_index_count += 1
                for item in nested_sitemaps:
                    if item not in visited:
                        pending.append(item)

    sampled = discovered_urls[: settings.max_sitemap_urls]
    non_https_urls = [u for u in sampled if urlparse(u).scheme.lower() == "http"][:20]
    dirty_urls = [u for u in sampled if DIRTY_SITEMAP_URL_RE.search(u)][:20]
    lastmod_ratio = round(min(1.0, lastmod_count / total_url_entries), 4) if total_url_entries else 0.0

    return SitemapResult(
        url=primary_url,
        exists=primary_url is not None and not (invalid_xml and not sampled and not has_sitemap_index),
        status_code=status_code,
        discovered_urls=sampled,
        total_urls_sampled=len(sampled),
        invalid_xml=invalid_xml and not sampled and not has_sitemap_index,
        has_sitemap_index=has_sitemap_index,
        non_https_urls=non_https_urls,
        dirty_urls=dirty_urls,
        lastmod_count=lastmod_count,
        lastmod_ratio=lastmod_ratio,
    )
