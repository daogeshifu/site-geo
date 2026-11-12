"""Task-scoped URL inventory. Unknown measurements remain unknown."""
from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from app.utils.url_utils import is_internal_url, normalize_url


def task_site_pages(task) -> list[dict]:
    result = task.result or {}
    step = task.steps.get("discovery")
    discovery = result.get("discovery") or (step.data if step else None) or {}
    if not isinstance(discovery, dict):
        return []
    scope = discovery.get("scope_root_url") or discovery.get("final_url") or task.url
    pages: dict[str, dict] = {}

    def add(url, data=None, source="sitemap"):
        if not url or urlparse(url).scheme not in {"http", "https"} or not is_internal_url(scope, url):
            return
        key = normalize_url(url)
        page = pages.setdefault(key, {"id": hashlib.sha256(key.encode()).hexdigest()[:24], "url": key, "discovery_source": source})
        if data:
            # A newer SEO fetch is authoritative; do not mix its capture metadata
            # with a different discovery fetch when a field is missing.
            page.update(data)
            page["url"] = key
            page["discovery_source"] = source
            page["has_snapshot"] = True
        page["source_available"] = bool(page.get("source_key"))

    for name, profile in discovery.get("page_profiles", {}).items():
        add(profile.get("final_url"), {**profile, "page_type": name}, "discovery")
    for profile in discovery.get("additional_page_profiles", []):
        add(profile.get("final_url"), profile, "full_audit")
    geo_step = task.steps.get("sgeo") or task.steps.get("geo")
    geo = result.get("sgeo") or result.get("geo") or (geo_step.data if geo_step else None) or {}
    sample_source = "sgeo_sample" if result.get("sgeo") or (geo_step and geo_step.name == "sgeo") else "geo_sample"
    for sample in geo.get("pages", []):
        add(sample.get("url") or sample.get("final_url"), sample, sample_source)
    seo_step = task.steps.get("seo")
    seo = {} if result.get("sgeo") else result.get("seo") or (seo_step.data if seo_step else None) or {}
    for sample in seo.get("sampled_pages", []):
        data = {"fetched_at": None, "source_key": None, "response_headers": {}, "response_time_ms": None, **sample}
        add(sample.get("url") or sample.get("final_url"), data, "seo_sample")
    for url in discovery.get("sitemap", {}).get("discovered_urls", []):
        add(url)
    for link in discovery.get("homepage", {}).get("internal_links", []):
        add(link.get("url") if isinstance(link, dict) else link, source="internal_link")
    return list(pages.values())
