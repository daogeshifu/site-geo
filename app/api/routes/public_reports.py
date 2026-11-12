"""Read-only access to completed reports through their existing task links."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.report import build_task_report_response
from app.api.routes.tasks import task_service
from app.core.exceptions import AppError
from app.models.responses import success_response
from app.services.infra.page_sources import read_page_source
from app.services.reporting.site_pages import task_site_pages

router = APIRouter(prefix="/api/v1/public/reports", tags=["shared reports"])


async def completed_task(task_id: str):
    task = await task_service.get_task(task_id)
    if task is None or task.status != "completed" or task.result is None:
        raise AppError(404, "Completed report not found")
    return task


@router.get("/{task_id}")
async def get_public_report(task_id: str) -> dict:
    task = await completed_task(task_id)
    payload = task.model_dump(mode="json", exclude={
        "cache_key": True, "error_details": True,
        "llm": {"api_key", "base_url"}, "steps": {"__all__": {"data"}},
    })
    payload["public_report"] = True
    return success_response(payload)


@router.get("/{task_id}/pages")
async def get_public_report_pages(task_id: str) -> dict:
    pages = task_site_pages(await completed_task(task_id))
    return success_response({"pages": [{k: v for k, v in page.items() if k != "source_key"} for page in pages]})


@router.get("/{task_id}/pages/{page_id}/source")
async def get_public_report_page_source(task_id: str, page_id: str) -> dict:
    pages = task_site_pages(await completed_task(task_id))
    page = next((page for page in pages if page["id"] == page_id), None)
    if page is None:
        raise AppError(404, "Page not found in this report")
    source = await read_page_source(page["source_key"]) if page.get("source_key") else None
    return success_response({"html": source, "fetched_at": page.get("fetched_at"),
                             "truncated": page.get("source_truncated", False)})


@router.get("/{task_id}/report")
async def export_public_report(task_id: str):
    await completed_task(task_id)
    return await build_task_report_response(task_id)
