from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.api.demo_access import DEMO_TOKEN_HEADER, is_demo_token_enabled, require_demo_token
from app.api.routes.report import build_task_report_response
from app.api.routes.tasks import task_service
from app.core.exceptions import AppError
from app.models.responses import success_response
from app.models.task import TaskAuditRequest

# Demo 路由：返回模板化后的交互式 GEO 审计控制台页面
router = APIRouter(tags=["demo"])

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "web" / "templates" / "demo.html"


@router.get("/", response_class=HTMLResponse)
async def demo_page() -> HTMLResponse:
    """返回 demo 模板页面。

    页面主体、样式和脚本都已拆分到:
    - app/web/templates/demo.html
    - app/web/static/css/demo.css
    - app/web/static/js/demo/
    """
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))


@router.get("/api/v1/demo/token-status")
async def demo_token_status() -> dict:
    """返回 demo token 保护状态，不暴露真实 token。"""
    return success_response(
        {
            "token_required": is_demo_token_enabled(),
            "header_name": DEMO_TOKEN_HEADER,
        }
    )


@router.post("/api/v1/demo/verify-token")
async def verify_demo_token(request: Request) -> dict:
    """校验 demo token，用于页面显式解锁按钮。"""
    require_demo_token(request)
    return success_response(
        {
            "token_required": is_demo_token_enabled(),
            "verified": True,
        }
    )


@router.post("/api/v1/demo/tasks/audit")
async def create_demo_audit_task(request: Request, payload: TaskAuditRequest) -> dict:
    """demo 页专用创建任务入口，要求携带 demo token。"""
    require_demo_token(request)
    task = await task_service.create_task(payload)
    return success_response(task.model_dump(mode="json"))


@router.get("/api/v1/demo/tasks/{task_id}")
async def get_demo_audit_task(task_id: str, request: Request) -> dict:
    """demo 页专用任务查询入口，要求携带 demo token。"""
    require_demo_token(request)
    task = await task_service.get_task(task_id)
    if not task:
        raise AppError(404, "task not found")
    return success_response(task.model_dump(mode="json"))


@router.get("/api/v1/demo/tasks/{task_id}/knowledge-graph")
async def get_demo_task_knowledge_graph(task_id: str, request: Request) -> dict:
    """demo 页专用知识图谱查询入口，要求携带 demo token。"""
    require_demo_token(request)
    graph_payload = await task_service.site_graph_service.load_task_graph(task_id)
    if graph_payload is None:
        raise AppError(404, "task knowledge graph not found")
    return success_response(graph_payload)


@router.get("/api/v1/demo/tasks/{task_id}/report", response_class=PlainTextResponse)
async def export_demo_task_report(task_id: str, request: Request) -> PlainTextResponse:
    """demo 页专用报告导出入口，要求携带 demo token。"""
    require_demo_token(request)
    return await build_task_report_response(task_id)
