"""Unified search and generative-engine readiness, scored from unique checks."""
from pydantic import Field

from app.models.geo import GeoAuditResult, GeoPageResult

SGEO_SCORING_VERSION = "onsite-sgeo-v1"


class SgeoPageResult(GeoPageResult):
    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    lang: str | None = None
    h1_count: int | None = None
    word_count: int | None = None
    html_length: int | None = None
    image_count: int | None = None
    noindex_detected: bool | None = None


class SgeoAuditResult(GeoAuditResult):
    scoring_version: str = SGEO_SCORING_VERSION
    score_name: str = "SGEO search readiness"
    pages: list[SgeoPageResult] = Field(default_factory=list)
