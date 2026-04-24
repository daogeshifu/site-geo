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
from app.utils.url_utils import normalize_url, scope_identifier


class CacheService:
    """基于文件系统的审计结果缓存服务

    缓存键（SHA256）格式：domain|mode|provider|model
    缓存文件：{cache_dir}/{sha256_key}.json
    TTL：默认 7 天（可通过 CACHE_TTL_DAYS 配置）

    设计决策：
    - 使用 SHA256 哈希键避免文件名包含特殊字符
    - standard 模式的缓存键中 provider/model 为 "none"，与 premium 模式隔离
    """

    def __init__(self, cache_dir: str | None = None, ttl_days: int | None = None) -> None:
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)   # 自动创建缓存目录
        self.ttl_days = ttl_days or settings.cache_ttl_days

    def build_cache_key(
        self,
        url: str,
        mode: str,
        llm_config: LLMConfig | None = None,
        full_audit: bool = False,
        max_pages: int = 12,
        feedback_lang: str = "en",
        task_type: str = "site_geo_audit",
        target_locale: str | None = None,
    ) -> tuple[str, str, str]:
        """生成缓存键，返回 (sha256_digest, normalized_url, domain)

        - standard 模式：provider=none, model=none（不区分 LLM 配置）
        - premium 模式：包含 provider 和 model（不同模型结果不共享缓存）
        """
        normalized_url = normalize_url(url)
        parsed = urlparse(normalized_url)
        domain = parsed.netloc.lower()
        scope_key = scope_identifier(normalized_url)
        provider = llm_config.provider if llm_config and mode == "premium" else "none"
        model = (
            (llm_config.model if llm_config and llm_config.model else settings.default_openrouter_model)
            if mode == "premium"
            else "none"
        )
        normalized_pages = max_pages if full_audit else 5
        raw_key = (
            f"{task_type}|{scope_key}|{mode}|{provider}|{model}"
            f"|full={int(full_audit)}|pages={normalized_pages}|lang={feedback_lang}|target_locale={target_locale or 'auto'}"
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return digest, normalized_url, domain

    def _cache_path(self, cache_key: str) -> Path:
        """返回缓存文件的完整路径"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> CachedAuditRecord | None:
        """读取缓存记录，过期或解析失败时返回 None"""
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = CachedAuditRecord.model_validate(payload)
        except Exception:
            return None
        # TTL 过期检查
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
        feedback_lang: str,
        full_audit: bool,
        max_pages: int,
        payload: dict[str, Any],
        llm_config: LLMConfig | None = None,
        task_type: str = "site_geo_audit",
        target_locale: str | None = None,
    ) -> CachedAuditRecord:
        """将审计结果写入缓存文件（JSON 格式，缩进 2 格）"""
        now = datetime.now(timezone.utc)
        record = CachedAuditRecord(
            cache_key=cache_key,
            url=url,
            normalized_url=normalized_url,
            domain=domain,
            task_type=task_type,
            mode=mode,
            feedback_lang=feedback_lang,
            full_audit=full_audit,
            max_pages=max_pages,
            # premium 模式记录 LLM 提供商和模型，便于缓存管理和调试
            llm_provider=llm_config.provider if llm_config and mode == "premium" else None,
            llm_model=llm_config.model if llm_config and mode == "premium" else None,
            target_locale=target_locale,
            created_at=now,
            expires_at=now + timedelta(days=self.ttl_days),
            payload=payload,
        )
        self._cache_path(cache_key).write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return record
