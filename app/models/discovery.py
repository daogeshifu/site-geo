from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HeadingItem(BaseModel):
    """页面标题标签（h1-h6）的数据模型"""

    level: str   # 标题级别，如 "h1"、"h2"
    text: str    # 标题文本内容


class LinkItem(BaseModel):
    """页面链接（<a> 标签）的数据模型"""

    url: str
    text: str | None = None   # 链接锚文本


class ImageItem(BaseModel):
    """页面图片（<img> 标签）的数据模型"""

    src: str
    alt: str | None = None       # alt 属性（SEO 和可访问性关键）
    loading: str | None = None   # lazy/eager，用于评估懒加载实现
    width: str | None = None
    height: str | None = None


class ScriptItem(BaseModel):
    """页面脚本（<script> 标签）的数据模型"""

    src: str | None = None
    is_inline: bool = False     # 是否内联脚本
    async_attr: bool = False    # 是否有 async 属性（非阻塞）
    defer_attr: bool = False    # 是否有 defer 属性（延迟执行）
    type: str | None = None


class StylesheetItem(BaseModel):
    """页面样式表（<link rel="stylesheet">）的数据模型"""

    href: str
    media: str | None = None  # media query 条件


class FetchMetadata(BaseModel):
    """HTTP 请求的元数据，记录最终 URL、状态码和响应时间"""

    final_url: str          # 重定向后的最终 URL
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    response_time_ms: int   # 请求响应耗时（毫秒），用于性能评估


class HomepageExtract(BaseModel):
    """首页 HTML 解析结果，包含 SEO、结构化数据和性能相关字段"""

    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None       # 规范链接，避免重复内容
    lang: str | None = None            # 页面语言声明
    viewport: str | None = None        # 移动端适配声明
    h1: str | None = None              # 主标题文本
    headings: list[HeadingItem] = Field(default_factory=list)
    hreflang: list[str] = Field(default_factory=list)          # 多语言链接
    internal_links: list[LinkItem] = Field(default_factory=list)
    external_links: list[LinkItem] = Field(default_factory=list)
    images: list[ImageItem] = Field(default_factory=list)
    scripts: list[ScriptItem] = Field(default_factory=list)
    stylesheets: list[StylesheetItem] = Field(default_factory=list)
    json_ld_blocks: list[str] = Field(default_factory=list)    # JSON-LD 结构化数据块
    open_graph: dict[str, str] = Field(default_factory=dict)   # Open Graph 社交元数据
    twitter_cards: dict[str, str] = Field(default_factory=dict)
    word_count: int = 0
    html_length: int = 0               # 原始 HTML 字节长度，用于 SSR 判断
    text_excerpt: str = ""             # 页面纯文本前 400 字符摘要


class RobotsUserAgentRule(BaseModel):
    """robots.txt 中针对特定 User-Agent 的访问规则"""

    allowed: bool = True               # 是否允许访问根路径
    matched_user_agent: str = "*"      # 匹配到的 UA 规则（具体名称或 "*"）


class RobotsResult(BaseModel):
    """robots.txt 检查结果，包含 AI 爬虫访问权限"""

    url: str
    exists: bool                       # robots.txt 是否存在
    status_code: int | None = None
    allows_all: bool = True            # 通配符 "*" 规则是否允许全站爬取
    has_sitemap_directive: bool = False  # 是否包含 Sitemap 指令
    sitemaps: list[str] = Field(default_factory=list)
    user_agents: dict[str, RobotsUserAgentRule] = Field(default_factory=dict)  # 各 AI 爬虫访问状态
    raw_preview: str = ""              # robots.txt 原始内容前 300 字符


class SitemapResult(BaseModel):
    """Sitemap 检查结果，包含发现的 URL 列表"""

    url: str | None = None
    exists: bool = False
    status_code: int | None = None
    discovered_urls: list[str] = Field(default_factory=list)
    total_urls_sampled: int = 0   # 实际采样的 URL 数量


class LlmsResult(BaseModel):
    """llms.txt 检查结果，评估对 AI 系统的机器引导质量"""

    url: str
    exists: bool
    status_code: int | None = None
    content_preview: str = ""          # 内容前 500 字符预览
    content_length: int = 0
    effectiveness_score: int = 0       # 0-100 的有效性评分
    signals: dict[str, bool] = Field(default_factory=dict)  # 各质量信号检查结果


class BacklinkOverviewResult(BaseModel):
    """外链概览数据，来自 Semrush API"""

    provider: str = "semrush"
    available: bool = False            # 数据是否可用
    source: str | None = None         # API 请求 URL
    target: str | None = None         # 被分析的目标域名
    target_type: str = "root_domain"
    authority_score: int | None = None   # Semrush 权威分（0-100）
    backlinks_num: int | None = None     # 外链总数
    referring_domains: int | None = None  # 引用域数量
    referring_ips: int | None = None
    referring_ip_classes: int | None = None
    follow_ratio: float | None = None    # follow 链接比例（0-1）
    raw: dict[str, Any] = Field(default_factory=dict)  # 原始 API 返回数据
    error: str | None = None             # 错误信息


class SiteSignals(BaseModel):
    """站点实体信号，用于品牌权威和可信度评估"""

    company_name_detected: bool = False     # 是否检测到公司名称
    address_detected: bool = False          # 是否检测到实体地址
    phone_detected: bool = False            # 是否检测到联系电话
    email_detected: bool = False            # 是否检测到公开邮箱
    awards_detected: bool = False           # 是否提及奖项荣誉
    certifications_detected: bool = False   # 是否提及认证资质
    same_as_detected: bool = False          # JSON-LD 中是否有 sameAs 引用
    detected_company_name: str | None = None  # 从标题中提取的公司名称
    homepage_brand_mentions: int = 0         # 首页正文中品牌名出现次数


class PageProfile(BaseModel):
    """单页面综合画像，融合 E-E-A-T 信号和内容质量评估"""

    page_type: str    # 页面类型：homepage/about/service/article/case_study
    final_url: str
    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    lang: str | None = None
    headings: list[HeadingItem] = Field(default_factory=list)
    word_count: int = 0
    has_faq: bool = False             # 是否包含 FAQ 内容
    has_author: bool = False          # 是否有作者信息
    has_publish_date: bool = False    # 是否有发布日期
    has_quantified_data: bool = False  # 是否包含量化数据（%、$、数字等）
    answer_first: bool = False        # 是否先答后述（AI 引用友好结构）
    heading_quality_score: int = 0    # 标题层级质量评分（0-100）
    information_density_score: int = 0  # 信息密度评分（词汇多样性+数量）
    chunk_structure_score: int = 0    # 内容分块结构评分
    json_ld_summary: dict[str, Any] = Field(default_factory=dict)  # 本页 schema 汇总
    json_ld_blocks: list[str] = Field(default_factory=list)
    entity_signals: SiteSignals = Field(default_factory=SiteSignals)  # 本页实体信号
    text_excerpt: str = ""


class KeyPages(BaseModel):
    """关键页面 URL 索引，由 select_key_pages 从候选 URL 中识别"""

    about: str | None = None        # 关于/公司页
    service: str | None = None      # 产品/服务页
    contact: str | None = None      # 联系页
    article: str | None = None      # 文章/博客页
    case_study: str | None = None   # 案例研究页


class DiscoveryResult(BaseModel):
    """站点快照 v2：整合首页、多关键页、协议文件和信号的完整数据模型

    所有审计模块共享同一个 DiscoveryResult 实例，避免重复网络请求。
    """

    url: str              # 原始输入 URL
    normalized_url: str   # 规范化后的 URL（统一协议头、去片段等）
    final_url: str        # 跟随重定向后的最终 URL
    domain: str           # 注册域名（如 example.com）
    fetch: FetchMetadata  # 首页请求元数据
    homepage: HomepageExtract          # 首页解析结果
    robots: RobotsResult               # robots.txt 检查结果
    sitemap: SitemapResult             # Sitemap 检查结果
    llms: LlmsResult                   # llms.txt 检查结果
    business_type: str                 # 推断的业务类型（agency/saas/ecommerce 等）
    key_pages: KeyPages                # 关键页面 URL 索引
    schema_summary: dict[str, Any] = Field(default_factory=dict)   # 全站 JSON-LD 汇总
    site_signals: SiteSignals = Field(default_factory=SiteSignals)  # 全站实体信号汇总
    backlinks: BacklinkOverviewResult = Field(default_factory=BacklinkOverviewResult)
    page_profiles: dict[str, PageProfile] = Field(default_factory=dict)  # 各页面画像
    site_snapshot_version: str = "snapshot-v2"  # 数据模型版本标识
