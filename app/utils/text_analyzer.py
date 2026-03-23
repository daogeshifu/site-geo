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


def estimate_information_density(text: str, headings: list[dict[str, str]] | list[Any]) -> dict[str, Any]:
    words = re.findall(r"\b\w+\b", text or "")
    headings_count = len([item for item in headings if isinstance(item, dict) and item.get("text")])
    unique_words = {word.lower() for word in words if len(word) > 2}
    lexical_ratio = len(unique_words) / max(len(words), 1)

    score = 0
    if len(words) >= 180:
        score += 30
    elif len(words) >= 90:
        score += 20
    elif len(words) >= 40:
        score += 10

    if lexical_ratio >= 0.45:
        score += 25
    elif lexical_ratio >= 0.30:
        score += 18
    elif lexical_ratio >= 0.20:
        score += 10

    if has_quantified_data(text):
        score += 25

    if headings_count >= 4:
        score += 20
    elif headings_count >= 2:
        score += 10

    return {
        "score": min(score, 100),
        "word_count": len(words),
        "lexical_ratio": round(lexical_ratio, 2),
        "heading_count": headings_count,
    }


def evaluate_chunk_structure(text: str, headings: list[dict[str, str]] | list[Any]) -> dict[str, Any]:
    normalized = [item for item in headings if isinstance(item, dict) and item.get("text")]
    heading_count = len(normalized)
    word_count = estimate_word_count(text)
    if heading_count == 0:
        return {"score": 20, "chunk_count": 0, "avg_words_per_chunk": word_count}

    avg_words_per_chunk = word_count / max(heading_count + 1, 1)
    score = 30
    if heading_count >= 4:
        score += 30
    elif heading_count >= 2:
        score += 20

    if 60 <= avg_words_per_chunk <= 220:
        score += 30
    elif 35 <= avg_words_per_chunk <= 280:
        score += 20
    else:
        score += 10

    if normalized and normalized[0].get("level") == "h1":
        score += 10

    return {
        "score": min(score, 100),
        "chunk_count": heading_count + 1,
        "avg_words_per_chunk": int(avg_words_per_chunk),
    }
