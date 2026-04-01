from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.utils.url_utils import ensure_absolute_url, is_internal_url


def _first_content(items: list[Any]) -> str | None:
    """从 meta 标签列表中提取第一个非空的 content 属性值"""
    for item in items:
        content = item.get("content")
        if content:
            return content.strip()
    return None


def parse_html(base_url: str, html: str, *, scope_url: str | None = None) -> dict[str, Any]:
    """解析 HTML 页面，提取 SEO/GEO 审计所需的所有结构化信息

    Args:
        base_url: 页面的最终 URL（用于解析相对链接）
        html: 原始 HTML 字符串

    Returns:
        包含以下键的字典：
        title, meta_description, canonical, lang, viewport, h1,
        headings, hreflang, internal_links, external_links,
        images, scripts, stylesheets, json_ld_blocks,
        open_graph, twitter_cards, word_count, html_length,
        text_excerpt, text_content
    """
    soup = BeautifulSoup(html or "", "lxml")

    # 基础 SEO 元数据
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta_description = _first_content(soup.find_all("meta", attrs={"name": re.compile("^description$", re.I)}))
    viewport = _first_content(soup.find_all("meta", attrs={"name": re.compile("^viewport$", re.I)}))
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = canonical_tag.get("href", "").strip() or None if canonical_tag else None
    lang = soup.html.get("lang", "").strip() or None if soup.html else None

    # 主标题 H1
    h1 = None
    if soup.find("h1"):
        h1 = soup.find("h1").get_text(" ", strip=True) or None

    # 所有标题标签（h1-h6），用于标题层级质量评估
    headings = [
        {"level": tag.name, "text": tag.get_text(" ", strip=True)}
        for tag in soup.find_all(re.compile("^h[1-6]$"))
        if tag.get_text(" ", strip=True)
    ]

    # 链接提取：按内部/外部分类，去重
    internal_links: list[dict[str, str | None]] = []
    external_links: list[dict[str, str | None]] = []
    seen_internal: set[str] = set()
    seen_external: set[str] = set()
    for link in soup.find_all("a", href=True):
        absolute_url = ensure_absolute_url(base_url, link["href"]).strip()
        text = link.get_text(" ", strip=True) or None
        item = {"url": absolute_url, "text": text}
        if is_internal_url(scope_url or base_url, absolute_url):
            if absolute_url not in seen_internal:
                internal_links.append(item)
                seen_internal.add(absolute_url)
        else:
            if absolute_url not in seen_external:
                external_links.append(item)
                seen_external.add(absolute_url)

    # 图片提取：包含 src/alt/loading/width/height，用于图片优化评估
    images = [
        {
            "src": ensure_absolute_url(base_url, image.get("src", "")),
            "alt": image.get("alt"),
            "loading": image.get("loading"),  # lazy/eager
            "width": image.get("width"),
            "height": image.get("height"),
        }
        for image in soup.find_all("img", src=True)
    ]

    # 脚本提取：包含 async/defer 属性，用于渲染阻塞风险评估
    scripts = [
        {
            "src": ensure_absolute_url(base_url, script.get("src", "")) if script.get("src") else None,
            "is_inline": not bool(script.get("src")),
            "async_attr": script.has_attr("async"),
            "defer_attr": script.has_attr("defer"),
            "type": script.get("type"),
        }
        for script in soup.find_all("script")
    ]

    # 样式表提取，用于渲染阻塞评估
    stylesheets = [
        {"href": ensure_absolute_url(base_url, link.get("href", "")), "media": link.get("media")}
        for link in soup.find_all("link", href=True, rel=lambda value: value and "stylesheet" in value)
    ]

    # JSON-LD 结构化数据块（完整字符串，供 Schema 解析器使用）
    json_ld_blocks = []
    for block in soup.find_all("script", attrs={"type": "application/ld+json"}):
        content = block.get_text(" ", strip=True)
        if content:
            json_ld_blocks.append(content)

    # Open Graph 社交元数据（og: 前缀）
    open_graph: dict[str, str] = {}
    # Twitter Cards 元数据（twitter: 前缀）
    twitter_cards: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "")
        name = meta.get("name", "")
        content = meta.get("content", "").strip()
        if prop.startswith("og:") and content:
            open_graph[prop] = content
        if name.startswith("twitter:") and content:
            twitter_cards[name] = content

    # hreflang 多语言链接标签
    hreflang = [
        link.get("hreflang", "").strip()
        for link in soup.find_all("link", attrs={"rel": lambda value: value and "alternate" in value, "hreflang": True})
        if link.get("hreflang", "").strip()
    ]

    # 提取纯文本，用于词数统计和内容分析
    text_content = soup.get_text(" ", strip=True)
    words = re.findall(r"\b\w+\b", text_content)

    return {
        "title": title,
        "meta_description": meta_description,
        "canonical": canonical,
        "lang": lang,
        "viewport": viewport,
        "h1": h1,
        "headings": headings,
        "hreflang": hreflang,
        "internal_links": internal_links,
        "external_links": external_links,
        "images": images,
        "scripts": scripts,
        "stylesheets": stylesheets,
        "json_ld_blocks": json_ld_blocks,
        "open_graph": open_graph,
        "twitter_cards": twitter_cards,
        "word_count": len(words),
        "html_length": len(html or ""),    # 原始 HTML 长度，用于 SSR 信号判断
        "text_excerpt": text_content[:400],  # 前 400 字符摘要
        "text_content": text_content,
    }
