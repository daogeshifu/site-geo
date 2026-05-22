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


def _graph_job_payload(task: AuditTask | None, graph_kind: str) -> dict | None:
    if task is None:
        return None
    job = (task.graph_jobs or {}).get(graph_kind)
    if job is None:
        return None
    return job.model_dump(mode="json")


def build_pending_graph_payload(task: AuditTask, note: str, *, graph_kind: str = "structure") -> dict:
    graph_service = (
        task_service.site_entity_graph_service
        if graph_kind == "entity"
        else task_service.site_graph_service
    )
    site_id = _task_site_id(task)
    return {
        "task_id": task.task_id,
        "snapshot_task_id": None,
        "exact_task_match": False,
        "backend": "mysql" if graph_service.enabled else (task.storage_backend or "file"),
        "available": task.build_knowledge_graph and graph_service.enabled,
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
        "job": _graph_job_payload(task, graph_kind),
        "site_id": site_id,
        "graph_kind": graph_kind,
        "graph_version": graph_service.GRAPH_VERSION,
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


async def _load_task_graph_response(task_id: str, *, graph_kind: str = "structure") -> dict:
    task = await task_service.get_task(task_id)
    graph_service = (
        task_service.site_entity_graph_service
        if graph_kind == "entity"
        else task_service.site_graph_service
    )
    graph_label = "Entity graph" if graph_kind == "entity" else "Structure graph"
    graph_job = _graph_job_payload(task, graph_kind)
    try:
        graph_payload = await graph_service.load_task_graph(task_id)
    except Exception:
        if task:
            note = f"{graph_label} is still being prepared for this task."
            if graph_job and graph_job.get("status") == "failed":
                note = graph_job.get("error") or graph_job.get("note") or f"{graph_label} failed for this task."
            elif graph_job and graph_job.get("status") == "skipped":
                note = graph_job.get("note") or f"{graph_label} was skipped for this task."
            return success_response(
                build_pending_graph_payload(
                    task,
                    note,
                    graph_kind=graph_kind,
                )
            )
        raise
    if graph_payload is None:
        if task:
            note = f"{graph_label} has not been built for this task yet."
            if graph_job and graph_job.get("status") == "running":
                note = graph_job.get("note") or f"{graph_label} is still being prepared for this task."
            elif graph_job and graph_job.get("status") == "failed":
                note = graph_job.get("error") or graph_job.get("note") or f"{graph_label} failed for this task."
            elif graph_job and graph_job.get("status") == "skipped":
                note = graph_job.get("note") or f"{graph_label} was skipped for this task."
            return success_response(
                build_pending_graph_payload(
                    task,
                    note,
                    graph_kind=graph_kind,
                )
            )
        raise AppError(404, f"task {graph_kind} graph not found")
    graph_payload["graph_kind"] = graph_kind
    graph_payload["job"] = graph_job
    return success_response(graph_payload)


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
    """兼容旧接口：返回结构图谱数据。"""
    return await _load_task_graph_response(task_id, graph_kind="structure")


@router.get("/{task_id}/structure-graph")
async def get_task_structure_graph(task_id: str) -> dict:
    """按任务 ID 返回结构图谱数据。"""
    return await _load_task_graph_response(task_id, graph_kind="structure")


@router.get("/{task_id}/entity-graph")
async def get_task_entity_graph(task_id: str) -> dict:
    """按任务 ID 返回内容实体图谱数据。"""
    return await _load_task_graph_response(task_id, graph_kind="entity")
