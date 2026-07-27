from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.demo_access import require_demo_token
from app.models.requests import GoogleCrawlerTestRequest
from app.models.responses import success_response
from app.services.google_crawler import GoogleRenderService, GooglebotService


router = APIRouter(tags=["google-crawler"])
googlebot_service = GooglebotService()
google_render_service = GoogleRenderService()


async def _run_full_test(url: str) -> dict:
    googlebot_run = await googlebot_service.run(url)
    render_result = await google_render_service.test(
        googlebot_run.result["request"]["final_url"],
        initial_html=googlebot_run.html,
        crawl_allowed=googlebot_run.result["crawlability"]["allowed"],
    )
    scores = [
        value
        for value in (googlebot_run.result.get("score"), render_result.get("score"))
        if isinstance(value, int)
    ]
    return {
        "url": url,
        "status": (
            "failed"
            if "failed" in {googlebot_run.result["status"], render_result["status"]}
            else "warning"
            if {googlebot_run.result["status"], render_result["status"]}.intersection({"warning", "skipped"})
            else "passed"
        ),
        "score": round(sum(scores) / len(scores)) if scores else None,
        "googlebot": googlebot_run.result,
        "google_render": render_result,
        "disclaimer": (
            "这是基于公开 Googlebot UA 与本地 Chromium 的近似模拟，不来自 Google IP，"
            "不能替代 Search Console URL Inspection 或 Rich Results Test。"
        ),
    }


@router.post("/api/v1/google-crawler/googlebot")
async def test_googlebot(payload: GoogleCrawlerTestRequest) -> dict:
    """仅运行 Googlebot Smartphone 抓取与可索引性检测。"""
    return success_response(await googlebot_service.test(payload.url))


@router.post("/api/v1/google-crawler/google-render")
async def test_google_render(payload: GoogleCrawlerTestRequest) -> dict:
    """运行抓取前置检查与 Chromium 渲染检测。"""
    googlebot_run = await googlebot_service.run(payload.url)
    result = await google_render_service.test(
        googlebot_run.result["request"]["final_url"],
        initial_html=googlebot_run.html,
        crawl_allowed=googlebot_run.result["crawlability"]["allowed"],
    )
    return success_response(result)


@router.post("/api/v1/google-crawler/test")
async def test_google_crawler(payload: GoogleCrawlerTestRequest) -> dict:
    """一次返回 Googlebot 与 Google Render 两项检测结果。"""
    return success_response(await _run_full_test(payload.url))


@router.post("/api/v1/demo/google-crawler/test", include_in_schema=False)
async def test_google_crawler_demo(request: Request, payload: GoogleCrawlerTestRequest) -> dict:
    """Demo 页面专用入口，复用现有 X-Demo-Token 保护。"""
    require_demo_token(request)
    return success_response(await _run_full_test(payload.url))
