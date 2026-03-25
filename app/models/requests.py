from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.audit import (
    ContentAuditResult,
    ObservationInput,
    ObservationResult,
    PlatformAuditResult,
    SchemaAuditResult,
    TechnicalAuditResult,
    VisibilityAuditResult,
)
from app.models.discovery import DiscoveryResult

# 审计模式：standard（规则驱动）或 premium（LLM 增强）
AuditMode = Literal["standard", "premium"]
# 目前仅支持 OpenRouter 作为 LLM 提供商
LLMProvider = Literal["openrouter"]


class LLMConfig(BaseModel):
    """LLM 调用配置，premium 模式下用于指定模型和调用参数"""

    provider: LLMProvider = "openrouter"
    model: str | None = None           # 指定模型，留空则使用全局默认模型
    api_key: str | None = None         # 覆盖全局 API key
    base_url: str | None = None        # 覆盖全局 base URL
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)   # 生成温度，越低越确定
    max_tokens: int = Field(default=1200, ge=200, le=4000)     # 最大输出 token 数


class UrlRequest(BaseModel):
    """最基础的请求模型，包含 URL 和审计模式"""

    url: str = Field(..., min_length=3)   # 待审计的网站 URL
    mode: AuditMode = "standard"          # 审计模式
    llm: LLMConfig | None = None          # 可选 LLM 配置（premium 模式专用）
    observation: ObservationInput | None = None  # 可选观测层输入，不参与评分
    full_audit: bool = False
    max_pages: int = Field(default=12, ge=5, le=50)


class AuditModuleRequest(UrlRequest):
    """单模块审计请求，可携带预先完成的 discovery 结果以复用"""

    discovery: DiscoveryResult | None = None  # 已有的站点快照，避免重复抓取


class FullAuditRequest(UrlRequest):
    """全量审计请求（5 个模块并行），可携带预先完成的 discovery 结果"""

    discovery: DiscoveryResult | None = None


class SummarizeRequest(UrlRequest):
    """汇总计算请求：接收 5 个模块结果，计算复合 GEO 分数"""

    discovery: DiscoveryResult
    visibility: VisibilityAuditResult
    technical: TechnicalAuditResult
    content: ContentAuditResult
    schema_result: SchemaAuditResult = Field(alias="schema")  # 字段别名适配 JSON 中的 "schema" 键
    platform: PlatformAuditResult
    observation_result: ObservationResult | None = Field(default=None, alias="observationResult")
