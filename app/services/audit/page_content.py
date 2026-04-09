from __future__ import annotations

import re
import time
from typing import Any

from app.models.audit import (
    ActionPlanItem,
    ContentAuditResult,
    ContentPageAnalysis,
    ContentRuleCheck,
    PageContentAuditResult,
    PageContentSummaryResult,
    SkillLensResult,
)
from app.models.requests import LLMConfig
from app.services.audit.base import AuditBaseService
from app.services.llm.enrichment import LLMEnrichmentService
from app.services.audit.scoring import ScoringService


class PageContentAuditService(AuditBaseService):
    """单篇内容审计服务，结合 GEO 内容可引用性与页面级 SEO 信号。"""

    FACTOR_LABELS = {
        "clear_definitions": ("Clear definitions", "定义清晰度"),
        "quotable_statements": ("Quotable statements", "可引用表述"),
        "factual_density": ("Factual density", "事实密度"),
        "source_citations": ("Source citations", "来源与引用"),
        "qa_format": ("Q&A format", "问答结构"),
        "authority_signals": ("Authority signals", "权威信号"),
        "content_freshness": ("Content freshness", "内容新鲜度"),
        "structure_clarity": ("Structure clarity", "结构清晰度"),
    }

    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()
        self.llm_enrichment = LLMEnrichmentService()

    def _t(self, feedback_lang: str, en_text: str, zh_text: str) -> str:
        return zh_text if feedback_lang == "zh" else en_text

    def _status(self, score: int) -> str:
        return self.scoring.status_from_score(score)

    def _definition_forward(self, text: str) -> bool:
        lead = " ".join(re.findall(r"\S+", text or "")[:120]).lower()
        patterns = [" is a ", " is an ", " refers to ", " means ", " defined as ", "指的是", "是指", "是一个"]
        return any(pattern in f" {lead} " for pattern in patterns)

    def _content_analysis_from_profile(self, profile) -> ContentPageAnalysis:
        return ContentPageAnalysis(
            url=profile.final_url,
            page_type=profile.page_type,
            title=profile.title,
            word_count=profile.word_count,
            has_faq=profile.has_faq,
            has_author=profile.has_author,
            has_publish_date=profile.has_publish_date,
            has_quantified_data=profile.has_quantified_data,
            has_reference_section=profile.has_reference_section,
            has_inline_citations=profile.has_inline_citations,
            has_tldr=profile.has_tldr,
            has_update_log=profile.has_update_log,
            answer_first=profile.answer_first,
            heading_quality_score=profile.heading_quality_score,
            information_density_score=profile.information_density_score,
            chunk_structure_score=profile.chunk_structure_score,
            internal_link_count=profile.internal_link_count,
            external_link_count=profile.external_link_count,
            descriptive_internal_link_ratio=profile.descriptive_internal_link_ratio,
            descriptive_external_link_ratio=profile.descriptive_external_link_ratio,
            text_excerpt=profile.text_excerpt,
        )

    def _images_alt_ratio(self, images: list[dict[str, Any]]) -> float:
        if not images:
            return 1.0
        with_alt = sum(
            1 for image in images
            if (image.get("alt") if isinstance(image, dict) else getattr(image, "alt", None))
        )
        return round(with_alt / len(images), 2)

    def _build_on_page_checks(self, resolved, target_page: ContentPageAnalysis) -> dict[str, Any]:
        title = resolved.homepage.title or ""
        meta = resolved.homepage.meta_description or ""
        alt_ratio = self._images_alt_ratio(resolved.homepage.images)
        link_context_score = int(
            round(
                target_page.descriptive_internal_link_ratio * 55
                + target_page.descriptive_external_link_ratio * 45
            )
        )
        return {
            "title_present": bool(title),
            "title_length": len(title),
            "meta_description_present": bool(meta),
            "meta_description_length": len(meta),
            "canonical_present": bool(resolved.homepage.canonical),
            "lang_present": bool(resolved.homepage.lang),
            "h1_present": bool(resolved.homepage.h1),
            "heading_count": len(resolved.homepage.headings),
            "image_count": len(resolved.homepage.images),
            "images_with_alt_ratio": alt_ratio,
            "internal_link_count": target_page.internal_link_count,
            "external_link_count": target_page.external_link_count,
            "link_context_score": link_context_score,
            "open_graph_present": bool(resolved.homepage.open_graph),
            "twitter_card_present": bool(resolved.homepage.twitter_cards),
            "json_ld_block_count": len(resolved.homepage.json_ld_blocks),
        }

    def _score_on_page(self, checks: dict[str, Any]) -> int:
        title_len = checks["title_length"]
        meta_len = checks["meta_description_length"]
        heading_count = checks["heading_count"]
        internal_links = checks["internal_link_count"]
        score = 0
        score += 10 if checks["title_present"] else 0
        score += 5 if 45 <= title_len <= 65 else 2 if 30 <= title_len <= 75 and title_len > 0 else 0
        score += 8 if checks["meta_description_present"] else 0
        score += 4 if 80 <= meta_len <= 170 else 2 if 40 <= meta_len <= 200 and meta_len > 0 else 0
        score += 8 if checks["canonical_present"] else 0
        score += 5 if checks["lang_present"] else 0
        score += 10 if checks["h1_present"] else 0
        score += 10 if heading_count >= 3 else 5 if heading_count >= 2 else 0
        score += int(round(checks["images_with_alt_ratio"] * 10))
        score += 8 if internal_links >= 3 else 4 if internal_links >= 1 else 0
        score += min(12, int(round(checks["link_context_score"] * 0.12)))
        score += 5 if checks["open_graph_present"] else 0
        score += 2 if checks["twitter_card_present"] else 0
        score += 3 if checks["json_ld_block_count"] > 0 else 0
        return self.scoring.clamp_score(score)

    def _build_schema_checks(self, page_schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "json_ld_present": bool(page_schema.get("json_ld_present")),
            "has_article": bool(page_schema.get("has_article")),
            "has_faq_page": bool(page_schema.get("has_faq_page")),
            "has_organization": bool(page_schema.get("has_organization")),
            "has_website": bool(page_schema.get("has_website")),
            "has_defined_term": bool(page_schema.get("has_defined_term")),
            "has_breadcrumb_list": bool(page_schema.get("has_breadcrumb_list")),
            "has_date_published": bool(page_schema.get("has_date_published")),
            "has_date_modified": bool(page_schema.get("has_date_modified")),
            "visible_alignment_score": int(page_schema.get("visible_alignment_score", 0) or 0),
            "same_as_count": len(page_schema.get("same_as", []) or []),
            "entity_id_count": int(page_schema.get("entity_id_count", 0) or 0),
            "relation_count": int(page_schema.get("relation_count", 0) or 0),
            "types": page_schema.get("types", []) or [],
        }

    def _score_schema_support(self, checks: dict[str, Any]) -> int:
        score = 0
        score += 15 if checks["json_ld_present"] else 0
        score += 15 if checks["has_article"] else 0
        score += 10 if checks["has_faq_page"] else 0
        score += 10 if checks["has_organization"] or checks["has_website"] else 0
        score += 10 if checks["has_date_published"] else 0
        score += 10 if checks["has_date_modified"] else 0
        score += 5 if checks["has_breadcrumb_list"] else 0
        score += 8 if checks["same_as_count"] > 0 else 0
        score += min(10, int(round(checks["visible_alignment_score"] * 0.1)))
        score += 7 if checks["entity_id_count"] >= 2 else 0
        score += 5 if checks["relation_count"] >= 3 else 0
        score += 5 if checks["has_defined_term"] else 0
        return self.scoring.clamp_score(score)

    def _build_geo_factors(
        self,
        resolved,
        target_page: ContentPageAnalysis,
        schema_checks: dict[str, Any],
    ) -> dict[str, int]:
        clear_definitions = 92 if self._definition_forward(target_page.text_excerpt) else 72 if target_page.answer_first else 35
        quotable_statements = self.scoring.clamp_score(
            (25 if target_page.has_quantified_data else 0)
            + (25 if target_page.has_inline_citations else 0)
            + (15 if target_page.has_reference_section else 0)
            + int(round(target_page.information_density_score * 0.2))
            + int(round(target_page.chunk_structure_score * 0.15))
        )
        source_citations = self.scoring.clamp_score(
            (55 if target_page.has_reference_section else 0)
            + (45 if target_page.has_inline_citations else 0)
        )
        qa_format = self.scoring.clamp_score((60 if target_page.has_faq else 0) + (40 if target_page.answer_first else 0))
        authority_signals = self.scoring.clamp_score(
            (28 if target_page.has_author else 0)
            + (18 if resolved.site_signals.same_as_detected else 0)
            + (14 if resolved.site_signals.company_name_detected else 0)
            + (20 if target_page.has_reference_section else 0)
            + (20 if schema_checks["has_article"] else 0)
        )
        content_freshness = self.scoring.clamp_score(
            (40 if target_page.has_publish_date else 0)
            + (20 if target_page.has_update_log else 0)
            + (20 if schema_checks["has_date_published"] else 0)
            + (20 if schema_checks["has_date_modified"] else 0)
        )
        structure_clarity = self.scoring.clamp_score(
            int(round(target_page.heading_quality_score * 0.55 + target_page.chunk_structure_score * 0.45))
        )
        return {
            "clear_definitions": clear_definitions,
            "quotable_statements": quotable_statements,
            "factual_density": target_page.information_density_score,
            "source_citations": source_citations,
            "qa_format": qa_format,
            "authority_signals": authority_signals,
            "content_freshness": content_freshness,
            "structure_clarity": structure_clarity,
        }

    def _build_core_checks(
        self,
        feedback_lang: str,
        target_page: ContentPageAnalysis,
        geo_factors: dict[str, int],
        schema_checks: dict[str, Any],
        resolved,
    ) -> list[ContentRuleCheck]:
        def check(item_id: str, en_label: str, zh_label: str, passed: bool, priority: str, en_note: str, zh_note: str) -> ContentRuleCheck:
            return ContentRuleCheck(
                id=item_id,
                label=f"{item_id} · {self._t(feedback_lang, en_label, zh_label)}",
                passed=passed,
                priority=priority,
                notes=self._t(feedback_lang, en_note, zh_note),
            )

        return [
            check(
                "C02",
                "Direct answer in first 150 words",
                "前 150 词直接回答",
                target_page.answer_first,
                "high",
                "Lead with a concise answer block before supporting detail.",
                "在正文开头先给出简明答案，再展开解释。",
            ),
            check(
                "C09",
                "Structured FAQ with schema",
                "FAQ 及对应结构化数据",
                target_page.has_faq and schema_checks["has_faq_page"],
                "high",
                "FAQ and FAQPage schema should appear together on the same page.",
                "FAQ 内容与 FAQPage Schema 最好同时出现在同一页面。",
            ),
            check(
                "O02",
                "Summary box / key takeaways",
                "摘要框 / 要点总结",
                target_page.has_tldr,
                "medium",
                "A TL;DR block improves answer-first extraction and snippet reuse.",
                "TL;DR 或要点块有助于答案前置和摘要复用。",
            ),
            check(
                "O05",
                "JSON-LD schema markup",
                "JSON-LD 结构化数据",
                schema_checks["json_ld_present"],
                "high",
                "The page should expose machine-readable context through JSON-LD.",
                "页面应通过 JSON-LD 提供机器可读上下文。",
            ),
            check(
                "O06",
                "Section chunking",
                "分块结构",
                target_page.chunk_structure_score >= 60,
                "medium",
                "Aim for shorter sections and cleaner H2/H3 segmentation.",
                "建议缩短段落，并用更清晰的 H2/H3 做分块。",
            ),
            check(
                "R01",
                "Precise data points",
                "精确数据点",
                target_page.has_quantified_data and geo_factors["factual_density"] >= 60,
                "high",
                "Specific numbers, units, and benchmarks help AI quote the page.",
                "具体数字、单位和基准数据更利于 AI 引用。",
            ),
            check(
                "R02",
                "Visible citations",
                "可见引用信号",
                target_page.has_reference_section or target_page.has_inline_citations,
                "high",
                "Pages making factual claims should show sources inline or in a references section.",
                "带事实主张的页面应展示内联来源或参考资料区。",
            ),
            check(
                "R04",
                "Claims backed by evidence",
                "主张有证据支撑",
                target_page.has_quantified_data and (target_page.has_reference_section or target_page.has_inline_citations),
                "high",
                "Evidence is strongest when quantified claims and citations appear together.",
                "量化数据与引用同时出现时，证据强度最高。",
            ),
            check(
                "R07",
                "Full entity names",
                "完整实体名称",
                resolved.site_signals.company_name_detected,
                "medium",
                "Expose the brand or organization name clearly in visible copy and schema.",
                "在可见正文和 Schema 中清晰暴露品牌或组织名称。",
            ),
        ]

    def _page_content_score(
        self,
        geo_readiness_score: int,
        experience_score: int,
        expertise_score: int,
        authoritativeness_score: int,
        trustworthiness_score: int,
    ) -> int:
        eeat_average = (
            experience_score
            + expertise_score
            + authoritativeness_score
            + trustworthiness_score
        ) / 4
        return self.scoring.clamp_score(int(round(geo_readiness_score * 0.55 + eeat_average * 0.45)))

    def _build_skill_lenses(
        self,
        feedback_lang: str,
        geo_readiness_score: int,
        on_page_seo_score: int,
        schema_support_score: int,
        issues: list[str],
        recommendations: list[str],
        on_page_issues: list[str],
        on_page_recommendations: list[str],
    ) -> list[SkillLensResult]:
        geo_score = self.scoring.clamp_score(int(round(geo_readiness_score * 0.75 + schema_support_score * 0.25)))
        return [
            SkillLensResult(
                key="geo-content-optimizer",
                label="geo-content-optimizer",
                score=geo_score,
                status=self._status(geo_score),
                summary=self._t(
                    feedback_lang,
                    "Focuses on citation readiness, quotable structure, evidence, freshness, and schema support.",
                    "聚焦内容可引用性、可摘录结构、证据密度、新鲜度与 Schema 支撑。",
                ),
                issues=issues[:3],
                recommendations=recommendations[:3],
            ),
            SkillLensResult(
                key="on-page-seo-auditor",
                label="on-page-seo-auditor",
                score=on_page_seo_score,
                status=self._status(on_page_seo_score),
                summary=self._t(
                    feedback_lang,
                    "Focuses on title, meta description, headings, canonical, images, and link context.",
                    "聚焦标题、描述、标题结构、canonical、图片和链接上下文。",
                ),
                issues=on_page_issues[:3],
                recommendations=on_page_recommendations[:3],
            ),
        ]

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        feedback_lang: str = "en",
    ) -> PageContentAuditResult:
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(url, discovery)
        homepage_profile = resolved.page_profiles["homepage"]
        target_page = self._content_analysis_from_profile(homepage_profile)
        target_page.page_type = "article"
        page_schema = homepage_profile.json_ld_summary or {}

        on_page_checks = self._build_on_page_checks(resolved, target_page)
        on_page_seo_score = self._score_on_page(on_page_checks)
        schema_checks = self._build_schema_checks(page_schema)
        schema_support_score = self._score_schema_support(schema_checks)
        geo_factors = self._build_geo_factors(resolved, target_page, schema_checks)
        geo_readiness_score = self.scoring.clamp_score(
            int(round(sum(geo_factors.values()) / max(len(geo_factors), 1)))
        )

        experience_score = self.scoring.clamp_score(
            (25 if target_page.has_quantified_data else 0)
            + (20 if target_page.has_reference_section else 0)
            + (15 if target_page.has_inline_citations else 0)
            + (15 if target_page.has_update_log else 0)
            + (25 if target_page.word_count >= 900 else 15 if target_page.word_count >= 500 else 5)
        )
        expertise_score = self.scoring.clamp_score(
            (25 if target_page.answer_first else 0)
            + (20 if target_page.word_count >= 900 else 10 if target_page.word_count >= 500 else 0)
            + int(round(target_page.heading_quality_score * 0.2))
            + int(round(target_page.information_density_score * 0.2))
            + int(round(target_page.chunk_structure_score * 0.15))
        )
        authoritativeness_score = self.scoring.clamp_score(
            (25 if target_page.has_author else 0)
            + (15 if resolved.site_signals.company_name_detected else 0)
            + (15 if resolved.site_signals.same_as_detected else 0)
            + (15 if target_page.has_reference_section else 0)
            + (15 if schema_checks["has_article"] else 0)
            + (15 if resolved.site_signals.awards_detected or resolved.site_signals.certifications_detected else 0)
        )
        trustworthiness_score = self.scoring.clamp_score(
            (20 if target_page.has_publish_date else 0)
            + (15 if on_page_checks["canonical_present"] else 0)
            + (10 if on_page_checks["lang_present"] else 0)
            + (15 if target_page.has_inline_citations else 0)
            + (10 if on_page_checks["meta_description_present"] else 0)
            + (10 if schema_checks["has_date_published"] or schema_checks["has_date_modified"] else 0)
            + (10 if target_page.has_update_log else 0)
            + (10 if resolved.site_signals.phone_detected or resolved.site_signals.email_detected or resolved.site_signals.address_detected else 0)
        )

        page_content_score = self._page_content_score(
            geo_readiness_score,
            experience_score,
            expertise_score,
            authoritativeness_score,
            trustworthiness_score,
        )
        overall_score = self.scoring.clamp_score(
            int(round(page_content_score * 0.65 + on_page_seo_score * 0.2 + schema_support_score * 0.15))
        )

        issues: list[str] = []
        strengths: list[str] = []
        recommendations: list[str] = []
        on_page_issues: list[str] = []
        on_page_recommendations: list[str] = []

        if not target_page.answer_first:
            issues.append(self._t(feedback_lang, "The page does not lead with a direct answer or definition.", "页面开头没有直接回答或定义。"))
            recommendations.append(self._t(feedback_lang, "Rewrite the opening 40-60 words as a standalone answer block.", "将开头 40-60 词改写为可独立引用的答案块。"))
        else:
            strengths.append(self._t(feedback_lang, "The article opens with an answer-first structure.", "文章采用了先答后述结构。"))

        if not target_page.has_faq:
            issues.append(self._t(feedback_lang, "The page is missing FAQ-style follow-up content.", "页面缺少 FAQ 式补充问答内容。"))
            recommendations.append(self._t(feedback_lang, "Add 3-5 question-led follow-up sections covering common reader questions.", "补充 3-5 个常见问题的小节。"))
        if target_page.has_faq and not schema_checks["has_faq_page"]:
            issues.append(self._t(feedback_lang, "FAQ content exists but FAQPage schema is missing.", "页面已有 FAQ 内容，但缺少 FAQPage Schema。"))
            recommendations.append(self._t(feedback_lang, "Publish FAQPage JSON-LD that matches the visible FAQ block.", "补充与页面 FAQ 一致的 FAQPage JSON-LD。"))

        if not target_page.has_reference_section and not target_page.has_inline_citations:
            issues.append(self._t(feedback_lang, "Claims are not visibly supported by sources or citations.", "页面中的主张缺少可见来源或引用。"))
            recommendations.append(self._t(feedback_lang, "Add inline citations or a references section for factual claims.", "为事实性主张补充内联引用或参考资料区。"))
        if not target_page.has_quantified_data:
            issues.append(self._t(feedback_lang, "The article lacks concrete numbers or benchmark data.", "文章缺少具体数字或基准数据。"))
            recommendations.append(self._t(feedback_lang, "Add precise statistics, units, or before/after data points.", "补充精确统计、单位或前后对比数据。"))
        if not target_page.has_author:
            issues.append(self._t(feedback_lang, "No author or expert byline was detected.", "未检测到作者或专家署名。"))
            recommendations.append(self._t(feedback_lang, "Expose an author block with credentials and expertise.", "增加带资历说明的作者信息块。"))
        if not target_page.has_publish_date:
            issues.append(self._t(feedback_lang, "Publish date signals are missing on the page.", "页面缺少发布日期信号。"))
            recommendations.append(self._t(feedback_lang, "Expose published and updated timestamps near the title.", "在标题附近展示发布时间和更新时间。"))
        if not target_page.has_tldr:
            recommendations.append(self._t(feedback_lang, "Add a TL;DR or key takeaways block near the top.", "在页面上方增加 TL;DR 或要点总结。"))
        if target_page.heading_quality_score < 60 or target_page.chunk_structure_score < 60:
            issues.append(self._t(feedback_lang, "Section structure is weaker than ideal for AI extraction.", "分块结构还不够利于 AI 抽取。"))
            recommendations.append(self._t(feedback_lang, "Split long sections into shorter H2/H3-led chunks of 3-5 sentences.", "把长段落拆成由 H2/H3 引导的 3-5 句短块。"))
        if not schema_checks["json_ld_present"]:
            issues.append(self._t(feedback_lang, "No JSON-LD markup was detected on the target page.", "目标页面没有检测到 JSON-LD。"))
            recommendations.append(self._t(feedback_lang, "Add Article JSON-LD with headline, author, datePublished, and dateModified.", "增加包含标题、作者、发布时间和更新时间的 Article JSON-LD。"))
        if not schema_checks["has_article"]:
            issues.append(self._t(feedback_lang, "Article schema is missing for the blog page.", "博客页面缺少 Article Schema。"))
            recommendations.append(self._t(feedback_lang, "Model the page as Article or BlogPosting schema.", "将页面建模为 Article 或 BlogPosting Schema。"))

        if not on_page_checks["title_present"]:
            on_page_issues.append(self._t(feedback_lang, "The page title is missing.", "页面标题缺失。"))
            on_page_recommendations.append(self._t(feedback_lang, "Add a unique title tag aligned to the article topic.", "增加与文章主题一致的唯一 title。"))
        elif not 45 <= on_page_checks["title_length"] <= 65:
            on_page_issues.append(self._t(feedback_lang, "The title length is outside the ideal range.", "title 长度不在理想范围内。"))
            on_page_recommendations.append(self._t(feedback_lang, "Keep the title close to 45-65 characters.", "将 title 长度控制在 45-65 个字符左右。"))

        if not on_page_checks["meta_description_present"]:
            on_page_issues.append(self._t(feedback_lang, "Meta description is missing.", "meta description 缺失。"))
            on_page_recommendations.append(self._t(feedback_lang, "Add a descriptive meta description summarizing the page value.", "增加概括页面价值的 meta description。"))
        if not on_page_checks["canonical_present"]:
            on_page_issues.append(self._t(feedback_lang, "Canonical tag is missing.", "canonical 标签缺失。"))
            on_page_recommendations.append(self._t(feedback_lang, "Publish a canonical tag pointing at the preferred URL.", "增加指向首选 URL 的 canonical。"))
        if not on_page_checks["lang_present"]:
            on_page_issues.append(self._t(feedback_lang, "HTML lang declaration is missing.", "HTML lang 声明缺失。"))
            on_page_recommendations.append(self._t(feedback_lang, "Declare the document language on the html element.", "在 html 元素上声明页面语言。"))
        if not on_page_checks["h1_present"]:
            on_page_issues.append(self._t(feedback_lang, "No visible H1 was detected.", "未检测到 H1。"))
            on_page_recommendations.append(self._t(feedback_lang, "Add a clear H1 aligned to the article intent.", "增加与文章意图一致的 H1。"))
        if on_page_checks["images_with_alt_ratio"] < 0.7:
            on_page_issues.append(self._t(feedback_lang, "Image alt text coverage is too low.", "图片 alt 文本覆盖率偏低。"))
            on_page_recommendations.append(self._t(feedback_lang, "Add descriptive alt text to editorial images.", "为内容图片补充描述性 alt 文本。"))
        if on_page_checks["link_context_score"] < 55:
            on_page_issues.append(self._t(feedback_lang, "Link anchor context is too generic.", "链接锚文本语义不够明确。"))
            on_page_recommendations.append(self._t(feedback_lang, "Use more descriptive internal and external anchor text.", "使用更具描述性的内外链锚文本。"))

        strengths.extend(
            item
            for item in [
                self._t(feedback_lang, "The page includes quantified claims that can become quotable evidence.", "页面包含可引用的量化信息。")
                if target_page.has_quantified_data else "",
                self._t(feedback_lang, "Visible source signals improve trust and answer reuse.", "可见引用信号有助于建立信任和答案复用。")
                if target_page.has_reference_section or target_page.has_inline_citations else "",
                self._t(feedback_lang, "On-page basics such as title, H1, and canonical are largely in place.", "title、H1、canonical 等页面基础信号较完整。")
                if on_page_seo_score >= 70 else "",
                self._t(feedback_lang, "Schema support is strong enough to help machines interpret the page.", "Schema 支撑较好，便于机器理解页面。")
                if schema_support_score >= 70 else "",
            ]
            if item
        )

        core_checks = self._build_core_checks(
            feedback_lang,
            target_page,
            geo_factors,
            schema_checks,
            resolved,
        )
        skill_lenses = self._build_skill_lenses(
            feedback_lang,
            geo_readiness_score,
            on_page_seo_score,
            schema_support_score,
            issues,
            recommendations,
            on_page_issues,
            on_page_recommendations,
        )

        findings = {
            "factor_count": len(geo_factors),
            "geo_factor_scores": geo_factors,
            "definition_forward": self._definition_forward(target_page.text_excerpt),
            "schema_types": schema_checks["types"],
            "images_with_alt_ratio": on_page_checks["images_with_alt_ratio"],
            "core_check_passed": sum(1 for item in core_checks if item.passed),
        }
        checks = {
            "word_count": target_page.word_count,
            "faq_present": target_page.has_faq,
            "author_present": target_page.has_author,
            "publish_date_present": target_page.has_publish_date,
            "quantified_data_present": target_page.has_quantified_data,
            "reference_section_present": target_page.has_reference_section,
            "inline_citations_present": target_page.has_inline_citations,
            "tldr_present": target_page.has_tldr,
            "update_log_present": target_page.has_update_log,
            "answer_first_present": target_page.answer_first,
        }

        result = PageContentAuditResult(
            score=overall_score,
            status=self._status(overall_score),
            findings=findings,
            issues=issues + [item for item in on_page_issues if item not in issues],
            strengths=strengths,
            recommendations=recommendations + [item for item in on_page_recommendations if item not in recommendations],
            page_content_score=page_content_score,
            geo_readiness_score=geo_readiness_score,
            on_page_seo_score=on_page_seo_score,
            schema_support_score=schema_support_score,
            experience_score=experience_score,
            expertise_score=expertise_score,
            authoritativeness_score=authoritativeness_score,
            trustworthiness_score=trustworthiness_score,
            checks=checks,
            geo_factors=geo_factors,
            on_page_checks=on_page_checks,
            schema_checks=schema_checks,
            target_page=target_page,
            core_checks=core_checks,
            skill_lenses=skill_lenses,
            processing_notes=[
                self._t(
                    feedback_lang,
                    "Single-page content audit treats the provided URL as the primary article page.",
                    "单页内容审计会把输入 URL 视为主要文章页。",
                )
            ],
        )
        self.set_execution_metadata(result, mode, llm_config)

        if mode == "premium":
            proxy_result = ContentAuditResult(
                score=page_content_score,
                status=self._status(page_content_score),
                findings=result.findings.copy(),
                issues=result.issues.copy(),
                strengths=result.strengths.copy(),
                recommendations=result.recommendations.copy(),
                content_score=page_content_score,
                experience_score=experience_score,
                expertise_score=expertise_score,
                authoritativeness_score=authoritativeness_score,
                trustworthiness_score=trustworthiness_score,
                checks=result.checks.copy(),
                page_analyses={"target": target_page},
            )
            self.set_execution_metadata(proxy_result, mode, llm_config)
            proxy_result = await self.llm_enrichment.enrich_content(resolved, proxy_result, llm_config, feedback_lang=feedback_lang)
            result.page_content_score = proxy_result.content_score
            result.experience_score = proxy_result.experience_score
            result.expertise_score = proxy_result.expertise_score
            result.authoritativeness_score = proxy_result.authoritativeness_score
            result.trustworthiness_score = proxy_result.trustworthiness_score
            result.score = self.scoring.clamp_score(
                int(round(proxy_result.content_score * 0.65 + on_page_seo_score * 0.2 + schema_support_score * 0.15))
            )
            result.status = self._status(result.score)
            result.issues = proxy_result.issues
            result.strengths = proxy_result.strengths
            result.recommendations = proxy_result.recommendations
            result.findings = proxy_result.findings
            result.llm_enhanced = proxy_result.llm_enhanced
            result.llm_provider = proxy_result.llm_provider
            result.llm_model = proxy_result.llm_model
            result.llm_insights = proxy_result.llm_insights
            result.processing_notes = proxy_result.processing_notes
            result.skill_lenses = self._build_skill_lenses(
                feedback_lang,
                result.geo_readiness_score,
                result.on_page_seo_score,
                result.schema_support_score,
                result.issues,
                result.recommendations,
                on_page_issues,
                on_page_recommendations,
            )

        result = self.finalize_audit_result(
            result,
            module_key="content",
            input_pages=[resolved.final_url],
            started_at=started_at,
            confidence=0.82 if resolved.site_signals.company_name_detected else 0.74,
        )
        return result

    def summarize(
        self,
        discovery,
        content_result: PageContentAuditResult,
        *,
        feedback_lang: str = "en",
    ) -> PageContentSummaryResult:
        factor_items = sorted(
            content_result.geo_factors.items(),
            key=lambda item: item[1],
        )
        weakest_factors = [self._t(feedback_lang, *self.FACTOR_LABELS[key]) for key, _ in factor_items[:2]]
        summary_text = content_result.findings.get("llm_summary") or self._t(
            feedback_lang,
            (
                f"This page scores {content_result.score}/100 for content readiness. "
                f"The biggest gaps are in {weakest_factors[0] if weakest_factors else 'content structure'}"
                f"{f' and {weakest_factors[1]}' if len(weakest_factors) > 1 else ''}. "
                "Fixing answer-first structure, evidence signals, and page-level schema will usually produce the fastest gains."
            ),
            (
                f"当前页面内容就绪度为 {content_result.score}/100。"
                f"最大短板集中在{weakest_factors[0] if weakest_factors else '内容结构'}"
                f"{f' 和 {weakest_factors[1]}' if len(weakest_factors) > 1 else ''}。"
                "通常优先补齐答案前置、证据引用和页面级 Schema，会带来最快提升。"
            ),
        )

        actions = [
            ActionPlanItem(
                priority="high",
                module="geo-content-optimizer",
                action=item,
                rationale=self._t(
                    feedback_lang,
                    "This is one of the highest-leverage fixes for AI citation readiness.",
                    "这是提升 AI 引用就绪度的高杠杆动作。",
                ),
            )
            for item in content_result.recommendations[:5]
        ]

        return PageContentSummaryResult(
            overall_score=content_result.score,
            status=content_result.status,
            summary=summary_text,
            audit_mode=content_result.audit_mode,
            llm_enhanced=content_result.llm_enhanced,
            llm_provider=content_result.llm_provider,
            llm_model=content_result.llm_model,
            applied_skills=["geo-content-optimizer", "on-page-seo-auditor"],
            score_breakdown={
                "page_content_score": content_result.page_content_score,
                "geo_readiness_score": content_result.geo_readiness_score,
                "on_page_seo_score": content_result.on_page_seo_score,
                "schema_support_score": content_result.schema_support_score,
                "experience_score": content_result.experience_score,
                "expertise_score": content_result.expertise_score,
                "authoritativeness_score": content_result.authoritativeness_score,
                "trustworthiness_score": content_result.trustworthiness_score,
                "target_url": discovery.final_url,
            },
            top_issues=content_result.issues[:5],
            quick_wins=content_result.recommendations[:5],
            prioritized_action_plan=actions,
            processing_notes=content_result.processing_notes,
        )
