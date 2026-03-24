from __future__ import annotations

import httpx

from app.models.discovery import LlmsResult
from app.utils.fetcher import fetch_url
from app.utils.heuristics import assess_llms_effectiveness
from app.utils.url_utils import get_site_root


async def inspect_llms(base_url: str, client: httpx.AsyncClient | None = None) -> LlmsResult:
    """抓取并评估站点的 llms.txt 文件

    llms.txt 是新兴的机器可读引导文件标准，帮助 AI 系统了解：
    - 网站的目的和主要内容
    - 可引用的品牌/服务信息
    - 引用偏好和联系方式

    Args:
        base_url: 站点 URL（取根域名路径 /llms.txt）
        client: 可选的共享 HTTP 客户端

    Returns:
        LlmsResult：包含存在状态、内容预览、有效性评分和信号检查
    """
    llms_url = f"{get_site_root(base_url)}/llms.txt"
    try:
        response = await fetch_url(llms_url, client=client)
    except Exception:
        return LlmsResult(url=llms_url, exists=False)

    if response.status_code >= 400:
        return LlmsResult(url=llms_url, exists=False, status_code=response.status_code)

    # 取前 500 字符作为预览（供后续质量评估和 LLM 分析使用）
    preview = response.text[:500].strip()
    result = LlmsResult(
        url=llms_url,
        exists=True,
        status_code=response.status_code,
        content_preview=preview,
        content_length=len(response.text),
    )
    # 评估 llms.txt 的有效性（品牌提及、服务描述、引导关键词等）
    quality = assess_llms_effectiveness(result)
    result.effectiveness_score = quality["score"]
    result.signals = quality["signals"]
    return result
