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
    """GEO 审计汇总服务：将 5 个模块结果合并为复合 GEO 评分

    GEO 综合分由 6 个维度加权计算（总权重 100%）：
    - AI Citability & Visibility:   25%（ai_visibility_score）
    - Brand Authority Signals:      20%（brand_authority_score）
    - Content Quality & E-E-A-T:   20%（E-E-A-T 五维平均）
    - Technical Foundations:        15%（technical_score）
    - Structured Data:              10%（structured_data_score）
    - Platform Optimization:        10%（platform_optimization_score）
    """

    def __init__(self) -> None:
        self.scoring = ScoringService()
        self.llm_enrichment = LLMEnrichmentService()

    def _content_eeat_score(self, content: ContentAuditResult) -> int:
        """计算内容 E-E-A-T 综合分：5 项评分的简单平均值"""
        return self.scoring.clamp_score(
            (
                content.content_score
                + content.experience_score
                + content.expertise_score
                + content.authoritativeness_score
                + content.trustworthiness_score
            )
            / 5
        )

    def _visibility_dimension_views(self, visibility: VisibilityAuditResult) -> tuple[dict, dict]:
        """将 visibility 模块结果拆分为"AI 可见性"和"品牌权威"两个独立维度视图

        返回 (ai_dimension, brand_dimension) 元组，每个视图包含 module/score/issues/recommendations
        """
        llms_quality = visibility.findings.get("llms_quality", {}).get("score", 0)
        citability = visibility.findings.get("citability", {}).get("score", 0)
        crawler_score = visibility.findings.get("ai_crawler_access_score", 0)
        basic_presence = visibility.findings.get("basic_brand_presence", {}).get("score", 0)
        brand_components = visibility.checks.get("brand_authority_components", {})
        backlink_component = brand_components.get("backlink_quality", {})
        entity_component = brand_components.get("entity_consistency", {})

        # AI 可见性维度问题
        ai_issues: list[str] = []
        ai_actions: list[str] = []
        if crawler_score < 100:
            ai_issues.append("AI crawlers are not fully allowed by robots.txt.")
            ai_actions.append(
                "Review robots.txt and allow GPTBot, OAI-SearchBot, PerplexityBot, and Google-Extended."
            )
        if llms_quality < 60:
            ai_issues.append("llms.txt is missing or too thin to guide AI systems effectively.")
            ai_actions.append("Publish or expand llms.txt with brand context, services, and citation guidance.")
        if citability < 70:
            ai_issues.append("Citation-ready page structure is not yet strong enough for consistent reuse.")
            ai_actions.append("Improve answer-first copy, chunk structure, and metadata coverage on key pages.")
        if basic_presence < 60:
            ai_issues.append("Basic entity presence across homepage, about, and contact experiences is thin.")
            ai_actions.append("Strengthen homepage, about, and contact-page brand and contact signals.")

        # 品牌权威维度问题
        brand_issues: list[str] = []
        brand_actions: list[str] = []
        if visibility.brand_authority_score < 60:
            brand_issues.append("Brand authority is weak relative to GEO citation needs.")
        if backlink_component.get("available") and (backlink_component.get("score") or 0) < 60:
            brand_issues.append("External backlink authority is still light for a strong entity profile.")
            brand_actions.append("Grow high-quality referring domains and editorial backlinks.")
        if entity_component.get("same_domain_sitemap") is False:
            brand_issues.append("Entity consistency is weakened by sitemap or domain mismatch.")
            brand_actions.append("Align sitemap URLs, canonical signals, and the primary domain.")
        if not brand_actions:
            brand_actions.append("Add company details, sameAs references, and stronger entity consistency signals.")

        return (
            {
                "module": "visibility",
                "score": visibility.ai_visibility_score,
                "issues": ai_issues or visibility.issues[:2],
                "recommendations": ai_actions or visibility.recommendations[:2],
            },
            {
                "module": "brand_authority",
                "score": visibility.brand_authority_score,
                "issues": brand_issues or ["Brand entity signals need stronger external and structured support."],
                "recommendations": brand_actions,
            },
        )

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
        """计算复合 GEO 评分并生成汇总报告

        流程：
        1. 计算内容 E-E-A-T 综合分
        2. 按 6 维权重加权计算复合 GEO 分
        3. 将 6 个维度按分数从低到高排序（最弱维度排前面）
        4. 从最弱维度提取问题/快速行动/优先计划
        5. premium 模式：LLM 生成更丰富的执行摘要
        """
        content_eeat_score = self._content_eeat_score(content)

        # 6 个维度的加权输入
        weighted_inputs = {
            "AI Citability & Visibility": {"raw_score": visibility.ai_visibility_score, "weight": 0.25},
            "Brand Authority Signals": {"raw_score": visibility.brand_authority_score, "weight": 0.20},
            "Content Quality & E-E-A-T": {"raw_score": content_eeat_score, "weight": 0.20},
            "Technical Foundations": {"raw_score": technical.technical_score, "weight": 0.15},
            "Structured Data": {"raw_score": schema.structured_data_score, "weight": 0.10},
            "Platform Optimization": {"raw_score": platform.platform_optimization_score, "weight": 0.10},
        }
        composite_score, weighted_scores = self.scoring.weighted_composite(weighted_inputs)
        status = self.scoring.status_from_score(composite_score)

        ai_dimension, brand_dimension = self._visibility_dimension_views(visibility)
        # 构建 6 个维度视图（中文标签便于展示）
        dimensions = [
            ("AI 可见性", ai_dimension),
            ("品牌权威", brand_dimension),
            (
                "内容与 E-E-A-T",
                {
                    "module": "content",
                    "score": content_eeat_score,
                    "issues": content.issues,
                    "recommendations": content.recommendations,
                },
            ),
            (
                "技术基础",
                {
                    "module": "technical",
                    "score": technical.technical_score,
                    "issues": technical.issues,
                    "recommendations": technical.recommendations,
                },
            ),
            (
                "结构化数据",
                {
                    "module": "schema",
                    "score": schema.structured_data_score,
                    "issues": schema.issues,
                    "recommendations": schema.recommendations,
                },
            ),
            (
                "平台适配",
                {
                    "module": "platform",
                    "score": platform.platform_optimization_score,
                    "issues": platform.issues,
                    "recommendations": platform.recommendations,
                },
            ),
        ]
        # 按分数升序排列维度（最弱的优先处理）
        ordered_dimensions = sorted(dimensions, key=lambda item: item[1]["score"])

        top_issues: list[str] = []
        quick_wins: list[str] = []
        prioritized_action_plan: list[ActionPlanItem] = []

        for index, (label, payload) in enumerate(ordered_dimensions):
            # 提取每个维度的顶部问题（合并后最多 5 条）
            for issue in payload["issues"]:
                if len(top_issues) >= 5:
                    break
                formatted = f"{label}: {issue}"
                if formatted not in top_issues:
                    top_issues.append(formatted)
            # 提取快速行动建议（最多 5 条）
            for recommendation in payload["recommendations"]:
                if len(quick_wins) >= 5:
                    break
                if recommendation not in quick_wins:
                    quick_wins.append(recommendation)
            # 为最弱维度生成优先行动计划（分数最低→high, 前3→medium, 其余→low）
            if payload["recommendations"]:
                prioritized_action_plan.append(
                    ActionPlanItem(
                        priority="high" if index == 0 else "medium" if index < 3 else "low",
                        module=payload["module"],
                        action=payload["recommendations"][0],
                        rationale=f"{label} is one of the weakest scoring dimensions and is constraining the composite GEO score.",
                    )
                )

        # 生成文字摘要
        summary_text = (
            f"{discovery.domain or url} currently scores {composite_score}/100 for GEO readiness. "
            f"The biggest gaps are in {ordered_dimensions[0][0]} and {ordered_dimensions[1][0]}."
        )
        result = SummaryResult(
            composite_geo_score=composite_score,
            status=status,
            audit_mode=mode,
            dimensions={label: payload for label, payload in dimensions},
            weighted_scores=weighted_scores,
            summary=summary_text,
            top_issues=top_issues,
            quick_wins=quick_wins,
            prioritized_action_plan=prioritized_action_plan[:5],  # 最多 5 条优先行动
        )
        if llm_config:
            result.llm_provider = llm_config.provider
            result.llm_model = llm_config.model
        # premium 模式：LLM 生成更丰富的执行摘要和行动计划
        if mode == "premium":
            result = await self.llm_enrichment.enrich_summary(discovery, visibility, content, platform, result, llm_config)
        return result
