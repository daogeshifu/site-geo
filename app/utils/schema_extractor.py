from __future__ import annotations

import html
import json
import re
from typing import Any


RELATION_KEYS = {
    "brand",
    "manufacturer",
    "haspart",
    "offer",
    "offers",
    "about",
    "mentions",
    "sameas",
    "memberof",
    "subjectof",
    "knowsabout",
    "contactpoint",
    "mainentity",
}

ORGANIZATION_LIKE_TYPES = {
    "organization",
    "airline",
    "consortium",
    "corporation",
    "educationalorganization",
    "fundingagency",
    "governmentorganization",
    "localbusiness",
    "medicalorganization",
    "ngo",
    "newsmediaorganization",
    "onlinestore",
    "performinggroup",
    "sportsorganization",
    "store",
    "travelagency",
}

ARTICLE_LIKE_TYPES = {
    "article",
    "blogposting",
    "newsarticle",
    "report",
    "scholarlyarticle",
    "socialmediaposting",
    "techarticle",
}

PRODUCT_LIKE_TYPES = {
    "product",
    "productmodel",
    "individualproduct",
    "someproducts",
}

TEXT_VALUE_KEYS = {"name", "headline", "description", "text", "alternateName"}
DATE_KEYS = {"datePublished", "dateModified"}


def _normalize_type_name(raw_type: str) -> str:
    """将 @type 统一归一化为短类型名，兼容完整 URL 和命名空间写法。"""
    value = raw_type.strip()
    if not value:
        return ""
    for separator in ("/", "#", ":"):
        if separator in value:
            value = value.rsplit(separator, 1)[-1]
    return value.strip()


def _normalize_text_value(raw_value: str) -> str:
    value = html.unescape(raw_value or "").lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _walk_schema(
    data: Any,
    types: set[str],
    same_as: set[str],
    entity_ids: set[str],
    relation_count: list[int],
    text_values: set[str],
    date_fields: set[str],
) -> None:
    """递归遍历 JSON-LD 数据，收集所有 @type 和 sameAs 值

    处理：
    - 列表：递归遍历每个元素
    - 字典：提取 @type（支持字符串和列表格式）
               提取 sameAs（支持字符串和列表格式）
               递归处理 @graph 和所有嵌套 dict/list 值
    """
    if isinstance(data, list):
        for item in data:
            _walk_schema(item, types, same_as, entity_ids, relation_count, text_values, date_fields)
        return

    if isinstance(data, dict):
        # 处理 @type（支持多类型：["Organization", "LocalBusiness"]）
        raw_type = data.get("@type")
        if isinstance(raw_type, list):
            for item in raw_type:
                if isinstance(item, str):
                    normalized = _normalize_type_name(item)
                    if normalized:
                        types.add(normalized)
        elif isinstance(raw_type, str):
            normalized = _normalize_type_name(raw_type)
            if normalized:
                types.add(normalized)

        # 处理 sameAs（支持单值和数组）
        raw_same_as = data.get("sameAs")
        if isinstance(raw_same_as, list):
            same_as.update(str(item) for item in raw_same_as if item)
        elif isinstance(raw_same_as, str):
            same_as.add(raw_same_as)

        raw_id = data.get("@id")
        if isinstance(raw_id, str) and raw_id:
            entity_ids.add(raw_id)

        for key in DATE_KEYS:
            if isinstance(data.get(key), str) and data.get(key).strip():
                date_fields.add(key)

        # 处理 @graph（Schema.org 中常用的图形化结构）
        if "@graph" in data:
            _walk_schema(data["@graph"], types, same_as, entity_ids, relation_count, text_values, date_fields)

        # 递归遍历所有嵌套的 dict/list 值
        for key, value in data.items():
            if key.lower() in RELATION_KEYS and isinstance(value, (dict, list, str)):
                relation_count[0] += 1
            if key in TEXT_VALUE_KEYS and isinstance(value, str):
                normalized = _normalize_text_value(value)
                if 8 <= len(normalized) <= 220:
                    text_values.add(normalized[:140])
            if isinstance(value, (dict, list)):
                _walk_schema(value, types, same_as, entity_ids, relation_count, text_values, date_fields)


def extract_schema_summary(json_ld_blocks: list[str], visible_text: str | None = None) -> dict[str, Any]:
    """从 JSON-LD 文本块列表中提取 Schema 摘要

    Args:
        json_ld_blocks: JSON-LD 字符串列表（来自 <script type="application/ld+json">）

    Returns:
        包含以下键的摘要字典：
        - json_ld_present: 是否存在任何 JSON-LD
        - types: 所有检测到的 Schema @type 列表（排序）
        - has_organization: 是否有 Organization schema
        - has_local_business: 是否有 LocalBusiness schema
        - has_article: 是否有 Article 或 NewsArticle schema
        - has_faq_page: 是否有 FAQPage schema
        - has_service: 是否有 Service schema
        - has_website: 是否有 WebSite schema
        - same_as: 所有 sameAs URL 列表（排序）
    """
    types: set[str] = set()
    same_as: set[str] = set()
    entity_ids: set[str] = set()
    relation_count = [0]
    text_values: set[str] = set()
    date_fields: set[str] = set()
    valid_block_count = 0

    for block in json_ld_blocks:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue  # 跳过无法解析的块
        valid_block_count += 1
        _walk_schema(payload, types, same_as, entity_ids, relation_count, text_values, date_fields)

    # 使用小写集合进行类型匹配（不区分大小写）
    lowered = {item.lower() for item in types}
    alignment_score = 0
    aligned_text_items = 0
    if valid_block_count > 0:
        if text_values and visible_text:
            normalized_visible_text = _normalize_text_value(visible_text)
            aligned_text_items = sum(1 for item in text_values if item and item in normalized_visible_text)
            alignment_score = int(round((aligned_text_items / len(text_values)) * 100))
        elif text_values:
            alignment_score = 0
        else:
            alignment_score = 50
    return {
        "json_ld_present": valid_block_count > 0,
        "types": sorted(types),
        "has_organization": bool(ORGANIZATION_LIKE_TYPES & lowered),
        "has_local_business": "localbusiness" in lowered,
        "has_article": bool(ARTICLE_LIKE_TYPES & lowered),
        "has_faq_page": "faqpage" in lowered,
        "has_service": "service" in lowered,
        "has_website": "website" in lowered,
        "has_product": bool(PRODUCT_LIKE_TYPES & lowered),
        "has_defined_term": "definedterm" in lowered,
        "has_offer": "offer" in lowered,
        "has_breadcrumb_list": "breadcrumblist" in lowered,
        "has_date_published": "datePublished" in date_fields,
        "has_date_modified": "dateModified" in date_fields,
        "date_signal_count": len(date_fields),
        "visible_alignment_score": alignment_score,
        "aligned_text_items": aligned_text_items,
        "text_item_count": len(text_values),
        "entity_id_count": len(entity_ids),
        "relation_count": relation_count[0],
        "same_as": sorted(same_as),
    }
