from __future__ import annotations

from fastapi import APIRouter

from app.core.exceptions import AppError
from app.models.responses import success_response
from app.models.task import TaskAuditRequest
from app.services.orchestration.tasks import TaskService

# 异步任务路由，挂载在 /api/v1/tasks 前缀下
router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# 模块级单例：TaskService 内部维护任务内存存储和缓存服务
task_service = TaskService()


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
    graph_payload = await task_service.site_graph_service.load_task_graph(task_id)
    if graph_payload is None:
        raise AppError(404, "task knowledge graph not found")
    return success_response(graph_payload)
