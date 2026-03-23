from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.exceptions import AppError
from app.models.audit import (
    ContentAuditResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.models.report import ReportExportRequest
from app.models.responses import success_response
from app.services.report_service import ReportService
from app.services.summarizer_service import SummarizerService
from app.api.routes.tasks import task_service

router = APIRouter(prefix="/api/v1", tags=["report"])
report_service = ReportService()
summarizer_service = SummarizerService()


@router.post("/report/export")
async def export_report(request: ReportExportRequest) -> dict:
    summary = request.summary or await summarizer_service.summarize(
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
    markdown = report_service.render_markdown(
        url=request.url,
        discovery=request.discovery,
        visibility=request.visibility,
        technical=request.technical,
        content=request.content,
        schema_result=request.schema_result,
        platform=request.platform,
        summary=summary,
    )
    filename = report_service.build_filename(request.discovery)
    return success_response({"filename": filename, "markdown": markdown})


@router.get("/tasks/{task_id}/report", response_class=PlainTextResponse)
async def export_task_report(task_id: str) -> PlainTextResponse:
    task = await task_service.get_task(task_id)
    if not task:
        raise AppError(404, "task not found")
    if task.status != "completed" or not task.result:
        raise AppError(409, "task is not completed yet")

    discovery = DiscoveryResult.model_validate(task.result["discovery"])
    visibility = VisibilityAuditResult.model_validate(task.result["visibility"])
    technical = TechnicalAuditResult.model_validate(task.result["technical"])
    content = ContentAuditResult.model_validate(task.result["content"])
    schema_result = SchemaAuditResult.model_validate(task.result["schema"])
    platform = PlatformAuditResult.model_validate(task.result["platform"])
    summary = SummaryResult.model_validate(task.result["summary"])
    markdown = report_service.render_markdown(
        url=task.url,
        discovery=discovery,
        visibility=visibility,
        technical=technical,
        content=content,
        schema_result=schema_result,
        platform=platform,
        summary=summary,
    )
    filename = report_service.build_filename(discovery)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(content=markdown, media_type="text/markdown; charset=utf-8", headers=headers)
