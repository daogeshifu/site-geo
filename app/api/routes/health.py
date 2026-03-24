from __future__ import annotations

from fastapi import APIRouter

from app.models.responses import success_response

# 健康检查路由，不挂载前缀，供容器编排（K8s liveness probe）等直接访问
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """健康检查接口

    返回 {"ok": true}，供负载均衡器和监控系统确认服务存活。
    该接口不依赖任何外部资源，始终快速返回。
    """
    return success_response({"ok": True})
