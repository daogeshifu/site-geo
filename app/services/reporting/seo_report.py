from __future__ import annotations

from datetime import datetime

from app.models.audit import SeoAuditResult, SeoIssueResult, SeoRoadmapItem, SeoSummaryResult
from app.models.discovery import DiscoveryResult


class SeoReportService:
    """Markdown report renderer for the dedicated SEO audit."""

    def build_filename(self, discovery: DiscoveryResult) -> str:
        stamp = datetime.now().strftime("%Y%m%d")
        domain = discovery.domain or "site"
        return f"seo-audit-report-{domain}-{stamp}.md"

    def render_markdown(
        self,
        *,
        url: str,
        discovery: DiscoveryResult,
        seo: SeoAuditResult,
        summary: SeoSummaryResult,
    ) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        weighted_rows = []
        for key, value in seo.weighted_scores.items():
            dimension = seo.dimensions.get(key)
            weighted_rows.append(
                f"| {dimension.label if dimension else key} | {int(value['raw_weight'] * 100)}% | {value['raw_score']}/100 | {value['weighted_value']} |"
            )

        coverage_rows = [
            f"| {item.id} | {item.category} | {item.check} | {item.status.upper()} | {item.summary} | {item.evidence or '-'} |"
            for item in seo.coverage_checks
        ]
        issue_rows = [
            self._issue_row(item)
            for item in seo.issues_table
        ]
        sample_rows = [
            f"| {item.page_type} | {item.status_code} | {item.title_length} | {item.meta_description_length} | {item.h1_count} | {item.alt_coverage_ratio} | {item.url} |"
            for item in seo.sampled_pages
        ]
        dimension_sections = []
        for dimension in sorted(seo.dimensions.values(), key=lambda item: item.score):
            highlight_lines = [f"- {item}" for item in dimension.highlights[:4]] or ["- No explicit strengths recorded."]
            issue_lines = [f"- {item}" for item in dimension.issues[:4]] or ["- No explicit gaps recorded."]
            recommendation_lines = [f"- {item}" for item in dimension.recommendations[:4]] or [
                "- Maintain current implementation and continue monitoring."
            ]
            dimension_sections.extend(
                [
                    f"### {dimension.label} ({dimension.score}/100)",
                    "",
                    dimension.summary,
                    "",
                    "Highlights:",
                    *highlight_lines,
                    "",
                    "Gaps:",
                    *issue_lines,
                    "",
                    "Recommendations:",
                    *recommendation_lines,
                    "",
                ]
            )

        roadmap_phases = {"0-30": [], "31-60": [], "61-90": []}
        for item in seo.roadmap:
            roadmap_phases.setdefault(item.phase, []).append(item)
        top_issue_lines = [f"- {item}" for item in summary.top_issues] or ["- No major issues recorded."]
        quick_win_lines = [f"- {item}" for item in summary.quick_wins] or ["- No quick wins recorded."]
        note_lines = [f"- {item}" for item in summary.processing_notes] or ["- No additional processing notes."]
        sample_lines = sample_rows or ["| - | - | - | - | - | - | - |"]
        roadmap_0_30_lines = [self._roadmap_row(item) for item in roadmap_phases.get("0-30", [])] or ["| - | - | - | - | - |"]
        roadmap_31_60_lines = [self._roadmap_row(item) for item in roadmap_phases.get("31-60", [])] or ["| - | - | - | - | - |"]
        roadmap_61_90_lines = [self._roadmap_row(item) for item in roadmap_phases.get("61-90", [])] or ["| - | - | - | - | - |"]

        return "\n".join(
            [
                f"# Google SEO Audit Report: {discovery.domain or url}",
                "",
                f"> Date: {date_str}",
                f"> Website: {discovery.final_url}",
                f"> Audit Mode: {summary.audit_mode}",
                f"> Scoring Version: {summary.scoring_version}",
                "",
                "## Executive Summary",
                "",
                f"**SEO Health Score: {summary.overall_score}/100**",
                "",
                summary.summary,
                "",
                "Top findings:",
                *top_issue_lines,
                "",
                "Quick wins:",
                *quick_win_lines,
                "",
                "## Score Dashboard",
                "",
                "| Dimension | Weight | Score | Weighted Contribution |",
                "|---|---:|---:|---:|",
                *weighted_rows,
                f"| **Overall** | **100% (normalized)** | **{summary.overall_score}/100** | **{sum(item['weighted_value'] for item in seo.weighted_scores.values())}** |",
                "",
                "## Coverage Checklist",
                "",
                "| ID | Category | Check | Status | Summary | Evidence |",
                "|---|---|---|---|---|---|",
                *coverage_rows,
                "",
                "## Issue Backlog",
                "",
                "| Issue ID | Priority | Severity | Category | Scope | Recommendation |",
                "|---|---|---|---|---|---|",
                *issue_rows,
                "",
                "## Dimension Analysis",
                "",
                *dimension_sections,
                "## Sampled Pages",
                "",
                "| Page Type | Status | Title Len | Meta Len | H1 Count | Alt Coverage | URL |",
                "|---|---:|---:|---:|---:|---:|---|",
                *sample_lines,
                "",
                "## 30-60-90 Roadmap",
                "",
                "### 0-30 Days",
                "",
                "| Priority | Task | Related Issues | Owner | Acceptance Criteria |",
                "|---|---|---|---|---|",
                *roadmap_0_30_lines,
                "",
                "### 31-60 Days",
                "",
                "| Priority | Task | Related Issues | Owner | Acceptance Criteria |",
                "|---|---|---|---|---|",
                *roadmap_31_60_lines,
                "",
                "### 61-90 Days",
                "",
                "| Priority | Task | Related Issues | Owner | Acceptance Criteria |",
                "|---|---|---|---|---|",
                *roadmap_61_90_lines,
                "",
                "## Audit Notes",
                "",
                *note_lines,
            ]
        )

    def _issue_row(self, item: SeoIssueResult) -> str:
        return (
            f"| {item.issue_id} | {item.priority} | {item.severity} | {item.category} | "
            f"{item.scope or '-'} | {item.recommendation or '-'} |"
        )

    def _roadmap_row(self, item: SeoRoadmapItem) -> str:
        related = ", ".join(item.related_issue_ids) or "-"
        return (
            f"| {item.priority} | {item.task} | {related} | "
            f"{item.owner_team or '-'} | {item.acceptance_criteria or '-'} |"
        )
