from __future__ import annotations

from app.models.audit import PlatformAuditDetail, PlatformAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.llm_enrichment_service import LLMEnrichmentService
from app.services.scoring_service import ScoringService
from app.utils.heuristics import assess_citability, calculate_brand_authority


class PlatformService(AuditBaseService):
    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()
        self.llm_enrichment = LLMEnrichmentService()

    def _platform_detail(self, score: float, primary_gap: str, recommendations: list[str]) -> PlatformAuditDetail:
        return PlatformAuditDetail(
            platform_score=self.scoring.clamp_score(score),
            primary_gap=primary_gap,
            key_recommendations=recommendations[:3],
        )

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
    ) -> PlatformAuditResult:
        resolved = await self.ensure_discovery(url, discovery)
        citability = assess_citability(resolved.homepage.model_dump())
        brand = calculate_brand_authority(resolved.site_signals, bool(resolved.key_pages.about))
        ai_crawler_allowed_ratio = sum(1 for rule in resolved.robots.user_agents.values() if rule.allowed) / max(
            len(resolved.robots.user_agents), 1
        )
        metadata_signal = 100 if resolved.homepage.meta_description and resolved.homepage.canonical else 40
        schema_signal = 100 if resolved.schema_summary.get("json_ld_present") else 35
        faq_signal = 100 if resolved.schema_summary.get("has_faq_page") else 30

        platform_scores = {
            "google_ai_overviews": self._platform_detail(
                score=citability["score"] * 0.35 + schema_signal * 0.35 + faq_signal * 0.15 + metadata_signal * 0.15,
                primary_gap="Weak structured answers and FAQ/schema coverage."
                if schema_signal < 80 or faq_signal < 80
                else "No major gap detected.",
                recommendations=[
                    "Add FAQPage and Service schema to key commercial pages.",
                    "Lead pages with concise answer-first summaries.",
                    "Expand headings so sections map cleanly to user questions.",
                ],
            ),
            "chatgpt_web_search": self._platform_detail(
                score=ai_crawler_allowed_ratio * 40 + (100 if resolved.llms.exists else 20) * 0.25 + citability["score"] * 0.2 + brand["score"] * 0.15,
                primary_gap="Crawler access or llms.txt guidance is incomplete."
                if ai_crawler_allowed_ratio < 1 or not resolved.llms.exists
                else "No major gap detected.",
                recommendations=[
                    "Allow major AI crawlers in robots.txt.",
                    "Publish llms.txt with site purpose, services, and canonical citations.",
                    "Strengthen entity and contact signals on the homepage.",
                ],
            ),
            "perplexity": self._platform_detail(
                score=citability["score"] * 0.4 + brand["score"] * 0.2 + schema_signal * 0.2 + metadata_signal * 0.2,
                primary_gap="Site needs more citable facts and entity context."
                if citability["score"] < 70 or brand["score"] < 60
                else "No major gap detected.",
                recommendations=[
                    "Add quantified proof points, case studies, and sourceable claims.",
                    "Improve organization/contact signals to support citation confidence.",
                    "Publish more insight-led content for long-tail retrieval.",
                ],
            ),
            "google_gemini": self._platform_detail(
                score=schema_signal * 0.4 + metadata_signal * 0.2 + citability["score"] * 0.2 + brand["score"] * 0.2,
                primary_gap="Entity schema and metadata are underdeveloped."
                if schema_signal < 80 or metadata_signal < 80
                else "No major gap detected.",
                recommendations=[
                    "Add Organization, WebSite, and sameAs schema.",
                    "Tighten title, meta description, and canonical coverage.",
                    "Clarify business category and services on the homepage.",
                ],
            ),
            "bing_copilot": self._platform_detail(
                score=metadata_signal * 0.3 + schema_signal * 0.25 + citability["score"] * 0.2 + brand["score"] * 0.25,
                primary_gap="Metadata and brand trust signals need improvement."
                if metadata_signal < 80 or brand["score"] < 60
                else "No major gap detected.",
                recommendations=[
                    "Improve social proof, contact details, and about-page completeness.",
                    "Ensure Open Graph and Twitter metadata are present.",
                    "Use structured data to reinforce brand entity identity.",
                ],
            ),
        }

        platform_optimization_score = self.scoring.clamp_score(
            sum(item.platform_score for item in platform_scores.values()) / len(platform_scores)
        )
        status = self.scoring.status_from_score(platform_optimization_score)
        issues = [detail.primary_gap for detail in platform_scores.values() if detail.primary_gap != "No major gap detected."]
        strengths = [
            f"{platform.replace('_', ' ').title()} readiness is acceptable."
            for platform, detail in platform_scores.items()
            if detail.platform_score >= 65
        ]
        recommendations = []
        for detail in platform_scores.values():
            for recommendation in detail.key_recommendations:
                if recommendation not in recommendations:
                    recommendations.append(recommendation)

        findings = {
            "llms_exists": resolved.llms.exists,
            "ai_crawler_allowed_ratio": round(ai_crawler_allowed_ratio, 2),
            "schema_signal": schema_signal,
            "brand_authority_score": brand["score"],
        }
        checks = {
            "llms_exists": resolved.llms.exists,
            "schema_present": resolved.schema_summary.get("json_ld_present", False),
            "faq_schema_present": resolved.schema_summary.get("has_faq_page", False),
            "metadata_complete": metadata_signal == 100,
            "ai_crawler_allowed_ratio": round(ai_crawler_allowed_ratio, 2),
        }
        result = PlatformAuditResult(
            score=platform_optimization_score,
            status=status,
            findings=findings,
            issues=issues,
            strengths=strengths,
            recommendations=recommendations[:6],
            platform_optimization_score=platform_optimization_score,
            checks=checks,
            platform_scores=platform_scores,
        )
        self.set_execution_metadata(result, mode, llm_config)
        if mode == "premium":
            result = await self.llm_enrichment.enrich_platform(resolved, result, llm_config)
        return result
