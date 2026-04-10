from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.models.discovery import DiscoveryResult, PageProfile
from app.models.storage import PageSnapshotRecord, SiteAssetSummary, SiteRecord, SiteUrlRecord
from app.models.task import AuditTask
from app.services.infra.mysql import MySQLClient
from app.utils.url_classifier import classify_url_type
from app.utils.url_utils import get_scope_root, get_site_root, normalize_url, registered_domain

logger = logging.getLogger(__name__)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _json_loads(payload: Any, default: Any) -> Any:
    if payload is None or payload == "":
        return default
    if isinstance(payload, (dict, list)):
        return payload
    try:
        return json.loads(payload)
    except Exception:
        return default


class SiteAssetStore:
    """按域名持久化站点 URL、页面快照和任务记录。"""

    def __init__(self) -> None:
        self.client = MySQLClient()
        self.enabled = self.client.enabled
        self.backend = "mysql" if self.enabled else "file"
        self._degraded = False

    def _mark_degraded(self, exc: Exception, operation: str) -> None:
        logger.warning("MySQL asset storage degraded", extra={"operation": operation, "error": str(exc)})
        self._degraded = True

    def _recover_if_needed(self) -> None:
        if self.enabled and self._degraded:
            logger.info("MySQL asset storage recovered")
            self._degraded = False

    @property
    def available(self) -> bool:
        return self.enabled and not self._degraded

    async def ensure_site(self, url: str) -> SiteRecord | None:
        if not self.enabled:
            return None
        normalized_url = normalize_url(url)
        domain = registered_domain(normalized_url) or urlparse(normalized_url).netloc.lower()
        site_root_url = get_site_root(normalized_url)
        scope_root_url = get_scope_root(normalized_url)
        scope_key = _hash_value(f"{domain}|{scope_root_url}")
        try:
            row = await self.client.fetchone(
                """
                SELECT site_id, domain, site_root_url, scope_root_url, scope_key, business_type,
                       total_url_count, snapshot_url_count, last_discovered_at, last_snapshot_at
                FROM geo_sites
                WHERE domain=%s AND scope_key=%s
                """,
                (domain, scope_key),
            )
            if row:
                self._recover_if_needed()
                return SiteRecord.model_validate(row)

            await self.client.execute(
                """
                INSERT INTO geo_sites (domain, site_root_url, scope_root_url, scope_key)
                VALUES (%s, %s, %s, %s)
                """,
                (domain, site_root_url, scope_root_url, scope_key),
            )
            created = await self.client.fetchone(
                """
                SELECT site_id, domain, site_root_url, scope_root_url, scope_key, business_type,
                       total_url_count, snapshot_url_count, last_discovered_at, last_snapshot_at
                FROM geo_sites
                WHERE domain=%s AND scope_key=%s
                """,
                (domain, scope_key),
            )
            self._recover_if_needed()
            return SiteRecord.model_validate(created) if created else None
        except Exception as exc:
            self._mark_degraded(exc, "ensure_site")
            return None

    async def clear_site_content(self, site_id: int) -> None:
        if not self.enabled:
            return
        try:
            await self.client.execute("DELETE FROM geo_page_snapshots WHERE site_id=%s", (site_id,))
            await self.client.execute(
                """
                UPDATE geo_sites
                SET discovery_json=NULL,
                    snapshot_url_count=0,
                    last_snapshot_at=NULL,
                    updated_at=CURRENT_TIMESTAMP(6)
                WHERE site_id=%s
                """,
                (site_id,),
            )
            await self.client.execute(
                """
                UPDATE geo_urls
                SET fetch_status='stale',
                    last_fetched_at=NULL,
                    updated_at=CURRENT_TIMESTAMP(6)
                WHERE site_id=%s
                """,
                (site_id,),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "clear_site_content")

    async def load_cached_discovery(self, site_id: int, *, full_audit: bool, max_pages: int) -> DiscoveryResult | None:
        if not self.enabled:
            return None
        try:
            row = await self.client.fetchone(
                """
                SELECT site_id, domain, scope_root_url, total_url_count, snapshot_url_count,
                       discovery_json, last_discovered_at, last_snapshot_at
                FROM geo_sites
                WHERE site_id=%s
                """,
                (site_id,),
            )
        except Exception as exc:
            self._mark_degraded(exc, "load_cached_discovery")
            return None
        if not row or not row.get("discovery_json"):
            return None
        payload = _json_loads(row["discovery_json"], None)
        if not payload:
            return None
        result = DiscoveryResult.model_validate(payload)
        if full_audit and result.profiled_page_count < max_pages:
            return None
        summary = await self.build_asset_summary(
            site_id,
            reused_discovery=True,
            reused_snapshot_count=result.profiled_page_count,
            fetched_snapshot_count=0,
            inventory_satisfied=row.get("total_url_count", 0) >= max_pages,
            note="Loaded discovery and page profiles from MySQL asset storage.",
        )
        result.asset_summary = summary
        self._recover_if_needed()
        return result

    async def load_site_urls(self, site_id: int) -> list[SiteUrlRecord]:
        if not self.enabled:
            return []
        try:
            rows = await self.client.fetchall(
                """
                SELECT url_id, site_id, normalized_url, final_url, url_type, discovery_source,
                       priority, fetch_status, last_discovered_at, last_fetched_at
                FROM geo_urls
                WHERE site_id=%s AND is_active=1
                ORDER BY priority ASC, url_id ASC
                """,
                (site_id,),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "load_site_urls")
            return []
        return [SiteUrlRecord.model_validate(row) for row in rows]

    async def load_snapshot_map(self, site_id: int) -> dict[str, PageProfile]:
        if not self.enabled:
            return {}
        try:
            rows = await self.client.fetchall(
                """
                SELECT snapshot_id, site_id, url_id, normalized_url, final_url, url_type, fetch_status,
                       status_code, page_profile_json, content_hash, fetched_at
                FROM geo_page_snapshots
                WHERE site_id=%s
                """,
                (site_id,),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "load_snapshot_map")
            return {}
        snapshots: dict[str, PageProfile] = {}
        for row in rows:
            record = PageSnapshotRecord.model_validate(row)
            try:
                profile = PageProfile.model_validate(_json_loads(record.page_profile_json, {}))
            except Exception:
                continue
            snapshots[record.normalized_url] = profile
            snapshots[record.final_url] = profile
        return snapshots

    async def upsert_urls(self, site_id: int, items: list[dict[str, Any]]) -> None:
        if not self.enabled or not items:
            return
        now = datetime.now(timezone.utc)
        rows = []
        for item in items:
            normalized_url = normalize_url(item["normalized_url"])
            final_url = item.get("final_url")
            final_url = normalize_url(final_url) if final_url else None
            rows.append(
                (
                    site_id,
                    normalized_url,
                    _hash_value(normalized_url),
                    final_url,
                    item.get("url_type") or classify_url_type(normalized_url),
                    item.get("discovery_source") or "unknown",
                    int(item.get("priority", 100)),
                    item.get("fetch_status") or ("success" if item.get("last_fetched_at") else "pending"),
                    item.get("last_discovered_at") or now,
                    item.get("last_fetched_at"),
                )
            )
        try:
            await self.client.executemany(
                """
                INSERT INTO geo_urls (
                  site_id, normalized_url, url_hash, final_url, url_type, discovery_source,
                  priority, fetch_status, last_discovered_at, last_fetched_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  final_url=COALESCE(VALUES(final_url), final_url),
                  url_type=CASE
                    WHEN geo_urls.url_type IN ('unknown', 'page') THEN VALUES(url_type)
                    ELSE geo_urls.url_type
                  END,
                  discovery_source=VALUES(discovery_source),
                  priority=LEAST(priority, VALUES(priority)),
                  fetch_status=CASE
                    WHEN VALUES(last_fetched_at) IS NOT NULL THEN VALUES(fetch_status)
                    ELSE geo_urls.fetch_status
                  END,
                  is_active=1,
                  last_discovered_at=COALESCE(VALUES(last_discovered_at), geo_urls.last_discovered_at),
                  last_fetched_at=COALESCE(VALUES(last_fetched_at), geo_urls.last_fetched_at),
                  updated_at=CURRENT_TIMESTAMP(6)
                """,
                rows,
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "upsert_urls")

    async def save_page_snapshot(
        self,
        *,
        site_id: int,
        page_url: str,
        final_url: str,
        url_type: str,
        discovery_source: str,
        status_code: int,
        parsed: dict[str, Any],
        page_profile: PageProfile,
        raw_html: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        normalized_url = normalize_url(page_url)
        normalized_final_url = normalize_url(final_url)
        now = datetime.now(timezone.utc)
        await self.upsert_urls(
            site_id,
            [
                {
                    "normalized_url": normalized_url,
                    "final_url": normalized_final_url,
                    "url_type": url_type or classify_url_type(normalized_final_url),
                    "discovery_source": discovery_source,
                    "priority": 10,
                    "fetch_status": "success" if status_code < 400 else "error",
                    "last_discovered_at": now,
                    "last_fetched_at": now,
                }
            ],
        )
        try:
            url_row = await self.client.fetchone(
                "SELECT url_id FROM geo_urls WHERE site_id=%s AND url_hash=%s",
                (site_id, _hash_value(normalized_url)),
            )
        except Exception as exc:
            self._mark_degraded(exc, "save_page_snapshot.fetch_url_id")
            return
        if not url_row:
            return

        parsed_payload = dict(parsed)
        text_content = parsed_payload.pop("text_content", None)
        if not settings.mysql_store_parsed_content:
            text_content = None
        stored_raw_html = raw_html if settings.mysql_store_raw_html else None
        content_hash_source = text_content or stored_raw_html or page_profile.text_excerpt or normalized_final_url
        content_hash = _hash_value(content_hash_source)
        try:
            await self.client.execute(
                """
                INSERT INTO geo_page_snapshots (
                  site_id, url_id, normalized_url, final_url, url_type, fetch_status, status_code,
                  title, meta_description, canonical, lang, word_count, html_length, text_excerpt,
                  content_hash, page_profile_json, parsed_json, text_content, raw_html, fetched_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  final_url=VALUES(final_url),
                  url_type=VALUES(url_type),
                  fetch_status=VALUES(fetch_status),
                  status_code=VALUES(status_code),
                  title=VALUES(title),
                  meta_description=VALUES(meta_description),
                  canonical=VALUES(canonical),
                  lang=VALUES(lang),
                  word_count=VALUES(word_count),
                  html_length=VALUES(html_length),
                  text_excerpt=VALUES(text_excerpt),
                  content_hash=VALUES(content_hash),
                  page_profile_json=VALUES(page_profile_json),
                  parsed_json=VALUES(parsed_json),
                  text_content=VALUES(text_content),
                  raw_html=VALUES(raw_html),
                  fetched_at=VALUES(fetched_at),
                  updated_at=CURRENT_TIMESTAMP(6)
                """,
                (
                    site_id,
                    int(url_row["url_id"]),
                    normalized_url,
                    normalized_final_url,
                    url_type or classify_url_type(normalized_final_url),
                    "success" if status_code < 400 else "error",
                    status_code,
                    page_profile.title,
                    page_profile.meta_description,
                    page_profile.canonical,
                    page_profile.lang,
                    int(page_profile.word_count or 0),
                    int(parsed.get("html_length", 0) or 0),
                    page_profile.text_excerpt,
                    content_hash,
                    _json_dumps(page_profile.model_dump(mode="json")),
                    _json_dumps(parsed_payload),
                    text_content,
                    stored_raw_html,
                    now,
                ),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "save_page_snapshot")

    async def save_discovery(
        self,
        *,
        site_id: int,
        discovery: DiscoveryResult,
        url_items: list[dict[str, Any]],
        reused_snapshot_count: int,
        fetched_snapshot_count: int,
    ) -> SiteAssetSummary:
        if not self.enabled:
            return SiteAssetSummary()
        await self.upsert_urls(site_id, url_items)
        try:
            counts_row = await self.client.fetchone(
                """
                SELECT
                  (SELECT COUNT(*) FROM geo_urls WHERE site_id=%s AND is_active=1) AS total_url_count,
                  (SELECT COUNT(*) FROM geo_page_snapshots WHERE site_id=%s) AS snapshot_url_count
                """,
                (site_id, site_id),
            )
        except Exception as exc:
            self._mark_degraded(exc, "save_discovery.counts")
            return SiteAssetSummary(backend="file", note="MySQL unavailable; using live discovery only.")
        total_url_count = int((counts_row or {}).get("total_url_count") or 0)
        snapshot_url_count = int((counts_row or {}).get("snapshot_url_count") or 0)
        now = datetime.now(timezone.utc)
        try:
            await self.client.execute(
                """
                UPDATE geo_sites
                SET site_root_url=%s,
                    scope_root_url=%s,
                    business_type=%s,
                    total_url_count=%s,
                    snapshot_url_count=%s,
                    discovery_json=%s,
                    key_pages_json=%s,
                    last_discovered_at=%s,
                    last_snapshot_at=%s,
                    updated_at=CURRENT_TIMESTAMP(6)
                WHERE site_id=%s
                """,
                (
                    discovery.site_root_url,
                    discovery.scope_root_url,
                    discovery.business_type,
                    total_url_count,
                    snapshot_url_count,
                    _json_dumps(discovery.model_dump(mode="json")),
                    _json_dumps(discovery.key_pages.model_dump(mode="json")),
                    now,
                    now if snapshot_url_count else None,
                    site_id,
                ),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "save_discovery.update_site")
            return SiteAssetSummary(backend="file", note="MySQL unavailable; discovery result not persisted.")
        return await self.build_asset_summary(
            site_id,
            reused_discovery=False,
            reused_snapshot_count=reused_snapshot_count,
            fetched_snapshot_count=fetched_snapshot_count,
            inventory_satisfied=total_url_count >= discovery.requested_max_pages,
            note="Stored site URLs and page snapshots in MySQL.",
        )

    async def build_asset_summary(
        self,
        site_id: int,
        *,
        reused_discovery: bool,
        reused_snapshot_count: int,
        fetched_snapshot_count: int,
        inventory_satisfied: bool,
        note: str | None = None,
    ) -> SiteAssetSummary:
        if not self.enabled:
            return SiteAssetSummary()
        try:
            site_row = await self.client.fetchone(
                """
                SELECT site_id, domain, scope_root_url, total_url_count, snapshot_url_count,
                       last_discovered_at, last_snapshot_at
                FROM geo_sites
                WHERE site_id=%s
                """,
                (site_id,),
            )
            url_type_rows = await self.client.fetchall(
                "SELECT url_type, COUNT(*) AS total FROM geo_urls WHERE site_id=%s AND is_active=1 GROUP BY url_type",
                (site_id,),
            )
            source_rows = await self.client.fetchall(
                "SELECT discovery_source, COUNT(*) AS total FROM geo_urls WHERE site_id=%s AND is_active=1 GROUP BY discovery_source",
                (site_id,),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "build_asset_summary")
            return SiteAssetSummary(backend="file", note="MySQL unavailable; asset summary skipped.")
        return SiteAssetSummary(
            enabled=True,
            backend=self.backend,
            site_id=site_id,
            domain=(site_row or {}).get("domain"),
            scope_root_url=(site_row or {}).get("scope_root_url"),
            stored_url_count=int((site_row or {}).get("total_url_count") or 0),
            stored_snapshot_count=int((site_row or {}).get("snapshot_url_count") or 0),
            reused_discovery=reused_discovery,
            reused_snapshot_count=reused_snapshot_count,
            fetched_snapshot_count=fetched_snapshot_count,
            inventory_satisfied=inventory_satisfied,
            url_type_counts={row["url_type"]: int(row["total"]) for row in url_type_rows},
            discovery_source_counts={row["discovery_source"]: int(row["total"]) for row in source_rows},
            last_discovered_at=(site_row or {}).get("last_discovered_at"),
            last_snapshot_at=(site_row or {}).get("last_snapshot_at"),
            note=note,
        )

    async def save_task(self, task: AuditTask) -> None:
        if not self.enabled:
            return
        site_id = None
        if task.site_asset_summary:
            if hasattr(task.site_asset_summary, "site_id"):
                site_id = getattr(task.site_asset_summary, "site_id")
            elif isinstance(task.site_asset_summary, dict):
                site_id = task.site_asset_summary.get("site_id")
            site_id = int(site_id) if site_id is not None else None
        result_json = _json_dumps(task.result) if task.result is not None else None
        try:
            await self.client.execute(
                """
                INSERT INTO geo_audit_tasks (
                  task_id, site_id, domain, task_type, mode, status, cache_key, url, normalized_url,
                  feedback_lang, force_refresh, cached, full_audit, requested_max_pages,
                  result_json, error_text, created_at, updated_at, completed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  site_id=VALUES(site_id),
                  domain=VALUES(domain),
                  task_type=VALUES(task_type),
                  mode=VALUES(mode),
                  status=VALUES(status),
                  cache_key=VALUES(cache_key),
                  feedback_lang=VALUES(feedback_lang),
                  force_refresh=VALUES(force_refresh),
                  cached=VALUES(cached),
                  full_audit=VALUES(full_audit),
                  requested_max_pages=VALUES(requested_max_pages),
                  result_json=VALUES(result_json),
                  error_text=VALUES(error_text),
                  updated_at=VALUES(updated_at),
                  completed_at=VALUES(completed_at)
                """,
                (
                    task.task_id,
                    site_id,
                    task.domain,
                    task.task_type,
                    task.mode,
                    task.status,
                    task.cache_key,
                    task.url,
                    task.normalized_url,
                    task.feedback_lang,
                    1 if task.force_refresh else 0,
                    1 if task.cached else 0,
                    1 if task.full_audit else 0,
                    task.max_pages,
                    result_json,
                    task.error,
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                ),
            )
            self._recover_if_needed()
        except Exception as exc:
            self._mark_degraded(exc, "save_task")
