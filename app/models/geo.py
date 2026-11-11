"""Evidence-based on-site GEO scoring, separate from the legacy module scores."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from app.models.page_fetch import PageFetchMetadata


class GeoCheckResult(BaseModel):
    id: str
    dimension: str
    label: str
    max_points: float
    status: Literal["pass", "partial", "fail", "unknown", "na"]
    value: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    evidence_type: str = "observed_html"
    blocker: bool = False


class GeoDimensionResult(BaseModel):
    key: str
    label: str
    weight: float
    score: float | None = None
    earned_points: float = 0
    applicable_points: float = 0
    measured_points: float = 0
    evidence_coverage: float = 0
    checks: list[GeoCheckResult] = Field(default_factory=list)


class GeoPageResult(PageFetchMetadata):
    url: str
    final_url: str
    page_type: str
    score: float | None = None
    status: str
    evidence_coverage: float = 0
    source_key: str | None = None
    fetched_at: str | None = None
    dimensions: dict[str, GeoDimensionResult] = Field(default_factory=dict)
    blockers: list[dict[str, Any]] = Field(default_factory=list)


class GeoAuditResult(BaseModel):
    scoring_version: str = "onsite-geo-v1"
    score_name: str = "On-site GEO readiness"
    score: float | None = None
    status: str = "provisional"
    readiness_status: str = "unverified"
    provisional: bool = True
    score_range: list[float] = Field(default_factory=list)
    dimensions: dict[str, GeoDimensionResult] = Field(default_factory=dict)
    pages: list[GeoPageResult] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    auxiliary: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)
    audit_mode: str = "standard"
    llm_enhanced: bool = False
    duration_ms: int = 0
