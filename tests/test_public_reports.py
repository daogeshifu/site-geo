import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.routes import public_reports, report
from app.core.config import settings
from app.main import app
from app.models.requests import LLMConfig
from app.models.task import AuditTask, TaskAuditRequest, TaskStep
from app.services.audit.sgeo import SgeoAuditService
from app.services.infra.cache import CacheService
from app.services.infra.site_assets import SiteAssetStore
from app.services.infra.task_reports import TaskReportStore
from app.services.orchestration.tasks import TaskService


def completed_report():
    now = datetime.now(timezone.utc) - timedelta(days=30)
    return AuditTask(
        task_id="saved-report-123", task_type="site_geo_audit", url="https://example.com/",
        normalized_url="https://example.com/", domain="example.com", cache_key="cache-key",
        created_at=now, updated_at=now, completed_at=now, status="completed",
        current_step="completed", progress_percent=100, feedback_lang="zh",
        llm=LLMConfig(api_key="private-llm-key", base_url="https://private-llm.example/"),
        step_order=["sgeo", "summary"],
        steps={"sgeo": TaskStep(name="sgeo", status="completed", data={"score": 77.44})},
        result={"url": "https://example.com/", "sgeo": {
            "score": 77.44, "scoring_version": "onsite-sgeo-v1", "status": "provisional",
            "pages": [{"url": "https://example.com/", "final_url": "https://example.com/",
                       "page_type": "homepage", "status": "provisional", "score": 80}],
        }, "summary": {"sgeo_score": 77.44, "summary": "SGEO 就绪度：77.44/100"}},
    )


def service_at(directory):
    service = TaskService.__new__(TaskService)
    service.tasks = {}
    service._lock = asyncio.Lock()
    service.cache_service = CacheService(str(directory / "cache"))
    service.report_store = TaskReportStore(directory / "reports")
    service.asset_store = SimpleNamespace(available=False, backend="file")
    service.sgeo_audit_service = SgeoAuditService()
    return service


@pytest.fixture
def public_client(tmp_path, monkeypatch):
    service = service_at(tmp_path)
    service.report_store.save(completed_report())
    monkeypatch.setattr(public_reports, "task_service", service)
    monkeypatch.setattr(report, "task_service", service)
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "owner-secret")
    try:
        with TestClient(app) as client:
            yield client, service
    finally:
        object.__setattr__(settings, "demo_access_token", original)


def test_public_report_restores_after_restart_without_token_or_llm_credentials(public_client):
    client, service = public_client
    assert service.tasks == {}
    response = client.get("/api/v1/public/reports/saved-report-123")
    assert response.status_code == 200
    task = response.json()["data"]
    assert task["result"]["sgeo"]["score"] == 77.44
    assert task["public_report"] is True
    assert "private-llm-key" not in response.text
    assert "private-llm.example" not in response.text
    assert "cache_key" not in task
    assert "data" not in task["steps"]["sgeo"]
    assert service.tasks["saved-report-123"].steps["sgeo"].data["score"] == 77.44


def test_public_pages_and_markdown_use_saved_result_without_token(public_client):
    client, _ = public_client
    pages = client.get("/api/v1/public/reports/saved-report-123/pages")
    assert pages.status_code == 200
    assert pages.json()["data"]["pages"][0]["url"] == "https://example.com/"
    assert "source_key" not in pages.json()["data"]["pages"][0]
    markdown = client.get("/api/v1/public/reports/saved-report-123/report")
    assert markdown.status_code == 200
    assert "SGEO score: 77.44/100" in markdown.text
    assert "attachment" in markdown.headers["content-disposition"]


def test_public_reader_cannot_create_or_read_active_tasks(public_client):
    client, service = public_client
    active = completed_report().model_copy(update={"task_id": "active-task-123", "status": "running"})
    service.tasks[active.task_id] = active
    assert client.get("/api/v1/public/reports/active-task-123").status_code == 404
    assert client.get("/api/v1/public/reports/active-task-123/pages").status_code == 404
    assert client.post("/api/v1/public/reports/saved-report-123").status_code == 401
    assert client.post("/api/v1/tasks/audit", json={"url": "https://example.com/"}).status_code == 401
    assert client.get("/api/v1/tasks/saved-report-123").status_code == 401
    assert client.get("/api/v1/public/reports/missing-task-123").status_code == 404


def test_report_files_ignore_request_cache_ttl_and_do_not_store_credentials(tmp_path):
    store = TaskReportStore(tmp_path)
    task = completed_report()
    store.save(task)
    saved = (tmp_path / f"{task.task_id}.json").read_text()
    assert "private-llm-key" not in saved
    assert "private-llm.example" not in saved
    assert TaskReportStore(tmp_path).get(task.task_id).result["sgeo"]["score"] == 77.44
    assert store.get("../outside") is None
    assert not list(tmp_path.glob("*.tmp"))
    (tmp_path / "broken-task-123.json").write_text("{")
    assert store.get("broken-task-123") is None


@pytest.mark.asyncio
async def test_new_and_cache_hit_tasks_are_durable_before_completion_is_visible(tmp_path):
    service = service_at(tmp_path)
    result = completed_report().result
    service._run_site_geo_task = AsyncMock(return_value=result)
    request = TaskAuditRequest(url="https://example.com/", task_type="site_geo_audit")
    task = await service.create_task(request)
    for _ in range(1000):
        if task.status in {"completed", "failed"}:
            break
        await asyncio.sleep(.001)
    assert task.status == "completed", task.error
    assert service.report_store.get(task.task_id).result == result
    cached = await service.create_task(request)
    assert cached.cached is True
    assert service.report_store.get(cached.task_id).result == result
    restarted = service_at(tmp_path)
    assert (await restarted.get_task(task.task_id)).result == result
    assert (await restarted.get_task(cached.task_id)).task_id == cached.task_id
    service._run_site_geo_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_preexisting_mysql_report_is_backfilled_once(tmp_path):
    service = service_at(tmp_path)
    task = completed_report()
    service.asset_store = SimpleNamespace(available=True, load_task=AsyncMock(return_value=task))
    restored = await service.get_task(task.task_id)
    assert restored.result["sgeo"]["score"] == 77.44
    assert service.report_store.get(task.task_id) is not None
    service.tasks.clear()
    assert (await service.get_task(task.task_id)).result == task.result
    service.asset_store.load_task.assert_awaited_once_with(task.task_id)


@pytest.mark.asyncio
async def test_mysql_report_reader_decodes_stored_result_and_original_task_id():
    task = completed_report()
    row = task.model_dump(exclude={"result", "llm", "steps"})
    row.update(result_json=json.dumps(task.result), requested_max_pages=50)
    store = SiteAssetStore.__new__(SiteAssetStore)
    store.enabled, store._degraded = True, False
    store.client = SimpleNamespace(fetchone=AsyncMock(return_value=row))
    loaded = await store.load_task(task.task_id)
    assert loaded.task_id == task.task_id
    assert loaded.result["sgeo"]["score"] == 77.44
    assert loaded.max_pages == 50
    assert loaded.progress_percent == 100


def test_updated_report_assets_revalidate_and_public_api_needs_no_auth_in_docs(public_client):
    client, _ = public_client
    for path in ["/", "/static/js/demo/index.js", "/static/js/demo/site-report.js"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/api/v1/public/reports/{task_id}"]["get"]["security"] == []
    assert paths["/api/v1/tasks/{task_id}"]["get"]["security"] == [{"ApiToken": []}]
