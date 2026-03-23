from __future__ import annotations

import re
from typing import Any

from app.models.discovery import KeyPages, SiteSignals


BUSINESS_TYPE_RULES = {
    "agency": ["agency", "marketing", "seo", "growth"],
    "saas": ["platform", "software", "saas", "automation"],
    "ecommerce": ["shop", "store", "ecommerce", "product"],
    "local_service": ["clinic", "law firm", "dentist", "repair", "consulting"],
    "publisher": ["news", "blog", "media", "insights", "magazine"],
}

KEY_PAGE_KEYWORDS = {
    "about": ["about", "company", "关于"],
    "service": ["service", "services", "seo", "solution", "产品", "服务"],
    "contact": ["contact", "联系"],
    "article": ["blog", "news", "article", "insights", "posts"],
    "case_study": ["case", "study", "success", "work", "portfolio", "案例"],
}

ADDRESS_PATTERN = r"\b\d{1,6}\s+[A-Za-z0-9.\s]+(?:street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln)\b"
PHONE_PATTERN = r"(?:\+?\d[\d\s().-]{7,}\d)"
EMAIL_PATTERN = r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"


def infer_business_type(title: str | None, meta_description: str | None, text: str) -> str:
    haystack = " ".join(filter(None, [title, meta_description, text[:1000]])).lower()
    for business_type, keywords in BUSINESS_TYPE_RULES.items():
        if any(keyword in haystack for keyword in keywords):
            return business_type
    return "general_business"


def select_key_pages(candidate_urls: list[str]) -> KeyPages:
    result: dict[str, str | None] = {key: None for key in KEY_PAGE_KEYWORDS}
    ordered_urls = sorted(dict.fromkeys(candidate_urls), key=lambda item: (len(item), item))

    for page_type, keywords in KEY_PAGE_KEYWORDS.items():
        for url in ordered_urls:
            lowered = url.lower()
            if any(keyword.lower() in lowered for keyword in keywords):
                result[page_type] = url
                break

    return KeyPages(**result)


def detect_site_signals(
    text: str,
    schema_summary: dict[str, Any],
    key_pages: KeyPages,
    title: str | None = None,
) -> SiteSignals:
    company_name = None
    if title and ("|" in title or "-" in title):
        company_name = re.split(r"[|-]", title)[-1].strip() or None

    awards_detected = any(keyword in text.lower() for keyword in ["award", "awards", "certified", "top rated"])
    certifications_detected = any(
        keyword in text.lower()
        for keyword in ["certification", "certified", "iso", "accredited", "google partner"]
    )

    return SiteSignals(
        company_name_detected=bool(company_name),
        address_detected=bool(re.search(ADDRESS_PATTERN, text, re.I)),
        phone_detected=bool(re.search(PHONE_PATTERN, text, re.I)),
        email_detected=bool(re.search(EMAIL_PATTERN, text, re.I)),
        awards_detected=awards_detected,
        certifications_detected=certifications_detected,
        same_as_detected=bool(schema_summary.get("same_as")),
        detected_company_name=company_name,
    )


def calculate_brand_authority(signals: SiteSignals, has_about_page: bool) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []

    if signals.company_name_detected:
        score += 20
        reasons.append("Detected company naming signal.")
    if signals.address_detected:
        score += 15
        reasons.append("Detected business address.")
    if signals.phone_detected:
        score += 10
        reasons.append("Detected phone number.")
    if signals.email_detected:
        score += 10
        reasons.append("Detected public email address.")
    if signals.awards_detected:
        score += 15
        reasons.append("Detected awards or recognitions.")
    if signals.certifications_detected:
        score += 10
        reasons.append("Detected certifications or accreditation.")
    if has_about_page:
        score += 10
        reasons.append("Site exposes an about/company page.")
    if signals.same_as_detected:
        score += 10
        reasons.append("Schema exposes sameAs references.")

    return {"score": min(score, 100), "reasons": reasons}


def assess_citability(homepage: dict[str, Any]) -> dict[str, Any]:
    score = 0
    signals: dict[str, bool] = {
        "has_title": bool(homepage.get("title")),
        "has_meta_description": bool(homepage.get("meta_description")),
        "has_h1": bool(homepage.get("h1")),
        "has_canonical": bool(homepage.get("canonical")),
        "has_multiple_headings": len(homepage.get("headings", [])) >= 3,
        "has_substantial_copy": homepage.get("word_count", 0) >= 250,
    }
    weights = {
        "has_title": 15,
        "has_meta_description": 15,
        "has_h1": 15,
        "has_canonical": 15,
        "has_multiple_headings": 20,
        "has_substantial_copy": 20,
    }
    for name, present in signals.items():
        if present:
            score += weights[name]
    return {"score": min(score, 100), "signals": signals}


def assess_ssr_signal(html_length: int, word_count: int) -> dict[str, Any]:
    if html_length >= 5000 and word_count >= 300:
        return {"score": 100, "classification": "strong"}
    if html_length >= 2500 and word_count >= 120:
        return {"score": 70, "classification": "moderate"}
    if html_length >= 1200 and word_count >= 60:
        return {"score": 45, "classification": "weak"}
    return {"score": 20, "classification": "poor"}


def assess_render_blocking(scripts: list[dict[str, Any]], stylesheets: list[dict[str, Any]]) -> dict[str, Any]:
    sync_scripts = [
        item for item in scripts if item.get("src") and not item.get("async_attr") and not item.get("defer_attr")
    ]
    stylesheet_count = len(stylesheets)
    risk_score = min(100, len(sync_scripts) * 20 + stylesheet_count * 10)
    return {
        "score": max(0, 100 - risk_score),
        "sync_script_count": len(sync_scripts),
        "stylesheet_count": stylesheet_count,
        "risk_level": "high" if risk_score >= 70 else "medium" if risk_score >= 35 else "low",
    }
