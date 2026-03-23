from __future__ import annotations

import json
from typing import Any


def _walk_schema(data: Any, types: set[str], same_as: set[str]) -> None:
    if isinstance(data, list):
        for item in data:
            _walk_schema(item, types, same_as)
        return

    if isinstance(data, dict):
        raw_type = data.get("@type")
        if isinstance(raw_type, list):
            for item in raw_type:
                if isinstance(item, str):
                    types.add(item)
        elif isinstance(raw_type, str):
            types.add(raw_type)

        raw_same_as = data.get("sameAs")
        if isinstance(raw_same_as, list):
            same_as.update(str(item) for item in raw_same_as if item)
        elif isinstance(raw_same_as, str):
            same_as.add(raw_same_as)

        if "@graph" in data:
            _walk_schema(data["@graph"], types, same_as)

        for value in data.values():
            if isinstance(value, (dict, list)):
                _walk_schema(value, types, same_as)


def extract_schema_summary(json_ld_blocks: list[str]) -> dict[str, Any]:
    types: set[str] = set()
    same_as: set[str] = set()

    for block in json_ld_blocks:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        _walk_schema(payload, types, same_as)

    lowered = {item.lower() for item in types}
    return {
        "json_ld_present": bool(json_ld_blocks),
        "types": sorted(types),
        "has_organization": "organization" in lowered,
        "has_local_business": "localbusiness" in lowered,
        "has_article": bool({"article", "newsarticle"} & lowered),
        "has_faq_page": "faqpage" in lowered,
        "has_service": "service" in lowered,
        "has_website": "website" in lowered,
        "same_as": sorted(same_as),
    }
