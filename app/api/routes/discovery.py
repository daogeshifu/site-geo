from __future__ import annotations

from fastapi import APIRouter

from app.models.requests import UrlRequest
from app.models.responses import success_response
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/api/v1", tags=["discovery"])
discovery_service = DiscoveryService()


@router.post("/discovery")
async def run_discovery(request: UrlRequest) -> dict:
    result = await discovery_service.discover(request.url)
    return success_response(result.model_dump())
