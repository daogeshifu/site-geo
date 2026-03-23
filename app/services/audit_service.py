from __future__ import annotations

import asyncio
from typing import Any

from app.models.discovery import DiscoveryResult
from app.models.requests import LLMConfig
from app.services.discovery_service import DiscoveryService


class AuditBaseService:
    def __init__(self, discovery_service: DiscoveryService | None = None) -> None:
        self.discovery_service = discovery_service or DiscoveryService()

    async def ensure_discovery(
        self,
        url: str,
        discovery: DiscoveryResult | dict[str, Any] | None = None,
    ) -> DiscoveryResult:
        if isinstance(discovery, DiscoveryResult):
            return discovery
        if isinstance(discovery, dict):
            return DiscoveryResult.model_validate(discovery)
        return await self.discovery_service.discover(url)

    def set_execution_metadata(
        self,
        result: Any,
        mode: str,
        llm_config: LLMConfig | None = None,
    ) -> Any:
        result.audit_mode = mode
        if llm_config:
            result.llm_provider = llm_config.provider
            result.llm_model = llm_config.model
        return result


class FullAuditService(AuditBaseService):
    async def audit_full(self, url: str, mode: str = "standard", llm_config: LLMConfig | None = None) -> dict[str, Any]:
        from app.services.content_service import ContentService
        from app.services.platform_service import PlatformService
        from app.services.schema_service import SchemaService
        from app.services.summarizer_service import SummarizerService
        from app.services.technical_service import TechnicalService
        from app.services.visibility_service import VisibilityService

        discovery = await self.discovery_service.discover(url)
        visibility_service = VisibilityService(self.discovery_service)
        technical_service = TechnicalService(self.discovery_service)
        content_service = ContentService(self.discovery_service)
        schema_service = SchemaService(self.discovery_service)
        platform_service = PlatformService(self.discovery_service)
        summarizer_service = SummarizerService()

        visibility, technical, content, schema, platform = await asyncio.gather(
            visibility_service.audit(url, discovery, mode=mode, llm_config=llm_config),
            technical_service.audit(url, discovery, mode=mode, llm_config=llm_config),
            content_service.audit(url, discovery, mode=mode, llm_config=llm_config),
            schema_service.audit(url, discovery, mode=mode, llm_config=llm_config),
            platform_service.audit(url, discovery, mode=mode, llm_config=llm_config),
        )

        summary = await summarizer_service.summarize(
            url=url,
            discovery=discovery,
            visibility=visibility,
            technical=technical,
            content=content,
            schema=schema,
            platform=platform,
            mode=mode,
            llm_config=llm_config,
        )

        return {
            "url": url,
            "discovery": discovery.model_dump(),
            "visibility": visibility.model_dump(),
            "technical": technical.model_dump(),
            "content": content.model_dump(),
            "schema": schema.model_dump(),
            "platform": platform.model_dump(),
            "summary": summary.model_dump(),
        }
