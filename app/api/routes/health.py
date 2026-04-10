from __future__ import annotations

from fastapi import APIRouter

from app.models.responses import success_response
from app.services.infra.site_assets import SiteAssetStore

# 健康检查路由，不挂载前缀，供容器编排（K8s liveness probe）等直接访问
router = APIRouter(tags=["health"])
site_asset_store = SiteAssetStore()


@router.get("/health")
async def health_check() -> dict:
    """健康检查接口

    返回应用状态；启用 MySQL 资产库时会附带连通性信息。
    """
    mysql_ok = None
    if site_asset_store.enabled:
        try:
            mysql_ok = await site_asset_store.client.healthcheck()
        except Exception:
            mysql_ok = False
    return success_response(
        {
            "ok": True,
            "storage_backend": site_asset_store.backend,
            "mysql_enabled": site_asset_store.enabled,
            "mysql_ok": mysql_ok,
        }
    )
