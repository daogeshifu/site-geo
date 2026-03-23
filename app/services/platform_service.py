from __future__ import annotations

from app.models.audit import PlatformAuditDetail, PlatformAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.llm_enrichment_service import LLMEnrichmentService
from app.services.scoring_service import ScoringService
from app.utils.heuristics import assess_citability, assess_llms_effectiveness, calculate_brand_authority


class PlatformService(AuditBaseService):
    PLATFORM_WEIGHTS = {
        "chatgpt_web_search": 0.30,
        "google_ai_overviews": 0.20,
        "perplexity": 0.20,
        "google_gemini": 0.15,
        "bing_copilot": 0.15,
    }

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

    def _metadata_signal(self, resolved) -> int:
        return self.scoring.clamp_score(
            (35 if resolved.homepage.meta_description else 0)
            + (25 if resolved.homepage.canonical else 0)
            + (20 if resolved.homepage.open_graph else 0)
            + (20 if resolved.homepage.twitter_cards else 0)
        )

    def _schema_signal(self, resolved) -> int:
        return self.scoring.clamp_score(
            (20 if resolved.schema_summary.get("json_ld_present") else 0)
            + (25 if resolved.schema_summary.get("has_organization") else 0)
            + (15 if resolved.schema_summary.get("has_website") else 0)
            + (20 if resolved.schema_summary.get("has_service") else 0)
            + (20 if resolved.schema_summary.get("has_article") or resolved.schema_summary.get("has_faq_page") else 0)
        )

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
    ) -> PlatformAuditResult:
        resolved = await self.ensure_discovery(url, discovery)
        homepage_dict = resolved.homepage.model_dump()
        citability = assess_citability(homepage_dict)
        llms_quality = assess_llms_effectiveness(
            resolved.llms,
            company_name=resolved.site_signals.detected_company_name,
            business_type=resolved.business_type,
        )
        brand = calculate_brand_authority(
            signals=resolved.site_signals,
            homepage=homepage_dict,
            llms=resolved.llms,
            key_pages=resolved.key_pages,
            schema_summary=resolved.schema_summary,
            primary_domain=resolved.domain,
            sitemap_urls=resolved.robots.sitemaps,
            backlinks=resolved.backlinks,
        )
        ai_crawler_allowed_ratio = sum(1 for rule in resolved.robots.user_agents.values() if rule.allowed) / max(
            len(resolved.robots.user_agents), 1
        )
        metadata_signal = self._metadata_signal(resolved)
        schema_signal = self._schema_signal(resolved)
        faq_signal = 100 if resolved.schema_summary.get("has_faq_page") else 30

        platform_scores = {
            "google_ai_overviews": self._platform_detail(
                score=citability["score"] * 0.35 + schema_signal * 0.30 + faq_signal * 0.20 + metadata_signal * 0.15,
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
                score=ai_crawler_allowed_ratio * 40
                + llms_quality["score"] * 0.25
                + citability["score"] * 0.20
                + brand["score"] * 0.15,
                primary_gap="Crawler access or llms.txt guidance is incomplete."
                if ai_crawler_allowed_ratio < 1 or llms_quality["score"] < 60
                else "No major gap detected.",
                recommendations=[
                    "Allow major AI crawlers in robots.txt.",
                    "Publish llms.txt with site purpose, services, and machine-readable citation guidance.",
                    "Strengthen entity and contact signals on the homepage.",
                ],
            ),
            "perplexity": self._platform_detail(
                score=citability["score"] * 0.40 + brand["score"] * 0.25 + schema_signal * 0.20 + metadata_signal * 0.15,
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
                score=schema_signal * 0.40 + metadata_signal * 0.20 + citability["score"] * 0.15 + brand["score"] * 0.25,
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
                score=metadata_signal * 0.30 + schema_signal * 0.20 + citability["score"] * 0.20 + brand["score"] * 0.30,
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
            sum(platform_scores[name].platform_score * weight for name, weight in self.PLATFORM_WEIGHTS.items())
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
            "llms_quality_score": llms_quality["score"],
            "ai_crawler_allowed_ratio": round(ai_crawler_allowed_ratio, 2),
            "schema_signal": schema_signal,
            "metadata_signal": metadata_signal,
            "brand_authority_score": brand["score"],
            "platform_weights": self.PLATFORM_WEIGHTS,
        }
        checks = {
            "llms_exists": resolved.llms.exists,
            "schema_present": resolved.schema_summary.get("json_ld_present", False),
            "faq_schema_present": resolved.schema_summary.get("has_faq_page", False),
            "metadata_complete": metadata_signal == 100,
            "ai_crawler_allowed_ratio": round(ai_crawler_allowed_ratio, 2),
            "llms_quality_score": llms_quality["score"],
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
