from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.models.discovery import DiscoveryResult
from app.models.storage import KnowledgeGraphSummary
from app.services.infra.mysql import MySQLClient
from app.utils.url_utils import normalize_url, registered_domain

logger = logging.getLogger(__name__)


def _hash_key(*parts: str) -> str:
    raw = "|".join(part.strip().lower() for part in parts if part and part.strip())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def _json_loads(payload: Any) -> dict[str, Any]:
    if not payload:
        return {}
    if isinstance(payload, dict):
        return payload
    try:
        data = json.loads(payload)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    candidate = str(url).strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    try:
        return normalize_url(candidate)
    except Exception:
        return None


def _display_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    try:
        domain = registered_domain(url)
    except Exception:
        domain = ""
    return domain or parsed.netloc.lower() or url


@dataclass
class _ProjectedEntity:
    entity_key: str
    entity_type: str
    canonical_name: str | None
    canonical_url: str | None
    source_snapshot_id: int | None
    confidence: float
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class _ProjectedEdge:
    edge_key: str
    from_entity_key: str
    to_entity_key: str
    relation_type: str
    confidence: float
    attributes: dict[str, Any] = field(default_factory=dict)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    evidence_count: int = 0


@dataclass
class _ProjectedEvidence:
    entity_key: str | None
    edge_key: str | None
    snapshot_id: int | None
    url_id: int | None
    evidence_type: str
    evidence_field: str | None
    selector_or_path: str | None
    evidence_text: str | None
    confidence: float


class SiteKnowledgeGraphService:
    """基于站点快照构建站点级知识图谱投影。"""

    GRAPH_VERSION = "site-graph-v1"

    def __init__(self) -> None:
        self.client = MySQLClient()
        self.enabled = self.client.enabled

    def _summary_from_snapshot_row(self, snapshot_row: dict[str, Any] | None, *, site_id: int | None = None, note: str | None = None) -> KnowledgeGraphSummary:
        row = snapshot_row or {}
        return KnowledgeGraphSummary(
            enabled=self.enabled,
            built=snapshot_row is not None,
            site_id=int(row.get("site_id") or site_id or 0) or None,
            entity_count=int(row.get("entity_count") or 0),
            edge_count=int(row.get("edge_count") or 0),
            evidence_count=int(row.get("evidence_count") or 0),
            source_snapshot_count=int(row.get("source_snapshot_count") or 0),
            last_built_at=row.get("built_at"),
            note=note or row.get("note"),
        )

    def _serialize_entity(self, item: _ProjectedEntity) -> dict[str, Any]:
        return {
            "entity_key": item.entity_key,
            "entity_type": item.entity_type,
            "canonical_name": item.canonical_name,
            "canonical_url": item.canonical_url,
            "source_snapshot_id": item.source_snapshot_id,
            "confidence": round(item.confidence, 2),
            "attributes": item.attributes,
        }

    def _serialize_edge(
        self,
        item: _ProjectedEdge,
        entity_lookup: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "edge_key": item.edge_key,
            "from_entity_key": item.from_entity_key,
            "to_entity_key": item.to_entity_key,
            "from_entity_name": (entity_lookup.get(item.from_entity_key) or {}).get("canonical_name"),
            "to_entity_name": (entity_lookup.get(item.to_entity_key) or {}).get("canonical_name"),
            "relation_type": item.relation_type,
            "confidence": round(item.confidence, 2),
            "evidence_count": item.evidence_count,
            "attributes": item.attributes,
            "first_seen_at": item.first_seen_at.isoformat() if isinstance(item.first_seen_at, datetime) else item.first_seen_at,
            "last_seen_at": item.last_seen_at.isoformat() if isinstance(item.last_seen_at, datetime) else item.last_seen_at,
        }

    def _serialize_evidence(self, item: _ProjectedEvidence) -> dict[str, Any]:
        return {
            "entity_key": item.entity_key,
            "edge_key": item.edge_key,
            "snapshot_id": item.snapshot_id,
            "url_id": item.url_id,
            "evidence_type": item.evidence_type,
            "evidence_field": item.evidence_field,
            "selector_or_path": item.selector_or_path,
            "evidence_text": item.evidence_text,
            "confidence": round(item.confidence, 2),
        }

    def _build_snapshot_graph_json(
        self,
        *,
        site_id: int,
        discovery: DiscoveryResult,
        snapshot_rows: list[dict[str, Any]],
        entities: list[_ProjectedEntity],
        edges: list[_ProjectedEdge],
        evidences: list[_ProjectedEvidence],
    ) -> dict[str, Any]:
        entity_payloads = [self._serialize_entity(item) for item in entities]
        entity_lookup = {item["entity_key"]: item for item in entity_payloads}
        edge_payloads = [self._serialize_edge(item, entity_lookup) for item in edges]
        evidence_payloads = [self._serialize_evidence(item) for item in evidences]
        source_pages = [
            {
                "entity_key": item["entity_key"],
                "canonical_name": item["canonical_name"],
                "canonical_url": item["canonical_url"],
                "page_type": (item.get("attributes") or {}).get("page_type"),
                "word_count": (item.get("attributes") or {}).get("word_count"),
                "source_snapshot_id": item.get("source_snapshot_id"),
                "confidence": item.get("confidence"),
            }
            for item in entity_payloads
            if item.get("entity_type") == "page"
        ]
        return {
            "graph_version": self.GRAPH_VERSION,
            "site_id": site_id,
            "site": {
                "domain": discovery.domain,
                "scope_root_url": discovery.scope_root_url,
                "site_root_url": discovery.site_root_url,
                "business_type": discovery.business_type,
            },
            "summary": {
                "entity_count": len(entity_payloads),
                "edge_count": len(edge_payloads),
                "evidence_count": len(evidence_payloads),
                "source_snapshot_count": len(snapshot_rows),
                "entity_type_counts": dict(Counter(item["entity_type"] for item in entity_payloads)),
                "relation_type_counts": dict(Counter(item["relation_type"] for item in edge_payloads)),
            },
            "entities": entity_payloads,
            "edges": edge_payloads,
            "evidence": evidence_payloads,
            "source_pages": source_pages,
        }

    async def _load_current_site_graph(self, site_id: int) -> dict[str, Any]:
        entity_rows = await self.client.fetchall(
            """
            SELECT entity_id, entity_key, entity_type, canonical_name, canonical_url,
                   source_snapshot_id, confidence, attributes_json
            FROM geo_graph_entities
            WHERE site_id=%s
            ORDER BY entity_type ASC, canonical_name ASC, entity_id ASC
            """,
            (site_id,),
        )
        entities = [
            {
                "entity_id": int(row["entity_id"]),
                "entity_key": row.get("entity_key"),
                "entity_type": row.get("entity_type"),
                "canonical_name": row.get("canonical_name"),
                "canonical_url": row.get("canonical_url"),
                "source_snapshot_id": row.get("source_snapshot_id"),
                "confidence": float(row.get("confidence") or 0),
                "attributes": _json_loads(row.get("attributes_json")),
            }
            for row in entity_rows
        ]
        edge_rows = await self.client.fetchall(
            """
            SELECT edge.edge_id, edge.edge_key, edge.relation_type, edge.confidence, edge.evidence_count,
                   edge.attributes_json, edge.first_seen_at, edge.last_seen_at,
                   src.entity_key AS from_entity_key, src.canonical_name AS from_entity_name,
                   dst.entity_key AS to_entity_key, dst.canonical_name AS to_entity_name
            FROM geo_graph_edges AS edge
            INNER JOIN geo_graph_entities AS src ON src.entity_id=edge.from_entity_id
            INNER JOIN geo_graph_entities AS dst ON dst.entity_id=edge.to_entity_id
            WHERE edge.site_id=%s
            ORDER BY edge.relation_type ASC, edge.edge_id ASC
            """,
            (site_id,),
        )
        edges = [
            {
                "edge_id": int(row["edge_id"]),
                "edge_key": row.get("edge_key"),
                "from_entity_key": row.get("from_entity_key"),
                "to_entity_key": row.get("to_entity_key"),
                "from_entity_name": row.get("from_entity_name"),
                "to_entity_name": row.get("to_entity_name"),
                "relation_type": row.get("relation_type"),
                "confidence": float(row.get("confidence") or 0),
                "evidence_count": int(row.get("evidence_count") or 0),
                "attributes": _json_loads(row.get("attributes_json")),
                "first_seen_at": row.get("first_seen_at").isoformat() if isinstance(row.get("first_seen_at"), datetime) else row.get("first_seen_at"),
                "last_seen_at": row.get("last_seen_at").isoformat() if isinstance(row.get("last_seen_at"), datetime) else row.get("last_seen_at"),
            }
            for row in edge_rows
        ]
        evidence_rows = await self.client.fetchall(
            """
            SELECT evidence.evidence_id, evidence.snapshot_id, evidence.url_id,
                   evidence.evidence_type, evidence.evidence_field, evidence.selector_or_path,
                   evidence.evidence_text, evidence.confidence,
                   entity.entity_key AS entity_key,
                   edge.edge_key AS edge_key
            FROM geo_graph_evidence AS evidence
            LEFT JOIN geo_graph_entities AS entity ON entity.entity_id=evidence.entity_id
            LEFT JOIN geo_graph_edges AS edge ON edge.edge_id=evidence.edge_id
            WHERE evidence.site_id=%s
            ORDER BY evidence.evidence_id ASC
            """,
            (site_id,),
        )
        evidence = [
            {
                "evidence_id": int(row["evidence_id"]),
                "entity_key": row.get("entity_key"),
                "edge_key": row.get("edge_key"),
                "snapshot_id": row.get("snapshot_id"),
                "url_id": row.get("url_id"),
                "evidence_type": row.get("evidence_type"),
                "evidence_field": row.get("evidence_field"),
                "selector_or_path": row.get("selector_or_path"),
                "evidence_text": row.get("evidence_text"),
                "confidence": float(row.get("confidence") or 0),
            }
            for row in evidence_rows
        ]
        source_pages = [
            {
                "entity_key": item["entity_key"],
                "canonical_name": item["canonical_name"],
                "canonical_url": item["canonical_url"],
                "page_type": (item.get("attributes") or {}).get("page_type"),
                "word_count": (item.get("attributes") or {}).get("word_count"),
                "source_snapshot_id": item.get("source_snapshot_id"),
                "confidence": item.get("confidence"),
            }
            for item in entities
            if item.get("entity_type") == "page"
        ]
        return {
            "entities": entities,
            "edges": edges,
            "evidence": evidence,
            "source_pages": source_pages,
            "summary": {
                "entity_count": len(entities),
                "edge_count": len(edges),
                "evidence_count": len(evidence),
                "source_snapshot_count": len({item.get("source_snapshot_id") for item in entities if item.get("source_snapshot_id")}),
                "entity_type_counts": dict(Counter(item.get("entity_type") for item in entities if item.get("entity_type"))),
                "relation_type_counts": dict(Counter(item.get("relation_type") for item in edges if item.get("relation_type"))),
            },
        }

    async def load_task_graph(self, task_id: str) -> dict[str, Any] | None:
        if not self.enabled:
            return {
                "task_id": task_id,
                "snapshot_task_id": None,
                "exact_task_match": False,
                "backend": "file",
                "available": False,
                "built": False,
                "note": "MySQL is not enabled; knowledge graph is unavailable.",
                "task": None,
                "site_id": None,
                "graph_version": self.GRAPH_VERSION,
                "built_at": None,
                "summary": {
                    "entity_count": 0,
                    "edge_count": 0,
                    "evidence_count": 0,
                    "source_snapshot_count": 0,
                    "entity_type_counts": {},
                    "relation_type_counts": {},
                },
                "site": {},
                "entities": [],
                "edges": [],
                "evidence": [],
                "source_pages": [],
            }

        task_row = await self.client.fetchone(
            """
            SELECT task_id, site_id, domain, status, url, normalized_url,
                   full_audit, requested_max_pages, created_at, updated_at, completed_at
            FROM geo_audit_tasks
            WHERE task_id=%s
            """,
            (task_id,),
        )
        snapshot_row = await self.client.fetchone(
            """
            SELECT graph_snapshot_id, site_id, task_id, graph_version, source_snapshot_count,
                   entity_count, edge_count, evidence_count, graph_json, note, built_at
            FROM geo_site_graph_snapshots
            WHERE task_id=%s
            ORDER BY built_at DESC, graph_snapshot_id DESC
            LIMIT 1
            """,
            (task_id,),
        )
        exact_task_match = snapshot_row is not None
        if snapshot_row is None:
            site_id = int((task_row or {}).get("site_id") or 0) or None
            if site_id is not None:
                snapshot_row = await self.client.fetchone(
                    """
                    SELECT graph_snapshot_id, site_id, task_id, graph_version, source_snapshot_count,
                           entity_count, edge_count, evidence_count, graph_json, note, built_at
                    FROM geo_site_graph_snapshots
                    WHERE site_id=%s
                    ORDER BY built_at DESC, graph_snapshot_id DESC
                    LIMIT 1
                    """,
                    (site_id,),
                )
        if not task_row and not snapshot_row:
            return None

        site_id = int((snapshot_row or task_row or {}).get("site_id") or 0) or None
        graph_json = _json_loads((snapshot_row or {}).get("graph_json"))
        if site_id and (
            not graph_json.get("entities")
            or not graph_json.get("edges")
            or "evidence" not in graph_json
        ):
            try:
                current_graph = await self._load_current_site_graph(site_id)
            except Exception:
                current_graph = {}
            graph_json = {
                **current_graph,
                **graph_json,
                "entities": graph_json.get("entities") or current_graph.get("entities") or [],
                "edges": graph_json.get("edges") or current_graph.get("edges") or [],
                "evidence": graph_json.get("evidence") or current_graph.get("evidence") or [],
                "source_pages": graph_json.get("source_pages") or current_graph.get("source_pages") or [],
                "summary": {
                    **(current_graph.get("summary") or {}),
                    **(graph_json.get("summary") or {}),
                },
            }

        summary = graph_json.get("summary") or {}
        snapshot_task_id = (snapshot_row or {}).get("task_id")
        note = (snapshot_row or {}).get("note")
        if snapshot_row is None:
            note = "Knowledge graph has not been built for this task yet." if task_row else "Knowledge graph task not found."
        elif not exact_task_match and snapshot_task_id and snapshot_task_id != task_id:
            note = (
                note
                or "Using the latest site-level knowledge graph snapshot because no exact snapshot was stored for this task."
            )
        payload = {
            "task_id": task_id,
            "snapshot_task_id": snapshot_task_id,
            "exact_task_match": exact_task_match,
            "backend": "mysql",
            "available": True,
            "built": snapshot_row is not None,
            "note": note,
            "task": {
                "task_id": (task_row or {}).get("task_id"),
                "site_id": (task_row or {}).get("site_id"),
                "domain": (task_row or {}).get("domain"),
                "status": (task_row or {}).get("status"),
                "url": (task_row or {}).get("url"),
                "normalized_url": (task_row or {}).get("normalized_url"),
                "full_audit": bool((task_row or {}).get("full_audit")) if task_row else None,
                "requested_max_pages": (task_row or {}).get("requested_max_pages"),
                "created_at": (task_row or {}).get("created_at"),
                "updated_at": (task_row or {}).get("updated_at"),
                "completed_at": (task_row or {}).get("completed_at"),
            }
            if task_row
            else None,
            "site_id": site_id,
            "graph_version": (snapshot_row or {}).get("graph_version") or graph_json.get("graph_version") or self.GRAPH_VERSION,
            "built_at": (snapshot_row or {}).get("built_at"),
            "site": graph_json.get("site") or {},
            "summary": {
                "entity_count": int(summary.get("entity_count") or (snapshot_row or {}).get("entity_count") or 0),
                "edge_count": int(summary.get("edge_count") or (snapshot_row or {}).get("edge_count") or 0),
                "evidence_count": int(summary.get("evidence_count") or (snapshot_row or {}).get("evidence_count") or 0),
                "source_snapshot_count": int(summary.get("source_snapshot_count") or (snapshot_row or {}).get("source_snapshot_count") or 0),
                "entity_type_counts": summary.get("entity_type_counts") or {},
                "relation_type_counts": summary.get("relation_type_counts") or {},
            },
            "entities": graph_json.get("entities") or [],
            "edges": graph_json.get("edges") or [],
            "evidence": graph_json.get("evidence") or [],
            "source_pages": graph_json.get("source_pages") or [],
        }
        return payload

    async def ensure_task_snapshot(self, *, task_id: str, site_id: int) -> KnowledgeGraphSummary:
        if not self.enabled:
            return KnowledgeGraphSummary(enabled=False, built=False, site_id=site_id, note="MySQL is not enabled.")

        exact_row = await self.client.fetchone(
            """
            SELECT graph_snapshot_id, site_id, task_id, graph_version, source_snapshot_count,
                   entity_count, edge_count, evidence_count, graph_json, note, built_at
            FROM geo_site_graph_snapshots
            WHERE task_id=%s
            ORDER BY built_at DESC, graph_snapshot_id DESC
            LIMIT 1
            """,
            (task_id,),
        )
        if exact_row:
            return self._summary_from_snapshot_row(exact_row)

        latest_row = await self.client.fetchone(
            """
            SELECT graph_snapshot_id, site_id, task_id, graph_version, source_snapshot_count,
                   entity_count, edge_count, evidence_count, graph_json, note, built_at
            FROM geo_site_graph_snapshots
            WHERE site_id=%s
            ORDER BY built_at DESC, graph_snapshot_id DESC
            LIMIT 1
            """,
            (site_id,),
        )
        if not latest_row:
            return KnowledgeGraphSummary(
                enabled=True,
                built=False,
                site_id=site_id,
                note="No reusable site knowledge graph snapshot was available for this task.",
            )

        source_task_id = latest_row.get("task_id")
        await self.client.execute(
            """
            INSERT INTO geo_site_graph_snapshots (
              site_id, task_id, graph_version, source_snapshot_count,
              entity_count, edge_count, evidence_count, graph_json, note, built_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(latest_row.get("site_id") or site_id),
                task_id,
                latest_row.get("graph_version") or self.GRAPH_VERSION,
                int(latest_row.get("source_snapshot_count") or 0),
                int(latest_row.get("entity_count") or 0),
                int(latest_row.get("edge_count") or 0),
                int(latest_row.get("evidence_count") or 0),
                latest_row.get("graph_json"),
                (
                    f"Reused latest site knowledge graph snapshot from task {source_task_id}."
                    if source_task_id
                    else "Reused latest site knowledge graph snapshot for this task."
                ),
                datetime.now(timezone.utc),
            ),
        )
        return KnowledgeGraphSummary(
            enabled=True,
            built=True,
            site_id=int(latest_row.get("site_id") or site_id),
            entity_count=int(latest_row.get("entity_count") or 0),
            edge_count=int(latest_row.get("edge_count") or 0),
            evidence_count=int(latest_row.get("evidence_count") or 0),
            source_snapshot_count=int(latest_row.get("source_snapshot_count") or 0),
            last_built_at=datetime.now(timezone.utc),
            note=(
                f"Reused latest site knowledge graph snapshot from task {source_task_id}."
                if source_task_id
                else "Reused latest site knowledge graph snapshot for this task."
            ),
        )

    def _add_entity(
        self,
        entities: dict[str, _ProjectedEntity],
        *,
        entity_type: str,
        canonical_name: str | None,
        canonical_url: str | None,
        source_snapshot_id: int | None,
        confidence: float,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        stable_ref = canonical_url or canonical_name or entity_type
        entity_key = _hash_key(entity_type, stable_ref)
        incoming = _ProjectedEntity(
            entity_key=entity_key,
            entity_type=entity_type,
            canonical_name=canonical_name,
            canonical_url=canonical_url,
            source_snapshot_id=source_snapshot_id,
            confidence=confidence,
            attributes=attributes or {},
        )
        current = entities.get(entity_key)
        if current is None:
            entities[entity_key] = incoming
            return entity_key

        current.canonical_name = current.canonical_name or incoming.canonical_name
        current.canonical_url = current.canonical_url or incoming.canonical_url
        current.source_snapshot_id = current.source_snapshot_id or incoming.source_snapshot_id
        current.confidence = max(current.confidence, incoming.confidence)
        current.attributes.update({k: v for k, v in incoming.attributes.items() if v not in (None, "", [], {})})
        return entity_key

    def _add_edge(
        self,
        edges: dict[str, _ProjectedEdge],
        *,
        from_entity_key: str,
        to_entity_key: str,
        relation_type: str,
        confidence: float,
        attributes: dict[str, Any] | None = None,
        seen_at: datetime | None = None,
    ) -> str:
        edge_key = _hash_key(from_entity_key, relation_type, to_entity_key)
        incoming = _ProjectedEdge(
            edge_key=edge_key,
            from_entity_key=from_entity_key,
            to_entity_key=to_entity_key,
            relation_type=relation_type,
            confidence=confidence,
            attributes=attributes or {},
            first_seen_at=seen_at,
            last_seen_at=seen_at,
        )
        current = edges.get(edge_key)
        if current is None:
            edges[edge_key] = incoming
            return edge_key

        current.confidence = max(current.confidence, incoming.confidence)
        current.attributes.update({k: v for k, v in incoming.attributes.items() if v not in (None, "", [], {})})
        if incoming.first_seen_at and (current.first_seen_at is None or incoming.first_seen_at < current.first_seen_at):
            current.first_seen_at = incoming.first_seen_at
        if incoming.last_seen_at and (current.last_seen_at is None or incoming.last_seen_at > current.last_seen_at):
            current.last_seen_at = incoming.last_seen_at
        return edge_key

    def _project_graph(
        self,
        discovery: DiscoveryResult,
        snapshot_rows: list[dict[str, Any]],
    ) -> tuple[list[_ProjectedEntity], list[_ProjectedEdge], list[_ProjectedEvidence]]:
        entities: dict[str, _ProjectedEntity] = {}
        edges: dict[str, _ProjectedEdge] = {}
        evidences: list[_ProjectedEvidence] = []
        page_entity_keys: dict[str, str] = {}
        snapshot_payloads: list[dict[str, Any]] = []

        site_url = discovery.scope_root_url or discovery.site_root_url or discovery.final_url
        site_key = self._add_entity(
            entities,
            entity_type="site",
            canonical_name=discovery.domain,
            canonical_url=site_url,
            source_snapshot_id=None,
            confidence=100.0,
            attributes={
                "business_type": discovery.business_type,
                "scope_root_url": discovery.scope_root_url,
                "site_root_url": discovery.site_root_url,
            },
        )

        organization_name = discovery.site_signals.detected_company_name or discovery.domain
        organization_key = self._add_entity(
            entities,
            entity_type="organization",
            canonical_name=organization_name,
            canonical_url=discovery.site_root_url or site_url,
            source_snapshot_id=None,
            confidence=88.0 if discovery.site_signals.company_name_detected else 72.0,
            attributes=discovery.site_signals.model_dump(mode="json"),
        )
        organization_edge = self._add_edge(
            edges,
            from_entity_key=site_key,
            to_entity_key=organization_key,
            relation_type="represents",
            confidence=92.0,
            attributes={"source": "discovery"},
        )
        evidences.append(
            _ProjectedEvidence(
                entity_key=organization_key,
                edge_key=organization_edge,
                snapshot_id=None,
                url_id=None,
                evidence_type="heuristic",
                evidence_field="site_signals",
                selector_or_path="discovery.site_signals",
                evidence_text=organization_name,
                confidence=80.0,
            )
        )

        for row in snapshot_rows:
            profile = _json_loads(row.get("page_profile_json"))
            parsed = _json_loads(row.get("parsed_json"))
            final_url = _safe_normalize_url(row.get("final_url")) or _safe_normalize_url(row.get("normalized_url"))
            normalized_url = _safe_normalize_url(row.get("normalized_url")) or final_url
            if not final_url:
                continue
            snapshot_id = int(row["snapshot_id"])
            url_id = int(row["url_id"])
            page_type = str(row.get("url_type") or profile.get("page_type") or "page")
            title = profile.get("title") or parsed.get("title") or final_url
            seen_at = row.get("fetched_at")
            page_key = self._add_entity(
                entities,
                entity_type="page",
                canonical_name=title,
                canonical_url=final_url,
                source_snapshot_id=snapshot_id,
                confidence=100.0,
                attributes={
                    "page_type": page_type,
                    "lang": profile.get("lang"),
                    "word_count": profile.get("word_count", 0),
                    "has_faq": profile.get("has_faq", False),
                    "has_author": profile.get("has_author", False),
                    "has_publish_date": profile.get("has_publish_date", False),
                    "has_reference_section": profile.get("has_reference_section", False),
                    "has_tldr": profile.get("has_tldr", False),
                    "schema_types": (profile.get("json_ld_summary") or {}).get("types", []),
                },
            )
            page_entity_keys[final_url] = page_key
            if normalized_url:
                page_entity_keys[normalized_url] = page_key

            has_page_edge = self._add_edge(
                edges,
                from_entity_key=site_key,
                to_entity_key=page_key,
                relation_type="has_page",
                confidence=100.0,
                attributes={"url_type": page_type},
                seen_at=seen_at,
            )
            evidences.append(
                _ProjectedEvidence(
                    entity_key=page_key,
                    edge_key=has_page_edge,
                    snapshot_id=snapshot_id,
                    url_id=url_id,
                    evidence_type="inventory",
                    evidence_field="url_type",
                    selector_or_path="geo_page_snapshots",
                    evidence_text=page_type,
                    confidence=100.0,
                )
            )

            if page_type in {"homepage", "about", "contact"}:
                relation_type = "entity_home" if page_type == "homepage" else "about"
                edge_key = self._add_edge(
                    edges,
                    from_entity_key=page_key,
                    to_entity_key=organization_key,
                    relation_type=relation_type,
                    confidence=86.0 if page_type == "homepage" else 78.0,
                    attributes={"page_type": page_type},
                    seen_at=seen_at,
                )
                evidences.append(
                    _ProjectedEvidence(
                        entity_key=organization_key,
                        edge_key=edge_key,
                        snapshot_id=snapshot_id,
                        url_id=url_id,
                        evidence_type="heuristic",
                        evidence_field="page_type",
                        selector_or_path=page_type,
                        evidence_text=title,
                        confidence=75.0,
                    )
                )

            if page_type == "product":
                product_key = self._add_entity(
                    entities,
                    entity_type="product",
                    canonical_name=title,
                    canonical_url=final_url,
                    source_snapshot_id=snapshot_id,
                    confidence=84.0,
                    attributes={"page_url": final_url},
                )
                offers_edge = self._add_edge(
                    edges,
                    from_entity_key=organization_key,
                    to_entity_key=product_key,
                    relation_type="offers",
                    confidence=82.0,
                    attributes={"source_page_type": page_type},
                    seen_at=seen_at,
                )
                about_edge = self._add_edge(
                    edges,
                    from_entity_key=page_key,
                    to_entity_key=product_key,
                    relation_type="about",
                    confidence=90.0,
                    attributes={"source_page_type": page_type},
                    seen_at=seen_at,
                )
                evidences.extend(
                    [
                        _ProjectedEvidence(
                            entity_key=product_key,
                            edge_key=offers_edge,
                            snapshot_id=snapshot_id,
                            url_id=url_id,
                            evidence_type="heuristic",
                            evidence_field="url_type",
                            selector_or_path="product",
                            evidence_text=title,
                            confidence=82.0,
                        ),
                        _ProjectedEvidence(
                            entity_key=product_key,
                            edge_key=about_edge,
                            snapshot_id=snapshot_id,
                            url_id=url_id,
                            evidence_type="heuristic",
                            evidence_field="title",
                            selector_or_path="page.title",
                            evidence_text=title,
                            confidence=90.0,
                        ),
                    ]
                )
            elif page_type in {"landing", "service"}:
                service_key = self._add_entity(
                    entities,
                    entity_type="service",
                    canonical_name=title,
                    canonical_url=final_url,
                    source_snapshot_id=snapshot_id,
                    confidence=82.0,
                    attributes={"page_url": final_url},
                )
                offers_edge = self._add_edge(
                    edges,
                    from_entity_key=organization_key,
                    to_entity_key=service_key,
                    relation_type="offers",
                    confidence=80.0,
                    attributes={"source_page_type": page_type},
                    seen_at=seen_at,
                )
                about_edge = self._add_edge(
                    edges,
                    from_entity_key=page_key,
                    to_entity_key=service_key,
                    relation_type="about",
                    confidence=88.0,
                    attributes={"source_page_type": page_type},
                    seen_at=seen_at,
                )
                evidences.extend(
                    [
                        _ProjectedEvidence(
                            entity_key=service_key,
                            edge_key=offers_edge,
                            snapshot_id=snapshot_id,
                            url_id=url_id,
                            evidence_type="heuristic",
                            evidence_field="url_type",
                            selector_or_path=page_type,
                            evidence_text=title,
                            confidence=80.0,
                        ),
                        _ProjectedEvidence(
                            entity_key=service_key,
                            edge_key=about_edge,
                            snapshot_id=snapshot_id,
                            url_id=url_id,
                            evidence_type="heuristic",
                            evidence_field="title",
                            selector_or_path="page.title",
                            evidence_text=title,
                            confidence=88.0,
                        ),
                    ]
                )

            snapshot_payloads.append(
                {
                    "snapshot_id": snapshot_id,
                    "url_id": url_id,
                    "final_url": final_url,
                    "normalized_url": normalized_url,
                    "title": title,
                    "page_type": page_type,
                    "page_key": page_key,
                    "profile": profile,
                    "parsed": parsed,
                    "seen_at": seen_at,
                }
            )

        for item in snapshot_payloads:
            profile = item["profile"]
            parsed = item["parsed"]
            page_key = item["page_key"]
            snapshot_id = item["snapshot_id"]
            url_id = item["url_id"]
            seen_at = item["seen_at"]
            schema_summary = profile.get("json_ld_summary") or {}
            for same_as_url in schema_summary.get("same_as", [])[:20]:
                normalized_same_as = _safe_normalize_url(same_as_url)
                if not normalized_same_as:
                    continue
                external_key = self._add_entity(
                    entities,
                    entity_type="external_profile",
                    canonical_name=_display_name_from_url(normalized_same_as),
                    canonical_url=normalized_same_as,
                    source_snapshot_id=snapshot_id,
                    confidence=90.0,
                    attributes={"source": "sameAs"},
                )
                edge_key = self._add_edge(
                    edges,
                    from_entity_key=organization_key,
                    to_entity_key=external_key,
                    relation_type="same_as",
                    confidence=94.0,
                    attributes={},
                    seen_at=seen_at,
                )
                evidences.append(
                    _ProjectedEvidence(
                        entity_key=external_key,
                        edge_key=edge_key,
                        snapshot_id=snapshot_id,
                        url_id=url_id,
                        evidence_type="json_ld",
                        evidence_field="sameAs",
                        selector_or_path="page_profile.json_ld_summary.same_as",
                        evidence_text=normalized_same_as,
                        confidence=94.0,
                    )
                )

            for link in (parsed.get("internal_links") or [])[:30]:
                target_url = _safe_normalize_url((link or {}).get("url"))
                if not target_url:
                    continue
                target_key = page_entity_keys.get(target_url)
                if not target_key or target_key == page_key:
                    continue
                anchor_text = ((link or {}).get("text") or "").strip() or None
                edge_key = self._add_edge(
                    edges,
                    from_entity_key=page_key,
                    to_entity_key=target_key,
                    relation_type="links_to",
                    confidence=72.0,
                    attributes={"anchor_text": anchor_text},
                    seen_at=seen_at,
                )
                evidences.append(
                    _ProjectedEvidence(
                        entity_key=None,
                        edge_key=edge_key,
                        snapshot_id=snapshot_id,
                        url_id=url_id,
                        evidence_type="anchor",
                        evidence_field="internal_links",
                        selector_or_path="a[href]",
                        evidence_text=anchor_text or target_url,
                        confidence=72.0,
                    )
                )

            page_has_references = bool(profile.get("has_reference_section") or profile.get("has_inline_citations"))
            external_relation = "cites" if page_has_references else "references"
            for link in (parsed.get("external_links") or [])[:20]:
                target_url = _safe_normalize_url((link or {}).get("url"))
                if not target_url:
                    continue
                anchor_text = ((link or {}).get("text") or "").strip() or None
                external_key = self._add_entity(
                    entities,
                    entity_type="external_source",
                    canonical_name=_display_name_from_url(target_url),
                    canonical_url=target_url,
                    source_snapshot_id=snapshot_id,
                    confidence=70.0,
                    attributes={"source": "external_link"},
                )
                edge_key = self._add_edge(
                    edges,
                    from_entity_key=page_key,
                    to_entity_key=external_key,
                    relation_type=external_relation,
                    confidence=70.0 if page_has_references else 62.0,
                    attributes={"anchor_text": anchor_text},
                    seen_at=seen_at,
                )
                evidences.append(
                    _ProjectedEvidence(
                        entity_key=external_key,
                        edge_key=edge_key,
                        snapshot_id=snapshot_id,
                        url_id=url_id,
                        evidence_type="anchor",
                        evidence_field="external_links",
                        selector_or_path="a[href]",
                        evidence_text=anchor_text or target_url,
                        confidence=70.0 if page_has_references else 62.0,
                    )
                )

        edge_evidence_counts: dict[str, int] = {}
        for evidence in evidences:
            if evidence.edge_key:
                edge_evidence_counts[evidence.edge_key] = edge_evidence_counts.get(evidence.edge_key, 0) + 1
        for edge_key, edge in edges.items():
            edge.evidence_count = edge_evidence_counts.get(edge_key, 0)

        return list(entities.values()), list(edges.values()), evidences

    async def build(
        self,
        *,
        site_id: int,
        discovery: DiscoveryResult,
        task_id: str | None = None,
    ) -> KnowledgeGraphSummary:
        if not self.enabled:
            return KnowledgeGraphSummary(enabled=False, built=False, note="MySQL is not enabled.")

        try:
            snapshot_rows = await self.client.fetchall(
                """
                SELECT snapshot_id, site_id, url_id, normalized_url, final_url, url_type,
                       page_profile_json, parsed_json, fetched_at
                FROM geo_page_snapshots
                WHERE site_id=%s
                ORDER BY fetched_at ASC, snapshot_id ASC
                """,
                (site_id,),
            )
        except Exception as exc:
            logger.warning("Knowledge graph build skipped while loading snapshots", extra={"site_id": site_id, "error": str(exc)})
            return KnowledgeGraphSummary(
                enabled=True,
                built=False,
                site_id=site_id,
                note="Failed to load page snapshots for knowledge graph build.",
            )

        if not snapshot_rows:
            logger.info(
                "Knowledge graph build skipped because no snapshots were stored",
                extra={"site_id": site_id, "task_id": task_id},
            )
            return KnowledgeGraphSummary(
                enabled=True,
                built=False,
                site_id=site_id,
                note="No page snapshots were available for knowledge graph build.",
            )

        logger.info(
            "Knowledge graph source snapshots loaded",
            extra={
                "site_id": site_id,
                "task_id": task_id,
                "source_snapshot_count": len(snapshot_rows),
            },
        )

        entities, edges, evidences = self._project_graph(discovery, snapshot_rows)
        entity_rows = [
            (
                site_id,
                item.entity_key,
                item.entity_type,
                item.canonical_name,
                item.canonical_url,
                item.source_snapshot_id,
                round(item.confidence, 2),
                _json_dumps(item.attributes),
            )
            for item in entities
        ]
        graph_built_at = datetime.now(timezone.utc)

        try:
            await self.client.execute("DELETE FROM geo_graph_evidence WHERE site_id=%s", (site_id,))
            await self.client.execute("DELETE FROM geo_graph_edges WHERE site_id=%s", (site_id,))
            await self.client.execute("DELETE FROM geo_graph_entities WHERE site_id=%s", (site_id,))
            if entity_rows:
                await self.client.executemany(
                    """
                    INSERT INTO geo_graph_entities (
                      site_id, entity_key, entity_type, canonical_name, canonical_url,
                      source_snapshot_id, confidence, attributes_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    entity_rows,
                )
            entity_map_rows = await self.client.fetchall(
                "SELECT entity_id, entity_key FROM geo_graph_entities WHERE site_id=%s",
                (site_id,),
            )
            entity_id_map = {str(row["entity_key"]): int(row["entity_id"]) for row in entity_map_rows}

            edge_rows = [
                (
                    site_id,
                    item.edge_key,
                    entity_id_map[item.from_entity_key],
                    entity_id_map[item.to_entity_key],
                    item.relation_type,
                    round(item.confidence, 2),
                    int(item.evidence_count),
                    _json_dumps(item.attributes),
                    item.first_seen_at,
                    item.last_seen_at,
                )
                for item in edges
                if item.from_entity_key in entity_id_map and item.to_entity_key in entity_id_map
            ]
            if edge_rows:
                await self.client.executemany(
                    """
                    INSERT INTO geo_graph_edges (
                      site_id, edge_key, from_entity_id, to_entity_id, relation_type,
                      confidence, evidence_count, attributes_json, first_seen_at, last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    edge_rows,
                )
            edge_map_rows = await self.client.fetchall(
                "SELECT edge_id, edge_key FROM geo_graph_edges WHERE site_id=%s",
                (site_id,),
            )
            edge_id_map = {str(row["edge_key"]): int(row["edge_id"]) for row in edge_map_rows}

            evidence_rows = [
                (
                    site_id,
                    entity_id_map.get(item.entity_key) if item.entity_key else None,
                    edge_id_map.get(item.edge_key) if item.edge_key else None,
                    item.snapshot_id,
                    item.url_id,
                    item.evidence_type,
                    item.evidence_field,
                    item.selector_or_path,
                    item.evidence_text,
                    round(item.confidence, 2),
                )
                for item in evidences
                if (item.entity_key is None or item.entity_key in entity_id_map)
                and (item.edge_key is None or item.edge_key in edge_id_map)
            ]
            if evidence_rows:
                await self.client.executemany(
                    """
                    INSERT INTO geo_graph_evidence (
                      site_id, entity_id, edge_id, snapshot_id, url_id,
                      evidence_type, evidence_field, selector_or_path, evidence_text, confidence
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    evidence_rows,
                )

            graph_json = self._build_snapshot_graph_json(
                site_id=site_id,
                discovery=discovery,
                snapshot_rows=snapshot_rows,
                entities=entities,
                edges=edges,
                evidences=evidences,
            )
            await self.client.execute(
                """
                INSERT INTO geo_site_graph_snapshots (
                  site_id, task_id, graph_version, source_snapshot_count,
                  entity_count, edge_count, evidence_count, graph_json, note, built_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    site_id,
                    task_id,
                    self.GRAPH_VERSION,
                    len(snapshot_rows),
                    len(entities),
                    len(edges),
                    len(evidences),
                    _json_dumps(graph_json),
                    "Projected from page snapshots and discovery signals.",
                    graph_built_at,
                ),
            )
        except Exception as exc:
            logger.warning("Knowledge graph build failed", extra={"site_id": site_id, "error": str(exc)})
            return KnowledgeGraphSummary(
                enabled=True,
                built=False,
                site_id=site_id,
                source_snapshot_count=len(snapshot_rows),
                note="Knowledge graph build failed while writing projection tables.",
            )

        summary = KnowledgeGraphSummary(
            enabled=True,
            built=True,
            site_id=site_id,
            entity_count=len(entities),
            edge_count=len(edges),
            evidence_count=len(evidences),
            source_snapshot_count=len(snapshot_rows),
            last_built_at=graph_built_at,
            note="Knowledge graph projection stored in MySQL.",
        )
        logger.info(
            "Knowledge graph projection stored",
            extra={
                "site_id": site_id,
                "task_id": task_id,
                "entity_count": summary.entity_count,
                "edge_count": summary.edge_count,
                "evidence_count": summary.evidence_count,
                "source_snapshot_count": summary.source_snapshot_count,
            },
        )
        return summary
