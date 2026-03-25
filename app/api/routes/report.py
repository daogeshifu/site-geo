from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.exceptions import AppError
from app.models.audit import (
    ContentAuditResult,
    ObservationResult,
    PageDiagnosticResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.models.report import ReportExportRequest
from app.models.responses import success_response
from app.services.observation_service import ObservationService
from app.services.report_service import ReportService
from app.services.summarizer_service import SummarizerService
from app.api.routes.tasks import task_service  # 复用 tasks 路由中的 task_service 单例

# 报告导出路由，挂载在 /api/v1 前缀下
router = APIRouter(prefix="/api/v1", tags=["report"])
report_service = ReportService()
summarizer_service = SummarizerService()
observation_service = ObservationService()


@router.post("/report/export")
async def export_report(request: ReportExportRequest) -> dict:
    """将审计结果渲染为 Markdown 报告

    如果请求中未携带 summary，会先调用 SummarizerService 生成摘要，
    再将所有审计结果汇入 Markdown 报告模板。

    报告包含：执行摘要、GEO 总分、各模块详情、
    关键发现、改进建议和附录数据。

    Args:
        request: 包含所有模块审计结果、URL 和可选 summary 的导出请求体

    Returns:
        包含 filename（建议文件名）和 markdown（报告内容）的字典
    """
    # 若请求中已附带摘要则直接使用，否则实时生成（Premium 模式下由 LLM 丰富内容）
    summary = request.summary or await summarizer_service.summarize(
        url=request.url,
        discovery=request.discovery,
        visibility=request.visibility,
        technical=request.technical,
        content=request.content,
        schema=request.schema_result,
        platform=request.platform,
        observation=request.observation_result or observation_service.build(request.observation),
        mode=request.mode,
        llm_config=request.llm,
    )
    if not summary.observation and request.observation_result:
        summary.observation = request.observation_result
    markdown = report_service.render_markdown(
        url=request.url,
        discovery=request.discovery,
        visibility=request.visibility,
        technical=request.technical,
        content=request.content,
        schema_result=request.schema_result,
        platform=request.platform,
        summary=summary,
        page_diagnostics=request.page_diagnostics,
    )
    filename = report_service.build_filename(request.discovery)
    return success_response({"filename": filename, "markdown": markdown})


@router.get("/tasks/{task_id}/report", response_class=PlainTextResponse)
async def export_task_report(task_id: str) -> PlainTextResponse:
    """从已完成任务中导出 Markdown 报告（文件下载）

    从任务存储中反序列化所有审计结果，渲染为 Markdown 报告，
    以文件下载形式（Content-Disposition: attachment）返回。

    Args:
        task_id: 已完成的审计任务 ID

    Returns:
        PlainTextResponse：Markdown 格式的报告，Content-Type 为 text/markdown

    Raises:
        AppError 404: 任务不存在
        AppError 409: 任务尚未完成（status != completed 或 result 为空）
    """
    task = await task_service.get_task(task_id)
    if not task:
        raise AppError(404, "task not found")
    # 任务未完成时拒绝导出，返回 409 Conflict
    if task.status != "completed" or not task.result:
        raise AppError(409, "task is not completed yet")

    # 从任务结果字典中反序列化各模块 Pydantic 模型
    discovery = DiscoveryResult.model_validate(task.result["discovery"])
    visibility = VisibilityAuditResult.model_validate(task.result["visibility"])
    technical = TechnicalAuditResult.model_validate(task.result["technical"])
    content = ContentAuditResult.model_validate(task.result["content"])
    schema_result = SchemaAuditResult.model_validate(task.result["schema"])
    platform = PlatformAuditResult.model_validate(task.result["platform"])
    summary = SummaryResult.model_validate(task.result["summary"])
    observation = ObservationResult.model_validate(task.result["observation"]) if task.result.get("observation") else None
    page_diagnostics = [PageDiagnosticResult.model_validate(item) for item in task.result.get("page_diagnostics", [])]
    if observation and not summary.observation:
        summary.observation = observation
    markdown = report_service.render_markdown(
        url=task.url,
        discovery=discovery,
        visibility=visibility,
        technical=technical,
        content=content,
        schema_result=schema_result,
        platform=platform,
        summary=summary,
        page_diagnostics=page_diagnostics,
    )
    filename = report_service.build_filename(discovery)
    # 设置 Content-Disposition 头触发浏览器下载行为
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(content=markdown, media_type="text/markdown; charset=utf-8", headers=headers)
