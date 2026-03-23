from __future__ import annotations

import asyncio
import time

import httpx

from app.core.config import settings
from app.models.requests import LLMConfig
from app.models.audit import ContentAuditResult, ContentPageAnalysis
from app.services.audit_service import AuditBaseService
from app.services.llm_enrichment_service import LLMEnrichmentService
from app.services.scoring_service import ScoringService
from app.utils.fetcher import fetch_url
from app.utils.html_parser import parse_html
from app.utils.text_analyzer import (
    contains_faq,
    evaluate_heading_quality,
    has_author_signals,
    has_publish_date,
    has_quantified_data,
    is_answer_first,
)


class ContentService(AuditBaseService):
    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()
        self.llm_enrichment = LLMEnrichmentService()

    async def _analyze_page(self, client: httpx.AsyncClient, page_type: str, page_url: str) -> ContentPageAnalysis:
        response = await fetch_url(page_url, client=client)
        parsed = parse_html(response.final_url, response.text)
        heading_quality = evaluate_heading_quality(parsed["headings"])
        return ContentPageAnalysis(
            url=response.final_url,
            page_type=page_type,
            title=parsed["title"],
            word_count=parsed["word_count"],
            has_faq=contains_faq(parsed["text_content"], parsed["headings"]),
            has_author=has_author_signals(parsed["text_content"]),
            has_publish_date=has_publish_date(parsed["text_content"]),
            has_quantified_data=has_quantified_data(parsed["text_content"]),
            answer_first=is_answer_first(parsed["text_content"]),
            heading_quality_score=heading_quality["score"],
            text_excerpt=parsed["text_excerpt"],
        )

    def _analysis_from_profile(self, page_type: str, profile) -> ContentPageAnalysis:
        return ContentPageAnalysis(
            url=profile.final_url,
            page_type=page_type,
            title=profile.title,
            word_count=profile.word_count,
            has_faq=profile.has_faq,
            has_author=profile.has_author,
            has_publish_date=profile.has_publish_date,
            has_quantified_data=profile.has_quantified_data,
            answer_first=profile.answer_first,
            heading_quality_score=profile.heading_quality_score,
            text_excerpt=profile.text_excerpt,
        )

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
    ) -> ContentAuditResult:
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(url, discovery)
        targets = {
            "service": resolved.key_pages.service,
            "article": resolved.key_pages.article,
            "about": resolved.key_pages.about,
            "case_study": resolved.key_pages.case_study,
        }
        page_analyses: dict[str, ContentPageAnalysis] = {}

        for page_type in ["service", "article", "about", "case_study"]:
            profile = resolved.page_profiles.get(page_type)
            if profile:
                page_analyses[page_type] = self._analysis_from_profile(page_type, profile)

        missing_targets = {
            key: page_url
            for key, page_url in targets.items()
            if page_url and key not in page_analyses
        }
        if missing_targets:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.request_timeout_seconds),
                follow_redirects=True,
                headers={"User-Agent": settings.default_user_agent},
            ) as client:
                coroutines = {
                    key: self._analyze_page(client, key, page_url)
                    for key, page_url in missing_targets.items()
                }
                results = await asyncio.gather(*coroutines.values(), return_exceptions=True)
                for page_type, result in zip(coroutines.keys(), results):
                    if isinstance(result, Exception):
                        continue
                    page_analyses[page_type] = result

        service_page = page_analyses.get("service")
        article_page = page_analyses.get("article")
        about_page = page_analyses.get("about")
        case_study_page = page_analyses.get("case_study")

        has_faq_any = any(page.has_faq for page in page_analyses.values())
        has_author_any = any(page.has_author for page in page_analyses.values())
        has_publish_any = any(page.has_publish_date for page in page_analyses.values())
        has_quant_any = any(page.has_quantified_data for page in page_analyses.values())
        has_answer_first_any = any(page.answer_first for page in page_analyses.values())
        avg_heading_quality = (
            sum(page.heading_quality_score for page in page_analyses.values()) / len(page_analyses)
            if page_analyses
            else 0
        )

        content_score = self.scoring.clamp_score(
            (15 if service_page and service_page.word_count >= 400 else 7 if service_page and service_page.word_count >= 200 else 0)
            + (20 if article_page and article_page.word_count >= 800 else 10 if article_page and article_page.word_count >= 400 else 0)
            + (10 if has_faq_any else 0)
            + (10 if has_author_any else 0)
            + (10 if has_publish_any else 0)
            + (10 if has_quant_any else 0)
            + (15 * (avg_heading_quality / 100))
            + (10 if has_answer_first_any else 0)
        )

        experience_score = self.scoring.clamp_score(
            (30 if case_study_page else 0)
            + (20 if has_quant_any else 0)
            + (20 if service_page and service_page.word_count >= 300 else 0)
            + (30 if about_page else 0)
        )
        expertise_score = self.scoring.clamp_score(
            (35 if service_page and service_page.word_count >= 400 else 0)
            + (25 if article_page and article_page.word_count >= 800 else 0)
            + (20 if has_answer_first_any else 0)
            + (20 * (avg_heading_quality / 100))
        )
        authoritativeness_score = self.scoring.clamp_score(
            (25 if about_page else 0)
            + (20 if has_author_any else 0)
            + (20 if resolved.site_signals.awards_detected else 0)
            + (15 if resolved.site_signals.certifications_detected else 0)
            + (20 if resolved.site_signals.same_as_detected else 0)
        )
        trustworthiness_score = self.scoring.clamp_score(
            (25 if resolved.key_pages.contact else 0)
            + (15 if resolved.site_signals.phone_detected else 0)
            + (15 if resolved.site_signals.email_detected else 0)
            + (15 if resolved.site_signals.address_detected else 0)
            + (15 if has_publish_any else 0)
            + (15 if has_author_any else 0)
        )
        status = self.scoring.status_from_score(content_score)

        issues: list[str] = []
        strengths: list[str] = []
        recommendations: list[str] = []

        if not service_page:
            issues.append("No clear service page was discovered for content evaluation.")
            recommendations.append("Create a dedicated service page with clear offerings, outcomes, and supporting proof.")
        elif service_page.word_count < 300:
            issues.append("Service page copy is thin for AI citation and retrieval.")
            recommendations.append("Expand service pages with problem framing, process details, deliverables, and FAQs.")
        else:
            strengths.append("Service page has enough depth for baseline retrieval.")

        if not article_page:
            issues.append("No article or news page was discovered.")
            recommendations.append("Publish insight or blog content to increase topical coverage and retrievable expertise.")
        elif article_page.word_count < 600:
            issues.append("Article content is too short to establish durable topical authority.")
            recommendations.append("Publish longer-form articles with original data, examples, and authored bylines.")
        else:
            strengths.append("Article content demonstrates topical depth.")

        if not has_faq_any:
            issues.append("FAQ content is missing.")
            recommendations.append("Add FAQ sections to commercial pages and high-intent landing pages.")
        if not has_author_any:
            issues.append("Author bylines are missing from evaluated content.")
            recommendations.append("Add author profiles and bylines to articles and expert pages.")
        if not has_publish_any:
            issues.append("Publication dates are missing from evaluated content.")
            recommendations.append("Expose publish/update timestamps on editorial content.")
        if has_answer_first_any:
            strengths.append("Some content follows an answer-first structure.")
        else:
            recommendations.append("Lead pages with direct answers before deeper explanation.")

        findings = {
            "evaluated_pages": len(page_analyses),
            "average_heading_quality": self.scoring.clamp_score(avg_heading_quality),
            "has_faq_any": has_faq_any,
            "has_author_any": has_author_any,
            "has_publish_date_any": has_publish_any,
            "has_quantified_data_any": has_quant_any,
            "has_answer_first_any": has_answer_first_any,
        }
        checks = {
            "service_page_word_count": service_page.word_count if service_page else 0,
            "article_page_word_count": article_page.word_count if article_page else 0,
            "faq_present": has_faq_any,
            "author_present": has_author_any,
            "publish_date_present": has_publish_any,
            "quantified_data_present": has_quant_any,
            "answer_first_present": has_answer_first_any,
            "average_heading_quality": self.scoring.clamp_score(avg_heading_quality),
        }
        result = ContentAuditResult(
            score=content_score,
            status=status,
            findings=findings,
            issues=issues,
            strengths=strengths,
            recommendations=recommendations,
            content_score=content_score,
            experience_score=experience_score,
            expertise_score=expertise_score,
            authoritativeness_score=authoritativeness_score,
            trustworthiness_score=trustworthiness_score,
            checks=checks,
            page_analyses=page_analyses,
        )
        self.set_execution_metadata(result, mode, llm_config)
        if mode == "premium":
            result = await self.llm_enrichment.enrich_content(resolved, result, llm_config)
        result = self.finalize_audit_result(
            result,
            module_key="content",
            input_pages=self.collect_input_pages(resolved, "service", "article", "about", "case_study"),
            started_at=started_at,
            confidence=min(0.98, 0.45 + (len(page_analyses) / 4) * 0.45),
        )
        return result
