from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def count_words(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text or ""))


def initial_status_code(
    final_status_code: int | None,
    redirect_chain: list[dict[str, Any]] | None,
) -> int | None:
    """Return the response code for the originally requested URL."""
    if redirect_chain:
        value = redirect_chain[0].get("status_code")
        return int(value) if isinstance(value, int) else final_status_code
    return final_status_code


def parse_retry_after(
    value: str | None,
    *,
    now: datetime | None = None,
) -> int | None:
    """Parse Retry-After seconds or an HTTP date into a non-negative delay."""
    if not value:
        return None
    normalized = value.strip()
    if normalized.isdigit():
        return max(0, int(normalized))
    try:
        retry_at = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return max(0, int((retry_at - reference).total_seconds()))


def request_http_metadata(
    *,
    status_code: int | None,
    headers: dict[str, str] | None,
    redirect_chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Expose edge/rate-limit evidence without leaking all response headers."""
    normalized_headers = {
        str(key).lower(): str(value)
        for key, value in (headers or {}).items()
    }
    retry_after = normalized_headers.get("retry-after")
    return {
        "initial_status_code": initial_status_code(status_code, redirect_chain),
        "final_status_code": status_code,
        "outcome": (
            "rate_limited"
            if status_code == 429
            else "success"
            if status_code is not None and 200 <= status_code < 300
            else "redirect"
            if status_code is not None and 300 <= status_code < 400
            else "http_error"
            if status_code is not None
            else "network_error"
        ),
        "retry_after": retry_after,
        "retry_after_seconds": parse_retry_after(retry_after),
        "server": normalized_headers.get("server", ""),
        "cf_ray": normalized_headers.get("cf-ray", ""),
        "request_id": normalized_headers.get("x-request-id", ""),
    }


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
