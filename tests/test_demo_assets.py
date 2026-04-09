from fastapi.testclient import TestClient

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
