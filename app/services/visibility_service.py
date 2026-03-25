from __future__ import annotations

import time

from app.models.audit import VisibilityAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.brand_authority_service import BrandAuthorityService
from app.services.llm_enrichment_service import LLMEnrichmentService
from app.services.scoring_service import ScoringService
from app.utils.heuristics import (
    assess_basic_brand_presence,
    assess_citability,
    assess_llms_effectiveness,
)


class VisibilityService(AuditBaseService):
    """AI 可见性审计模块（占 GEO 总分 45%：AI 可见性 25% + 品牌权威 20%）

    评分公式：
        ai_visibility_score =
            crawler_score * 0.32        # AI 爬虫访问权限
            + citability * 0.40         # 页面可引用性（最高权重）
            + llms_quality * 0.12       # llms.txt 有效性
            + basic_brand_presence * 0.16  # 基础品牌实体存在感
    """

    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()
        self.brand_authority = BrandAuthorityService()
        self.llm_enrichment = LLMEnrichmentService()

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        feedback_lang: str = "en",
    ) -> VisibilityAuditResult:
        """执行 AI 可见性审计

        1. 计算 AI 爬虫访问率（robots.txt）
        2. 评估首页和多页面的可引用性
        3. 评估 llms.txt 有效性
        4. 评估基础品牌实体存在感
        5. 综合计算 AI 可见性分数，并生成问题/优势/建议
        6. premium 模式下进行 LLM 增强
        """
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(url, discovery)

        # 计算 AI 爬虫访问率（允许爬取的爬虫数 / 总检查爬虫数）
        crawler_rules = resolved.robots.user_agents
        allowed_crawlers = sum(1 for rule in crawler_rules.values() if rule.allowed)
        crawler_score = int((allowed_crawlers / max(len(crawler_rules), 1)) * 100)

        # 评估各维度信号
        homepage_dict = resolved.homepage.model_dump()
        citability = assess_citability(homepage_dict, resolved.page_profiles)
        llms_quality = assess_llms_effectiveness(
            resolved.llms,
            company_name=resolved.site_signals.detected_company_name,
            business_type=resolved.business_type,
        )
        basic_brand_presence = assess_basic_brand_presence(resolved.site_signals, resolved.key_pages)
        brand = self.brand_authority.assess(resolved)

        # 加权计算 AI 可见性分数
        ai_visibility_score = self.scoring.clamp_score(
            crawler_score * 0.32
            + citability["score"] * 0.40
            + llms_quality["score"] * 0.12
            + basic_brand_presence["score"] * 0.16
        )
        status = self.scoring.status_from_score(ai_visibility_score)

        issues: list[str] = []
        strengths: list[str] = []
        recommendations: list[str] = []

        # AI 爬虫访问权限检查
        if allowed_crawlers < len(crawler_rules):
            issues.append("robots.txt blocks one or more major AI crawlers.")
            recommendations.append("Review robots.txt and allow GPTBot, OAI-SearchBot, PerplexityBot, and Google-Extended.")
        else:
            strengths.append("robots.txt appears open to major AI crawlers.")

        # llms.txt 检查
        if not resolved.llms.exists:
            issues.append("Site does not expose llms.txt guidance.")
            recommendations.append("Publish a concise llms.txt that describes the site, services, and citation preferences.")
        elif llms_quality["score"] < 60:
            issues.append("llms.txt exists but does not yet provide strong machine-facing guidance.")
            recommendations.append("Expand llms.txt with brand context, services, citation preferences, and structured sections.")
        else:
            strengths.append("llms.txt exists and can help AI systems understand the site.")

        # 可引用性检查
        if citability["score"] < 60:
            issues.append("Homepage lacks strong citation-friendly structure and content depth.")
            recommendations.append("Improve homepage metadata, add clearer headings, and strengthen answer-first copy.")
        else:
            strengths.append("Homepage exposes baseline citability signals.")

        # 基础品牌实体检查
        if basic_brand_presence["score"] < 50:
            issues.append("Basic entity presence is thin across about/contact and contact signals.")
            recommendations.append("Strengthen homepage, about, and contact-page entity signals with brand and contact details.")
        else:
            strengths.append("Baseline entity presence is detectable across the site.")

        # 品牌权威检查
        if brand["score"] < 50:
            issues.append("Brand authority signals are weak on-site.")
            recommendations.append(
                "Add complete company details, sameAs references, stronger entity consistency, and external authority proof."
            )
        else:
            strengths.append("Brand authority signals show meaningful baseline coverage.")

        findings = {
            "ai_crawler_access_score": crawler_score,
            "citability": citability,
            "llms_quality": llms_quality,
            "basic_brand_presence": basic_brand_presence,
            "brand_authority": brand,
            "llms_exists": resolved.llms.exists,
            "backlink_provider_available": resolved.backlinks.available,
        }
        checks = {
            "allowed_ai_crawlers": allowed_crawlers,
            "total_ai_crawlers_checked": len(crawler_rules),
            "llms_exists": resolved.llms.exists,
            "llms_effectiveness": llms_quality["signals"],
            "citability_signals": citability["signals"],
            "brand_signals": resolved.site_signals.model_dump(),
            "brand_authority_components": brand.get("components", {}),
            "backlinks": resolved.backlinks.model_dump(),
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

        # premium 模式：使用 LLM 微调评分并增加深度洞察
        if mode == "premium":
            result = await self.llm_enrichment.enrich_visibility(resolved, result, llm_config, feedback_lang=feedback_lang)

        # 置信度随覆盖页面数增加（最多 5 页），llms.txt 存在额外加 0.05
        result = self.finalize_audit_result(
            result,
            module_key="visibility",
            input_pages=self.collect_input_pages(resolved, "homepage", "about", "service", "article", "case_study"),
            started_at=started_at,
            confidence=min(0.97, 0.6 + (len(resolved.page_profiles) / 5) * 0.25 + (0.05 if resolved.llms.exists else 0)),
        )
        return result
