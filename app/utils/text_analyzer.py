from __future__ import annotations

import re
from typing import Any


# FAQ 检测关键词（中英文）
FAQ_PATTERNS = ["faq", "frequently asked questions", "常见问题", "问答"]
# 作者信号正则模式（英文"by"前缀 + 中文"作者/编辑"）
AUTHOR_PATTERNS = [r"\bby\s+[A-Z][a-z]+", r"\bauthor\b", r"\bwritten by\b", r"\b编辑\b", r"\b作者\b"]
# 发布日期正则模式：YYYY-MM-DD / YYYY/MM/DD / 英文月份格式
DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{4}/\d{2}/\d{2}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
]
# 量化数据正则模式：百分比、美元、大数字、货币单位
QUANT_PATTERNS = [r"\b\d+(\.\d+)?%\b", r"\$\d[\d,]*(?:\.\d+)?", r"\b\d{2,}\b", r"\bUSD\b", r"\bRMB\b"]
REFERENCE_PATTERNS = ["references", "sources", "bibliography", "works cited", "citations", "参考资料", "参考文献", "资料来源"]
SUMMARY_PATTERNS = ["tl;dr", "summary", "key takeaways", "in brief", "quick answer", "overview", "摘要", "要点", "结论"]
UPDATE_PATTERNS = ["last updated", "updated on", "updated:", "revision history", "changelog", "最近更新", "更新记录", "修订"]
INLINE_CITATION_PATTERNS = [
    r"\[\d{1,3}\]",
    r"\([A-Z][A-Za-z]+(?:\s+et al\.)?,\s*\d{4}\)",
    r"\bsource:\b",
    r"\baccording to\b",
]
GENERIC_ANCHOR_TEXTS = {
    "click here",
    "learn more",
    "read more",
    "more",
    "details",
    "here",
    "this link",
    "view more",
    "see more",
    "了解更多",
    "点击这里",
    "更多",
    "详情",
    "查看",
}


def estimate_word_count(text: str) -> int:
    """统计文本中的单词数（使用 `\\b\\w+\\b` 正则）"""
    return len(re.findall(r"\b\w+\b", text or ""))


def contains_faq(text: str, headings: list[dict[str, str]] | list[Any]) -> bool:
    """检测页面是否包含 FAQ 内容（在正文和标题中搜索关键词）"""
    haystack = f"{text} {' '.join(str(item.get('text', '')) for item in headings if isinstance(item, dict))}".lower()
    return any(pattern in haystack for pattern in FAQ_PATTERNS)


def has_author_signals(text: str) -> bool:
    """检测页面是否包含作者署名信号（by X / author / 作者等）"""
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in AUTHOR_PATTERNS)


def has_publish_date(text: str) -> bool:
    """检测页面是否包含发布日期（YYYY-MM-DD 等格式）"""
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in DATE_PATTERNS)


def has_quantified_data(text: str) -> bool:
    """检测页面是否包含量化数据（%, $, 大数字, 货币符号）

    量化数据是 AI 引用的强信号（可验证的事实和数据点）
    """
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in QUANT_PATTERNS)


def has_reference_section(text: str, headings: list[dict[str, str]] | list[Any]) -> bool:
    """检测页面是否存在参考资料/引用来源区块。"""
    haystack = f"{text} {' '.join(str(item.get('text', '')) for item in headings if isinstance(item, dict))}".lower()
    return any(pattern in haystack for pattern in REFERENCE_PATTERNS)


def has_inline_citations(text: str) -> bool:
    """检测正文是否出现内联引用信号。"""
    lowered = text or ""
    return any(re.search(pattern, lowered, re.I) for pattern in INLINE_CITATION_PATTERNS)


def has_tldr_summary(text: str, headings: list[dict[str, str]] | list[Any]) -> bool:
    """检测页面是否包含 TL;DR / summary / key takeaways 一类结论前置模块。"""
    haystack = f"{text[:1200]} {' '.join(str(item.get('text', '')) for item in headings if isinstance(item, dict))}".lower()
    return any(pattern in haystack for pattern in SUMMARY_PATTERNS)


def has_update_log(text: str, headings: list[dict[str, str]] | list[Any]) -> bool:
    """检测页面是否公开暴露了更新说明或修订历史。"""
    haystack = f"{text[:1600]} {' '.join(str(item.get('text', '')) for item in headings if isinstance(item, dict))}".lower()
    return any(pattern in haystack for pattern in UPDATE_PATTERNS)


def assess_link_context(internal_links: list[dict[str, Any]], external_links: list[dict[str, Any]]) -> dict[str, Any]:
    """评估站内/站外链接锚文本是否足够描述性，便于 RAG 检索建立上下文。"""

    def _summary(links: list[dict[str, Any]]) -> tuple[int, float]:
        labels = [str(item.get("text") or "").strip() for item in links if isinstance(item, dict)]
        labels = [label for label in labels if label]
        if not labels:
            return 0, 0.0

        descriptive = 0
        for label in labels:
            normalized = re.sub(r"\s+", " ", label.lower()).strip()
            word_count = len(re.findall(r"\b\w+\b", normalized))
            if normalized in GENERIC_ANCHOR_TEXTS:
                continue
            if word_count >= 2 or len(normalized) >= 12:
                descriptive += 1
        return len(labels), descriptive / len(labels)

    internal_count, internal_ratio = _summary(internal_links)
    external_count, external_ratio = _summary(external_links)
    score = min(
        100,
        int(
            round(
                internal_ratio * 45
                + external_ratio * 35
                + min(internal_count, 8) * 2
                + min(external_count, 4) * 1
            )
        ),
    )
    return {
        "score": score,
        "internal_link_count": len(internal_links),
        "external_link_count": len(external_links),
        "descriptive_internal_link_ratio": round(internal_ratio, 2),
        "descriptive_external_link_ratio": round(external_ratio, 2),
    }


def is_answer_first(text: str) -> bool:
    """检测页面是否采用"先答后述"结构（AI 引用友好的写作方式）

    检查前 80 个词是否包含直接回答性短语（"we help"/"is a"/"can help" 等）
    至少需要 20 个词才进行判断
    """
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
    """评估页面标题层级质量（0-100 分）

    扣分规则：
    - 第一个标题不是 H1：-25 分
    - 标题层级跳跃（如 H1 → H3）：-20 分
    - 标题结构过浅（少于 3 个）：-20 分
    - 存在重复标题文本：-10 分
    """
    normalized = [item for item in headings if isinstance(item, dict) and item.get("level")]
    issues: list[str] = []
    score = 100

    if not normalized:
        return {"score": 0, "issues": ["No heading structure detected."]}

    # 检查是否以 H1 开头
    if normalized[0]["level"] != "h1":
        score -= 25
        issues.append("Page does not start with an H1 heading.")

    # 检查标题层级是否有跳跃（如 H1→H3 跳过 H2）
    levels = [int(item["level"][1]) for item in normalized if item["level"].startswith("h")]
    if any(current - previous > 1 for previous, current in zip(levels, levels[1:])):
        score -= 20
        issues.append("Heading levels skip important structure levels.")

    # 检查标题数量是否足够（至少 3 个）
    if len(normalized) < 3:
        score -= 20
        issues.append("Heading structure is shallow.")

    # 检查是否有重复标题（集合去重后数量不等于原数量）
    if len({item["text"].strip().lower() for item in normalized}) != len(normalized):
        score -= 10
        issues.append("Repeated headings reduce scan-ability.")

    return {"score": max(score, 0), "issues": issues}


def estimate_information_density(text: str, headings: list[dict[str, str]] | list[Any]) -> dict[str, Any]:
    """评估页面信息密度（0-100 分）

    评分维度：
    - 词数（最高 30 分）：≥180词30分/≥90词20分/≥40词10分
    - 词汇多样性（最高 25 分）：独特词占比 ≥0.45 为 25 分
    - 量化数据（25 分）：包含数字/统计则加分
    - 标题数量（最高 20 分）：≥4个标题20分/≥2个10分
    """
    words = re.findall(r"\b\w+\b", text or "")
    headings_count = len([item for item in headings if isinstance(item, dict) and item.get("text")])
    # 词汇多样性：长度>2的独特词占总词数的比例
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
    """评估页面内容分块结构（0-100 分）

    评分维度：
    - 基础分：30 分
    - 标题数量（最高 30 分）：≥4个30分/≥2个20分
    - 平均每块词数（最高 30 分）：60-220词最优/35-280词次优
    - 首标题为 H1（10 分）

    AI 系统偏好每块 60-220 词的分块结构（便于段落级引用）
    """
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

    # 60-220 词/块是 AI 引用的最优区间
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
        "chunk_count": heading_count + 1,  # 标题数 + 1 = 块数
        "avg_words_per_chunk": int(avg_words_per_chunk),
    }
