from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def count_words(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text or ""))


def inspect_html(html: str, base_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    h1_tags = soup.find_all("h1")
    h1 = h1_tags[0].get_text(" ", strip=True) if h1_tags else ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = urljoin(base_url, canonical_tag.get("href", "")) if canonical_tag else ""

    directives: list[str] = []
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").strip().lower()
        if name in {"robots", "googlebot"}:
            directives.extend(
                item.strip().lower()
                for item in (meta.get("content") or "").split(",")
                if item.strip()
            )

    for node in soup(["script", "style", "noscript", "template", "svg"]):
        node.decompose()
    visible_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()

    host = (urlparse(base_url).hostname or "").lower()
    internal_links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url, anchor.get("href", ""))
        if (urlparse(absolute).hostname or "").lower() == host:
            internal_links.add(absolute.split("#", 1)[0])

    return {
        "title": title,
        "h1": h1,
        "h1_count": len(h1_tags),
        "canonical": canonical,
        "directives": sorted(set(directives)),
        "word_count": count_words(visible_text),
        "visible_text": visible_text,
        "text_preview": visible_text[:500],
        "internal_link_count": len(internal_links),
        "script_count": len(BeautifulSoup(html or "", "lxml").find_all("script")),
        "html_bytes": len((html or "").encode("utf-8", errors="ignore")),
    }


def issue(
    code: str,
    severity: str,
    title: str,
    detail: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "recommendation": recommendation,
    }


def status_from_issues(issues: list[dict[str, str]], *, score: int) -> str:
    severities = {item["severity"] for item in issues}
    if "critical" in severities or score < 50:
        return "failed"
    if severities.intersection({"high", "medium"}) or score < 80:
        return "warning"
    return "passed"
