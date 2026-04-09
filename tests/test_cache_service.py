from app.services.infra.cache import CacheService


def test_cache_key_changes_with_mode() -> None:
    service = CacheService(cache_dir=".cache/test-audits", ttl_days=7)
    standard_key, _, domain = service.build_cache_key("https://example.com", "standard", None)
    premium_key, _, _ = service.build_cache_key("https://example.com", "premium", None)
    full_audit_key, _, _ = service.build_cache_key("https://example.com", "standard", None, True, 12)
    zh_key, _, _ = service.build_cache_key("https://example.com", "standard", None, False, 12, "zh")
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
    assert standard_key != content_key
