from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_demo_page_serves_template_assets() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert '/static/css/demo.css' in response.text
    assert '/static/js/demo/index.js' in response.text
    assert 'href="/docs"' in response.text
    assert 'href="/health"' in response.text


def test_demo_static_assets_are_mounted() -> None:
    css_response = client.get("/static/css/demo.css")
    js_response = client.get("/static/js/demo/index.js")
    assert css_response.status_code == 200
    assert js_response.status_code == 200


def test_demo_token_status_reports_enabled_flag() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "demo-secret")
    try:
        response = client.get("/api/v1/demo/token-status")
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["token_required"] is True
    assert payload["data"]["header_name"] == "X-Demo-Token"


def test_demo_verify_token_requires_matching_header() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "demo-secret")
    try:
        denied = client.post("/api/v1/demo/verify-token")
        allowed = client.post("/api/v1/demo/verify-token", headers={"X-Demo-Token": "demo-secret"})
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert denied.status_code == 401
    assert denied.json()["message"] == "demo token required or invalid"
    assert allowed.status_code == 200
    assert allowed.json()["data"]["verified"] is True


def test_demo_task_routes_reject_missing_token_when_enabled() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "demo-secret")
    try:
        response = client.get("/api/v1/demo/tasks/non-existent-task")
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert response.status_code == 401
    assert response.json()["message"] == "demo token required or invalid"
