from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BaseAuditResult(BaseModel):
    score: int
    status: str
    module_key: str = ""
    input_pages: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    confidence: float = 0.0
    audit_mode: str = "standard"
    llm_enhanced: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_insights: dict[str, Any] = Field(default_factory=dict)
    processing_notes: list[str] = Field(default_factory=list)
    findings: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class VisibilityAuditResult(BaseAuditResult):
    ai_visibility_score: int
    brand_authority_score: int
    checks: dict[str, Any] = Field(default_factory=dict)


class TechnicalAuditResult(BaseAuditResult):
    technical_score: int
    checks: dict[str, Any] = Field(default_factory=dict)
    security_headers: dict[str, Any] = Field(default_factory=dict)
    ssr_signal: dict[str, Any] = Field(default_factory=dict)
    render_blocking_risk: dict[str, Any] = Field(default_factory=dict)


class ContentPageAnalysis(BaseModel):
    url: str
    page_type: str
    title: str | None = None
    word_count: int = 0
    has_faq: bool = False
    has_author: bool = False
    has_publish_date: bool = False
    has_quantified_data: bool = False
    answer_first: bool = False
    heading_quality_score: int = 0
    text_excerpt: str = ""


class ContentAuditResult(BaseAuditResult):
    content_score: int
    experience_score: int
    expertise_score: int
    authoritativeness_score: int
    trustworthiness_score: int
    checks: dict[str, Any] = Field(default_factory=dict)
    page_analyses: dict[str, ContentPageAnalysis] = Field(default_factory=dict)


class SchemaAuditResult(BaseAuditResult):
    structured_data_score: int
    checks: dict[str, Any] = Field(default_factory=dict)
    schema_types: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    missing_schema_recommendations: list[str] = Field(default_factory=list)


class PlatformAuditDetail(BaseModel):
    platform_score: int
    primary_gap: str
    key_recommendations: list[str] = Field(default_factory=list)


class PlatformAuditResult(BaseAuditResult):
    platform_optimization_score: int
    checks: dict[str, Any] = Field(default_factory=dict)
    platform_scores: dict[str, PlatformAuditDetail] = Field(default_factory=dict)


class ActionPlanItem(BaseModel):
    priority: str
    module: str
    action: str
    rationale: str


class SummaryResult(BaseModel):
    composite_geo_score: int
    status: str
    audit_mode: str = "standard"
    llm_enhanced: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_insights: dict[str, Any] = Field(default_factory=dict)
    processing_notes: list[str] = Field(default_factory=list)
    dimensions: dict[str, Any] = Field(default_factory=dict)
    weighted_scores: dict[str, Any] = Field(default_factory=dict)
    summary: str
    top_issues: list[str] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)
    prioritized_action_plan: list[ActionPlanItem] = Field(default_factory=list)
