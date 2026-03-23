from __future__ import annotations

from app.models.audit import (
    ActionPlanItem,
    ContentAuditResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.models.requests import LLMConfig
from app.services.llm_enrichment_service import LLMEnrichmentService
from app.services.scoring_service import ScoringService


class SummarizerService:
    def __init__(self) -> None:
        self.scoring = ScoringService()
        self.llm_enrichment = LLMEnrichmentService()

    async def summarize(
        self,
        url: str,
        discovery: DiscoveryResult,
        visibility: VisibilityAuditResult,
        technical: TechnicalAuditResult,
        content: ContentAuditResult,
        schema: SchemaAuditResult,
        platform: PlatformAuditResult,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
    ) -> SummaryResult:
        content_eeat_score = self.scoring.clamp_score(
            (
                content.content_score
                + content.experience_score
                + content.expertise_score
                + content.authoritativeness_score
                + content.trustworthiness_score
            )
            / 5
        )
        composite_score, weighted_scores = self.scoring.weighted_composite(
            {
                "AI Citability & Visibility": {"raw_score": visibility.ai_visibility_score, "weight": 0.25},
                "Brand Authority Signals": {"raw_score": visibility.brand_authority_score, "weight": 0.20},
                "Content Quality & E-E-A-T": {"raw_score": content_eeat_score, "weight": 0.20},
                "Technical Foundations": {"raw_score": technical.technical_score, "weight": 0.15},
                "Structured Data": {"raw_score": schema.structured_data_score, "weight": 0.10},
                "Platform Optimization": {"raw_score": platform.platform_optimization_score, "weight": 0.10},
            }
        )
        status = self.scoring.status_from_score(composite_score)

        module_scores = [
            ("visibility", visibility.score, visibility.issues, visibility.recommendations),
            ("technical", technical.score, technical.issues, technical.recommendations),
            ("content", content.score, content.issues, content.recommendations),
            ("schema", schema.score, schema.issues, schema.recommendations),
            ("platform", platform.score, platform.issues, platform.recommendations),
        ]
        ordered_modules = sorted(module_scores, key=lambda item: item[1])

        top_issues: list[str] = []
        quick_wins: list[str] = []
        prioritized_action_plan: list[ActionPlanItem] = []

        for module_name, _, issues, recommendations in ordered_modules:
            for issue in issues:
                if len(top_issues) >= 5:
                    break
                labeled_issue = f"{module_name}: {issue}"
                if labeled_issue not in top_issues:
                    top_issues.append(labeled_issue)
            for recommendation in recommendations:
                if len(quick_wins) >= 5:
                    break
                if recommendation not in quick_wins:
                    quick_wins.append(recommendation)
            if recommendations:
                prioritized_action_plan.append(
                    ActionPlanItem(
                        priority="high" if len(prioritized_action_plan) == 0 else "medium" if len(prioritized_action_plan) < 3 else "low",
                        module=module_name,
                        action=recommendations[0],
                        rationale=f"{module_name} is one of the weakest scoring areas and is constraining the composite GEO score.",
                    )
                )

        summary_text = (
            f"{discovery.domain or url} currently scores {composite_score}/100 for GEO readiness. "
            f"The biggest gaps are in {ordered_modules[0][0]} and {ordered_modules[1][0]} coverage."
        )
        result = SummaryResult(
            composite_geo_score=composite_score,
            status=status,
            audit_mode=mode,
            weighted_scores=weighted_scores,
            summary=summary_text,
            top_issues=top_issues,
            quick_wins=quick_wins,
            prioritized_action_plan=prioritized_action_plan[:5],
        )
        if llm_config:
            result.llm_provider = llm_config.provider
            result.llm_model = llm_config.model
        if mode == "premium":
            result = await self.llm_enrichment.enrich_summary(discovery, visibility, content, platform, result, llm_config)
        return result
