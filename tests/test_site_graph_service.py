import asyncio
import json

from app.models.discovery import (
    DiscoveryResult,
    FetchMetadata,
    HomepageExtract,
    KeyPages,
    LlmsResult,
    RobotsResult,
    SitemapResult,
    SiteSignals,
)
from app.services.infra.site_graph import SiteKnowledgeGraphService


def _discovery() -> DiscoveryResult:
    return DiscoveryResult(
        url="https://example.com/",
        normalized_url="https://example.com/",
        final_url="https://example.com/",
        site_root_url="https://example.com",
        scope_root_url="https://example.com/",
        domain="example.com",
        fetch=FetchMetadata(final_url="https://example.com/", status_code=200, headers={}, response_time_ms=100),
        homepage=HomepageExtract(title="Example"),
        robots=RobotsResult(url="https://example.com/robots.txt", exists=True),
        sitemap=SitemapResult(url="https://example.com/sitemap.xml", exists=True),
        llms=LlmsResult(url="https://example.com/llms.txt", exists=False),
        business_type="saas",
        key_pages=KeyPages(about="https://example.com/about/", service="https://example.com/products/widget/"),
        site_signals=SiteSignals(
            company_name_detected=True,
            same_as_detected=True,
            detected_company_name="Example Inc",
        ),
    )


def test_project_graph_builds_entities_edges_and_evidence() -> None:
    service = SiteKnowledgeGraphService()
    discovery = _discovery()
    snapshot_rows = [
        {
            "snapshot_id": 1,
            "site_id": 1,
            "url_id": 11,
            "normalized_url": "https://example.com/",
            "final_url": "https://example.com/",
            "url_type": "homepage",
            "page_profile_json": json.dumps(
                {
                    "title": "Example Inc",
                    "lang": "en",
                    "word_count": 400,
                    "json_ld_summary": {
                        "types": ["Organization"],
                        "same_as": ["https://www.linkedin.com/company/example-inc/"],
                    },
                }
            ),
            "parsed_json": json.dumps(
                {
                    "title": "Example Inc",
                    "internal_links": [{"url": "https://example.com/products/widget/", "text": "Widget"}],
                    "external_links": [],
                }
            ),
            "fetched_at": None,
        },
        {
            "snapshot_id": 2,
            "site_id": 1,
            "url_id": 12,
            "normalized_url": "https://example.com/products/widget/",
            "final_url": "https://example.com/products/widget/",
            "url_type": "product",
            "page_profile_json": json.dumps(
                {
                    "title": "Widget 3000",
                    "lang": "en",
                    "word_count": 900,
                    "has_reference_section": True,
                    "json_ld_summary": {"types": ["Product"], "same_as": []},
                }
            ),
            "parsed_json": json.dumps(
                {
                    "title": "Widget 3000",
                    "internal_links": [{"url": "https://example.com/", "text": "Home"}],
                    "external_links": [{"url": "https://docs.vendor.com/spec", "text": "spec sheet"}],
                }
            ),
            "fetched_at": None,
        },
    ]

    entities, edges, evidences = service._project_graph(discovery, snapshot_rows)

    entity_types = {item.entity_type for item in entities}
    relation_types = {item.relation_type for item in edges}

    assert "site" in entity_types
    assert "organization" in entity_types
    assert "page" in entity_types
    assert "product" in entity_types
    assert "external_profile" in entity_types
    assert "external_source" in entity_types
    assert "has_page" in relation_types
    assert "represents" in relation_types
    assert "same_as" in relation_types
    assert "links_to" in relation_types
    assert "offers" in relation_types
    assert "cites" in relation_types
    assert any(item.evidence_type == "json_ld" for item in evidences)
    assert any(item.evidence_type == "anchor" for item in evidences)


def test_build_snapshot_graph_json_is_self_contained() -> None:
    service = SiteKnowledgeGraphService()
    discovery = _discovery()
    snapshot_rows = [
        {
            "snapshot_id": 1,
            "site_id": 1,
            "url_id": 11,
            "normalized_url": "https://example.com/",
            "final_url": "https://example.com/",
            "url_type": "homepage",
            "page_profile_json": json.dumps(
                {
                    "title": "Example Inc",
                    "lang": "en",
                    "word_count": 400,
                    "json_ld_summary": {
                        "types": ["Organization"],
                        "same_as": ["https://www.linkedin.com/company/example-inc/"],
                    },
                }
            ),
            "parsed_json": json.dumps(
                {
                    "title": "Example Inc",
                    "internal_links": [{"url": "https://example.com/products/widget/", "text": "Widget"}],
                    "external_links": [],
                }
            ),
            "fetched_at": None,
        },
        {
            "snapshot_id": 2,
            "site_id": 1,
            "url_id": 12,
            "normalized_url": "https://example.com/products/widget/",
            "final_url": "https://example.com/products/widget/",
            "url_type": "product",
            "page_profile_json": json.dumps(
                {
                    "title": "Widget 3000",
                    "lang": "en",
                    "word_count": 900,
                    "has_reference_section": True,
                    "json_ld_summary": {"types": ["Product"], "same_as": []},
                }
            ),
            "parsed_json": json.dumps(
                {
                    "title": "Widget 3000",
                    "internal_links": [{"url": "https://example.com/", "text": "Home"}],
                    "external_links": [{"url": "https://docs.vendor.com/spec", "text": "spec sheet"}],
                }
            ),
            "fetched_at": None,
        },
    ]
    entities, edges, evidences = service._project_graph(discovery, snapshot_rows)

    payload = service._build_snapshot_graph_json(
        site_id=1,
        discovery=discovery,
        snapshot_rows=snapshot_rows,
        entities=entities,
        edges=edges,
        evidences=evidences,
    )

    assert payload["summary"]["entity_count"] == len(payload["entities"])
    assert payload["summary"]["edge_count"] == len(payload["edges"])
    assert payload["summary"]["evidence_count"] == len(payload["evidence"])
    assert payload["summary"]["source_snapshot_count"] == 2
    assert payload["source_pages"]
    assert any(item["entity_type"] == "product" for item in payload["entities"])
    assert any(item["relation_type"] == "same_as" for item in payload["edges"])
    assert any(item["evidence_type"] == "json_ld" for item in payload["evidence"])


def test_load_task_graph_returns_snapshot_payload() -> None:
    service = SiteKnowledgeGraphService()
    service.enabled = True
    graph_json = {
        "graph_version": "site-graph-v1",
        "site_id": 9,
        "site": {"domain": "example.com", "scope_root_url": "https://example.com/", "site_root_url": "https://example.com", "business_type": "saas"},
        "summary": {
            "entity_count": 2,
            "edge_count": 1,
            "evidence_count": 1,
            "source_snapshot_count": 1,
            "entity_type_counts": {"site": 1, "page": 1},
            "relation_type_counts": {"has_page": 1},
        },
        "entities": [
            {"entity_key": "site-key", "entity_type": "site", "canonical_name": "example.com", "canonical_url": "https://example.com/", "source_snapshot_id": None, "confidence": 100, "attributes": {}},
            {"entity_key": "page-key", "entity_type": "page", "canonical_name": "Home", "canonical_url": "https://example.com/", "source_snapshot_id": 1, "confidence": 100, "attributes": {"page_type": "homepage", "word_count": 123}},
        ],
        "edges": [
            {"edge_key": "edge-key", "from_entity_key": "site-key", "to_entity_key": "page-key", "from_entity_name": "example.com", "to_entity_name": "Home", "relation_type": "has_page", "confidence": 100, "evidence_count": 1, "attributes": {}, "first_seen_at": None, "last_seen_at": None},
        ],
        "evidence": [
            {"entity_key": "page-key", "edge_key": "edge-key", "snapshot_id": 1, "url_id": 11, "evidence_type": "inventory", "evidence_field": "url_type", "selector_or_path": "geo_page_snapshots", "evidence_text": "homepage", "confidence": 100},
        ],
        "source_pages": [
            {"entity_key": "page-key", "canonical_name": "Home", "canonical_url": "https://example.com/", "page_type": "homepage", "word_count": 123, "source_snapshot_id": 1, "confidence": 100},
        ],
    }

    class _FakeClient:
        async def fetchone(self, sql, params):
            if "FROM geo_audit_tasks" in sql:
                return {
                    "task_id": "task-1",
                    "site_id": 9,
                    "domain": "example.com",
                    "status": "completed",
                    "url": "https://example.com/",
                    "normalized_url": "https://example.com/",
                    "full_audit": 1,
                    "requested_max_pages": 12,
                    "created_at": None,
                    "updated_at": None,
                    "completed_at": None,
                }
            if "FROM geo_site_graph_snapshots" in sql:
                return {
                    "graph_snapshot_id": 3,
                    "site_id": 9,
                    "task_id": "task-1",
                    "graph_version": "site-graph-v1",
                    "source_snapshot_count": 1,
                    "entity_count": 2,
                    "edge_count": 1,
                    "evidence_count": 1,
                    "graph_json": json.dumps(graph_json),
                    "note": "Projected from page snapshots and discovery signals.",
                    "built_at": None,
                }
            return None

        async def fetchall(self, sql, params):
            return []

    service.client = _FakeClient()

    payload = asyncio.run(service.load_task_graph("task-1"))

    assert payload is not None
    assert payload["built"] is True
    assert payload["snapshot_task_id"] == "task-1"
    assert payload["exact_task_match"] is True
    assert payload["site_id"] == 9
    assert payload["summary"]["entity_count"] == 2
    assert len(payload["entities"]) == 2
    assert len(payload["edges"]) == 1
    assert len(payload["evidence"]) == 1


def test_load_task_graph_falls_back_to_latest_site_snapshot() -> None:
    service = SiteKnowledgeGraphService()
    service.enabled = True
    graph_json = {
        "graph_version": "site-graph-v1",
        "site_id": 9,
        "site": {"domain": "example.com", "scope_root_url": "https://example.com/", "site_root_url": "https://example.com", "business_type": "saas"},
        "summary": {
            "entity_count": 1,
            "edge_count": 0,
            "evidence_count": 0,
            "source_snapshot_count": 1,
            "entity_type_counts": {"site": 1},
            "relation_type_counts": {},
        },
        "entities": [
            {"entity_key": "site-key", "entity_type": "site", "canonical_name": "example.com", "canonical_url": "https://example.com/", "source_snapshot_id": None, "confidence": 100, "attributes": {}},
        ],
        "edges": [],
        "evidence": [],
        "source_pages": [],
    }

    class _FakeClient:
        async def fetchone(self, sql, params):
            if "FROM geo_audit_tasks" in sql:
                return {
                    "task_id": "task-new",
                    "site_id": 9,
                    "domain": "example.com",
                    "status": "completed",
                    "url": "https://example.com/",
                    "normalized_url": "https://example.com/",
                    "full_audit": 1,
                    "requested_max_pages": 12,
                    "created_at": None,
                    "updated_at": None,
                    "completed_at": None,
                }
            if "FROM geo_site_graph_snapshots" in sql and "WHERE task_id=%s" in sql:
                return None
            if "FROM geo_site_graph_snapshots" in sql and "WHERE site_id=%s" in sql:
                return {
                    "graph_snapshot_id": 7,
                    "site_id": 9,
                    "task_id": "task-old",
                    "graph_version": "site-graph-v1",
                    "source_snapshot_count": 1,
                    "entity_count": 1,
                    "edge_count": 0,
                    "evidence_count": 0,
                    "graph_json": json.dumps(graph_json),
                    "note": None,
                    "built_at": None,
                }
            return None

        async def fetchall(self, sql, params):
            return []

    service.client = _FakeClient()

    payload = asyncio.run(service.load_task_graph("task-new"))

    assert payload is not None
    assert payload["task_id"] == "task-new"
    assert payload["snapshot_task_id"] == "task-old"
    assert payload["exact_task_match"] is False
    assert payload["built"] is True
    assert payload["site_id"] == 9
    assert "latest site-level knowledge graph snapshot" in payload["note"]


def test_ensure_task_snapshot_reuses_latest_site_snapshot() -> None:
    service = SiteKnowledgeGraphService()
    service.enabled = True
    executed: list[tuple[str, tuple]] = []

    class _FakeClient:
        async def fetchone(self, sql, params):
            if "FROM geo_site_graph_snapshots" in sql and "WHERE task_id=%s" in sql:
                return None
            if "FROM geo_site_graph_snapshots" in sql and "WHERE site_id=%s" in sql:
                return {
                    "graph_snapshot_id": 7,
                    "site_id": 9,
                    "task_id": "task-old",
                    "graph_version": "site-graph-v1",
                    "source_snapshot_count": 1,
                    "entity_count": 3,
                    "edge_count": 2,
                    "evidence_count": 4,
                    "graph_json": json.dumps({"summary": {"entity_count": 3}}),
                    "note": "Projected from page snapshots and discovery signals.",
                    "built_at": None,
                }
            return None

        async def execute(self, sql, params):
            executed.append((sql, params))
            return 1

    service.client = _FakeClient()

    summary = asyncio.run(service.ensure_task_snapshot(task_id="task-new", site_id=9))

    assert summary.built is True
    assert summary.site_id == 9
    assert summary.entity_count == 3
    assert executed
    assert executed[0][1][1] == "task-new"
    assert "task-old" in executed[0][1][8]
