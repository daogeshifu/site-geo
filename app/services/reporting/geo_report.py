"""Export the new GEO score and, optionally, a separate complete SEO report."""
from __future__ import annotations

import json

from app.models.audit import SeoAuditResult, SeoSummaryResult
from app.models.geo import GeoAuditResult
from app.services.reporting.seo_report import SeoReportService


def _cell(value):
    return str(value if value is not None else "unverified").replace("|", "\\|").replace("\n", " ")


def render_geo_report(payload: dict) -> str:
    geo = GeoAuditResult.model_validate(payload["geo"])
    lines = ["# On-site GEO Readiness Audit", "", f"Website: {payload.get('url', '')}",
             f"Scoring version: {geo.scoring_version}", f"GEO score: {geo.score if geo.score is not None else 'unverified'}/100",
             f"Status: {geo.status}; readiness: {geo.readiness_status}; provisional: {geo.provisional}",
             f"Evidence coverage: {geo.coverage.get('evidence_coverage', 0):.1%}",
             f"Score bounds: {geo.score_range}", "", "SEO and GEO are independent scores; there is no averaged combined score.", "",
             "## Dimensions", "", "| Dimension | Weight | Score | Evidence coverage |", "|---|---:|---:|---:|"]
    for dimension in geo.dimensions.values():
        lines.append(f"| {_cell(dimension.label)} | {dimension.weight:.0%} | {_cell(dimension.score)} | {dimension.evidence_coverage:.1%} |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {_cell(item['url'])}: {_cell(item['reason'])}" for item in geo.blockers)
    if not geo.blockers:
        lines.append("No measured blockers. Unknown checks still require verification.")
    lines.extend(["", "## Page evidence", ""])
    for page in geo.pages:
        lines.extend([f"### {_cell(page.url)}", "", f"Page type: {page.page_type}; score: {page.score}; status: {page.status}", "",
                      "| Check | Points | State | Value | Evidence |", "|---|---:|---|---:|---|"])
        for dimension in page.dimensions.values():
            for check in dimension.checks:
                lines.append(f"| {check.id} {_cell(check.label)} | {check.max_points} | {check.status} | {_cell(check.value)} | {_cell(json.dumps(check.evidence, ensure_ascii=False))} |")
    lines.extend(["", "## Limits and methodology", "", *[f"- {item}" for item in geo.processing_notes]])
    lines.extend(["", "## Unscored auxiliary information", "", "```json", json.dumps(geo.auxiliary, ensure_ascii=False, indent=2), "```"])
    if payload.get("seo"):
        seo = SeoAuditResult.model_validate(payload["seo"])
        summary = SeoSummaryResult.model_validate(payload["seo_summary"])
        from app.models.discovery import DiscoveryResult
        lines.extend(["", "---", "", SeoReportService().render_markdown(
            url=payload["url"], discovery=DiscoveryResult.model_validate(payload["discovery"]), seo=seo, summary=summary)])
    return "\n".join(lines)
