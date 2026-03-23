from __future__ import annotations

import asyncio

import httpx

from app.core.config import settings
from app.models.audit import SchemaAuditResult
from app.models.requests import LLMConfig
from app.services.audit_service import AuditBaseService
from app.services.scoring_service import ScoringService
from app.utils.fetcher import fetch_url
from app.utils.html_parser import parse_html
from app.utils.schema_extractor import extract_schema_summary


class SchemaService(AuditBaseService):
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
        resolved = await self.ensure_discovery(url, discovery)
        blocks = list(resolved.homepage.json_ld_blocks)
        targets = [
            page
            for page in [
                resolved.key_pages.service,
                resolved.key_pages.article,
                resolved.key_pages.about,
            ]
            if page
        ]

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        ) as client:
            responses = await asyncio.gather(
                *(fetch_url(page_url, client=client) for page_url in targets),
                return_exceptions=True,
            )

        for result in responses:
            if isinstance(result, Exception):
                continue
            parsed = parse_html(result.final_url, result.text)
            blocks.extend(parsed["json_ld_blocks"])

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
        if mode == "premium":
            result.processing_notes.append("Premium mode currently keeps schema audit rule-based for deterministic validation.")
        return result
