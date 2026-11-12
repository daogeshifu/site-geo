import pytest

from app.core.config import settings
from app.services.infra.cache import CacheService


def test_cache_key_changes_with_mode() -> None:
    service = CacheService(cache_dir=".cache/test-audits", ttl_days=7)
    standard_key, _, domain = service.build_cache_key("https://example.com", "standard", None)
    premium_key, _, _ = service.build_cache_key("https://example.com", "premium", None)
    full_audit_key, _, _ = service.build_cache_key("https://example.com", "standard", None, True, 12)
    zh_key, _, _ = service.build_cache_key("https://example.com", "standard", None, False, 12, "zh")
    nl_target_key, _, _ = service.build_cache_key("https://example.com", "standard", None, False, 12, "en", "site_geo_audit", "nl")
    content_key, _, _ = service.build_cache_key(
        "https://example.com/blog/post",
        "standard",
        None,
        False,
        12,
        "en",
        "site_content_audit",
    )
    assert domain == "example.com"
    assert standard_key != premium_key
    assert standard_key != full_audit_key
    assert standard_key != zh_key
    assert standard_key != nl_target_key
    assert standard_key != content_key


def test_combined_seo_geo_cache_namespace_differs_from_seo_only() -> None:
    service = CacheService(cache_dir=".cache/test-audits", ttl_days=7)
    combined_key, _, _ = service.build_cache_key(
        "https://example.com", "standard", task_type="site_geo_audit"
    )
    seo_key, _, _ = service.build_cache_key(
        "https://example.com", "standard", task_type="site_seo_audit"
    )
    assert combined_key != seo_key


@pytest.mark.parametrize(("task_type", "previous_key"), [
    ("site_geo_only_audit", "0d1a8e0608d0d79b2fa9711e5677f336b4f4e5fcd274d11d4452139c69ea3fd4"),
    ("site_geo_audit", "243876db2f533bf9c5798d969dae48df7ce323f3097312a7eaa659027f3c8870"),
])
def test_geo_does_not_reuse_reports_from_navigation_extraction_bug(tmp_path, monkeypatch, task_type, previous_key):
    monkeypatch.setitem(settings.__dict__, "allow_playwright", False)
    service = CacheService(cache_dir=str(tmp_path))
    current_key, _, _ = service.build_cache_key("https://example.com", "standard", task_type=task_type)
    assert current_key != previous_key
