from __future__ import annotations

from fastapi import APIRouter

from app.core.exceptions import AppError
from app.models.responses import success_response
from app.models.task import TaskAuditRequest
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
task_service = TaskService()


@router.post("/audit")
async def create_audit_task(request: TaskAuditRequest) -> dict:
    task = await task_service.create_task(request)
    return success_response(task.model_dump(mode="json"))


@router.get("/{task_id}")
async def get_audit_task(task_id: str) -> dict:
    task = await task_service.get_task(task_id)
    if not task:
        raise AppError(404, "task not found")
    return success_response(task.model_dump(mode="json"))
