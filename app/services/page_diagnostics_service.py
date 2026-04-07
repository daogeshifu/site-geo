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
        issue_details, recommendation_details = self._issues_and_recommendations(
            profile, citability, content_score, technical_score, schema_score
        )
        issues = self._flatten_detail_map(issue_details)
        recommendations = self._flatten_detail_map(recommendation_details)
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
            issues=issues,
            recommendations=recommendations,
            issue_details=issue_details,
            recommendation_details=recommendation_details,
        )

    def _flatten_detail_map(self, detail_map: dict[str, list[str]]) -> list[str]:
        ordered: list[str] = []
        for values in detail_map.values():
            for item in values:
                if item not in ordered:
                    ordered.append(item)
        return ordered

    def _append_issue(
        self,
        issue_details: dict[str, list[str]],
        recommendation_details: dict[str, list[str]],
        category: str,
        issue: str,
        recommendation: str | None = None,
    ) -> None:
        issue_details.setdefault(category, [])
        recommendation_details.setdefault(category, [])
        if issue not in issue_details[category]:
            issue_details[category].append(issue)
        if recommendation and recommendation not in recommendation_details[category]:
            recommendation_details[category].append(recommendation)

    def _content_score(self, profile: PageProfile) -> int:
        return self.scoring.clamp_score(
            (25 if profile.word_count >= 700 else 15 if profile.word_count >= 350 else 5)
            + (15 if profile.has_faq else 0)
            + (12 if profile.has_author else 0)
            + (10 if profile.has_publish_date else 0)
            + (15 if profile.has_quantified_data else 0)
            + (10 if profile.has_reference_section else 0)
            + (6 if profile.has_inline_citations else 0)
            + (6 if profile.has_tldr else 0)
            + (12 if profile.answer_first else 0)
            + profile.information_density_score * 0.06
            + profile.chunk_structure_score * 0.05
            + profile.descriptive_internal_link_ratio * 6
            + profile.descriptive_external_link_ratio * 4
        )

    def _technical_score(self, profile: PageProfile) -> int:
        h1_count = sum(1 for heading in profile.headings if heading.level == "h1")
        return self.scoring.clamp_score(
            (20 if profile.title else 0)
            + (15 if profile.meta_description else 0)
            + (15 if profile.canonical else 0)
            + (10 if profile.lang else 0)
            + (10 if h1_count == 1 else 0)
            + (20 if len(profile.headings) >= 3 else 10 if profile.headings else 0)
            + (20 if profile.word_count >= 250 else 10 if profile.word_count >= 100 else 0)
        )

    def _schema_score(self, profile: PageProfile) -> int:
        summary = profile.json_ld_summary or {}
        return self.scoring.clamp_score(
            (18 if summary.get("json_ld_present") else 0)
            + (15 if summary.get("has_organization") else 0)
            + (15 if summary.get("has_service") else 0)
            + (10 if summary.get("has_article") else 0)
            + (10 if summary.get("has_faq_page") else 0)
            + (10 if summary.get("has_product") else 0)
            + (6 if summary.get("has_defined_term") else 0)
            + (6 if summary.get("has_breadcrumb_list") else 0)
            + (5 if summary.get("has_date_published") else 0)
            + (5 if summary.get("has_date_modified") else 0)
            + (5 if summary.get("visible_alignment_score", 0) >= 60 else 0)
            + (10 if len(summary.get("same_as", [])) > 0 else 0)
        )

    def _issues_and_recommendations(
        self,
        profile: PageProfile,
        citability: dict,
        content_score: int,
        technical_score: int,
        schema_score: int,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        issue_details: dict[str, list[str]] = {}
        recommendation_details: dict[str, list[str]] = {}
        if citability["score"] < 60:
            self._append_issue(
                issue_details,
                recommendation_details,
                "citability",
                "Page is not yet citation-ready enough for consistent AI extraction.",
                "Restructure the page with answer-first sections, stronger headings, and tighter proof blocks.",
            )
        if content_score < 60:
            self._append_issue(
                issue_details,
                recommendation_details,
                "content",
                "Content depth and fact density are weaker than ideal for GEO reuse.",
                "Add concrete claims, specifications, FAQs, and sourced proof to the page.",
            )
        if not profile.has_reference_section and profile.has_quantified_data:
            self._append_issue(
                issue_details,
                recommendation_details,
                "evidence",
                "Claims appear without a visible references or sources section.",
                "Add a references section or source list near factual and comparative claims.",
            )
        if not profile.has_inline_citations and profile.has_reference_section:
            self._append_issue(
                issue_details,
                recommendation_details,
                "evidence",
                "Page has source sections but lacks inline citation cues near important claims.",
                "Support key facts with inline citations, source labels, or explicit linked proof near the claim.",
            )
        if profile.descriptive_internal_link_ratio < 0.5 or profile.descriptive_external_link_ratio < 0.5:
            self._append_issue(
                issue_details,
                recommendation_details,
                "linking",
                "Link anchors are not descriptive enough to provide strong retrieval context.",
                "Use anchor text that names the linked topic, evidence source, or destination intent more explicitly.",
            )
        if technical_score < 60:
            self._append_issue(
                issue_details,
                recommendation_details,
                "technical",
                "Page-level metadata or structure is incomplete.",
                "Improve title, meta description, canonical tags, language declaration, and heading coverage.",
            )
        h1_count = sum(1 for heading in profile.headings if heading.level == "h1")
        if h1_count != 1:
            self._append_issue(
                issue_details,
                recommendation_details,
                "semantic_html",
                "Page should expose exactly one H1 for stronger semantic structure.",
                "Keep a single descriptive H1 and nest supporting content under logical H2 and H3 sections.",
            )
        if schema_score < 50:
            self._append_issue(
                issue_details,
                recommendation_details,
                "schema",
                "Structured data on this page is too thin.",
                "Add page-relevant JSON-LD such as Service, Product, FAQPage, Article, or DefinedTerm.",
            )
        elif (profile.json_ld_summary or {}).get("visible_alignment_score", 0) < 60:
            self._append_issue(
                issue_details,
                recommendation_details,
                "schema",
                "Schema content is present but not tightly aligned with visible page copy.",
                "Keep schema names, descriptions, FAQs, and dates synchronized with visible on-page content.",
            )
        schema_summary = profile.json_ld_summary or {}
        if schema_summary.get("json_ld_present") and not (
            schema_summary.get("has_date_published") or schema_summary.get("has_date_modified")
        ):
            self._append_issue(
                issue_details,
                recommendation_details,
                "freshness",
                "Structured data is present but does not expose machine-readable publish or update dates.",
                "Add datePublished and/or dateModified in the page's JSON-LD where relevant.",
            )
        if not profile.has_author and profile.page_type in {"article", "documentation"}:
            self._append_issue(
                issue_details,
                recommendation_details,
                "trust",
                "Editorial page lacks an author signal.",
                "Expose named authors or reviewers for editorial and knowledge pages.",
            )
        if not profile.has_publish_date and profile.page_type in {"article", "documentation"}:
            self._append_issue(
                issue_details,
                recommendation_details,
                "freshness",
                "Editorial page lacks a visible publish or update timestamp.",
                "Expose visible publish and update timestamps on editorial and knowledge pages.",
            )
        if not profile.has_tldr and citability["score"] < 75:
            self._append_issue(
                issue_details,
                recommendation_details,
                "ux",
                "Page lacks a concise answer-first summary block.",
                "Add a TL;DR or key takeaways block near the top of the page.",
            )
        return issue_details, recommendation_details
