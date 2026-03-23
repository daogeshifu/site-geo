from __future__ import annotations

import httpx

from app.models.discovery import LlmsResult
from app.utils.fetcher import fetch_url
from app.utils.heuristics import assess_llms_effectiveness
from app.utils.url_utils import get_site_root


async def inspect_llms(base_url: str, client: httpx.AsyncClient | None = None) -> LlmsResult:
    llms_url = f"{get_site_root(base_url)}/llms.txt"
    try:
        response = await fetch_url(llms_url, client=client)
    except Exception:
        return LlmsResult(url=llms_url, exists=False)

    if response.status_code >= 400:
        return LlmsResult(url=llms_url, exists=False, status_code=response.status_code)

    preview = response.text[:500].strip()
    result = LlmsResult(
        url=llms_url,
        exists=True,
        status_code=response.status_code,
        content_preview=preview,
        content_length=len(response.text),
    )
    quality = assess_llms_effectiveness(result)
    result.effectiveness_score = quality["score"]
    result.signals = quality["signals"]
    return result
