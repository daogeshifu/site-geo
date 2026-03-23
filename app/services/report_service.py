from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.audit import (
    ContentAuditResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.services.scoring_service import ScoringService


class ReportService:
    def __init__(self) -> None:
        self.scoring = ScoringService()

    def build_filename(self, discovery: DiscoveryResult) -> str:
        stamp = datetime.now().strftime("%Y%m%d")
        domain = discovery.domain or "site"
        return f"geo-audit-report-{domain}-{stamp}.md"

    def render_markdown(
        self,
        *,
        url: str,
        discovery: DiscoveryResult,
        visibility: VisibilityAuditResult,
        technical: TechnicalAuditResult,
        content: ContentAuditResult,
        schema_result: SchemaAuditResult,
        platform: PlatformAuditResult,
        summary: SummaryResult,
    ) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        business_label = discovery.business_type.replace("_", " ").title()
        composite = summary.composite_geo_score
        composite_status = summary.status.title()

        weighted_rows = []
        for name, item in summary.weighted_scores.items():
            weighted_rows.append(
                f"| {name} | {int(item['weight'] * 100)}% | {item['raw_score']}/100 | {item['weighted_value']} | {self._status_badge(self.scoring.status_from_score(item['raw_score']))} |"
            )

        platform_rows = []
        for platform_name, detail in platform.platform_scores.items():
            platform_rows.append(
                f"| {platform_name.replace('_', ' ').title()} | {detail.platform_score}/100 | {detail.primary_gap} |"
            )

        critical_sections = []
        module_pairs = [
            ("Visibility", visibility),
            ("Technical", technical),
            ("Content", content),
            ("Schema", schema_result),
            ("Platform", platform),
        ]
        for label, module in sorted(module_pairs, key=lambda item: item[1].score)[:5]:
            issues = module.issues[:4] or ["No explicit issues recorded."]
            recommendations = module.recommendations[:3]
            severity = "CRITICAL" if module.score <= 24 else "HIGH" if module.score <= 44 else "MEDIUM"
            recommendation_lines = (
                [f"- {item}" for item in recommendations]
                if recommendations
                else ["- Maintain current implementation and continue monitoring."]
            )
            critical_sections.append(
                "\n".join(
                    [
                        f"### {'🔴' if severity == 'CRITICAL' else '🟠' if severity == 'HIGH' else '🟡'} {severity} — {label} ({module.score}/100)",
                        "",
                        *[f"- {issue}" for issue in issues],
                        "",
                        "Recommended fixes:",
                        *recommendation_lines,
                    ]
                )
            )

        strengths = self._unique_items(
            visibility.strengths
            + technical.strengths
            + content.strengths
            + schema_result.strengths
            + platform.strengths
        )[:10]

        eeat_rows = [
            f"| Experience | {content.experience_score}/100 | {self._dimension_comment(content.experience_score, 'experience proof and case evidence')} |",
            f"| Expertise | {content.expertise_score}/100 | {self._dimension_comment(content.expertise_score, 'topical depth and expert explanation')} |",
            f"| Authoritativeness | {content.authoritativeness_score}/100 | {self._dimension_comment(content.authoritativeness_score, 'brand/entity authority signals')} |",
            f"| Trustworthiness | {content.trustworthiness_score}/100 | {self._dimension_comment(content.trustworthiness_score, 'contact, transparency, and publication trust')} |",
        ]

        technical_rows = [
            ("HTTPS", self._pass_fail(discovery.final_url.startswith("https://")), "Critical" if not discovery.final_url.startswith("https://") else "Pass"),
            ("Server-Side Rendering", self._pass_fail(technical.ssr_signal.get("score", 0) >= 70), technical.ssr_signal.get("classification", "unknown").title()),
            ("robots.txt", self._pass_fail(discovery.robots.exists), "Critical" if not discovery.robots.exists else "Pass"),
            ("sitemap.xml", self._pass_fail(discovery.sitemap.exists), "Critical" if not discovery.sitemap.exists else "Pass"),
            ("Meta descriptions", self._pass_fail(bool(discovery.homepage.meta_description)), "Critical" if not discovery.homepage.meta_description else "Pass"),
            ("Canonical tags", self._pass_fail(bool(discovery.homepage.canonical)), "Critical" if not discovery.homepage.canonical else "Pass"),
            ("lang attribute", self._pass_fail(bool(discovery.homepage.lang)), "Critical" if not discovery.homepage.lang else "Pass"),
            ("Security headers", self._pass_fail(technical.security_headers.get("score", 0) >= 80), self._severity_label(technical.security_headers.get("score", 0))),
            ("Open Graph tags", self._pass_fail(bool(discovery.homepage.open_graph)), "Critical" if not discovery.homepage.open_graph else "Pass"),
            ("Twitter Cards", self._pass_fail(bool(discovery.homepage.twitter_cards)), "High" if not discovery.homepage.twitter_cards else "Pass"),
            ("hreflang tags", self._pass_fail(bool(discovery.homepage.hreflang)), "High" if not discovery.homepage.hreflang else "Pass"),
            ("robots.txt Sitemap directive", self._pass_fail(discovery.robots.has_sitemap_directive), "High" if not discovery.robots.has_sitemap_directive else "Pass"),
            ("Image optimization", self._pass_fail(technical.checks.get("image_optimization", {}).get("lazyload_ratio", 0) >= 0.5), "High"),
            ("Render-blocking risk", self._pass_fail(technical.render_blocking_risk.get("risk_level") == "low"), technical.render_blocking_risk.get("risk_level", "unknown").title()),
            ("llms.txt", self._pass_fail(discovery.llms.exists), "Medium" if not discovery.llms.exists else "Pass"),
        ]

        quick_wins = summary.quick_wins[:7]
        medium_term = self._build_medium_term_actions(content, schema_result, technical, platform)
        strategic = self._build_strategic_actions(discovery, content, platform)
        if not quick_wins:
            quick_wins = ["Address the highest-priority technical and structured-data gaps first."]

        roadmap = [
            "Week 1-2: Foundation",
            *[f"  - {item}" for item in quick_wins[:5]],
            "",
            "Week 3-4: Content & Schema",
            *[f"  - {item}" for item in medium_term[:5]],
            "",
            "Month 2-3: Strategic GEO Growth",
            *[f"  - {item}" for item in strategic[:5]],
        ]

        projected_rows = self._projected_scores(summary)

        appendix_rows = self._appendix_rows(discovery, technical, schema_result)

        return "\n".join(
            [
                f"# GEO Audit Report: {discovery.domain or url}",
                f"**{discovery.homepage.title or discovery.domain}**",
                "",
                "> Prepared by: GEO Audit Service",
                f"> Date: {date_str}",
                f"> Website: {discovery.final_url}",
                f"> Business Type: {business_label}",
                f"> Audit Mode: {summary.audit_mode}",
                "",
                "---",
                "",
                "## Executive Summary",
                "",
                f"**Composite GEO Score: {composite} / 100** — {composite_status}",
                "",
                summary.summary,
                "",
                "This export combines rule-based auditing with any available premium LLM enrichment. "
                "It is designed to preserve every major dimension present in the reference GEO client report while mapping to the current API outputs.",
                "",
                "---",
                "",
                "## Score Dashboard",
                "",
                "| Category | Weight | Score | Weighted | Status |",
                "|---|---|---|---|---|",
                *weighted_rows,
                f"| **COMPOSITE GEO SCORE** | **100%** | **{composite}/100** | **{sum(item['weighted_value'] for item in summary.weighted_scores.values())}** | **{self._status_badge(summary.status)}** |",
                "",
                "---",
                "",
                "## AI Platform Readiness",
                "",
                "| Platform | Score | Primary Gap |",
                "|---|---|---|",
                *platform_rows,
                f"| **Average** | **{platform.platform_optimization_score}/100** | {summary.top_issues[0] if summary.top_issues else 'No major gap detected.'} |",
                "",
                "---",
                "",
                "## Critical Findings",
                "",
                *critical_sections,
                "",
                "---",
                "",
                "## Strengths to Build On",
                "",
                "| Asset | GEO Application |",
                "|---|---|",
                *[f"| {item} | Reinforce and expose this signal in crawlable, machine-readable formats. |" for item in strengths],
                "",
                "---",
                "",
                "## E-E-A-T Assessment",
                "",
                f"**E-E-A-T Score: {self._eeat_average(content)}/100**",
                "",
                "| Dimension | Score | Assessment |",
                "|---|---|---|",
                *eeat_rows,
                "",
                "Critical E-E-A-T gap:",
                f"- {content.issues[0] if content.issues else 'No explicit E-E-A-T issue recorded.'}",
                "",
                "---",
                "",
                "## Technical Audit Summary",
                "",
                f"**Technical Score: {technical.technical_score}/100**",
                "",
                "| Check | Status | Severity |",
                "|---|---|---|",
                *[f"| {name} | {status} | {severity} |" for name, status, severity in technical_rows],
                "",
                "---",
                "",
                "## Prioritized Action Plan",
                "",
                "### Quick Wins (1-2 weeks)",
                "",
                *[f"**{index}.** {item}" for index, item in enumerate(quick_wins, start=1)],
                "",
                "### Medium-Term Actions (1-4 weeks)",
                "",
                *[f"**{index}.** {item}" for index, item in enumerate(medium_term, start=1)],
                "",
                "### Strategic Actions (1-3 months)",
                "",
                *[f"**{index}.** {item}" for index, item in enumerate(strategic, start=1)],
                "",
                "---",
                "",
                "## Implementation Roadmap",
                "",
                "```text",
                *roadmap,
                "```",
                "",
                "---",
                "",
                "## Projected Score After Full Implementation",
                "",
                "| Category | Current | Projected (3 months) | Change |",
                "|---|---|---|---|",
                *projected_rows,
                "",
                "---",
                "",
                "## Appendix: Site Facts",
                "",
                "| Property | Value |",
                "|---|---|",
                *appendix_rows,
                "",
                "---",
                "",
                f"*GEO Audit Service · GEO Score v1.0 · {discovery.domain or url} · {date_str}*",
            ]
        )

    def _status_badge(self, status: str) -> str:
        mapping = {
            "critical": "🔴 Critical",
            "poor": "🟠 Poor",
            "fair": "🟡 Fair",
            "good": "🟢 Good",
            "strong": "🟢 Strong",
        }
        return mapping.get(status, status.title())

    def _unique_items(self, items: list[str]) -> list[str]:
        seen = set()
        ordered = []
        for item in items:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    def _eeat_average(self, content: ContentAuditResult) -> int:
        return self.scoring.clamp_score(
            (
                content.experience_score
                + content.expertise_score
                + content.authoritativeness_score
                + content.trustworthiness_score
            )
            / 4
        )

    def _dimension_comment(self, score: int, dimension: str) -> str:
        if score >= 75:
            return f"Strong {dimension}."
        if score >= 50:
            return f"Moderate {dimension}, but still expandable."
        return f"Weak {dimension}; this needs focused work."

    def _pass_fail(self, passed: bool) -> str:
        return "✅ Pass" if passed else "❌ Missing"

    def _severity_label(self, score: int) -> str:
        if score >= 80:
            return "Pass"
        if score >= 50:
            return "Medium"
        return "Critical"

    def _build_medium_term_actions(
        self,
        content: ContentAuditResult,
        schema_result: SchemaAuditResult,
        technical: TechnicalAuditResult,
        platform: PlatformAuditResult,
    ) -> list[str]:
        actions = (
            schema_result.missing_schema_recommendations
            + content.recommendations
            + technical.recommendations
            + platform.recommendations
        )
        return self._unique_items(actions)[:8] or ["Expand structured data, service content, and platform-specific optimizations."]

    def _build_strategic_actions(
        self,
        discovery: DiscoveryResult,
        content: ContentAuditResult,
        platform: PlatformAuditResult,
    ) -> list[str]:
        actions = [
            "Build English-language thought leadership pages for the highest-value services.",
            "Create external entity/profile coverage on LinkedIn, Crunchbase, Clutch, and other AI-cited platforms.",
            "Publish quantified case studies and convert research assets into crawlable HTML.",
            "Strengthen sameAs and Organization schema after external profile creation.",
            "Operationalize a recurring GEO content and entity maintenance workflow.",
        ]
        if not discovery.key_pages.article:
            actions.insert(0, "Launch a recurring editorial program to build topical depth and retrievable expertise.")
        if content.authoritativeness_score < 50:
            actions.append("Expose named experts, author pages, and credential pages across content.")
        return self._unique_items(actions)[:8]

    def _projected_scores(self, summary: SummaryResult) -> list[str]:
        rows = []
        for name, item in summary.weighted_scores.items():
            current = int(item["raw_score"])
            projected = min(100, current + 20 if current < 60 else current + 10)
            rows.append(f"| {name} | {current}/100 | {projected}/100 | +{projected - current} |")
        rows.append(
            f"| **Composite GEO Score** | **{summary.composite_geo_score}/100** | **{min(100, summary.composite_geo_score + 20)}/100** | **+{min(20, 100 - summary.composite_geo_score)}** |"
        )
        return rows

    def _appendix_rows(
        self,
        discovery: DiscoveryResult,
        technical: TechnicalAuditResult,
        schema_result: SchemaAuditResult,
    ) -> list[str]:
        rows = [
            f"| Domain | {discovery.domain} |",
            f"| Final URL | {discovery.final_url} |",
            f"| Business Type | {discovery.business_type} |",
            f"| Rendering | {technical.ssr_signal.get('classification', 'unknown').title()} |",
            f"| Primary Language | {discovery.homepage.lang or 'Not declared'} |",
            f"| robots.txt | {'Found' if discovery.robots.exists else 'Not found'} |",
            f"| sitemap.xml | {'Found' if discovery.sitemap.exists else 'Not found'} |",
            f"| llms.txt | {'Found' if discovery.llms.exists else 'Not found'} |",
            f"| JSON-LD Schema | {'Detected' if schema_result.schema_types else 'None detected'} |",
            f"| Open Graph Tags | {'Detected' if discovery.homepage.open_graph else 'None detected'} |",
            f"| Meta Descriptions | {'Detected' if discovery.homepage.meta_description else 'None detected'} |",
            f"| Canonical Tags | {'Detected' if discovery.homepage.canonical else 'None detected'} |",
            f"| hreflang Tags | {'Detected' if discovery.homepage.hreflang else 'None detected'} |",
            f"| Security Headers | {technical.security_headers.get('score', 0)}/100 |",
            f"| Key Pages | about={discovery.key_pages.about or '-'}, service={discovery.key_pages.service or '-'}, contact={discovery.key_pages.contact or '-'}, article={discovery.key_pages.article or '-'}, case_study={discovery.key_pages.case_study or '-'} |",
        ]
        return rows
