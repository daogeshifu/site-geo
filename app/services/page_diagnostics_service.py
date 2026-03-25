from __future__ import annotations

from app.models.audit import PageDiagnosticResult
from app.models.discovery import DiscoveryResult, PageProfile
from app.services.scoring_service import ScoringService
from app.utils.heuristics import assess_page_citability


class PageDiagnosticsService:
    """full audit 模式下的逐页诊断服务"""

    def __init__(self) -> None:
        self.scoring = ScoringService()

    def build(self, discovery: DiscoveryResult, *, max_pages: int) -> list[PageDiagnosticResult]:
        pages: list[tuple[str, PageProfile]] = []
        for key, profile in discovery.page_profiles.items():
            pages.append((key, profile))
        for index, profile in enumerate(discovery.additional_page_profiles, start=1):
            pages.append((f"additional_{index}", profile))

        diagnostics = [self._diagnose_page(key, profile, source="core" if not key.startswith("additional_") else "extended") for key, profile in pages]
        diagnostics.sort(key=lambda item: (item.overall_score, -item.issue_count, item.url))
        return diagnostics[:max_pages]

    def _diagnose_page(self, key: str, profile: PageProfile, *, source: str) -> PageDiagnosticResult:
        citability = assess_page_citability(profile)
        content_score = self._content_score(profile)
        technical_score = self._technical_score(profile)
        schema_score = self._schema_score(profile)
        overall_score = self.scoring.clamp_score(
            citability["score"] * 0.35
            + content_score * 0.30
            + technical_score * 0.20
            + schema_score * 0.15
        )
        status = self.scoring.status_from_score(overall_score)
        issues, recommendations = self._issues_and_recommendations(profile, citability, content_score, technical_score, schema_score)
        return PageDiagnosticResult(
            url=profile.final_url,
            page_type=profile.page_type or key,
            source=source,
            overall_score=overall_score,
            status=status,
            citability_score=citability["score"],
            content_score=content_score,
            technical_score=technical_score,
            schema_score=schema_score,
            issue_count=len(issues),
            issues=issues[:5],
            recommendations=recommendations[:5],
        )

    def _content_score(self, profile: PageProfile) -> int:
        return self.scoring.clamp_score(
            (25 if profile.word_count >= 700 else 15 if profile.word_count >= 350 else 5)
            + (15 if profile.has_faq else 0)
            + (12 if profile.has_author else 0)
            + (10 if profile.has_publish_date else 0)
            + (15 if profile.has_quantified_data else 0)
            + (12 if profile.answer_first else 0)
            + profile.information_density_score * 0.06
            + profile.chunk_structure_score * 0.05
        )

    def _technical_score(self, profile: PageProfile) -> int:
        return self.scoring.clamp_score(
            (20 if profile.title else 0)
            + (15 if profile.meta_description else 0)
            + (15 if profile.canonical else 0)
            + (10 if profile.lang else 0)
            + (20 if len(profile.headings) >= 3 else 10 if profile.headings else 0)
            + (20 if profile.word_count >= 250 else 10 if profile.word_count >= 100 else 0)
        )

    def _schema_score(self, profile: PageProfile) -> int:
        summary = profile.json_ld_summary or {}
        return self.scoring.clamp_score(
            (20 if summary.get("json_ld_present") else 0)
            + (15 if summary.get("has_organization") else 0)
            + (15 if summary.get("has_service") else 0)
            + (10 if summary.get("has_article") else 0)
            + (10 if summary.get("has_faq_page") else 0)
            + (10 if summary.get("has_product") else 0)
            + (10 if summary.get("has_defined_term") else 0)
            + (10 if len(summary.get("same_as", [])) > 0 else 0)
        )

    def _issues_and_recommendations(
        self,
        profile: PageProfile,
        citability: dict,
        content_score: int,
        technical_score: int,
        schema_score: int,
    ) -> tuple[list[str], list[str]]:
        issues: list[str] = []
        recommendations: list[str] = []
        if citability["score"] < 60:
            issues.append("Page is not yet citation-ready enough for consistent AI extraction.")
            recommendations.append("Restructure the page with answer-first sections, stronger headings, and tighter proof blocks.")
        if content_score < 60:
            issues.append("Content depth and fact density are weaker than ideal for GEO reuse.")
            recommendations.append("Add concrete claims, specifications, FAQs, and sourced proof to the page.")
        if technical_score < 60:
            issues.append("Page-level metadata or structure is incomplete.")
            recommendations.append("Improve title, meta description, canonical tags, language declaration, and heading coverage.")
        if schema_score < 50:
            issues.append("Structured data on this page is too thin.")
            recommendations.append("Add page-relevant JSON-LD such as Service, Product, FAQPage, Article, or DefinedTerm.")
        if not profile.has_author and profile.page_type in {"article", "documentation"}:
            issues.append("Editorial page lacks an author signal.")
            recommendations.append("Expose named authors or reviewers for editorial and knowledge pages.")
        return issues, recommendations
