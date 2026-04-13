from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SiteAssetSummary(BaseModel):
    """站点资产存储概览，用于调试和 demo 展示。"""

    enabled: bool = False
    backend: str = "file"
    site_id: int | None = None
    domain: str | None = None
    scope_root_url: str | None = None
    stored_url_count: int = 0
    stored_snapshot_count: int = 0
    reused_discovery: bool = False
    reused_snapshot_count: int = 0
    fetched_snapshot_count: int = 0
    inventory_satisfied: bool = False
    url_type_counts: dict[str, int] = Field(default_factory=dict)
    discovery_source_counts: dict[str, int] = Field(default_factory=dict)
    last_discovered_at: datetime | None = None
    last_snapshot_at: datetime | None = None
    knowledge_graph: "KnowledgeGraphSummary" = Field(default_factory=lambda: KnowledgeGraphSummary())
    note: str | None = None


class KnowledgeGraphSummary(BaseModel):
    """站点知识图谱构建概览。"""

    enabled: bool = False
    built: bool = False
    site_id: int | None = None
    entity_count: int = 0
    edge_count: int = 0
    evidence_count: int = 0
    source_snapshot_count: int = 0
    last_built_at: datetime | None = None
    note: str | None = None


class SiteRecord(BaseModel):
    site_id: int
    domain: str
    site_root_url: str
    scope_root_url: str
    scope_key: str
    business_type: str | None = None
    total_url_count: int = 0
    snapshot_url_count: int = 0
    last_discovered_at: datetime | None = None
    last_snapshot_at: datetime | None = None


class SiteUrlRecord(BaseModel):
    url_id: int
    site_id: int
    normalized_url: str
    final_url: str | None = None
    url_type: str = "unknown"
    discovery_source: str = "unknown"
    priority: int = 0
    fetch_status: str = "pending"
    last_discovered_at: datetime | None = None
    last_fetched_at: datetime | None = None


class PageSnapshotRecord(BaseModel):
    snapshot_id: int
    site_id: int
    url_id: int
    normalized_url: str
    final_url: str
    url_type: str = "unknown"
    fetch_status: str = "success"
    status_code: int | None = None
    page_profile_json: str
    parsed_json: str | None = None
    raw_html: str | None = None
    text_content: str | None = None
    content_hash: str | None = None
    fetched_at: datetime | None = None
