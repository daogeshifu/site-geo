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
    lines.extend(["", "## Complete GEO checklist", "", "| Check | Dimension | State | Evidence |", "|---|---|---|---|"])
    for dimension in geo.dimensions.values():
        for check in dimension.checks:
            lines.append(f"| {check.id} {_cell(check.label)} | {_cell(dimension.label)} | {check.status} | {_cell(json.dumps(check.evidence, ensure_ascii=False))} |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {_cell(item['url'])}: {_cell(item['reason'])}" for item in geo.blockers)
    if not geo.blockers:
        lines.append("No measured blockers. Unknown checks still require verification.")
    lines.extend(["", "## Verification queue", ""])
    unknowns = [(page, check) for page in geo.pages for dimension in page.dimensions.values()
                for check in dimension.checks if check.status == "unknown"]
    lines.extend(f"- {check.id} {_cell(check.label)} — {_cell(page.url)}: {_cell(check.recommendation)}"
                 for page, check in unknowns)
    if not unknowns:
        lines.append("No unverified checks in the recorded evidence.")
    lines.extend(["", "## Recommendations", "", *[f"- {item}" for item in geo.recommendations]])
    lines.extend(["", "## Platform retrieval policies (unscored)", "",
                  "Observed robots policies on sampled paths, not actual platform visibility or citation measurements.", "",
                  "| Page | Crawler | Policy |", "|---|---|---|"])
    for page in geo.pages:
        for dimension in page.dimensions.values():
            for check in dimension.checks:
                if check.id != "GEO-002":
                    continue
                for crawler, allowed in check.evidence.get("policies", {}).items():
                    state = "unverified" if allowed is None else "allowed" if allowed else "blocked"
                    lines.append(f"| {_cell(page.url)} | {_cell(crawler)} | {state} |")
    lines.extend(["", "## Page evidence", ""])
    for page in geo.pages:
        lines.extend([f"### {_cell(page.url)}", "", f"Page type: {page.page_type}; score: {page.score}; status: {page.status}", "",
                      f"HTTP: {page.status_code}; fetched: {page.fetched_at}; evidence coverage: {page.evidence_coverage:.1%}", "",
                      "| Check | Points | State | Value | Evidence | Recommendation |", "|---|---:|---|---:|---|---|"])
        for dimension in page.dimensions.values():
            for check in dimension.checks:
                recommendation = check.recommendation if check.status in {"fail", "partial", "unknown"} else ""
                lines.append(f"| {check.id} {_cell(check.label)} | {check.max_points} | {check.status} | {_cell(check.value)} | {_cell(json.dumps(check.evidence, ensure_ascii=False))} | {_cell(recommendation)} |")
    lines.extend(["", "## Limits and methodology", "", *[f"- {item}" for item in geo.processing_notes]])
    lines.extend(["", "## Unscored auxiliary information", "", "```json", json.dumps(geo.auxiliary, ensure_ascii=False, indent=2), "```"])
    if payload.get("seo"):
        seo = SeoAuditResult.model_validate(payload["seo"])
        if payload.get("seo_summary"):
            summary = SeoSummaryResult.model_validate(payload["seo_summary"])
        else:
            from app.services.audit.seo import SeoAuditService
            summary = SeoAuditService().summarize(seo)
        from app.models.discovery import DiscoveryResult
        lines.extend(["", "---", "", SeoReportService().render_markdown(
            url=payload["url"], discovery=DiscoveryResult.model_validate(payload["discovery"]), seo=seo, summary=summary)])
    return "\n".join(lines)
