from __future__ import annotations

from fastapi import APIRouter

from app.models.requests import UrlRequest
from app.models.responses import success_response
from app.services.discovery_service import DiscoveryService

# 站点发现路由，挂载在 /api/v1 前缀下
router = APIRouter(prefix="/api/v1", tags=["discovery"])

# 模块级单例：复用 HTTP 连接池，避免每次请求重新建立连接
discovery_service = DiscoveryService()


@router.post("/discovery")
async def run_discovery(request: UrlRequest) -> dict:
    """执行站点发现分析

    抓取目标站点的主页及关键辅助文件（robots.txt / sitemap / llms.txt），
    提取品牌信号、Schema 结构、关键页面等 GEO 基础数据，
    供后续各审计模块复用，避免重复抓取。

    Args:
        request: 包含目标 URL 的请求体

    Returns:
        DiscoveryResult 的序列化字典，包含主页信息、爬虫配置、站点信号等
    """
    result = await discovery_service.discover(request.url)
    return success_response(result.model_dump())
