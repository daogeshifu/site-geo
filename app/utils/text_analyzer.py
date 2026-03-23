from __future__ import annotations

import re
from typing import Any


FAQ_PATTERNS = ["faq", "frequently asked questions", "常见问题", "问答"]
AUTHOR_PATTERNS = [r"\bby\s+[A-Z][a-z]+", r"\bauthor\b", r"\bwritten by\b", r"\b编辑\b", r"\b作者\b"]
DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{4}/\d{2}/\d{2}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
]
QUANT_PATTERNS = [r"\b\d+(\.\d+)?%\b", r"\$\d[\d,]*(?:\.\d+)?", r"\b\d{2,}\b", r"\bUSD\b", r"\bRMB\b"]


def estimate_word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def contains_faq(text: str, headings: list[dict[str, str]] | list[Any]) -> bool:
    haystack = f"{text} {' '.join(str(item.get('text', '')) for item in headings if isinstance(item, dict))}".lower()
    return any(pattern in haystack for pattern in FAQ_PATTERNS)


def has_author_signals(text: str) -> bool:
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in AUTHOR_PATTERNS)


def has_publish_date(text: str) -> bool:
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in DATE_PATTERNS)


def has_quantified_data(text: str) -> bool:
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in QUANT_PATTERNS)


def is_answer_first(text: str) -> bool:
    words = re.findall(r"\S+", text or "")
    lead = " ".join(words[:80]).lower()
    patterns = [
        "we help",
        "we provide",
        "our service",
        "is a",
        "is an",
        "helps businesses",
        "can help",
    ]
    return len(words) >= 20 and any(pattern in lead for pattern in patterns)


def evaluate_heading_quality(headings: list[dict[str, str]] | list[Any]) -> dict[str, Any]:
    normalized = [item for item in headings if isinstance(item, dict) and item.get("level")]
    issues: list[str] = []
    score = 100

    if not normalized:
        return {"score": 0, "issues": ["No heading structure detected."]}

    if normalized[0]["level"] != "h1":
        score -= 25
        issues.append("Page does not start with an H1 heading.")

    levels = [int(item["level"][1]) for item in normalized if item["level"].startswith("h")]
    if any(current - previous > 1 for previous, current in zip(levels, levels[1:])):
        score -= 20
        issues.append("Heading levels skip important structure levels.")

    if len(normalized) < 3:
        score -= 20
        issues.append("Heading structure is shallow.")

    if len({item["text"].strip().lower() for item in normalized}) != len(normalized):
        score -= 10
        issues.append("Repeated headings reduce scan-ability.")

    return {"score": max(score, 0), "issues": issues}
