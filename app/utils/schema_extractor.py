from __future__ import annotations

import json
from typing import Any


def _walk_schema(data: Any, types: set[str], same_as: set[str]) -> None:
    """递归遍历 JSON-LD 数据，收集所有 @type 和 sameAs 值

    处理：
    - 列表：递归遍历每个元素
    - 字典：提取 @type（支持字符串和列表格式）
               提取 sameAs（支持字符串和列表格式）
               递归处理 @graph 和所有嵌套 dict/list 值
    """
    if isinstance(data, list):
        for item in data:
            _walk_schema(item, types, same_as)
        return

    if isinstance(data, dict):
        # 处理 @type（支持多类型：["Organization", "LocalBusiness"]）
        raw_type = data.get("@type")
        if isinstance(raw_type, list):
            for item in raw_type:
                if isinstance(item, str):
                    types.add(item)
        elif isinstance(raw_type, str):
            types.add(raw_type)

        # 处理 sameAs（支持单值和数组）
        raw_same_as = data.get("sameAs")
        if isinstance(raw_same_as, list):
            same_as.update(str(item) for item in raw_same_as if item)
        elif isinstance(raw_same_as, str):
            same_as.add(raw_same_as)

        # 处理 @graph（Schema.org 中常用的图形化结构）
        if "@graph" in data:
            _walk_schema(data["@graph"], types, same_as)

        # 递归遍历所有嵌套的 dict/list 值
        for value in data.values():
            if isinstance(value, (dict, list)):
                _walk_schema(value, types, same_as)


def extract_schema_summary(json_ld_blocks: list[str]) -> dict[str, Any]:
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

    for block in json_ld_blocks:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue  # 跳过无法解析的块
        _walk_schema(payload, types, same_as)

    # 使用小写集合进行类型匹配（不区分大小写）
    lowered = {item.lower() for item in types}
    return {
        "json_ld_present": bool(json_ld_blocks),
        "types": sorted(types),
        "has_organization": "organization" in lowered,
        "has_local_business": "localbusiness" in lowered,
        "has_article": bool({"article", "newsarticle"} & lowered),  # Article 或 NewsArticle
        "has_faq_page": "faqpage" in lowered,
        "has_service": "service" in lowered,
        "has_website": "website" in lowered,
        "same_as": sorted(same_as),
    }
