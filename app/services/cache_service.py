from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.models.requests import LLMConfig
from app.models.task import CachedAuditRecord
from app.utils.url_utils import normalize_url


class CacheService:
    def __init__(self, cache_dir: str | None = None, ttl_days: int | None = None) -> None:
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days or settings.cache_ttl_days

    def build_cache_key(self, url: str, mode: str, llm_config: LLMConfig | None = None) -> tuple[str, str, str]:
        normalized_url = normalize_url(url)
        parsed = urlparse(normalized_url)
        domain = parsed.netloc.lower()
        provider = llm_config.provider if llm_config and mode == "premium" else "none"
        model = (
            (llm_config.model if llm_config and llm_config.model else settings.default_openrouter_model)
            if mode == "premium"
            else "none"
        )
        raw_key = f"{domain}|{mode}|{provider}|{model}"
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return digest, normalized_url, domain

    def _cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> CachedAuditRecord | None:
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
            record = CachedAuditRecord.model_validate(payload)
        except Exception:
            return None
        if record.expires_at <= datetime.now(timezone.utc):
            return None
        return record

    def set(
        self,
        cache_key: str,
        url: str,
        normalized_url: str,
        domain: str,
        mode: str,
        payload: dict[str, Any],
        llm_config: LLMConfig | None = None,
    ) -> CachedAuditRecord:
        now = datetime.now(timezone.utc)
        record = CachedAuditRecord(
            cache_key=cache_key,
            url=url,
            normalized_url=normalized_url,
            domain=domain,
            mode=mode,
            llm_provider=llm_config.provider if llm_config and mode == "premium" else None,
            llm_model=llm_config.model if llm_config and mode == "premium" else None,
            created_at=now,
            expires_at=now + timedelta(days=self.ttl_days),
            payload=payload,
        )
        self._cache_path(cache_key).write_text(record.model_dump_json(indent=2))
        return record
