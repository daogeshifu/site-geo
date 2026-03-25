from __future__ import annotations

import asyncio
import time
from typing import Any

from app.models.discovery import DiscoveryResult
from app.models.requests import LLMConfig
from app.services.discovery_service import DiscoveryService
from app.services.observation_service import ObservationService


class AuditBaseService:
    """所有审计模块服务的基类，提供公共工具方法"""

    def __init__(self, discovery_service: DiscoveryService | None = None) -> None:
        # 允许注入共享的 DiscoveryService 实例，避免重复创建
        self.discovery_service = discovery_service or DiscoveryService()

    async def ensure_discovery(
        self,
        url: str,
        discovery: DiscoveryResult | dict[str, Any] | None = None,
        *,
        full_audit: bool = False,
        max_pages: int = 12,
    ) -> DiscoveryResult:
        """确保 DiscoveryResult 可用：
        - 若已是 DiscoveryResult 实例，直接返回
        - 若是 dict，通过 Pydantic 反序列化
        - 若为 None，触发网络抓取
        """
        if isinstance(discovery, DiscoveryResult):
            return discovery
        if isinstance(discovery, dict):
            return DiscoveryResult.model_validate(discovery)
        return await self.discovery_service.discover(url, full_audit=full_audit, max_pages=max_pages)

    def set_execution_metadata(
        self,
        result: Any,
        mode: str,
        llm_config: LLMConfig | None = None,
    ) -> Any:
        """将审计模式和 LLM 配置信息写入结果对象"""
        result.audit_mode = mode
        if llm_config:
            result.llm_provider = llm_config.provider
            result.llm_model = llm_config.model
        return result

    def collect_input_pages(self, discovery: DiscoveryResult, *page_keys: str) -> list[str]:
        """收集本次审计使用的页面 URL 列表，去重后返回

        若指定的 page_keys 都不存在，回退到 discovery.final_url
        """
        keys = page_keys or tuple(discovery.page_profiles.keys())
        urls: list[str] = []
        for key in keys:
            profile = discovery.page_profiles.get(key)
            if profile and profile.final_url not in urls:
                urls.append(profile.final_url)
        if not urls and discovery.final_url:
            urls.append(discovery.final_url)
        return urls

    def finalize_audit_result(
        self,
        result: Any,
        *,
        module_key: str,
        input_pages: list[str],
        started_at: float,
        confidence: float,
    ) -> Any:
        """填充审计结果的通用元数据字段（模块标识、输入页面、耗时、置信度）"""
        result.module_key = module_key
        result.input_pages = input_pages
        result.duration_ms = int((time.perf_counter() - started_at) * 1000)
        # 置信度限制在 [0, 1] 范围内
        result.confidence = max(0.0, min(1.0, round(confidence, 2)))
        return result


class FullAuditService(AuditBaseService):
    """全量审计服务：并行执行 5 个审计模块并生成汇总报告"""

    def __init__(self, discovery_service: DiscoveryService | None = None) -> None:
        super().__init__(discovery_service)
        self.observation_service = ObservationService()

    async def audit_full(
        self,
        url: str,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        discovery: DiscoveryResult | dict[str, Any] | None = None,
        observation=None,
        full_audit: bool = False,
        max_pages: int = 12,
        feedback_lang: str = "en",
    ) -> dict[str, Any]:
        """执行完整 GEO 审计流程

        1. 确保 DiscoveryResult 可用（复用或重新抓取）
        2. 并行运行 5 个审计模块（visibility/technical/content/schema/platform）
        3. 汇总计算复合 GEO 评分
        返回包含所有模块结果的 dict
        """
        # 延迟导入避免循环依赖
        from app.services.content_service import ContentService
        from app.services.page_diagnostics_service import PageDiagnosticsService
        from app.services.platform_service import PlatformService
        from app.services.schema_service import SchemaService
        from app.services.summarizer_service import SummarizerService
        from app.services.technical_service import TechnicalService
        from app.services.visibility_service import VisibilityService

        resolved_discovery = await self.ensure_discovery(url, discovery, full_audit=full_audit, max_pages=max_pages)
        # 所有模块共享同一个 DiscoveryService 实例
        visibility_service = VisibilityService(self.discovery_service)
        technical_service = TechnicalService(self.discovery_service)
        content_service = ContentService(self.discovery_service)
        schema_service = SchemaService(self.discovery_service)
        platform_service = PlatformService(self.discovery_service)
        page_diagnostics_service = PageDiagnosticsService()
        summarizer_service = SummarizerService()

        # 5 个审计模块并行执行，共享已解析的 discovery
        visibility, technical, content, schema, platform = await asyncio.gather(
            visibility_service.audit(url, resolved_discovery, mode=mode, llm_config=llm_config, feedback_lang=feedback_lang),
            technical_service.audit(url, resolved_discovery, mode=mode, llm_config=llm_config),
            content_service.audit(url, resolved_discovery, mode=mode, llm_config=llm_config, feedback_lang=feedback_lang),
            schema_service.audit(url, resolved_discovery, mode=mode, llm_config=llm_config),
            platform_service.audit(url, resolved_discovery, mode=mode, llm_config=llm_config, feedback_lang=feedback_lang),
        )

        # 汇总：根据 5 个模块结果计算复合 GEO 评分
        summary = await summarizer_service.summarize(
            url=url,
            discovery=resolved_discovery,
            visibility=visibility,
            technical=technical,
            content=content,
            schema=schema,
            platform=platform,
            observation=self.observation_service.build(observation),
            mode=mode,
            llm_config=llm_config,
            feedback_lang=feedback_lang,
        )
        page_diagnostics = page_diagnostics_service.build(resolved_discovery, max_pages=max_pages) if full_audit else []

        return {
            "url": url,
            "discovery": resolved_discovery.model_dump(),
            "visibility": visibility.model_dump(),
            "technical": technical.model_dump(),
            "content": content.model_dump(),
            "schema": schema.model_dump(),
            "platform": platform.model_dump(),
            "page_diagnostics": [item.model_dump() for item in page_diagnostics],
            "observation": summary.observation.model_dump() if summary.observation else None,
            "summary": summary.model_dump(),
        }
