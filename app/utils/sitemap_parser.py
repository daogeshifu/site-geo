from __future__ import annotations

from collections import deque
from xml.etree import ElementTree

import httpx

from app.core.config import settings
from app.models.discovery import SitemapResult
from app.utils.fetcher import fetch_url
from app.utils.url_utils import get_site_root


def _strip_ns(tag: str) -> str:
    """去除 XML 命名空间前缀（如 {http://www.sitemaps.org/schemas/sitemap/0.9}urlset → urlset）"""
    return tag.split("}", 1)[-1]


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """解析 Sitemap XML，返回 (URL 列表, 子 Sitemap 列表)

    支持两种格式：
    - urlset：标准 Sitemap，从 <loc> 提取 URL
    - sitemapindex：Sitemap 索引，从 <loc> 提取子 Sitemap URL
    """
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        return [], []

    tag = _strip_ns(root.tag)
    urls: list[str] = []
    sitemap_indexes: list[str] = []

    if tag == "urlset":
        # 标准 Sitemap：收集所有 <loc> 中的 URL
        for node in root.findall(".//{*}loc"):
            if node.text:
                urls.append(node.text.strip())
    elif tag == "sitemapindex":
        # Sitemap 索引：收集子 Sitemap 的 URL（待后续递归处理）
        for node in root.findall(".//{*}loc"):
            if node.text:
                sitemap_indexes.append(node.text.strip())

    return urls, sitemap_indexes


async def inspect_sitemap(
    base_url: str,
    client: httpx.AsyncClient | None = None,
    candidate_urls: list[str] | None = None,
) -> SitemapResult:
    """发现并解析站点的 Sitemap，收集 URL 样本

    优先级：robots.txt 中声明的 Sitemap > /sitemap.xml > /sitemap_index.xml
    支持 Sitemap 索引（多层 Sitemap），通过 BFS 递归发现子 Sitemap
    采样限制：settings.max_sitemap_urls（默认 50 个 URL）

    Args:
        base_url: 站点根 URL
        client: 可选的共享 HTTP 客户端
        candidate_urls: 候选 Sitemap URL（来自 robots.txt 的 Sitemap 指令）
    """
    default_candidates = [
        f"{get_site_root(base_url)}/sitemap.xml",
        f"{get_site_root(base_url)}/sitemap_index.xml",
    ]
    # 优先尝试候选 URL，再尝试默认路径
    merged_candidates = (candidate_urls or []) + default_candidates
    pending = deque(dict.fromkeys(merged_candidates))  # 去重并保持顺序
    visited: set[str] = set()
    discovered_urls: list[str] = []
    primary_url: str | None = None   # 第一个成功响应的 Sitemap URL
    status_code: int | None = None
    sitemap_index_count = 0  # 已处理的 Sitemap 索引数量（防止无限递归）

    while pending and len(discovered_urls) < settings.max_sitemap_urls:
        current_url = pending.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)
        try:
            response = await fetch_url(current_url, client=client)
        except Exception:
            continue  # 忽略单个 Sitemap 抓取失败

        if response.status_code >= 400:
            status_code = response.status_code
            continue

        primary_url = primary_url or current_url
        status_code = response.status_code
        urls, nested_sitemaps = _parse_sitemap_xml(response.text)

        # 收集 URL，避免重复，到达上限时停止
        if urls:
            for item in urls:
                if item not in discovered_urls:
                    discovered_urls.append(item)
                if len(discovered_urls) >= settings.max_sitemap_urls:
                    break

        # 处理 Sitemap 索引：限制最大深度
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
