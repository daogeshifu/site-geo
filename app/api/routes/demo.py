from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

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
