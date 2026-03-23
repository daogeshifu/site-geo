from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "geo-audit-service")
    environment: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _get_int("PORT", 8000)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    request_timeout_seconds: float = _get_float("REQUEST_TIMEOUT_SECONDS", 15.0)
    request_retries: int = _get_int("REQUEST_RETRIES", 3)
    max_sitemap_urls: int = _get_int("MAX_SITEMAP_URLS", 50)
    max_sitemap_indexes: int = _get_int("MAX_SITEMAP_INDEXES", 10)
    cache_ttl_days: int = _get_int("CACHE_TTL_DAYS", 7)
    cache_dir: str = os.getenv("CACHE_DIR", ".cache/audits")
    default_user_agent: str = os.getenv(
        "DEFAULT_USER_AGENT",
        "GEOAuditBot/1.0 (+https://example.com/bot)",
    )
    allow_playwright: bool = os.getenv("ALLOW_PLAYWRIGHT", "false").lower() == "true"
    llm_request_timeout_seconds: float = _get_float("LLM_REQUEST_TIMEOUT_SECONDS", 30.0)
    default_openrouter_model: str = os.getenv("DEFAULT_OPENROUTER_MODEL", "openai/gpt-4.1")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8000")
    openrouter_app_name: str = os.getenv("OPENROUTER_APP_NAME", "geo-audit-service")


settings = Settings()
