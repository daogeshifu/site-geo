from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

import tldextract


EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=None)


def _normalize_embedded_absolute(href: str) -> str:
    candidate = href.strip()
    if candidate.startswith("/http://") or candidate.startswith("/https://"):
        return candidate.lstrip("/")
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    return candidate


def normalize_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        raise ValueError("URL is required")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    path = parsed.path or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
        path=path,
    )
    return urlunparse(normalized)


def get_site_root(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


def ensure_absolute_url(base_url: str, href: str) -> str:
    normalized_href = _normalize_embedded_absolute(href)
    return urljoin(base_url, normalized_href)


def registered_domain(url: str) -> str:
    extracted = EXTRACTOR(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return extracted.domain or ""


def is_internal_url(base_url: str, candidate_url: str) -> bool:
    return registered_domain(base_url) == registered_domain(candidate_url)
