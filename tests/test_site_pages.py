import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.api.routes import demo
from app.api import demo_access
from app.core.config import settings
from app.main import app
from app.models.task import AuditTask
from app.models.task import TaskAuditRequest
from app.services.infra.page_sources import MAX_SOURCE_BYTES, capture_page_metadata, read_page_source
from app.services.infra import page_sources
from app.services.reporting.site_pages import task_site_pages
from app.utils.fetcher import FetchedResponse


def make_task():
    now = datetime.now(timezone.utc)
    return AuditTask(
        task_id="inventory-test", url="https://example.com/de/", normalized_url="https://example.com/de/",
        domain="example.com", cache_key="test", created_at=now, updated_at=now,
        result={"discovery": {
            "scope_root_url": "https://example.com/de/",
            "page_profiles": {"homepage": {"final_url": "https://example.com/de/", "title": "Old title", "word_count": 14, "fetched_at": "2025-01-01T00:00:00Z", "source_key": "old"}},
            "sitemap": {"discovered_urls": ["https://example.com/de/", "https://example.com/de/product", "https://example.com/fr/", "https://other.example/de/"]},
        }, "seo": {"sampled_pages": [{"url": "https://example.com/de/", "title": "New title", "word_count": 25, "status_code": 200}]}},
    )


def test_inventory_deduplicates_scope_and_does_not_invent_measurements():
    pages = task_site_pages(make_task())
    assert len(pages) == 2
    sample, discovered = pages
    assert sample["title"] == "New title"
    assert sample["word_count"] == 25
    assert sample["fetched_at"] is None  # Do not reuse a stale timestamp from another fetch.
    assert sample["source_available"] is False
    assert "status_code" not in discovered
    assert "word_count" not in discovered
    assert "fetched_at" not in discovered


def test_html_capture_preserves_text_and_bounds_utf8(tmp_path, monkeypatch):
    monkeypatch.setattr(page_sources, "settings", replace(settings, cache_dir=str(tmp_path)))
    response = FetchedResponse("https://example.com/de/", 200, {"Content-Type": "text/html", "Set-Cookie": "private=value"}, "<script>alert('source only')</script>" + "中" * MAX_SOURCE_BYTES, 82)
    metadata = asyncio.run(capture_page_metadata(response))
    html = asyncio.run(read_page_source(metadata["source_key"]))
    assert len(html.encode("utf-8")) <= MAX_SOURCE_BYTES
    assert html.startswith("<script>alert('source only')</script>")
    assert "\ufffd" not in html
    assert metadata["source_truncated"] is True
    assert metadata["response_headers"] == {"content-type": "text/html"}
    assert metadata["fetched_at"]
    assert metadata["response_time_ms"] == 82
    assert asyncio.run(read_page_source("../../secrets")) is None


def test_source_endpoint_is_token_protected_and_task_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(page_sources, "settings", replace(settings, cache_dir=str(tmp_path)))
    monkeypatch.setattr(demo_access, "settings", replace(settings, demo_access_token="test-token"))
    task = make_task()
    metadata = asyncio.run(capture_page_metadata(FetchedResponse(task.url, 200, {}, "<h1>Captured page</h1>", 55)))
    task.result["seo"]["sampled_pages"][0].update(metadata)

    async def get_task(task_id):
        return task if task_id == task.task_id else None

    monkeypatch.setattr(demo.task_service, "get_task", get_task)
    client = TestClient(app)
    base = f"/api/v1/demo/tasks/{task.task_id}/pages"
    headers = {"X-Demo-Token": "test-token"}
    assert client.get(base).status_code == 401
    pages = client.get(base, headers=headers).json()["data"]["pages"]
    assert "source_key" not in pages[0]
    source_url = f"{base}/{pages[0]['id']}/source"
    assert client.get(source_url).status_code == 401
    assert client.get(source_url, headers=headers).json()["data"]["html"] == "<h1>Captured page</h1>"
    assert client.get(f"{base}/arbitrary-page/source", headers=headers).status_code == 404
    assert client.get(f"{base}/{pages[1]['id']}/source", headers=headers).json()["data"]["html"] is None


def test_seo_excel_export_contains_issue_and_link_sheets(monkeypatch):
    monkeypatch.setattr(demo_access, "settings", replace(settings, demo_access_token="test-token"))
    task = make_task().model_copy(update={"status": "completed", "task_type": "site_seo_audit"})
    task.result["seo"].update({
        "coverage_checks": [{"id": "CHK-014", "summary": "Title 缺失"}],
        "issues_table": [{
            "issue_id": "P-001", "check_item": "页面标题", "priority": "P1", "severity": "high",
            "category": "On-Page SEO", "description": "Title 缺失", "seo_impact": "影响排名",
            "evidence": "https://example.com/de/", "recommendation": "补齐 Title", "owner_team": "SEO",
        }],
    })

    async def get_task(task_id):
        return task if task_id == task.task_id else None

    monkeypatch.setattr(demo.task_service, "get_task", get_task)
    response = TestClient(app).get(
        f"/api/v1/demo/tasks/{task.task_id}/export.xlsx",
        headers={"X-Demo-Token": "test-token"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert response.headers["content-disposition"] == 'attachment; filename="example.com-seo-audit.xlsx"'
    with ZipFile(BytesIO(response.content)) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        strings_xml = archive.read("xl/sharedStrings.xml").decode("utf-8")
    assert 'name="问题清单"' in workbook_xml
    assert 'name="链接清单"' in workbook_xml
    for expected in ["问题类型", "检查事项", "问题描述", "影响", "建议", "负责人", "页面标题", "内容字数", "状态码", "抓取时间", "响应耗时（ms）"]:
        assert expected in strings_xml
    assert "页面标题" in strings_xml
    assert "补齐 Title" in strings_xml


def test_seo_excel_export_rejects_unfinished_task(monkeypatch):
    task = make_task()
    monkeypatch.setattr(demo_access, "settings", replace(settings, demo_access_token="test-token"))

    async def get_task(task_id):
        return task

    monkeypatch.setattr(demo.task_service, "get_task", get_task)
    response = TestClient(app).get(
        f"/api/v1/demo/tasks/{task.task_id}/export.xlsx",
        headers={"X-Demo-Token": "test-token"},
    )
    assert response.status_code == 409


def test_demo_defaults_and_explanations_live_in_docs():
    client = TestClient(app)
    html = client.get("/").text
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    assert soup.select_one('#task-type option[selected]')["value"] == "site_seo_audit"
    assert "checked" not in soup.select_one('#build-knowledge-graph').attrs
    assert soup.select_one('[data-tab="site-links"]')
    assert "汇总层维度业务落成" not in html
    api_docs = client.get("/api-doc").text
    assert "汇总层维度业务落成" in api_docs
    assert '默认 <code>false</code>' in api_docs
    request = TaskAuditRequest(url="https://example.com")
    assert request.task_type == "site_seo_audit"
    assert request.build_knowledge_graph is False
