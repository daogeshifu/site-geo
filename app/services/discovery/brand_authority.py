from __future__ import annotations

from app.models.discovery import DiscoveryResult
from app.utils.heuristics import calculate_brand_authority


class BrandAuthorityService:
    """品牌权威评估服务（为 visibility 和 platform 模块提供品牌分析）

    为未来独立的品牌权威审计 API 预留的服务边界。
    当前仅封装 calculate_brand_authority 启发式函数，
    评估 4 个维度（各占 25%）：
    - backlink_quality: 外链质量（Semrush 权威分 + 引用域数量）
    - brand_mentions: 品牌提及（标题/meta/H1/llms.txt 中出现次数）
    - entity_consistency: 实体一致性（sameAs + Organization schema + 域名一致性）
    - business_completeness: 业务信息完整度（名称/地址/电话/邮件/关于页/联系页）
    """

    def assess(self, discovery: DiscoveryResult) -> dict:
        """评估站点品牌权威，返回 {score, reasons, components} 字典"""
        return calculate_brand_authority(
            signals=discovery.site_signals,
            homepage=discovery.homepage.model_dump(),
            llms=discovery.llms,
            key_pages=discovery.key_pages,
            schema_summary=discovery.schema_summary,
            primary_domain=discovery.domain,
            sitemap_urls=discovery.robots.sitemaps,
            backlinks=discovery.backlinks,
        )
