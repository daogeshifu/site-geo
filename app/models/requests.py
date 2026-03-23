from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.audit import (
    ContentAuditResult,
    PlatformAuditResult,
    SchemaAuditResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult

AuditMode = Literal["standard", "premium"]
LLMProvider = Literal["openrouter"]


class LLMConfig(BaseModel):
    provider: LLMProvider = "openrouter"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1200, ge=200, le=4000)


class UrlRequest(BaseModel):
    url: str = Field(..., min_length=3)
    mode: AuditMode = "standard"
    llm: LLMConfig | None = None


class AuditModuleRequest(UrlRequest):
    discovery: DiscoveryResult | None = None


class FullAuditRequest(UrlRequest):
    discovery: DiscoveryResult | None = None


class SummarizeRequest(UrlRequest):
    discovery: DiscoveryResult
    visibility: VisibilityAuditResult
    technical: TechnicalAuditResult
    content: ContentAuditResult
    schema_result: SchemaAuditResult = Field(alias="schema")
    platform: PlatformAuditResult
