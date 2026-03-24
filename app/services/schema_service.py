from __future__ import annotations

import time

from app.models.audit import SchemaAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.scoring_service import ScoringService
from app.utils.schema_extractor import extract_schema_summary


class SchemaService(AuditBaseService):
    """结构化数据审计模块（占 GEO 总分 10%）

    评分构成（满分 100）：
    - json_ld_present: 20分（是否存在任何 JSON-LD）
    - organization: 20分（Organization schema）
    - local_business: 10分（LocalBusiness schema）
    - article: 15分（Article/NewsArticle schema）
    - faq_page: 10分（FAQPage schema）
    - service: 10分（Service schema）
    - website: 10分（WebSite schema）
    - same_as: 5分（至少一个 sameAs 引用）
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
    ) -> SchemaAuditResult:
        """执行结构化数据审计

        合并首页和所有关键页的 JSON-LD 块，统一提取 Schema 类型和 sameAs 引用
        """
        started_at = time.perf_counter()
        resolved = await self.ensure_discovery(url, discovery)

        # 收集所有页面的 JSON-LD 块
        blocks = list(resolved.homepage.json_ld_blocks)
        for page_type in ["service", "article", "about", "case_study"]:
            profile = resolved.page_profiles.get(page_type)
            if profile:
                blocks.extend(profile.json_ld_blocks)

        summary = extract_schema_summary(blocks)
        checks = {
            "json_ld_present": summary["json_ld_present"],
            "organization": summary["has_organization"],
            "local_business": summary["has_local_business"],
            "article": summary["has_article"],
            "faq_page": summary["has_faq_page"],
            "service": summary["has_service"],
            "website": summary["has_website"],
            "same_as_count": len(summary["same_as"]),
        }

        # 计算结构化数据分数
        structured_data_score = self.scoring.clamp_score(
            (20 if checks["json_ld_present"] else 0)
            + (20 if checks["organization"] else 0)
            + (10 if checks["local_business"] else 0)
            + (15 if checks["article"] else 0)
            + (10 if checks["faq_page"] else 0)
            + (10 if checks["service"] else 0)
            + (10 if checks["website"] else 0)
            + (5 if checks["same_as_count"] > 0 else 0)
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

        # 取前 5 条缺失 Schema 建议
        recommendations.extend(missing_schema_recommendations[:5])
        findings = {
            "schema_type_count": len(summary["types"]),
            "same_as_count": len(summary["same_as"]),
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
