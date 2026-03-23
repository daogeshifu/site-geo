from __future__ import annotations

import csv
import io
import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.discovery import BacklinkOverviewResult


class BacklinkService:
    EXPORT_COLUMNS = ",".join(
        [
            "ascore",
            "backlinks_num",
            "domains_num",
            "ips_num",
            "ipclass_c_num",
            "follows_num",
            "nofollows_num",
            "sponsored_num",
            "ugc_num",
        ]
    )

    async def fetch_overview(
        self,
        target: str,
        client: httpx.AsyncClient | None = None,
    ) -> BacklinkOverviewResult:
        if not settings.semrush_enabled:
            return BacklinkOverviewResult(
                available=False,
                target=target,
                target_type=settings.semrush_target_type,
                error="Semrush integration disabled.",
            )
        if not settings.semrush_api_key:
            return BacklinkOverviewResult(
                available=False,
                target=target,
                target_type=settings.semrush_target_type,
                error="Semrush API key not configured.",
            )

        owns_client = client is None
        request_client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        )
        try:
            response = await request_client.get(
                settings.semrush_base_url,
                params={
                    "type": "backlinks_overview",
                    "key": settings.semrush_api_key,
                    "target": target,
                    "target_type": settings.semrush_target_type,
                    "export_columns": self.EXPORT_COLUMNS,
                },
            )
        except httpx.HTTPError as exc:
            return BacklinkOverviewResult(
                available=False,
                source=settings.semrush_base_url,
                target=target,
                target_type=settings.semrush_target_type,
                error=str(exc),
            )
        finally:
            if owns_client:
                await request_client.aclose()

        if response.status_code >= 400:
            return BacklinkOverviewResult(
                available=False,
                source=str(response.url),
                target=target,
                target_type=settings.semrush_target_type,
                error=f"HTTP {response.status_code}",
            )

        payload = self._parse_payload(response.text)
        if not payload:
            return BacklinkOverviewResult(
                available=False,
                source=str(response.url),
                target=target,
                target_type=settings.semrush_target_type,
                error="Semrush response could not be parsed.",
            )

        follows = self._to_int(payload.get("follows_num"))
        nofollows = self._to_int(payload.get("nofollows_num"))
        follow_ratio = None
        if follows is not None and nofollows is not None and follows + nofollows > 0:
            follow_ratio = round(follows / (follows + nofollows), 2)

        return BacklinkOverviewResult(
            available=True,
            source=str(response.url),
            target=target,
            target_type=settings.semrush_target_type,
            authority_score=self._to_int(payload.get("ascore")),
            backlinks_num=self._to_int(payload.get("backlinks_num")),
            referring_domains=self._to_int(payload.get("domains_num")),
            referring_ips=self._to_int(payload.get("ips_num")),
            referring_ip_classes=self._to_int(payload.get("ipclass_c_num")),
            follow_ratio=follow_ratio,
            raw=payload,
        )

    def _parse_payload(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        if not stripped:
            return {}

        if stripped.startswith("{"):
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError:
                return {}
            if isinstance(loaded, dict):
                return {str(key): value for key, value in loaded.items()}
            return {}

        delimiter = ";" if ";" in stripped.splitlines()[0] else ","
        rows = list(csv.DictReader(io.StringIO(stripped), delimiter=delimiter))
        if not rows:
            return {}
        return {str(key): value for key, value in rows[0].items()}

    def _to_int(self, value: Any) -> int | None:
        if value in (None, "", "n/a", "N/A"):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            return None
