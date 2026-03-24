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
    """报告导出请求：需要提供所有审计模块的结果"""

    discovery: DiscoveryResult
    visibility: VisibilityAuditResult
    technical: TechnicalAuditResult
    content: ContentAuditResult
    schema_result: SchemaAuditResult
    platform: PlatformAuditResult
    summary: SummaryResult | None = None  # 可选：若不提供则自动计算


class ReportExportResponse(BaseModel):
    """报告导出响应，包含文件名和 Markdown 内容"""

    filename: str    # 格式：geo-audit-report-{domain}-{date}.md
    markdown: str    # 完整的 Markdown 报告内容
