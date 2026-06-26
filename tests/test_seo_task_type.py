from app.services.orchestration.tasks import TaskService


def test_task_service_exposes_seo_step_order() -> None:
    service = TaskService()
    assert service._step_order_for("site_seo_audit") == ["discovery", "seo", "summary"]
