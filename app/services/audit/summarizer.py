from __future__ import annotations

from app.models.audit import (
    ActionPlanItem,
    AIPerceptionResult,
    ContentAuditResult,
    MetricDefinition,
    ObservationResult,
    PlatformAuditResult,
    SchemaAuditResult,
    SummaryResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult
from app.models.requests import LLMConfig
from app.services.llm.enrichment import LLMEnrichmentService
from app.services.audit.scoring import ScoringService


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

    def _dimension_display_name(self, key: str, feedback_lang: str) -> str:
        labels = {
            "AI Citability & Visibility": {"en": "AI Citability & Visibility", "zh": "AI 可见性"},
            "Brand Authority Signals": {"en": "Brand Authority Signals", "zh": "品牌权威"},
            "Content Quality & E-E-A-T": {"en": "Content Quality & E-E-A-T", "zh": "内容与 E-E-A-T"},
            "Technical Foundations": {"en": "Technical Foundations", "zh": "技术基础"},
            "Structured Data": {"en": "Structured Data", "zh": "结构化数据"},
            "Platform Optimization": {"en": "Platform Optimization", "zh": "平台适配"},
        }
        return labels.get(key, {}).get(feedback_lang, key)

    def _normalize_percentages(self, values: dict[str, float]) -> dict[str, int]:
        total = sum(max(value, 0) for value in values.values()) or 1
        raw = {key: (max(value, 0) / total) * 100 for key, value in values.items()}
        rounded = {key: int(raw_value) for key, raw_value in raw.items()}
        remainder = 100 - sum(rounded.values())
        if remainder:
            order = sorted(raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True)
            for key, _ in order[:remainder]:
                rounded[key] += 1
        return rounded

    def _ai_perception_keywords(
        self,
        *,
        discovery: DiscoveryResult,
        visibility: VisibilityAuditResult,
        technical: TechnicalAuditResult,
        content: ContentAuditResult,
        schema: SchemaAuditResult,
        platform: PlatformAuditResult,
        feedback_lang: str,
    ) -> list[str]:
        llms_quality = visibility.findings.get("llms_quality", {}).get("score", 0)
        citability = visibility.findings.get("citability", {}).get("score", 0)
        has_defined_term = schema.checks.get("defined_term", False)
        has_publish_dates = content.findings.get("has_publish_date_any", False)
        has_quantified = content.findings.get("has_quantified_data_any", False)

        candidates = [
            (
                visibility.brand_authority_score >= 75 and discovery.site_signals.same_as_detected,
                {"zh": "官方权威", "en": "Authoritative"},
            ),
            (
                schema.structured_data_score >= 70 and technical.technical_score >= 70,
                {"zh": "结构清晰", "en": "Well-structured"},
            ),
            (
                content.expertise_score >= 72 and (discovery.key_pages.article or has_defined_term),
                {"zh": "行业先知", "en": "Thought Leader"},
            ),
            (
                llms_quality >= 70 and has_publish_dates,
                {"zh": "反应迅速", "en": "Fast-moving"},
            ),
            (
                content.experience_score >= 65 and has_quantified,
                {"zh": "证据充分", "en": "Evidence-led"},
            ),
            (
                content.trustworthiness_score >= 70 and discovery.site_signals.company_name_detected and discovery.site_signals.phone_detected,
                {"zh": "值得信赖", "en": "Trustworthy"},
            ),
            (
                citability >= 70 and platform.platform_optimization_score >= 70,
                {"zh": "表达直接", "en": "Answer-first"},
            ),
            (
                discovery.key_pages.service is not None and (schema.checks.get("service") or schema.checks.get("product")),
                {"zh": "产品导向", "en": "Product-led"},
            ),
        ]
        keywords = [labels[feedback_lang] for matched, labels in candidates if matched]
        fallbacks = [
            {"zh": "信号偏弱", "en": "Low-signal"},
            {"zh": "实体模糊", "en": "Entity-blurry"},
            {"zh": "佐证不足", "en": "Proof-light"},
            {"zh": "结构待强化", "en": "Structure-light"},
        ]
        for labels in fallbacks:
            if len(keywords) >= 4:
                break
            keywords.append(labels[feedback_lang])
        return keywords[:4]

    def _ai_perception_snapshot(
        self,
        *,
        discovery: DiscoveryResult,
        visibility: VisibilityAuditResult,
        technical: TechnicalAuditResult,
        content: ContentAuditResult,
        schema: SchemaAuditResult,
        platform: PlatformAuditResult,
        feedback_lang: str,
    ) -> AIPerceptionResult:
        citability = visibility.findings.get("citability", {}).get("score", 0)
        basic_presence = visibility.findings.get("basic_brand_presence", {}).get("score", 0)
        entity_components = visibility.checks.get("brand_authority_components", {}).get("entity_consistency", {})
        controversy_penalty = 0
        if entity_components.get("same_domain_sitemap") is False:
            controversy_penalty += 12
        if not discovery.site_signals.company_name_detected:
            controversy_penalty += 10
        if not discovery.site_signals.same_as_detected:
            controversy_penalty += 8
        if not discovery.llms.exists:
            controversy_penalty += 4

        positive_raw = (
            visibility.ai_visibility_score * 0.22
            + visibility.brand_authority_score * 0.22
            + content.expertise_score * 0.12
            + content.authoritativeness_score * 0.12
            + content.trustworthiness_score * 0.12
            + technical.technical_score * 0.08
            + schema.structured_data_score * 0.06
            + platform.platform_optimization_score * 0.06
        )
        neutral_raw = (
            (100 - citability) * 0.18
            + (100 - basic_presence) * 0.24
            + (100 - schema.structured_data_score) * 0.18
            + (100 - content.content_score) * 0.20
            + (100 - visibility.brand_authority_score) * 0.20
        )
        controversial_raw = (
            (100 - content.trustworthiness_score) * 0.28
            + (100 - visibility.brand_authority_score) * 0.22
            + (100 - technical.technical_score) * 0.12
            + (100 - schema.structured_data_score) * 0.16
            + (100 - content.authoritativeness_score) * 0.10
            + controversy_penalty
        )
        percentages = self._normalize_percentages(
            {
                "positive": max(positive_raw, 12),
                "neutral": max(neutral_raw, 10),
                "controversial": max(controversial_raw, 8),
            }
        )
        return AIPerceptionResult(
            positive_percentage=percentages["positive"],
            neutral_percentage=percentages["neutral"],
            controversial_percentage=percentages["controversial"],
            cognition_keywords=self._ai_perception_keywords(
                discovery=discovery,
                visibility=visibility,
                technical=technical,
                content=content,
                schema=schema,
                platform=platform,
                feedback_lang=feedback_lang,
            ),
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

    def _metric_definitions(self) -> list[MetricDefinition]:
        return [
            MetricDefinition(
                name="AI Citability & Visibility",
                category="Scored",
                scoring="scored",
                formula="Crawler access + citation structure + llms guidance + basic entity presence",
                why_it_matters="Determines whether AI systems can reach, parse, and reuse the site as source material.",
                data_source="robots.txt, llms.txt, homepage and key-page extraction",
                platform_relevance=["ChatGPT", "Google AI Mode", "Google AI Overviews", "Perplexity", "Gemini", "Grok"],
            ),
            MetricDefinition(
                name="Brand Authority Signals",
                category="Scored",
                scoring="scored",
                formula="Backlink quality + brand mentions + entity consistency + business completeness",
                why_it_matters="Helps generative engines trust the entity behind the content and prefer official or reinforced sources.",
                data_source="On-site entity signals, structured data, Semrush backlink overview when available",
                platform_relevance=["ChatGPT", "Perplexity", "Gemini", "Grok"],
            ),
            MetricDefinition(
                name="Content Quality & E-E-A-T",
                category="Scored",
                scoring="scored",
                formula="Content depth + E-E-A-T + fact density + chunk structure",
                why_it_matters="Higher-density, better-structured pages reduce model reasoning cost and increase extraction quality.",
                data_source="Service, article, about, and case-study pages",
                platform_relevance=["Perplexity", "Google AI Mode", "Google AI Overviews", "ChatGPT"],
            ),
            MetricDefinition(
                name="Structured Data & Entity Graph",
                category="Scored",
                scoring="scored",
                formula="Schema coverage + sameAs + stable @id + relation richness + product/defined-term support",
                why_it_matters="Entity-level machine readability supports disambiguation, brand ownership, and multi-hop reasoning.",
                data_source="JSON-LD blocks across homepage and key pages",
                platform_relevance=["Gemini", "Google AI Overviews", "Google AI Mode", "ChatGPT"],
            ),
            MetricDefinition(
                name="Platform Optimization",
                category="Scored",
                scoring="scored",
                formula="Weighted readiness across ChatGPT, Google AI Mode, AI Overviews, Perplexity, Gemini, and Grok",
                why_it_matters="Different GEO channels reward different source patterns, content shapes, and trust signals.",
                data_source="Cross-module signals remapped into platform-specific readiness",
                platform_relevance=["ChatGPT", "Google AI Mode", "Google AI Overviews", "Perplexity", "Gemini", "Grok"],
            ),
            MetricDefinition(
                name="Observation Layer",
                category="Unscored",
                scoring="unscored",
                formula="Optional GA4 / log / citation observation metrics for contextual reporting only",
                why_it_matters="Shows whether readiness work is translating into observed AI traffic or citation evidence.",
                data_source="User-uploaded optional observation data",
                platform_relevance=["ChatGPT", "Google AI Mode", "Google AI Overviews", "Perplexity", "Gemini", "Grok"],
            ),
        ]

    def _score_interpretation(self, observation: ObservationResult | None) -> list[str]:
        interpretation = [
            "GEO Audit v3 scores only readiness dimensions that can be derived from the site and supplied enrichment sources.",
            "Optional observation metrics are displayed separately and never change the composite GEO score.",
            "Platform readiness is comparative guidance, not a direct measurement of live mention share or citation rank.",
        ]
        if observation and observation.provided:
            interpretation.append("Observation data was uploaded and is included as contextual evidence alongside readiness scoring.")
        return interpretation

    async def summarize(
        self,
        url: str,
        discovery: DiscoveryResult,
        visibility: VisibilityAuditResult,
        technical: TechnicalAuditResult,
        content: ContentAuditResult,
        schema: SchemaAuditResult,
        platform: PlatformAuditResult,
        observation: ObservationResult | None = None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        feedback_lang: str = "en",
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
        ai_perception = self._ai_perception_snapshot(
            discovery=discovery,
            visibility=visibility,
            technical=technical,
            content=content,
            schema=schema,
            platform=platform,
            feedback_lang=feedback_lang,
        )

        ai_dimension, brand_dimension = self._visibility_dimension_views(visibility)
        # 构建 6 个维度视图（中文标签便于展示）
        dimensions = [
            ("AI Citability & Visibility", ai_dimension),
            ("Brand Authority Signals", brand_dimension),
            (
                "Content Quality & E-E-A-T",
                {
                    "module": "content",
                    "score": content_eeat_score,
                    "issues": content.issues,
                    "recommendations": content.recommendations,
                },
            ),
            (
                "Technical Foundations",
                {
                    "module": "technical",
                    "score": technical.technical_score,
                    "issues": technical.issues,
                    "recommendations": technical.recommendations,
                },
            ),
            (
                "Structured Data",
                {
                    "module": "schema",
                    "score": schema.structured_data_score,
                    "issues": schema.issues,
                    "recommendations": schema.recommendations,
                },
            ),
            (
                "Platform Optimization",
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
            display_label = self._dimension_display_name(label, feedback_lang)
            # 提取每个维度的顶部问题（合并后最多 5 条）
            for issue in payload["issues"]:
                if len(top_issues) >= 5:
                    break
                formatted = f"{display_label}: {issue}"
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
                        rationale=f"{display_label} is one of the weakest scoring dimensions and is constraining the composite GEO score.",
                    )
                )

        # 生成文字摘要
        summary_text = (
            f"{discovery.domain or url} currently scores {composite_score}/100 for GEO readiness. "
            f"The biggest gaps are in {self._dimension_display_name(ordered_dimensions[0][0], feedback_lang)} and {self._dimension_display_name(ordered_dimensions[1][0], feedback_lang)}."
        )
        if observation and observation.provided:
            summary_text += " Optional observation data was uploaded and is displayed separately without affecting the score."
        notices: list[str] = []
        if discovery.input_scope_warning:
            notices.append(f"Non-homepage input detected: {discovery.input_scope_warning}")
        if discovery.full_audit_enabled:
            notices.append(
                f"Full audit mode sampled {discovery.profiled_page_count} pages and produced page-level diagnostics without changing the site-level scoring weights."
            )
        result = SummaryResult(
            composite_geo_score=composite_score,
            status=status,
            audit_mode=mode,
            dimensions={
                label: {"display_name": self._dimension_display_name(label, feedback_lang), **payload}
                for label, payload in dimensions
            },
            weighted_scores=weighted_scores,
            summary=summary_text,
            top_issues=top_issues,
            quick_wins=quick_wins,
            prioritized_action_plan=prioritized_action_plan[:5],  # 最多 5 条优先行动
            metric_definitions=self._metric_definitions(),
            score_interpretation=self._score_interpretation(observation),
            ai_perception=ai_perception,
            observation=observation,
            notices=notices,
        )
        if llm_config:
            result.llm_provider = llm_config.provider
            result.llm_model = llm_config.model
        # premium 模式：LLM 生成更丰富的执行摘要和行动计划
        if mode == "premium":
            result = await self.llm_enrichment.enrich_summary(
                discovery,
                visibility,
                content,
                platform,
                result,
                llm_config,
                feedback_lang=feedback_lang,
            )
        return result
