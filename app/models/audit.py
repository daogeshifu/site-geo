from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BaseAuditResult(BaseModel):
    """所有审计模块结果的基类，定义通用字段"""

    score: int                  # 0-100 模块总分
    status: str                 # critical/poor/fair/good/strong
    module_key: str = ""        # 模块标识符，如 "visibility"
    input_pages: list[str] = Field(default_factory=list)  # 本次审计使用的页面 URL 列表
    duration_ms: int = 0        # 模块执行耗时（毫秒）
    confidence: float = 0.0     # 结果置信度（0-1），取决于抓取到的页面数量
    audit_mode: str = "standard"
    llm_enhanced: bool = False  # 是否经过 LLM 增强
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_insights: dict[str, Any] = Field(default_factory=dict)  # LLM 返回的原始洞察
    processing_notes: list[str] = Field(default_factory=list)   # 处理过程中的备注
    findings: dict[str, Any] = Field(default_factory=dict)      # 关键发现汇总
    issues: list[str] = Field(default_factory=list)             # 问题列表
    strengths: list[str] = Field(default_factory=list)          # 优势列表
    recommendations: list[str] = Field(default_factory=list)    # 优化建议列表


class VisibilityAuditResult(BaseAuditResult):
    """AI 可见性模块结果：评估 AI 爬虫访问、可引用性和品牌权威"""

    ai_visibility_score: int        # AI 可见性子分（占 GEO 总分 25%）
    brand_authority_score: int      # 品牌权威子分（占 GEO 总分 20%）
    checks: dict[str, Any] = Field(default_factory=dict)


class TechnicalAuditResult(BaseAuditResult):
    """技术基础模块结果：评估 HTTPS、SSR、安全响应头、性能等"""

    technical_score: int            # 技术评分（占 GEO 总分 15%）
    checks: dict[str, Any] = Field(default_factory=dict)
    security_headers: dict[str, Any] = Field(default_factory=dict)   # 安全响应头检查详情
    ssr_signal: dict[str, Any] = Field(default_factory=dict)          # 服务端渲染信号
    render_blocking_risk: dict[str, Any] = Field(default_factory=dict)  # 渲染阻塞风险


class ContentPageAnalysis(BaseModel):
    """单页面内容分析结果，用于 E-E-A-T 评估"""

    url: str
    page_type: str
    title: str | None = None
    word_count: int = 0
    has_faq: bool = False
    has_author: bool = False
    has_publish_date: bool = False
    has_quantified_data: bool = False
    has_reference_section: bool = False
    has_inline_citations: bool = False
    has_tldr: bool = False
    has_update_log: bool = False
    answer_first: bool = False
    heading_quality_score: int = 0
    information_density_score: int = 0
    chunk_structure_score: int = 0
    internal_link_count: int = 0
    external_link_count: int = 0
    descriptive_internal_link_ratio: float = 0.0
    descriptive_external_link_ratio: float = 0.0
    text_excerpt: str = ""


class ContentAuditResult(BaseAuditResult):
    """内容质量模块结果：评估 E-E-A-T 四个维度"""

    content_score: int              # 内容综合评分（占 GEO 总分 20%）
    experience_score: int           # Experience（经验）评分
    expertise_score: int            # Expertise（专业度）评分
    authoritativeness_score: int    # Authoritativeness（权威性）评分
    trustworthiness_score: int      # Trustworthiness（可信度）评分
    checks: dict[str, Any] = Field(default_factory=dict)
    page_analyses: dict[str, ContentPageAnalysis] = Field(default_factory=dict)  # 各页面分析详情


class SchemaAuditResult(BaseAuditResult):
    """结构化数据模块结果：评估 JSON-LD Schema 覆盖情况"""

    structured_data_score: int      # 结构化数据评分（占 GEO 总分 10%）
    checks: dict[str, Any] = Field(default_factory=dict)
    schema_types: list[str] = Field(default_factory=list)   # 检测到的 Schema 类型列表
    same_as: list[str] = Field(default_factory=list)        # sameAs 引用 URL 列表
    missing_schema_recommendations: list[str] = Field(default_factory=list)  # 缺失 Schema 建议


class PlatformAuditDetail(BaseModel):
    """单个 AI 平台的审计详情"""

    platform_score: int              # 0-100 平台就绪度评分
    primary_gap: str                 # 主要差距描述
    key_recommendations: list[str] = Field(default_factory=list)  # 针对该平台的优化建议
    optimization_focus: str | None = None
    preferred_sources: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class PlatformAuditResult(BaseAuditResult):
    """平台适配模块结果：评估在 5 大 AI 搜索平台的可见度"""

    platform_optimization_score: int    # 平台综合评分（占 GEO 总分 10%）
    checks: dict[str, Any] = Field(default_factory=dict)
    platform_scores: dict[str, PlatformAuditDetail] = Field(default_factory=dict)  # 各平台详情


class ActionPlanItem(BaseModel):
    """优先行动计划条目"""

    priority: str    # high/medium/low
    module: str      # 对应的审计模块
    action: str      # 具体行动描述
    rationale: str   # 行动理由（为何优先）


class ObservationSourceMetric(BaseModel):
    """可选观测层中的单个平台来源指标"""

    platform: str
    sessions: int | None = None
    users: int | None = None
    conversions: int | None = None
    revenue: float | None = None
    conversion_rate: float | None = None
    notes: list[str] = Field(default_factory=list)


class CitationObservation(BaseModel):
    """人工或系统记录的单条 AI 引用观测"""

    platform: str
    query: str | None = None
    cited: bool = False
    position: int | None = None
    citation_url: str | None = None
    notes: str | None = None


class ObservationInput(BaseModel):
    """可选观测层输入，不参与 GEO 评分"""

    data_period: str | None = None
    ga4_ai_sessions: int | None = None
    ga4_ai_users: int | None = None
    ga4_ai_conversions: int | None = None
    ga4_ai_revenue: float | None = None
    source_breakdown: list[ObservationSourceMetric] = Field(default_factory=list)
    citation_observations: list[CitationObservation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ObservationResult(BaseModel):
    """可选观测层结果，仅用于展示和叙事，不计分"""

    provided: bool = False
    scored: bool = False
    status: str = "not_provided"
    measurement_maturity: str = "none"
    summary: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    platform_breakdown: list[ObservationSourceMetric] = Field(default_factory=list)
    citation_observations: list[CitationObservation] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class PageDiagnosticResult(BaseModel):
    """逐页诊断结果，用于 full audit 模式"""

    url: str
    page_type: str = "page"
    source: str = "core"
    overall_score: int
    status: str
    citability_score: int
    content_score: int
    technical_score: int
    schema_score: int
    issue_count: int = 0
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    issue_details: dict[str, list[str]] = Field(default_factory=dict)
    recommendation_details: dict[str, list[str]] = Field(default_factory=dict)


class MetricDefinition(BaseModel):
    """汇总层指标说明卡片"""

    name: str
    category: str
    scoring: str
    formula: str
    why_it_matters: str
    data_source: str
    platform_relevance: list[str] = Field(default_factory=list)


class AIPerceptionResult(BaseModel):
    """AI 对站点认知的启发式画像，不参与 GEO 评分"""

    positive_percentage: int
    neutral_percentage: int
    controversial_percentage: int
    cognition_keywords: list[str] = Field(default_factory=list)


class SummaryResult(BaseModel):
    """GEO 审计汇总结果，计算 6 个维度的加权复合分数"""

    composite_geo_score: int    # 最终 GEO 综合评分（0-100）
    status: str                 # critical/poor/fair/good/strong
    scoring_version: str = "geo-audit-v3"
    audit_mode: str = "standard"
    llm_enhanced: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_insights: dict[str, Any] = Field(default_factory=dict)
    processing_notes: list[str] = Field(default_factory=list)
    dimensions: dict[str, Any] = Field(default_factory=dict)       # 6 个维度的详细评分
    weighted_scores: dict[str, Any] = Field(default_factory=dict)  # 加权计算过程数据
    summary: str                # 文字摘要描述
    top_issues: list[str] = Field(default_factory=list)            # 最关键问题（最多 5 条）
    quick_wins: list[str] = Field(default_factory=list)            # 快速优化建议（最多 5 条）
    prioritized_action_plan: list[ActionPlanItem] = Field(default_factory=list)  # 优先行动计划
    metric_definitions: list[MetricDefinition] = Field(default_factory=list)
    score_interpretation: list[str] = Field(default_factory=list)
    ai_perception: AIPerceptionResult | None = None
    observation: ObservationResult | None = None
    notices: list[str] = Field(default_factory=list)
