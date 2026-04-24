from __future__ import annotations

import time

from app.models.audit import SchemaAuditResult
from app.models.requests import LLMConfig
from app.services.audit.base import AuditBaseService
from app.services.audit.scoring import ScoringService
from app.utils.schema_extractor import extract_schema_summary


class SchemaService(AuditBaseService):
    """结构化数据审计模块（占 GEO 总分 10%）

    评分构成（满分 100）：
    - json_ld_present: 8分（是否存在任何 JSON-LD）
    - organization: 12分（Organization 或其子类型）
    - website: 6分（WebSite schema）
    - service: 9分（Service schema）
    - article: 9分（Article/NewsArticle schema）
    - faq_page: 7分（FAQPage schema）
    - product: 9分（Product schema）
    - defined_term: 5分（DefinedTerm schema）
    - same_as: 8分（至少一个 sameAs 引用）
    - entity_ids: 4分（至少 2 个稳定 @id）
    - relation_signals: 4分（关系谓词丰富度）
    - breadcrumb: 4分（BreadcrumbList）
    - machine_dates: 8分（datePublished / dateModified）
    - visible_alignment: 7分（Schema 内容与可见内容的一致性）
    """

    def __init__(self, discovery_service=None) -> None:
        super().__init__(discovery_service)
        self.scoring = ScoringService()

    async def audit(
        self,
        url: str,
        discovery=None,
        mode: str = "standard",
        llm_config: LLMConfig | None = None,
        target_locale: str | None = None,
    ) -> SchemaAuditResult:
        """执行结构化数据审计

        合并首页和所有关键页的 JSON-LD 块，统一提取 Schema 类型和 sameAs 引用
        """
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(url, discovery, target_locale=target_locale)

        summary = resolved.schema_summary or extract_schema_summary(list(resolved.homepage.json_ld_blocks))
        checks = {
            "json_ld_present": summary["json_ld_present"],
            "organization": summary["has_organization"],
            "local_business": summary["has_local_business"],
            "article": summary["has_article"],
            "faq_page": summary["has_faq_page"],
            "service": summary["has_service"],
            "website": summary["has_website"],
            "product": summary["has_product"],
            "defined_term": summary["has_defined_term"],
            "breadcrumb_list": summary.get("has_breadcrumb_list", False),
            "has_date_published": summary.get("has_date_published", False),
            "has_date_modified": summary.get("has_date_modified", False),
            "visible_alignment_score": summary.get("avg_visible_alignment_score", summary.get("visible_alignment_score", 0)),
            "same_as_count": len(summary["same_as"]),
            "entity_id_count": summary["entity_id_count"],
            "relation_count": summary["relation_count"],
        }

        # 计算结构化数据分数
        structured_data_score = self.scoring.clamp_score(
            (8 if checks["json_ld_present"] else 0)
            + (12 if checks["organization"] else 0)
            + (6 if checks["website"] else 0)
            + (9 if checks["service"] else 0)
            + (9 if checks["article"] else 0)
            + (7 if checks["faq_page"] else 0)
            + (9 if checks["product"] else 0)
            + (5 if checks["defined_term"] else 0)
            + (8 if checks["same_as_count"] > 0 else 0)
            + (4 if checks["entity_id_count"] >= 2 else 0)
            + (4 if checks["relation_count"] >= 3 else 0)
            + (4 if checks["breadcrumb_list"] else 0)
            + (4 if checks["has_date_published"] else 0)
            + (4 if checks["has_date_modified"] else 0)
            + (7 if checks["visible_alignment_score"] >= 60 else 3 if checks["visible_alignment_score"] >= 30 else 0)
        )
        status = self.scoring.status_from_score(structured_data_score)

        issues: list[str] = []
        strengths: list[str] = []
        recommendations: list[str] = []
        missing_schema_recommendations: list[str] = []

        if checks["json_ld_present"]:
            strengths.append("JSON-LD markup is present.")
        else:
            issues.append("No JSON-LD structured data detected.")
            missing_schema_recommendations.append("Implement baseline JSON-LD on homepage and core landing pages.")

        # 各 Schema 类型检查及对应的缺失建议
        schema_requirements = {
            "organization": "Add Organization schema with name, url, logo, contactPoint, and sameAs.",
            "local_business": "Add LocalBusiness schema if the business serves a local or regional market.",
            "article": "Add Article or NewsArticle schema to editorial pages.",
            "faq_page": "Add FAQPage schema to pages with FAQ sections.",
            "service": "Add Service schema to commercial pages.",
            "website": "Add WebSite schema with SearchAction where relevant.",
            "product": "Add Product schema to product or solution detail pages where applicable.",
            "defined_term": "Model proprietary technologies or frameworks with DefinedTerm and stable @id values.",
        }

        for key, suggestion in schema_requirements.items():
            if checks[key]:
                strengths.append(f"{key.replace('_', ' ').title()} schema detected.")
            else:
                issues.append(f"{key.replace('_', ' ').title()} schema is missing.")
                missing_schema_recommendations.append(suggestion)

        if checks["same_as_count"] == 0:
            issues.append("No sameAs references found in structured data.")
            missing_schema_recommendations.append("Add sameAs links for official social, knowledge, and profile URLs.")
        else:
            strengths.append("Structured data exposes sameAs entity references.")

        if not checks["breadcrumb_list"]:
            issues.append("BreadcrumbList schema is missing.")
            missing_schema_recommendations.append("Add BreadcrumbList schema so crawlers can infer page position and hierarchy.")
        else:
            strengths.append("BreadcrumbList schema is present.")

        if not checks["has_date_published"] and not checks["has_date_modified"]:
            issues.append("Structured data does not expose machine-readable freshness dates.")
            missing_schema_recommendations.append("Add datePublished and/or dateModified to content and solution schemas where relevant.")
        else:
            strengths.append("Structured data exposes machine-readable freshness dates.")

        if checks["visible_alignment_score"] < 60:
            issues.append("Schema text does not yet align strongly enough with visible page copy.")
            missing_schema_recommendations.append("Keep Schema names, descriptions, FAQs, and claims tightly aligned with on-page visible content.")
        else:
            strengths.append("Schema text aligns well with visible page content.")

        if checks["entity_id_count"] < 2:
            issues.append("Structured data lacks stable @id usage across brand and commercial entities.")
            missing_schema_recommendations.append("Add stable @id identifiers to Organization, WebSite, Product, and other core nodes.")
        else:
            strengths.append("Structured data uses stable @id values across multiple entities.")

        if checks["relation_count"] < 3:
            issues.append("Entity relationships are too sparse for strong machine reasoning.")
            missing_schema_recommendations.append(
                "Add richer entity relationships such as brand, manufacturer, hasPart, offers, about, and contactPoint."
            )
        else:
            strengths.append("Structured data exposes a usable baseline of entity relationships.")

        # 取前 5 条缺失 Schema 建议
        recommendations.extend(missing_schema_recommendations[:5])
        findings = {
            "schema_type_count": len(summary["types"]),
            "same_as_count": len(summary["same_as"]),
            "entity_id_count": summary["entity_id_count"],
            "relation_count": summary["relation_count"],
            "visible_alignment_score": checks["visible_alignment_score"],
            "machine_date_signals": int(checks["has_date_published"]) + int(checks["has_date_modified"]),
        }
        result = SchemaAuditResult(
            score=structured_data_score,
            status=status,
            findings=findings,
            issues=issues,
            strengths=strengths,
            recommendations=recommendations,
            structured_data_score=structured_data_score,
            checks=checks,
            schema_types=summary["types"],
            same_as=summary["same_as"],
            missing_schema_recommendations=missing_schema_recommendations,
        )
        self.set_execution_metadata(result, mode, llm_config)
        # schema 模块保持规则驱动，确保校验结果的确定性
        if mode == "premium":
            result.processing_notes.append("Premium mode currently keeps schema audit rule-based for deterministic validation.")
        # 置信度随覆盖页面数增加
        result = self.finalize_audit_result(
            result,
            module_key="schema",
            input_pages=self.collect_input_pages(resolved, "homepage", "service", "article", "about", "case_study"),
            started_at=started_at,
            confidence=min(0.96, 0.68 + (len(resolved.page_profiles) / 5) * 0.2),
        )
        return result
