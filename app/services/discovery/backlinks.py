from __future__ import annotations

import csv
import io
import json
from typing import Any

import httpx

from app.core.config import settings
from app.models.discovery import BacklinkOverviewResult


class BacklinkService:
    """Semrush 外链数据服务：查询目标域名的外链概览指标

    API 响应格式为 CSV（分号或逗号分隔），包含权威分、外链数、引用域等数据
    """

    # Semrush API 请求的数据列，对应 authority_score/backlinks/domains 等指标
    EXPORT_COLUMNS = ",".join(
        [
            "ascore",          # 权威分（0-100）
            "backlinks_num",   # 外链总数
            "domains_num",     # 引用域数量
            "ips_num",         # 引用 IP 数量
            "ipclass_c_num",   # C 类 IP 段数量
            "follows_num",     # follow 链接数
            "nofollows_num",   # nofollow 链接数
            "sponsored_num",
            "ugc_num",
        ]
    )

    async def fetch_overview(
        self,
        target: str,
        client: httpx.AsyncClient | None = None,
    ) -> BacklinkOverviewResult:
        """查询目标域名的外链概览

        - 若 Semrush 未启用或 API key 未配置，返回 available=False
        - 支持注入共享的 httpx.AsyncClient 以复用连接
        """
        # 功能开关检查
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

        # 若未注入 client，创建临时 client（finally 中关闭）
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
            # 仅关闭自己创建的 client
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

        # 解析 CSV/JSON 响应
        payload = self._parse_payload(response.text)
        if not payload:
            return BacklinkOverviewResult(
                available=False,
                source=str(response.url),
                target=target,
                target_type=settings.semrush_target_type,
                error="Semrush response could not be parsed.",
            )

        # 计算 follow 链接比例
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
        """解析 Semrush 响应：支持 JSON 和 CSV（自动检测分隔符）"""
        stripped = text.strip()
        if not stripped:
            return {}

        # 尝试 JSON 格式
        if stripped.startswith("{"):
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError:
                return {}
            if isinstance(loaded, dict):
                return {str(key): value for key, value in loaded.items()}
            return {}

        # 尝试 CSV 格式（检测分号或逗号分隔符）
        delimiter = ";" if ";" in stripped.splitlines()[0] else ","
        rows = list(csv.DictReader(io.StringIO(stripped), delimiter=delimiter))
        if not rows:
            return {}
        return {str(key): value for key, value in rows[0].items()}

    def _to_int(self, value: Any) -> int | None:
        """安全地将各种格式的数值转换为 int（处理 None/""/n/a/带逗号的数字）"""
        if value in (None, "", "n/a", "N/A"):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            return None
