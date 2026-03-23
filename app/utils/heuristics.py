from __future__ import annotations

import re
from typing import Any

from app.models.discovery import BacklinkOverviewResult, KeyPages, LlmsResult, PageProfile, SiteSignals


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
        homepage_brand_mentions=(len(re.findall(re.escape(company_name), text, re.I)) if company_name else 0),
    )


def assess_llms_effectiveness(
    llms: LlmsResult,
    *,
    company_name: str | None = None,
    business_type: str | None = None,
) -> dict[str, Any]:
    if not llms.exists:
        return {
            "score": 0,
            "signals": {
                "exists": False,
                "has_meaningful_length": False,
                "mentions_brand": False,
                "mentions_services": False,
                "includes_guidance": False,
                "has_structured_sections": False,
            },
            "reasons": ["No llms.txt file detected."],
        }

    preview = llms.content_preview.lower()
    company_lower = (company_name or "").lower()
    service_keywords = BUSINESS_TYPE_RULES.get(business_type or "", []) + [
        "service",
        "services",
        "solution",
        "solutions",
        "product",
        "products",
    ]
    guidance_keywords = ["cite", "citation", "canonical", "contact", "support", "policy", "preferred"]
    signals = {
        "exists": True,
        "has_meaningful_length": llms.content_length >= 250,
        "mentions_brand": bool(company_lower and company_lower in preview),
        "mentions_services": any(keyword in preview for keyword in service_keywords),
        "includes_guidance": any(keyword in preview for keyword in guidance_keywords),
        "has_structured_sections": "##" in llms.content_preview or "# " in llms.content_preview or "- " in llms.content_preview,
    }
    weights = {
        "exists": 20,
        "has_meaningful_length": 20,
        "mentions_brand": 20,
        "mentions_services": 20,
        "includes_guidance": 10,
        "has_structured_sections": 10,
    }
    score = sum(weights[name] for name, enabled in signals.items() if enabled)
    reasons = []
    if signals["mentions_brand"]:
        reasons.append("llms.txt names the site or brand directly.")
    if signals["mentions_services"]:
        reasons.append("llms.txt describes the site's services or core offering.")
    if signals["includes_guidance"]:
        reasons.append("llms.txt includes machine-facing guidance or citation hints.")
    if signals["has_structured_sections"]:
        reasons.append("llms.txt uses readable sections for machine consumption.")
    return {"score": min(score, 100), "signals": signals, "reasons": reasons}


def assess_basic_brand_presence(signals: SiteSignals, key_pages: KeyPages) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []

    if signals.company_name_detected:
        score += 35
        reasons.append("Detected company naming signal.")
    if signals.phone_detected or signals.email_detected:
        score += 25
        reasons.append("Detected direct contact signal.")
    if key_pages.about:
        score += 20
        reasons.append("Site exposes an about/company page.")
    if key_pages.contact:
        score += 20
        reasons.append("Site exposes a contact page.")

    return {"score": min(score, 100), "reasons": reasons}


def assess_brand_mentions(
    signals: SiteSignals,
    *,
    homepage: dict[str, Any],
    llms: LlmsResult,
    key_pages: KeyPages,
) -> dict[str, Any]:
    brand_name = (signals.detected_company_name or "").strip()
    brand_lower = brand_name.lower()
    text_fields = [
        homepage.get("title") or "",
        homepage.get("meta_description") or "",
        homepage.get("h1") or "",
        llms.content_preview or "",
    ]
    mention_hits = sum(1 for field in text_fields if brand_lower and brand_lower in field.lower())

    score = 0
    reasons: list[str] = []
    if mention_hits:
        score += min(45, mention_hits * 15)
        reasons.append("Brand is repeated across key crawlable fields.")
    if signals.homepage_brand_mentions >= 2:
        score += 20
        reasons.append("Homepage body copy repeats the brand enough to reinforce entity recall.")
    elif signals.homepage_brand_mentions == 1:
        score += 10
        reasons.append("Homepage body copy includes at least one brand mention.")
    if key_pages.about:
        score += 20
        reasons.append("About page supports brand/entity discovery.")
    if key_pages.contact:
        score += 15
        reasons.append("Contact page strengthens branded navigation and entity confirmation.")

    return {"score": min(score, 100), "reasons": reasons, "mention_hits": mention_hits}


def assess_entity_consistency(
    signals: SiteSignals,
    *,
    schema_summary: dict[str, Any],
    homepage: dict[str, Any],
    llms: LlmsResult,
    key_pages: KeyPages,
    primary_domain: str,
    sitemap_urls: list[str],
) -> dict[str, Any]:
    company_lower = (signals.detected_company_name or "").lower()
    title = (homepage.get("title") or "").lower()
    h1 = (homepage.get("h1") or "").lower()
    llms_preview = llms.content_preview.lower()
    same_as_count = len(schema_summary.get("same_as", []))
    sitemap_domains = {url.lower() for url in sitemap_urls[:10]}
    same_domain_sitemap = all(primary_domain in url for url in sitemap_domains) if sitemap_domains else True

    score = 0
    reasons: list[str] = []
    if same_as_count > 0:
        score += 35
        reasons.append("Schema exposes sameAs references.")
    if schema_summary.get("has_organization"):
        score += 20
        reasons.append("Organization schema is present.")
    if company_lower and any(company_lower in field for field in [title, h1, llms_preview]):
        score += 20
        reasons.append("Brand naming is consistent across page metadata and machine-readable copy.")
    if key_pages.about and key_pages.contact:
        score += 15
        reasons.append("About and contact pages reinforce entity continuity.")
    if same_domain_sitemap:
        score += 10
        reasons.append("Sitemap URLs align with the primary domain.")
    else:
        reasons.append("Sitemap URLs do not align with the primary domain.")

    return {
        "score": min(score, 100),
        "reasons": reasons,
        "same_as_count": same_as_count,
        "same_domain_sitemap": same_domain_sitemap,
    }


def assess_business_completeness(signals: SiteSignals, key_pages: KeyPages) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []

    if signals.company_name_detected:
        score += 20
        reasons.append("Detected company naming signal.")
    if signals.address_detected:
        score += 15
        reasons.append("Detected business address.")
    if signals.phone_detected:
        score += 15
        reasons.append("Detected phone number.")
    if signals.email_detected:
        score += 15
        reasons.append("Detected public email address.")
    if key_pages.about:
        score += 10
        reasons.append("Site exposes an about/company page.")
    if key_pages.contact:
        score += 10
        reasons.append("Site exposes a contact page.")
    if signals.awards_detected:
        score += 10
        reasons.append("Detected awards or recognitions.")
    if signals.certifications_detected:
        score += 5
        reasons.append("Detected certifications or accreditation.")

    return {"score": min(score, 100), "reasons": reasons}


def assess_backlink_quality(backlinks: BacklinkOverviewResult) -> dict[str, Any]:
    if not backlinks.available:
        return {
            "score": None,
            "available": False,
            "reasons": [backlinks.error or "Backlink provider unavailable."],
        }

    authority = min(backlinks.authority_score or 0, 100)
    domains = min(100, int(min((backlinks.referring_domains or 0) / 5, 100)))
    diversity = min(100, int(min((backlinks.referring_ip_classes or 0) / 3, 100)))
    follow_ratio_score = int((backlinks.follow_ratio or 0) * 100)
    score = int(round(authority * 0.4 + domains * 0.25 + diversity * 0.15 + follow_ratio_score * 0.2))

    reasons = [f"Semrush authority score: {backlinks.authority_score or 0}."]
    if backlinks.referring_domains is not None:
        reasons.append(f"Referring domains: {backlinks.referring_domains}.")
    if backlinks.follow_ratio is not None:
        reasons.append(f"Follow backlink ratio: {int(backlinks.follow_ratio * 100)}%.")
    return {"score": min(score, 100), "available": True, "reasons": reasons}


def calculate_brand_authority(
    *,
    signals: SiteSignals,
    homepage: dict[str, Any],
    llms: LlmsResult,
    key_pages: KeyPages,
    schema_summary: dict[str, Any],
    primary_domain: str,
    sitemap_urls: list[str],
    backlinks: BacklinkOverviewResult,
) -> dict[str, Any]:
    components = {
        "backlink_quality": assess_backlink_quality(backlinks),
        "brand_mentions": assess_brand_mentions(signals, homepage=homepage, llms=llms, key_pages=key_pages),
        "entity_consistency": assess_entity_consistency(
            signals,
            schema_summary=schema_summary,
            homepage=homepage,
            llms=llms,
            key_pages=key_pages,
            primary_domain=primary_domain,
            sitemap_urls=sitemap_urls,
        ),
        "business_completeness": assess_business_completeness(signals, key_pages),
    }
    weights = {
        "backlink_quality": 0.25,
        "brand_mentions": 0.25,
        "entity_consistency": 0.25,
        "business_completeness": 0.25,
    }

    weighted_total = 0.0
    weight_total = 0.0
    reasons: list[str] = []
    for name, component in components.items():
        score = component.get("score")
        if score is None:
            continue
        weighted_total += score * weights[name]
        weight_total += weights[name]
        reasons.extend(component.get("reasons", [])[:2])

    score = int(round(weighted_total / weight_total)) if weight_total else 0
    return {"score": min(score, 100), "reasons": reasons[:8], "components": components}


def _normalize_page_profile(page: PageProfile | dict[str, Any]) -> dict[str, Any]:
    if isinstance(page, PageProfile):
        return page.model_dump()
    return page


def _citation_probability(score: int, page: dict[str, Any]) -> str:
    support_signals = sum(
        1
        for present in [
            page.get("answer_first"),
            page.get("has_quantified_data"),
            page.get("has_faq"),
            page.get("has_author"),
            page.get("has_publish_date"),
        ]
        if present
    )
    if score >= 75 and support_signals >= 2:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def _score_page_citability(page: dict[str, Any]) -> dict[str, Any]:
    signals: dict[str, bool] = {
        "has_title": bool(page.get("title")),
        "has_meta_description": bool(page.get("meta_description")),
        "has_h1_or_headings": bool(page.get("h1")) or len(page.get("headings", [])) >= 1,
        "has_canonical": bool(page.get("canonical")),
        "has_multiple_headings": len(page.get("headings", [])) >= 3,
        "has_substantial_copy": page.get("word_count", 0) >= 250,
        "answer_first": bool(page.get("answer_first")),
        "has_data_points": bool(page.get("has_quantified_data")),
        "has_faq": bool(page.get("has_faq")),
        "has_author": bool(page.get("has_author")),
        "has_publish_date": bool(page.get("has_publish_date")),
    }
    information_density_score = int(page.get("information_density_score", 0))
    chunk_structure_score = int(page.get("chunk_structure_score", 0))
    score = 0.0
    weights = {
        "has_title": 8,
        "has_meta_description": 8,
        "has_h1_or_headings": 8,
        "has_canonical": 8,
        "has_multiple_headings": 10,
        "has_substantial_copy": 10,
        "answer_first": 15,
        "has_data_points": 8,
        "has_faq": 5,
        "has_author": 5,
        "has_publish_date": 5,
    }
    for name, present in signals.items():
        if present:
            score += weights[name]
    score += information_density_score * 0.1
    score += chunk_structure_score * 0.1
    normalized_score = min(int(round(score)), 100)
    return {
        "score": normalized_score,
        "signals": signals,
        "information_density_score": information_density_score,
        "chunk_structure_score": chunk_structure_score,
        "citation_probability": _citation_probability(normalized_score, page),
    }


def assess_citability(
    homepage: dict[str, Any],
    page_profiles: dict[str, PageProfile | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    homepage_payload = dict(homepage)
    homepage_payload.setdefault("information_density_score", 40 if homepage.get("word_count", 0) >= 250 else 20)
    homepage_payload.setdefault("chunk_structure_score", 50 if len(homepage.get("headings", [])) >= 3 else 25)
    homepage_payload.setdefault("answer_first", False)
    homepage_payload.setdefault("has_quantified_data", False)
    homepage_payload.setdefault("has_faq", False)
    homepage_payload.setdefault("has_author", False)
    homepage_payload.setdefault("has_publish_date", False)

    homepage_citability = _score_page_citability(homepage_payload)
    scored_pages: dict[str, Any] = {"homepage": homepage_citability}

    for key, profile in (page_profiles or {}).items():
        normalized = _normalize_page_profile(profile)
        scored_pages[key] = _score_page_citability(normalized)

    best_page_key, best_page = max(scored_pages.items(), key=lambda item: item[1]["score"])
    overall_score = homepage_citability["score"]
    if best_page_key != "homepage":
        overall_score = int(round(homepage_citability["score"] * 0.55 + best_page["score"] * 0.45))

    return {
        "score": min(overall_score, 100),
        "signals": homepage_citability["signals"],
        "homepage_citability": homepage_citability,
        "best_page_citability": {"page_key": best_page_key, **best_page},
        "citation_probability": best_page["citation_probability"],
        "page_scores": scored_pages,
    }


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
