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

router = APIRouter(prefix="/api/v1", tags=["audit"])
shared_discovery_service = DiscoveryService()
visibility_service = VisibilityService(shared_discovery_service)
technical_service = TechnicalService(shared_discovery_service)
content_service = ContentService(shared_discovery_service)
schema_service = SchemaService(shared_discovery_service)
platform_service = PlatformService(shared_discovery_service)
full_audit_service = FullAuditService(shared_discovery_service)
summarizer_service = SummarizerService()


@router.post("/audit/visibility")
async def audit_visibility(request: AuditModuleRequest) -> dict:
    result = await visibility_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/technical")
async def audit_technical(request: AuditModuleRequest) -> dict:
    result = await technical_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/content")
async def audit_content(request: AuditModuleRequest) -> dict:
    result = await content_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/schema")
async def audit_schema(request: AuditModuleRequest) -> dict:
    result = await schema_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/platform")
async def audit_platform(request: AuditModuleRequest) -> dict:
    result = await platform_service.audit(
        request.url,
        request.discovery,
        mode=request.mode,
        llm_config=request.llm,
    )
    return success_response(result.model_dump())


@router.post("/audit/full")
async def audit_full(request: FullAuditRequest) -> dict:
    result = await full_audit_service.audit_full(
        request.url,
        mode=request.mode,
        llm_config=request.llm,
        discovery=request.discovery,
    )
    return success_response(result)


@router.post("/audit/summarize")
async def summarize_audit(request: SummarizeRequest) -> dict:
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
