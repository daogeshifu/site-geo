from __future__ import annotations

from fastapi import APIRouter

from app.models.requests import AuditModuleRequest, FullAuditRequest, SummarizeRequest
from app.models.responses import success_response
from app.services.audit_service import FullAuditService
from app.services.content_service import ContentService
from app.services.discovery_service import DiscoveryService
from app.services.platform_service import PlatformService
from app.services.schema_service import SchemaService
from app.services.summarizer_service import SummarizerService
from app.services.technical_service import TechnicalService
from app.services.visibility_service import VisibilityService

# 审计路由，挂载在 /api/v1 前缀下，包含所有 GEO 审计模块端点
router = APIRouter(prefix="/api/v1", tags=["audit"])

# --- 服务实例（模块级单例）---
# 所有审计服务共享同一个 DiscoveryService 实例，
# 确保同一次全量审计中 Discovery 数据仅抓取一次
shared_discovery_service = DiscoveryService()
visibility_service = VisibilityService(shared_discovery_service)
technical_service = TechnicalService(shared_discovery_service)
content_service = ContentService(shared_discovery_service)
schema_service = SchemaService(shared_discovery_service)
platform_service = PlatformService(shared_discovery_service)
full_audit_service = FullAuditService(shared_discovery_service)
# Summarizer 不依赖 Discovery，独立实例化
summarizer_service = SummarizerService()


@router.post("/audit/visibility")
async def audit_visibility(request: AuditModuleRequest) -> dict:
    """执行 AI 可见性审计

    评估站点对 AI 爬虫的访问权限（robots.txt）、llms.txt 质量
    和内容可引用性，占 GEO 总分约 25% + 20%。

    Args:
        request: 包含 URL、可选 Discovery 缓存、审计模式和 LLM 配置的请求体

    Returns:
        VisibilityAuditResult 序列化字典
    """
    result = await visibility_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/technical")
async def audit_technical(request: AuditModuleRequest) -> dict:
    """执行技术 SEO 审计

    检查安全头、HTTPS、robots 配置、Sitemap、SSR 信号、
    渲染阻塞资源等 15 项技术指标，约占 GEO 总分 15%。

    Args:
        request: 包含 URL、可选 Discovery 缓存、审计模式和 LLM 配置的请求体

    Returns:
        TechnicalAuditResult 序列化字典
    """
    result = await technical_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/content")
async def audit_content(request: AuditModuleRequest) -> dict:
    """执行内容质量审计（E-E-A-T）

    从专业度（Expertise）、权威性（Authority）、可信度（Trust）
    和内容深度四个维度评估内容质量，约占 GEO 总分 20%。

    Args:
        request: 包含 URL、可选 Discovery 缓存、审计模式和 LLM 配置的请求体

    Returns:
        ContentAuditResult 序列化字典
    """
    result = await content_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/schema")
async def audit_schema(request: AuditModuleRequest) -> dict:
    """执行 Schema 结构化数据审计

    检测 JSON-LD 类型覆盖（Organization / Article / FAQPage 等）
    和 sameAs 跨平台链接，约占 GEO 总分 15%。

    Args:
        request: 包含 URL、可选 Discovery 缓存、审计模式和 LLM 配置的请求体

    Returns:
        SchemaAuditResult 序列化字典
    """
    result = await schema_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/platform")
async def audit_platform(request: AuditModuleRequest) -> dict:
    """执行 AI 平台优化审计

    针对 Google AI Overviews / ChatGPT / Perplexity / Gemini / Bing Copilot
    五大 AI 平台逐一评分，约占 GEO 总分 15%。

    Args:
        request: 包含 URL、可选 Discovery 缓存、审计模式和 LLM 配置的请求体

    Returns:
        PlatformAuditResult 序列化字典
    """
    result = await platform_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/full")
async def audit_full(request: FullAuditRequest) -> dict:
    """执行全量 GEO 审计

    并发运行五个审计模块（Visibility / Technical / Content / Schema / Platform），
    汇总结果并生成综合 GEO 分数（0-100）和优先行动计划。

    Args:
        request: 包含 URL、审计模式、LLM 配置和可选 Discovery 缓存的请求体

    Returns:
        包含所有模块审计结果和 Summary 的字典
    """
    result = await full_audit_service.audit_full(
        request.url,
        mode=request.mode,
        llm_config=request.llm,
        discovery=request.discovery,
    )
    return success_response(result)


@router.post("/audit/summarize")
async def summarize_audit(request: SummarizeRequest) -> dict:
    """生成 GEO 审计摘要和行动计划

    接收五个审计模块的结果，计算六维度加权综合分，
    识别最薄弱维度并生成优先排序的行动建议。
    可选 Premium 模式通过 LLM 丰富摘要内容。

    Args:
        request: 包含所有模块审计结果、URL 和 LLM 配置的请求体

    Returns:
        SummaryResult 序列化字典（含 geo_score / dimensions / action_plan）
    """
    result = await summarizer_service.summarize(
        url=request.url,
        discovery=request.discovery,
        visibility=request.visibility,
        technical=request.technical,
        content=request.content,
        schema=request.schema_result,
        platform=request.platform,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())
