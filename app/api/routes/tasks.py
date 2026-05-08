from __future__ import annotations

from fastapi import APIRouter

from app.core.exceptions import AppError
from app.models.responses import success_response
from app.models.task import AuditTask, TaskAuditRequest
from app.services.orchestration.tasks import TaskService

# 异步任务路由，挂载在 /api/v1/tasks 前缀下
router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# 模块级单例：TaskService 内部维护任务内存存储和缓存服务
task_service = TaskService()


def _task_site_id(task: AuditTask) -> int | None:
    summary = task.site_asset_summary
    if summary is None:
        return None
    if hasattr(summary, "site_id"):
        return getattr(summary, "site_id")
    if isinstance(summary, dict):
        return summary.get("site_id")
    return None


def build_pending_graph_payload(task: AuditTask, note: str) -> dict:
    site_id = _task_site_id(task)
    return {
        "task_id": task.task_id,
        "snapshot_task_id": None,
        "exact_task_match": False,
        "backend": "mysql" if task_service.site_graph_service.enabled else (task.storage_backend or "file"),
        "available": task.build_knowledge_graph and task_service.site_graph_service.enabled,
        "built": False,
        "note": note,
        "task": {
            "task_id": task.task_id,
            "site_id": site_id,
            "domain": task.domain,
            "status": task.status,
            "url": task.url,
            "normalized_url": task.normalized_url,
            "full_audit": task.full_audit,
            "requested_max_pages": task.max_pages,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
        },
        "site_id": site_id,
        "graph_version": task_service.site_graph_service.GRAPH_VERSION,
        "built_at": None,
        "site": {},
        "summary": {
            "entity_count": 0,
            "edge_count": 0,
            "evidence_count": 0,
            "source_snapshot_count": 0,
            "entity_type_counts": {},
            "relation_type_counts": {},
        },
        "entities": [],
        "edges": [],
        "evidence": [],
        "source_pages": [],
    }


@router.post("/audit")
async def create_audit_task(request: TaskAuditRequest) -> dict:
    """创建异步全量审计任务

    任务创建后立即返回任务 ID，审计在后台异步执行。
    客户端通过 GET /tasks/{task_id} 轮询任务状态和进度。

    缓存命中时任务会快速完成（直接返回缓存结果），
    未命中时则异步运行完整的五模块审计流程。

    Args:
        request: 包含目标 URL、审计模式和 LLM 配置的任务请求体

    Returns:
        AuditTask 序列化字典（含 task_id / status / steps）
    """
    task = await task_service.create_task(request)
    return success_response(task.model_dump(mode="json"))


@router.get("/{task_id}")
async def get_audit_task(task_id: str) -> dict:
    """查询审计任务状态

    返回任务的当前状态（pending / running / completed / failed）、
    各步骤进度和审计结果（completed 时）。

    Args:
        task_id: 任务唯一标识符

    Returns:
        AuditTask 序列化字典（completed 时含完整 result 字段）

    Raises:
        AppError 404: 任务 ID 不存在
    """
    task = await task_service.get_task(task_id)
    if not task:
        raise AppError(404, "task not found")
    return success_response(task.model_dump(mode="json"))


@router.get("/{task_id}/knowledge-graph")
async def get_task_knowledge_graph(task_id: str) -> dict:
    """按任务 ID 返回对应的知识图谱结构数据。"""
    task = await task_service.get_task(task_id)
    try:
        graph_payload = await task_service.site_graph_service.load_task_graph(task_id)
    except Exception:
        if task:
            return success_response(build_pending_graph_payload(task, "Knowledge graph is still being prepared for this task."))
        raise
    if graph_payload is None:
        if task:
            return success_response(build_pending_graph_payload(task, "Knowledge graph has not been built for this task yet."))
        raise AppError(404, "task knowledge graph not found")
    return success_response(graph_payload)
