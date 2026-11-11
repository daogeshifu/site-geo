import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.task import TaskAuditRequest
from app.services.audit.single_page import SinglePageAuditService
from app.services.infra.cache import CacheService
from app.services.orchestration.tasks import TaskService


def html(title="Product", lang="de"):
    return f'''<html lang="{lang}"><head><title>{title}</title>
    <meta name="description" content="Product details">
    <meta name="viewport" content="width=device-width">
    <link rel="canonical" href="https://example.com/de/product/buy/">
    <script type="application/ld+json">{{"@type":"ProductGroup","name":"Group","hasVariant":{{"@type":"Product","name":"{title}","image":"https://example.com/image.png"}}}}</script>
    </head><body><h1>{title}</h1><h2>Specifications</h2><p>Weight 200g.</p>
    <a href="/">Home</a><a href="/de/other">Other product</a>
    <img src="/image.png" alt="Product"><script src="/app.js"></script></body></html>'''


@pytest.mark.asyncio
async def test_only_requested_page_is_fetched():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        assert request.headers["accept-language"] == "de-DE,de;q=0.9"
        return httpx.Response(200, text=html(), headers={"content-type": "text/html"})
    url = "https://example.com/de/product/buy/?variant=red"
    result = await SinglePageAuditService(httpx.MockTransport(handler)).audit(url, country="DE", target_locale="de")
    assert calls == [url]
    assert result["audited_urls"] == [url]
    assert result["page"]["page_type"] == "product"
    assert not any("article" in c["key"] or "author" in c["key"] for c in result["page"]["checks"])
    assert result["summary"]["passed_required_checks"] == result["summary"]["total_required_checks"]
    assert result["summary"]["total_checks"] > 30
    assert result["summary"]["advisory_count"] > 0
    assert all(c.get('evidence') is not None for c in result['page']['findings'])


@pytest.mark.asyncio
async def test_detailed_findings_include_evidence_and_separate_advice():
    body = '''<html lang="de"><head><title>X</title><title>Duplicate</title>
    <meta name="description" content="Short">
    <meta name="viewport" content="width=device-width,user-scalable=no">
    <script src="http://example.com/blocking.js"></script>
    <script type="application/ld+json">{"@type":"Product","name":"Item","offers":{"@type":"Offer"}}</script>
    <script type="application/ld+json">{invalid}</script>
    </head><body><h2>Detail</h2><h4>Jump</h4><img src="a.jpg"><a href="/other"></a></body></html>'''
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,text=body,headers={'content-type':'text/html'})
    result=await SinglePageAuditService(httpx.MockTransport(handler)).audit('https://example.com/de/item/buy/')
    findings={c['key']:c for c in result['page']['findings']}
    assert {'title_unique','h1','image_alt','jsonld_valid','mixed_content','product_image'} <= findings.keys()
    assert {'title_length','description_length','heading_order','head_blocking_scripts','offer_price','offer_priceCurrency','offer_availability'} <= findings.keys()
    assert findings['title_unique']['severity']=='issue'
    assert findings['title_length']['severity']=='advisory'
    assert '1' in findings['head_blocking_scripts']['evidence']
    assert calls == ['https://example.com/de/item/buy/']
    assert result['summary']['issue_count'] > 1
    assert result['summary']['advisory_count'] > 1


@pytest.mark.asyncio
async def test_redirect_to_home_is_not_followed():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "/"})
    with pytest.raises(AppError) as err:
        await SinglePageAuditService(httpx.MockTransport(handler)).audit("https://example.com/de/old")
    assert calls == ["https://example.com/de/old"]
    assert err.value.errors["redirect_url"] == "https://example.com/"
    assert err.value.errors["audited_urls"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status,content_type", [(404,"text/html"),(403,"text/html"),(200,"application/pdf")])
async def test_unavailable_or_non_html_page_is_not_scored(status, content_type):
    transport = httpx.MockTransport(lambda r: httpx.Response(status, text=html(), headers={"content-type":content_type}))
    with pytest.raises(AppError):
        await SinglePageAuditService(transport).audit("https://example.com/a")


def test_page_cache_isolates_path_query_country_and_site(tmp_path):
    cache = CacheService(str(tmp_path))
    def key(url, **kwargs):
        return cache.build_cache_key(url, "standard", audit_scope="page", **kwargs)[0]
    first = key("https://example.com/de/a")
    assert first != key("https://example.com/de/b")
    assert first != key("https://example.com/de/a?v=1")
    assert first != key("https://example.com/de/a",country="DE")
    assert first != cache.build_cache_key("https://example.com/de/a", "standard")[0]
    assert first == key("https://example.com/de/a#section")


@pytest.mark.parametrize("locale", ["de","es","en","ar","tr"])
def test_page_request_forces_single_page_and_disables_graph(locale):
    request = TaskAuditRequest(url="https://example.com/a",audit_scope="page",country="sa",target_locale=locale,full_audit=True,max_pages=20,build_knowledge_graph=True)
    assert request.max_pages == 1 and not request.full_audit and not request.build_knowledge_graph
    assert request.country == "SA"
    with pytest.raises(ValidationError):
        TaskAuditRequest(url="https://example.com", max_pages=1)


@pytest.mark.asyncio
async def test_task_pipeline_and_cache_do_not_use_site_assets(tmp_path, monkeypatch):
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,text=html(request.url.path),headers={"content-type":"text/html"})
    monkeypatch.setattr("app.services.orchestration.tasks.SinglePageAuditService", lambda: SinglePageAuditService(httpx.MockTransport(handler)))
    service = TaskService.__new__(TaskService)
    service.tasks = {}
    service._lock = asyncio.Lock()
    service.cache_service = CacheService(str(tmp_path))
    service.asset_store = SimpleNamespace(available=True,backend="mysql",save_task=AsyncMock(side_effect=AssertionError("Site storage must not be used")))
    async def run(path):
        task = await service.create_task(TaskAuditRequest(url="https://example.com/de/"+path,audit_scope="page"))
        async def finished():
            while task.status not in {"completed","failed"}:
                await asyncio.sleep(0)
        await asyncio.wait_for(finished(),timeout=5)
        assert task.status == "completed", task.error
        assert task.step_order == ["page","summary"]
        return task
    a = await run("a")
    b = await run("b")
    cached = await run("a")
    assert calls == ["https://example.com/de/a","https://example.com/de/b"]
    assert cached.cached
    assert a.result["page"]["title"] != b.result["page"]["title"]
    service.asset_store.save_task.assert_not_called()
