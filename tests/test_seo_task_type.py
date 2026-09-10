from app.services.orchestration.tasks import TaskService
from app.services.audit.seo import SeoAuditService


def test_task_service_exposes_seo_step_order() -> None:
    service = TaskService()
    assert service._step_order_for("site_seo_audit") == ["discovery", "seo", "summary"]


def test_combined_geo_task_includes_seo_diagnosis_step() -> None:
    service = TaskService()
    assert service._step_order_for("site_geo_audit") == [
        "discovery", "seo", "visibility", "technical", "content", "schema",
        "platform", "observation", "summary",
    ]


def test_seo_issues_put_critical_p0_blockers_first() -> None:
    service = SeoAuditService()
    base = {
        "status": "fail", "category": "Technical SEO", "scope": "sitewide",
        "failure": "failure", "evidence": "evidence", "impact": "impact",
        "recommendation": "fix", "effort": "1 hour", "difficulty": "low", "owner": "Engineering",
    }
    issues = service._issue_results([
        {**base, "id": "CHK-003", "priority": "P1", "severity": "medium"},
        {**base, "id": "CHK-001", "priority": "P0", "severity": "high"},
        {**base, "id": "CHK-004", "priority": "P0", "severity": "critical"},
    ])
    assert [(item.priority, item.severity) for item in issues] == [
        ("P0", "critical"), ("P0", "high"), ("P1", "medium")
    ]
    assert [item.check_item for item in issues] == ["HTTPS", "Robots", "Analytics"]


def test_seo_issue_check_items_are_localized_and_concise() -> None:
    service = SeoAuditService()
    base = {
        "status": "fail", "category": "On-Page SEO", "scope": "sitewide",
        "failure": "页面标题异常", "evidence": "homepage", "impact": "impact",
        "recommendation": "fix", "effort": "1 hour", "difficulty": "low", "owner": "SEO",
        "id": "CHK-014", "priority": "P1", "severity": "high",
    }
    assert service._issue_results([base], feedback_lang="zh")[0].check_item == "页面标题"
    assert service._issue_results([base], feedback_lang="en")[0].check_item == "Title"
