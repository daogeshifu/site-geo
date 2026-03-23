from __future__ import annotations

from app.models.audit import VisibilityAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.llm_enrichment_service import LLMEnrichmentService
from app.services.scoring_service import ScoringService
from app.utils.heuristics import assess_citability, calculate_brand_authority


class VisibilityService(AuditBaseService):
    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()
        self.llm_enrichment = LLMEnrichmentService()

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
    ) -> VisibilityAuditResult:
        resolved = await self.ensure_discovery(url, discovery)
        crawler_rules = resolved.robots.user_agents
        allowed_crawlers = sum(1 for rule in crawler_rules.values() if rule.allowed)
        crawler_score = int((allowed_crawlers / max(len(crawler_rules), 1)) * 100)

        homepage_dict = resolved.homepage.model_dump()
        citability = assess_citability(homepage_dict)
        brand = calculate_brand_authority(resolved.site_signals, bool(resolved.key_pages.about))
        llms_score = 100 if resolved.llms.exists else 20
        ai_visibility_score = self.scoring.clamp_score(
            crawler_score * 0.35 + citability["score"] * 0.35 + llms_score * 0.15 + brand["score"] * 0.15
        )
        status = self.scoring.status_from_score(ai_visibility_score)

        issues: list[str] = []
        strengths: list[str] = []
        recommendations: list[str] = []

        if allowed_crawlers < len(crawler_rules):
            issues.append("robots.txt blocks one or more major AI crawlers.")
            recommendations.append("Review robots.txt and allow GPTBot, OAI-SearchBot, PerplexityBot, and Google-Extended.")
        else:
            strengths.append("robots.txt appears open to major AI crawlers.")

        if not resolved.llms.exists:
            issues.append("Site does not expose llms.txt guidance.")
            recommendations.append("Publish a concise llms.txt that describes the site, services, and citation preferences.")
        else:
            strengths.append("llms.txt exists and can help AI systems understand the site.")

        if citability["score"] < 60:
            issues.append("Homepage lacks strong citation-friendly structure and content depth.")
            recommendations.append("Improve homepage metadata, add clearer headings, and strengthen answer-first copy.")
        else:
            strengths.append("Homepage exposes baseline citability signals.")

        if brand["score"] < 50:
            issues.append("Brand authority signals are weak on-site.")
            recommendations.append("Add complete company details, contact information, about page content, and social sameAs links.")
        else:
            strengths.append("On-site brand authority signals are present.")

        findings = {
            "ai_crawler_access_score": crawler_score,
            "citability": citability,
            "brand_authority": brand,
            "llms_exists": resolved.llms.exists,
        }
        checks = {
            "allowed_ai_crawlers": allowed_crawlers,
            "total_ai_crawlers_checked": len(crawler_rules),
            "llms_exists": resolved.llms.exists,
            "citability_signals": citability["signals"],
            "brand_signals": resolved.site_signals.model_dump(),
        }
        result = VisibilityAuditResult(
            score=ai_visibility_score,
            status=status,
            findings=findings,
            issues=issues,
            strengths=strengths,
            recommendations=recommendations,
            ai_visibility_score=ai_visibility_score,
            brand_authority_score=brand["score"],
            checks=checks,
        )
        self.set_execution_metadata(result, mode, llm_config)
        if mode == "premium":
            result = await self.llm_enrichment.enrich_visibility(resolved, result, llm_config)
        return result
