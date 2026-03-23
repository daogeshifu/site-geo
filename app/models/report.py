from __future__ import annotations

from pydantic import BaseModel

from app.models.requests import UrlRequest
from app.models.discovery import DiscoveryResult
from app.models.audit import (
    ContentAuditResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)


class ReportExportRequest(UrlRequest):
    discovery: DiscoveryResult
    visibility: VisibilityAuditResult
    technical: TechnicalAuditResult
    content: ContentAuditResult
    schema_result: SchemaAuditResult
    platform: PlatformAuditResult
    summary: SummaryResult | None = None


class ReportExportResponse(BaseModel):
    filename: str
    markdown: str
