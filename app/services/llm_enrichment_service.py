from __future__ import annotations

from typing import Any

from app.models.audit import (
    ActionPlanItem,
    ContentAuditResult,
    PlatformAuditDetail,
    PlatformAuditResult,
    SummaryResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.models.requests import LLMConfig
from app.services.llm_service import LLMService, LLMServiceError
from app.services.scoring_service import ScoringService


def _merge_unique(existing: list[str], extra: list[str], limit: int = 8) -> list[str]:
    merged = list(existing)
    for item in extra:
        if item and item not in merged:
            merged.append(item)
        if len(merged) >= limit:
            break
    return merged[:limit]


class LLMEnrichmentService:
    def __init__(self) -> None:
        self.llm_service = LLMService()
        self.scoring = ScoringService()

    def _apply_metadata(self, result: Any, config: LLMConfig, insights: dict[str, Any]) -> None:
        result.llm_enhanced = True
        result.llm_provider = config.provider
        result.llm_model = config.model
        result.llm_insights = insights

    def _bounded_delta(self, value: Any, minimum: int = -10, maximum: int = 10) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return 0
        return max(minimum, min(maximum, numeric))

    def _append_note(self, result: Any, note: str) -> None:
        if note not in result.processing_notes:
            result.processing_notes.append(note)

    async def enrich_visibility(
        self,
        discovery: DiscoveryResult,
        result: VisibilityAuditResult,
        llm_config: LLMConfig | None,
    ) -> VisibilityAuditResult:
        system_prompt = (
            "You are a GEO audit reviewer. Analyze homepage brand/entity signals and AI citation readiness. "
            "Return JSON with keys: summary, score_adjustment, issues, strengths, recommendations, observations."
        )
        payload = {
            "domain": discovery.domain,
            "business_type": discovery.business_type,
            "homepage": {
                "title": discovery.homepage.title,
                "meta_description": discovery.homepage.meta_description,
                "h1": discovery.homepage.h1,
                "text_excerpt": discovery.homepage.text_excerpt,
                "word_count": discovery.homepage.word_count,
            },
            "site_signals": discovery.site_signals.model_dump(),
            "llms_exists": discovery.llms.exists,
            "robots": discovery.robots.model_dump(),
            "rule_result": result.model_dump(),
        }
        try:
            insights, config = await self.llm_service.generate_json(system_prompt, payload, llm_config)
        except (LLMServiceError, Exception) as exc:
            self._append_note(result, f"Premium LLM enrichment skipped: {exc}")
            return result

        adjustment = self._bounded_delta(insights.get("score_adjustment", 0))
        result.ai_visibility_score = self.scoring.clamp_score(result.ai_visibility_score + adjustment)
        result.score = result.ai_visibility_score
        result.status = self.scoring.status_from_score(result.ai_visibility_score)
        result.issues = _merge_unique(result.issues, insights.get("issues", []))
        result.strengths = _merge_unique(result.strengths, insights.get("strengths", []))
        result.recommendations = _merge_unique(result.recommendations, insights.get("recommendations", []))
        result.findings["llm_summary"] = insights.get("summary")
        result.findings["llm_observations"] = insights.get("observations", {})
        self._apply_metadata(result, config, insights)
        return result

    async def enrich_content(
        self,
        discovery: DiscoveryResult,
        result: ContentAuditResult,
        llm_config: LLMConfig | None,
    ) -> ContentAuditResult:
        system_prompt = (
            "You are a senior GEO content strategist. Review the provided page excerpts and assess content quality, "
            "E-E-A-T, expert voice, and citation readiness. "
            "Return JSON with keys: summary, content_score_adjustment, eeat_adjustments, issues, strengths, recommendations, observations."
        )
        payload = {
            "domain": discovery.domain,
            "business_type": discovery.business_type,
            "pages": {name: page.model_dump() for name, page in result.page_analyses.items()},
            "homepage_excerpt": discovery.homepage.text_excerpt,
            "rule_result": result.model_dump(),
        }
        try:
            insights, config = await self.llm_service.generate_json(system_prompt, payload, llm_config)
        except (LLMServiceError, Exception) as exc:
            self._append_note(result, f"Premium LLM enrichment skipped: {exc}")
            return result

        score_adjustment = self._bounded_delta(insights.get("content_score_adjustment", 0))
        eeat = insights.get("eeat_adjustments", {})
        result.content_score = self.scoring.clamp_score(result.content_score + score_adjustment)
        result.score = result.content_score
        result.experience_score = self.scoring.clamp_score(
            result.experience_score + self._bounded_delta(eeat.get("experience", 0), -15, 15)
        )
        result.expertise_score = self.scoring.clamp_score(
            result.expertise_score + self._bounded_delta(eeat.get("expertise", 0), -15, 15)
        )
        result.authoritativeness_score = self.scoring.clamp_score(
            result.authoritativeness_score + self._bounded_delta(eeat.get("authoritativeness", 0), -15, 15)
        )
        result.trustworthiness_score = self.scoring.clamp_score(
            result.trustworthiness_score + self._bounded_delta(eeat.get("trustworthiness", 0), -15, 15)
        )
        result.status = self.scoring.status_from_score(result.content_score)
        result.issues = _merge_unique(result.issues, insights.get("issues", []))
        result.strengths = _merge_unique(result.strengths, insights.get("strengths", []))
        result.recommendations = _merge_unique(result.recommendations, insights.get("recommendations", []))
        result.findings["llm_summary"] = insights.get("summary")
        result.findings["llm_observations"] = insights.get("observations", {})
        self._apply_metadata(result, config, insights)
        return result

    async def enrich_platform(
        self,
        discovery: DiscoveryResult,
        result: PlatformAuditResult,
        llm_config: LLMConfig | None,
    ) -> PlatformAuditResult:
        system_prompt = (
            "You are a GEO platform optimization strategist. Evaluate readiness for Google AI Overviews, ChatGPT Web Search, "
            "Perplexity, Google Gemini, and Bing Copilot. "
            "Return JSON with keys: summary, platform_adjustments, issues, strengths, recommendations."
        )
        payload = {
            "domain": discovery.domain,
            "homepage": {
                "title": discovery.homepage.title,
                "meta_description": discovery.homepage.meta_description,
                "text_excerpt": discovery.homepage.text_excerpt,
            },
            "schema_summary": discovery.schema_summary,
            "site_signals": discovery.site_signals.model_dump(),
            "rule_result": result.model_dump(),
        }
        try:
            insights, config = await self.llm_service.generate_json(system_prompt, payload, llm_config)
        except (LLMServiceError, Exception) as exc:
            self._append_note(result, f"Premium LLM enrichment skipped: {exc}")
            return result

        adjustments = insights.get("platform_adjustments", {})
        for platform_name, delta in adjustments.items():
            if platform_name not in result.platform_scores:
                continue
            detail = result.platform_scores[platform_name]
            detail.platform_score = self.scoring.clamp_score(detail.platform_score + self._bounded_delta(delta))
        platform_weights = {
            "chatgpt_web_search": 0.30,
            "google_ai_overviews": 0.20,
            "perplexity": 0.20,
            "google_gemini": 0.15,
            "bing_copilot": 0.15,
        }
        result.platform_optimization_score = self.scoring.clamp_score(
            sum(
                result.platform_scores[name].platform_score * weight
                for name, weight in platform_weights.items()
                if name in result.platform_scores
            )
        )
        result.score = result.platform_optimization_score
        result.status = self.scoring.status_from_score(result.platform_optimization_score)
        result.issues = _merge_unique(result.issues, insights.get("issues", []))
        result.strengths = _merge_unique(result.strengths, insights.get("strengths", []))
        result.recommendations = _merge_unique(result.recommendations, insights.get("recommendations", []))
        result.findings["llm_summary"] = insights.get("summary")
        self._apply_metadata(result, config, insights)
        return result

    async def enrich_summary(
        self,
        discovery: DiscoveryResult,
        visibility: VisibilityAuditResult,
        content: ContentAuditResult,
        platform: PlatformAuditResult,
        result: SummaryResult,
        llm_config: LLMConfig | None,
    ) -> SummaryResult:
        system_prompt = (
            "You are a principal GEO consultant writing an executive summary. "
            "Return JSON with keys: executive_summary, top_issues, quick_wins, prioritized_action_plan."
        )
        payload = {
            "domain": discovery.domain,
            "business_type": discovery.business_type,
            "visibility": visibility.model_dump(),
            "content": content.model_dump(),
            "platform": platform.model_dump(),
            "current_summary": result.model_dump(),
        }
        try:
            insights, config = await self.llm_service.generate_json(system_prompt, payload, llm_config)
        except (LLMServiceError, Exception) as exc:
            if f"Premium LLM synthesis skipped: {exc}" not in result.processing_notes:
                result.processing_notes.append(f"Premium LLM synthesis skipped: {exc}")
            return result

        result.summary = insights.get("executive_summary") or result.summary
        result.top_issues = _merge_unique(result.top_issues, insights.get("top_issues", []), limit=5)
        result.quick_wins = _merge_unique(result.quick_wins, insights.get("quick_wins", []), limit=5)
        action_plan = []
        for item in insights.get("prioritized_action_plan", [])[:5]:
            if not isinstance(item, dict) or "action" not in item or "module" not in item:
                continue
            action_plan.append(
                ActionPlanItem(
                    priority=str(item.get("priority", "medium")),
                    module=str(item.get("module", "general")),
                    action=str(item.get("action")),
                    rationale=str(item.get("rationale", "LLM-prioritized recommendation.")),
                )
            )
        if action_plan:
            result.prioritized_action_plan = action_plan
        result.llm_enhanced = True
        result.llm_provider = config.provider
        result.llm_model = config.model
        result.llm_insights = insights
        return result
