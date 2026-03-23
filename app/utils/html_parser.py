from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from app.utils.url_utils import ensure_absolute_url, is_internal_url


def _first_content(items: list[Any]) -> str | None:
    for item in items:
        content = item.get("content")
        if content:
            return content.strip()
    return None


def parse_html(base_url: str, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta_description = _first_content(soup.find_all("meta", attrs={"name": re.compile("^description$", re.I)}))
    viewport = _first_content(soup.find_all("meta", attrs={"name": re.compile("^viewport$", re.I)}))
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = canonical_tag.get("href", "").strip() or None if canonical_tag else None
    lang = soup.html.get("lang", "").strip() or None if soup.html else None

    h1 = None
    if soup.find("h1"):
        h1 = soup.find("h1").get_text(" ", strip=True) or None

    headings = [
        {"level": tag.name, "text": tag.get_text(" ", strip=True)}
        for tag in soup.find_all(re.compile("^h[1-6]$"))
        if tag.get_text(" ", strip=True)
    ]

    internal_links: list[dict[str, str | None]] = []
    external_links: list[dict[str, str | None]] = []
    seen_internal: set[str] = set()
    seen_external: set[str] = set()
    for link in soup.find_all("a", href=True):
        absolute_url = ensure_absolute_url(base_url, link["href"]).strip()
        text = link.get_text(" ", strip=True) or None
        item = {"url": absolute_url, "text": text}
        if is_internal_url(base_url, absolute_url):
            if absolute_url not in seen_internal:
                internal_links.append(item)
                seen_internal.add(absolute_url)
        else:
            if absolute_url not in seen_external:
                external_links.append(item)
                seen_external.add(absolute_url)

    images = [
        {
            "src": ensure_absolute_url(base_url, image.get("src", "")),
            "alt": image.get("alt"),
            "loading": image.get("loading"),
            "width": image.get("width"),
            "height": image.get("height"),
        }
        for image in soup.find_all("img", src=True)
    ]

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

    stylesheets = [
        {"href": ensure_absolute_url(base_url, link.get("href", "")), "media": link.get("media")}
        for link in soup.find_all("link", href=True, rel=lambda value: value and "stylesheet" in value)
    ]

    json_ld_blocks = [
        block.string.strip()
        for block in soup.find_all("script", attrs={"type": "application/ld+json"})
        if block.string and block.string.strip()
    ]

    open_graph: dict[str, str] = {}
    twitter_cards: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "")
        name = meta.get("name", "")
        content = meta.get("content", "").strip()
        if prop.startswith("og:") and content:
            open_graph[prop] = content
        if name.startswith("twitter:") and content:
            twitter_cards[name] = content

    hreflang = [
        link.get("hreflang", "").strip()
        for link in soup.find_all("link", attrs={"rel": lambda value: value and "alternate" in value, "hreflang": True})
        if link.get("hreflang", "").strip()
    ]

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
        "html_length": len(html or ""),
        "text_excerpt": text_content[:400],
        "text_content": text_content,
    }
