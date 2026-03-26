# GEO Audit 数据字段字典

本文档基于当前 `site-geo` 返回结构整理，适合产品、前端、运营和研发共同查看。  
目标是把字段按层级拆清楚，并明确：

- 字段路径
- 类型
- 是否参与计分
- 字段含义
- 备注 / 风险点

## 1. 顶层结构

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `url` | string | 否 | 用户输入的目标 URL | 审计入口 |
| `discovery` | object | 间接 | 发现层结果 | 所有模块上游输入 |
| `visibility` | object | 是 | 可见性审计结果 | 同时产出 AI 可见性与品牌权威基础分 |
| `technical` | object | 是 | 技术审计结果 | 对应汇总层“技术基础” |
| `content` | object | 是 | 内容审计结果 | 对应汇总层“内容与 E-E-A-T” |
| `schema` | object | 是 | 结构化数据审计结果 | 对应汇总层“结构化数据” |
| `platform` | object | 是 | 平台适配结果 | 对应汇总层“平台适配” |
| `page_diagnostics` | array | 否 | 逐页诊断结果 | 扩展展示层，不改变站点级权重 |
| `observation` | object | 否 | 外部观测层 | 可选展示，不计分 |
| `summary` | object | 是 | 汇总层结果 | 综合分、维度、行动计划都在这里 |

---

## 2. Discovery 发现层

### 2.1 基础站点信息

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `discovery.url` | string | 否 | 原始输入 URL | 可能与 `normalized_url` 不同 |
| `discovery.normalized_url` | string | 否 | 规范化 URL | 去除跳转歧义 |
| `discovery.final_url` | string | 否 | 实际落地 URL | 抓取后真实地址 |
| `discovery.site_root_url` | string | 否 | 站点根 URL | 如 `https://www.ipdraft.com` |
| `discovery.scope_root_url` | string | 否 | 本次审计作用域根 URL | 如语言子路径 `/zh/` |
| `discovery.domain` | string | 否 | 注册域名 | 如 `ipdraft.com` |
| `discovery.business_type` | string | 间接 | 推断业务类型 | 如 `saas / agency` |
| `discovery.input_is_likely_homepage` | bool | 否 | 输入是否像首页 | 用于提示 |
| `discovery.input_scope_warning` | string \| null | 否 | 作用域告警 | 为空表示无警告 |
| `discovery.full_audit_enabled` | bool | 否 | 是否启用 full audit | 决定是否扩展采样 |
| `discovery.requested_max_pages` | int | 否 | 最大采样页数 | 当前样例为 `50` |
| `discovery.profiled_page_count` | int | 否 | 实际画像页数 | 当前样例为 `14` |
| `discovery.site_snapshot_version` | string | 否 | 发现层版本号 | 当前样例为 `snapshot-v3` |

### 2.2 抓取结果 `fetch`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `discovery.fetch.final_url` | string | 否 | 抓取最终 URL | 通常与 `discovery.final_url` 一致 |
| `discovery.fetch.status_code` | int | 否 | 首页状态码 | 如 `200` |
| `discovery.fetch.headers` | object | 否 | 响应头原始数据 | 技术审计和排错用 |
| `discovery.fetch.response_time_ms` | int | 是 | 首页响应时间 | 技术模块性能项复用 |

### 2.3 首页画像 `homepage`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `title` | string | 间接 | 首页标题 | `title` 标签 |
| `meta_description` | string | 间接 | 首页描述 | `meta description` |
| `canonical` | string | 间接 | 规范链接 | `canonical` |
| `lang` | string | 间接 | 页面语言 | `html lang` |
| `viewport` | string | 间接 | viewport 配置 | 技术基础项 |
| `h1` | string | 间接 | 主标题 | H1 提取 |
| `headings` | array | 间接 | 标题结构列表 | 影响 citability / heading quality |
| `hreflang` | array | 间接 | 多语言声明 | 技术与国际化信号 |
| `internal_links` | array | 否 | 内链列表 | 用于页面发现 |
| `external_links` | array | 否 | 外链列表 | 可能含邮箱等联系信息 |
| `images` | array | 间接 | 图片列表 | 图片优化来源 |
| `scripts` | array | 间接 | 脚本列表 | render-blocking 判断 |
| `stylesheets` | array | 间接 | 样式表列表 | render-blocking 判断 |
| `json_ld_blocks` | array | 间接 | 原始 JSON-LD 区块 | schema 数据源 |
| `open_graph` | object | 间接 | OG 数据 | 技术与平台适配复用 |
| `twitter_cards` | object | 间接 | Twitter Card 数据 | 技术与平台适配复用 |
| `word_count` | int | 间接 | 首页词数 | 内容深度与 citability 使用 |
| `html_length` | int | 间接 | HTML 长度 | SSR 信号使用 |
| `text_excerpt` | string | 否 | 文本摘要 | 展示与 LLM 参考 |

### 2.4 Robots / Sitemap / llms

#### `discovery.robots`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `exists` | bool | 间接 | robots.txt 是否存在 | 技术与可见性基础信号 |
| `status_code` | int | 否 | robots 状态码 | 排错用 |
| `allows_all` | bool | 否 | 是否对通用爬虫开放 | 非 AI 专项结论 |
| `has_sitemap_directive` | bool | 间接 | 是否声明 sitemap | 技术项 |
| `sitemaps` | array | 间接 | robots 内的 sitemap 列表 | 索引信号 |
| `user_agents` | object | 间接 | 主要 AI crawler 放行结果 | GPTBot / OAI-SearchBot 等 |
| `raw_preview` | string | 否 | robots 预览 | 排错用 |

#### `discovery.sitemap`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `url` | string | 否 | sitemap 地址 | |
| `exists` | bool | 间接 | sitemap 是否存在 | 技术与品牌一致性信号 |
| `status_code` | int | 否 | sitemap 状态码 | |
| `discovered_urls` | array | 否 | sitemap 抽样 URL | full audit 页面发现来源 |
| `total_urls_sampled` | int | 否 | sitemap 采样数量 | 说明发现深度 |

#### `discovery.llms`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `url` | string | 否 | llms.txt 地址 | |
| `exists` | bool | 间接 | llms.txt 是否存在 | AI 可见性基础项 |
| `status_code` | int | 否 | llms 状态码 | |
| `content_preview` | string | 否 | llms 内容预览 | 当前样例看起来像 HTML，值得警惕 |
| `content_length` | int | 间接 | 内容长度 | llms 有效性判断 |
| `effectiveness_score` | int | 间接 | llms 有效性分 | visibility 与 platform 复用 |
| `signals` | object | 间接 | llms 规则信号 | brand/services/guidance/sections |

### 2.5 关键页面与实体信号

#### `discovery.key_pages`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `about` | string \| null | 否 | 识别出的 about 页面 | 可为空 |
| `service` | string \| null | 否 | 识别出的 service 页面 | 可为空 |
| `contact` | string \| null | 否 | 识别出的 contact 页面 | 可为空 |
| `article` | string \| null | 否 | 识别出的 article 页面 | 当前样例命中博客列表页 |
| `case_study` | string \| null | 否 | 识别出的案例页 | 可为空 |

#### `discovery.schema_summary`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `json_ld_present` | bool | 间接 | 聚合后是否存在 JSON-LD | 与 schema 模块可能不一致 |
| `types` | array | 间接 | 聚合发现到的 schema 类型 | 如 `Article / Organization` |
| `has_organization` | bool | 间接 | 是否有 Organization | |
| `has_article` | bool | 间接 | 是否有 Article | |
| `has_faq_page` | bool | 间接 | 是否有 FAQPage | |
| `has_service` | bool | 间接 | 是否有 Service | |
| `has_website` | bool | 间接 | 是否有 WebSite | |
| `has_product` | bool | 间接 | 是否有 Product | |
| `has_defined_term` | bool | 间接 | 是否有 DefinedTerm | |
| `entity_id_count` | int | 间接 | 稳定 `@id` 数量 | |
| `relation_count` | int | 间接 | 关系数量 | |
| `same_as` | array | 间接 | sameAs 列表 | |

#### `discovery.site_signals`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `company_name_detected` | bool | 间接 | 是否检测到公司名 | 品牌权威来源 |
| `address_detected` | bool | 间接 | 是否检测到地址 | 品牌权威来源 |
| `phone_detected` | bool | 间接 | 是否检测到电话 | 品牌权威来源 |
| `email_detected` | bool | 间接 | 是否检测到邮箱 | 品牌权威来源 |
| `awards_detected` | bool | 间接 | 是否检测到奖项 | 品牌权威来源 |
| `certifications_detected` | bool | 间接 | 是否检测到认证/资质 | 品牌权威来源 |
| `same_as_detected` | bool | 间接 | 是否检测到 sameAs | 品牌权威来源 |
| `detected_company_name` | string | 否 | 检测出的公司名 | 当前样例有误判风险 |
| `homepage_brand_mentions` | int | 间接 | 首页品牌提及次数 | 品牌提及子项来源 |

#### `discovery.backlinks`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `provider` | string | 否 | 外链数据源 | 当前为 `semrush` |
| `available` | bool | 间接 | 外链数据是否可用 | 未配置 key 时为 false |
| `target` | string | 否 | 外链查询目标 | 根域名 |
| `target_type` | string | 否 | 查询类型 | `root_domain` |
| `authority_score` | number \| null | 间接 | Authority Score | 品牌权威外链子项 |
| `backlinks_num` | number \| null | 间接 | 外链总量 | |
| `referring_domains` | number \| null | 间接 | 引用域数量 | |
| `referring_ips` | number \| null | 间接 | 引用 IP 数 | |
| `referring_ip_classes` | number \| null | 间接 | 引用 C 段数 | |
| `follow_ratio` | number \| null | 间接 | follow 比例 | |
| `raw` | object | 否 | 原始返回 | |
| `error` | string \| null | 否 | 错误信息 | 如未配置 API key |

### 2.6 页面画像 `page_profiles` / `additional_page_profiles`

这是统一页面画像模型，核心页放在 `page_profiles`，扩展页放在 `additional_page_profiles`。

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `page_type` | string | 间接 | 页面类型 | 如 `homepage/article/page/documentation` |
| `final_url` | string | 否 | 页面最终 URL | 页面画像主键之一 |
| `title` | string | 间接 | 页面标题 | 可引用性与内容判断 |
| `meta_description` | string | 间接 | 页面描述 | 可引用性与平台适配 |
| `canonical` | string | 间接 | canonical | 可引用性与实体一致性 |
| `lang` | string | 间接 | 页面语言 | |
| `headings` | array | 间接 | 标题结构 | heading 质量 |
| `word_count` | int | 间接 | 页面词数 | 内容深度 |
| `has_faq` | bool | 间接 | 是否有 FAQ | E-E-A-T 与 citability |
| `has_author` | bool | 间接 | 是否有作者 | E-E-A-T 与 citability |
| `has_publish_date` | bool | 间接 | 是否有发布日期 | E-E-A-T 与 citability |
| `has_quantified_data` | bool | 间接 | 是否有量化数据 | 内容与引用友好性 |
| `answer_first` | bool | 间接 | 是否先答后述 | citability 与平台适配 |
| `heading_quality_score` | int | 间接 | 标题质量分 | 内容与引用结构 |
| `information_density_score` | int | 间接 | 信息密度分 | 内容与引用结构 |
| `chunk_structure_score` | int | 间接 | 分块结构分 | 内容与引用结构 |
| `json_ld_summary` | object | 间接 | 页面级 schema 摘要 | 页面级结构化数据 |
| `json_ld_blocks` | array | 否 | 页面原始 JSON-LD | schema 复用与排错 |
| `entity_signals` | object | 间接 | 页面级实体信号 | 品牌权威来源 |
| `text_excerpt` | string | 否 | 文本摘要 | 展示和 LLM 使用 |

---

## 3. 审计层通用字段

`visibility / technical / content / schema / platform` 五个模块都有这些字段。

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `score` | int | 是 | 模块总分 | 站点级模块结果 |
| `status` | string | 是 | 模块状态 | `good/fair/poor/critical` |
| `module_key` | string | 否 | 模块唯一键 | 如 `visibility` |
| `input_pages` | array | 否 | 模块使用的页面 | 便于追溯上游输入 |
| `duration_ms` | int | 否 | 模块耗时 | 性能与调试用 |
| `confidence` | float | 否 | 模块置信度 | 当前为启发式可信度 |
| `audit_mode` | string | 否 | `standard/premium` | |
| `llm_enhanced` | bool | 否 | 是否经 LLM 增强 | technical/schema 通常为 false |
| `llm_provider` | string | 否 | LLM 服务方 | 如 `openrouter` |
| `llm_model` | string | 否 | 模型名 | |
| `llm_insights` | object | 否 | LLM 额外洞察 | 总结、问题、建议等 |
| `processing_notes` | array | 否 | 处理备注 | 说明规则驱动或降级 |
| `findings` | object | 间接 | 结构化发现 | 给 UI 和 summary 复用 |
| `issues` | array | 否 | 问题列表 | |
| `strengths` | array | 否 | 优势列表 | |
| `recommendations` | array | 否 | 建议列表 | |

---

## 4. 各审计模块

### 4.1 Visibility

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `visibility.ai_visibility_score` | int | 是 | AI 可见性分 | 汇总层原始分 |
| `visibility.brand_authority_score` | int | 是 | 品牌权威分 | 汇总层原始分 |
| `visibility.findings.ai_crawler_access_score` | int | 间接 | AI crawler 放行得分 | 来自 robots |
| `visibility.findings.citability` | object | 间接 | 可引用性结果 | 新版基于 page profiles |
| `visibility.findings.citability.score` | int | 是 | 可引用性总分 | 参与 AI 可见性 |
| `visibility.findings.citability.homepage_citability` | object | 间接 | 首页 citability 子结果 | |
| `visibility.findings.citability.best_page_citability` | object | 间接 | 最佳页 citability 子结果 | |
| `visibility.findings.citability.citation_probability` | string | 否 | 引用概率 | `LOW / MEDIUM / HIGH` |
| `visibility.findings.citability.page_scores` | object | 否 | 逐页 citability | 展示与排错用 |
| `visibility.findings.llms_quality` | object | 间接 | llms 质量结果 | AI 可见性与平台适配复用 |
| `visibility.findings.basic_brand_presence` | object | 间接 | 基础实体存在 | AI 可见性内的实体基础分 |
| `visibility.findings.brand_authority` | object | 间接 | 品牌权威详细结果 | 4 个子项组合 |
| `visibility.checks.allowed_ai_crawlers` | int | 间接 | 放行的 AI 爬虫数量 | |
| `visibility.checks.total_ai_crawlers_checked` | int | 间接 | 检查总数 | 当前通常为 6 |
| `visibility.checks.llms_effectiveness` | object | 间接 | llms 规则信号 | |
| `visibility.checks.citability_signals` | object | 间接 | citability 底层信号 | |
| `visibility.checks.brand_signals` | object | 间接 | 品牌底层信号 | company/address/phone/email 等 |
| `visibility.checks.brand_authority_components` | object | 间接 | 品牌权威 4 个子项 | `backlink / mentions / entity / business` |
| `visibility.checks.backlinks` | object | 间接 | 外链原始对象 | 与 discovery.backlinks 同源 |

#### `visibility.findings.brand_authority.components`

| 子项 | 类型 | 计分 | 说明 |
|---|---|---:|---|
| `backlink_quality` | object | 间接 | 外链质量子项 |
| `brand_mentions` | object | 间接 | 品牌提及子项 |
| `entity_consistency` | object | 间接 | sameAs / sitemap / 命名一致性子项 |
| `business_completeness` | object | 间接 | 电话/邮箱/地址/资质等完整度子项 |

### 4.2 Technical

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `technical.technical_score` | int | 是 | 技术总分 | 汇总层原始分 |
| `technical.findings.response_time_ms` | int | 间接 | 响应时间 | 性能项来源 |
| `technical.findings.security_headers_score` | int | 间接 | 安全头得分 | |
| `technical.findings.ssr_classification` | string | 间接 | SSR 级别 | `strong/moderate/weak/poor` |
| `technical.findings.performance_classification` | string | 间接 | 性能级别 | `fast/good/slow` 等 |
| `technical.findings.render_blocking_risk` | string | 间接 | 渲染阻塞风险 | `low/medium/high` |
| `technical.checks.https` | bool | 间接 | 是否 HTTPS | |
| `technical.checks.ssr` | object | 间接 | SSR 子项 | 基于 HTML 长度与词数 |
| `technical.checks.meta_description` | bool | 间接 | 是否有 meta description | |
| `technical.checks.canonical` | bool | 间接 | 是否有 canonical | |
| `technical.checks.lang` | bool | 间接 | 是否有 html lang | |
| `technical.checks.viewport` | bool | 间接 | 是否有 viewport | |
| `technical.checks.sitemap` | bool | 间接 | 是否有 sitemap | |
| `technical.checks.robots_sitemap_directive` | bool | 间接 | robots 是否声明 sitemap | |
| `technical.checks.open_graph` | bool | 间接 | 是否有 OG | |
| `technical.checks.twitter_card` | bool | 间接 | 是否有 Twitter Card | |
| `technical.checks.hreflang` | bool | 间接 | 是否有 hreflang | |
| `technical.checks.security_headers` | object | 间接 | 安全头明细 | HSTS/CSP/XFO/XCTO/Referrer-Policy |
| `technical.checks.image_optimization` | object | 间接 | 图片优化明细 | lazyload/dimension |
| `technical.checks.render_blocking` | object | 间接 | 渲染阻塞明细 | scripts/stylesheets |
| `technical.checks.performance` | object | 间接 | 性能评分对象 | 基于 response_time_ms |

### 4.3 Content

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `content.content_score` | int | 是 | 内容基础分 | 汇总内容维度子分之一 |
| `content.experience_score` | int | 是 | Experience 分 | E-E-A-T 子分 |
| `content.expertise_score` | int | 是 | Expertise 分 | E-E-A-T 子分 |
| `content.authoritativeness_score` | int | 是 | Authority 分 | E-E-A-T 子分 |
| `content.trustworthiness_score` | int | 是 | Trust 分 | E-E-A-T 子分 |
| `content.findings.evaluated_pages` | int | 否 | 被内容模块评估的页数 | 当前样例只有 1 |
| `content.findings.average_heading_quality` | int | 间接 | 平均标题质量 | |
| `content.findings.average_information_density` | int | 间接 | 平均信息密度 | |
| `content.findings.average_chunk_structure` | int | 间接 | 平均分块结构 | |
| `content.findings.has_faq_any` | bool | 间接 | 是否任一评估页有 FAQ | |
| `content.findings.has_author_any` | bool | 间接 | 是否任一评估页有作者 | |
| `content.findings.has_publish_date_any` | bool | 间接 | 是否任一评估页有日期 | |
| `content.findings.has_quantified_data_any` | bool | 间接 | 是否任一评估页有量化数据 | |
| `content.findings.has_answer_first_any` | bool | 间接 | 是否任一评估页先答后述 | |
| `content.checks.service_page_word_count` | int | 间接 | 服务页词数 | 无服务页时可能为 0 |
| `content.checks.article_page_word_count` | int | 间接 | 文章页词数 | 内容深度主信号 |
| `content.checks.faq_present` | bool | 间接 | 是否有 FAQ | |
| `content.checks.author_present` | bool | 间接 | 是否有作者 | |
| `content.checks.publish_date_present` | bool | 间接 | 是否有发布日期 | |
| `content.checks.quantified_data_present` | bool | 间接 | 是否有量化数据 | |
| `content.checks.answer_first_present` | bool | 间接 | 是否先答后述 | |
| `content.page_analyses` | object | 否 | 实际纳入内容评分的页面分析 | 当前样例只包含 article 列表页 |

### 4.4 Schema

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `schema.structured_data_score` | int | 是 | 结构化数据总分 | 汇总层原始分 |
| `schema.findings.schema_type_count` | int | 间接 | 类型数量 | |
| `schema.findings.same_as_count` | int | 间接 | sameAs 数量 | |
| `schema.findings.entity_id_count` | int | 间接 | 稳定 `@id` 数量 | |
| `schema.findings.relation_count` | int | 间接 | 关系数量 | |
| `schema.checks.json_ld_present` | bool | 间接 | 是否检测到 JSON-LD | |
| `schema.checks.organization` | bool | 间接 | 是否有 Organization | |
| `schema.checks.local_business` | bool | 间接 | 是否有 LocalBusiness | |
| `schema.checks.article` | bool | 间接 | 是否有 Article | |
| `schema.checks.faq_page` | bool | 间接 | 是否有 FAQPage | |
| `schema.checks.service` | bool | 间接 | 是否有 Service | |
| `schema.checks.website` | bool | 间接 | 是否有 WebSite | |
| `schema.checks.product` | bool | 间接 | 是否有 Product | |
| `schema.checks.defined_term` | bool | 间接 | 是否有 DefinedTerm | |
| `schema.schema_types` | array | 否 | 识别出的 schema 类型列表 | |
| `schema.same_as` | array | 否 | sameAs 列表 | |
| `schema.missing_schema_recommendations` | array | 否 | 缺失建议 | |

### 4.5 Platform

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `platform.platform_optimization_score` | int | 是 | 平台适配总分 | 汇总层原始分 |
| `platform.findings.llms_exists` | bool | 间接 | llms 是否存在 | |
| `platform.findings.llms_quality_score` | int | 间接 | llms 质量分 | |
| `platform.findings.ai_crawler_allowed_ratio` | float | 间接 | AI crawler 放行比例 | |
| `platform.findings.schema_signal` | int | 间接 | schema 信号分 | |
| `platform.findings.metadata_signal` | int | 间接 | metadata 信号分 | |
| `platform.findings.brand_authority_score` | int | 间接 | 品牌权威引用分 | |
| `platform.findings.entity_relationship_signal` | int | 间接 | 实体关系信号 | |
| `platform.findings.platform_weights` | object | 否 | 平台权重表 | 如 chatgpt/google_ai_mode/gemini 等 |
| `platform.checks.llms_exists` | bool | 间接 | llms 是否存在 | |
| `platform.checks.schema_present` | bool | 间接 | 是否存在 schema | |
| `platform.checks.faq_schema_present` | bool | 间接 | 是否存在 FAQ schema | |
| `platform.checks.metadata_complete` | bool | 间接 | 元数据是否完整 | |
| `platform.checks.ai_crawler_allowed_ratio` | float | 间接 | 放行比例 | |
| `platform.checks.llms_quality_score` | int | 间接 | llms 质量分 | |
| `platform.platform_scores` | object | 否 | 各平台单独评分详情 | |

#### `platform.platform_scores[*]`

| 字段 | 类型 | 计分 | 说明 |
|---|---|---:|---|
| `platform_score` | int | 否 | 单个平台得分 |
| `primary_gap` | string | 否 | 该平台主要缺口 |
| `key_recommendations` | array | 否 | 该平台核心建议 |
| `optimization_focus` | string | 否 | 该平台优化重点 |
| `preferred_sources` | array | 否 | 该平台偏好信源 |
| `evidence` | array | 否 | 该平台打分依据摘要 |

---

## 5. 逐页诊断 `page_diagnostics`

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `url` | string | 否 | 页面 URL | 可为 core 或 extended 页面 |
| `page_type` | string | 否 | 页面类型 | `homepage/article/page/documentation` 等 |
| `source` | string | 否 | 来源类型 | `core / extended` |
| `overall_score` | int | 否 | 页面综合分 | 仅页面层展示 |
| `status` | string | 否 | 页面状态 | |
| `citability_score` | int | 否 | 页面可引用分 | |
| `content_score` | int | 否 | 页面内容分 | |
| `technical_score` | int | 否 | 页面技术分 | |
| `schema_score` | int | 否 | 页面 schema 分 | |
| `issue_count` | int | 否 | 页面问题数 | |
| `issues` | array | 否 | 页面问题列表 | |
| `recommendations` | array | 否 | 页面建议列表 | |

---

## 6. Observation 观测层

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `observation.provided` | bool | 否 | 是否提供 observation 数据 | 当前样例为 false |
| `observation.scored` | bool | 否 | 是否计分 | 当前为 false |
| `observation.status` | string | 否 | 状态 | 如 `not_provided` |
| `observation.measurement_maturity` | string | 否 | 观测成熟度 | `none/basic/advanced` 等 |
| `observation.summary` | string | 否 | 观测总结 | |
| `observation.metrics` | object | 否 | 原始观测指标 | 可为空 |
| `observation.platform_breakdown` | array | 否 | 平台拆分观测 | 可为空 |
| `observation.citation_observations` | array | 否 | 引用观测 | 可为空 |
| `observation.highlights` | array | 否 | 观测亮点 | 可为空 |
| `observation.data_gaps` | array | 否 | 缺失项 | 如未提供 GA4 AI 流量 |

---

## 7. Summary 汇总层

### 7.1 基础汇总

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `summary.composite_geo_score` | int | 是 | GEO 综合分 | 最终站点分 |
| `summary.status` | string | 是 | 综合状态 | `poor/fair/good` 等 |
| `summary.scoring_version` | string | 否 | 评分版本 | 当前样例为 `geo-audit-v3` |
| `summary.audit_mode` | string | 否 | 模式 | `standard / premium` |
| `summary.llm_enhanced` | bool | 否 | 汇总是否经 LLM 增强 | |
| `summary.summary` | string | 否 | 汇总摘要 | 简版综合总结 |
| `summary.top_issues` | array | 否 | 关键问题 | |
| `summary.quick_wins` | array | 否 | 快速收益项 | |
| `summary.prioritized_action_plan` | array | 否 | 优先行动计划 | |
| `summary.notices` | array | 否 | 补充说明 | 如 full audit 采样提示 |

### 7.2 汇总维度 `summary.dimensions`

这是最终对外展示的 6 个一级维度。

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `summary.dimensions["AI Citability & Visibility"]` | object | 是 | AI 可见性维度 | 来源模块 `visibility` |
| `summary.dimensions["Brand Authority Signals"]` | object | 是 | 品牌权威维度 | 来源模块 `brand_authority` |
| `summary.dimensions["Content Quality & E-E-A-T"]` | object | 是 | 内容与 E-E-A-T | 来源模块 `content` |
| `summary.dimensions["Technical Foundations"]` | object | 是 | 技术基础 | 来源模块 `technical` |
| `summary.dimensions["Structured Data"]` | object | 是 | 结构化数据 | 来源模块 `schema` |
| `summary.dimensions["Platform Optimization"]` | object | 是 | 平台适配 | 来源模块 `platform` |

#### 维度内部字段

| 字段 | 类型 | 计分 | 说明 |
|---|---|---:|---|
| `display_name` | string | 否 | 中文显示名 |
| `module` | string | 否 | 来源模块 |
| `score` | int | 是 | 维度原始分 |
| `issues` | array | 否 | 维度问题 |
| `recommendations` | array | 否 | 维度建议 |

### 7.3 权重折算 `summary.weighted_scores`

| 字段 | 类型 | 计分 | 说明 |
|---|---|---:|---|
| `raw_score` | int | 是 | 原始分 |
| `weight` | float | 是 | 维度权重 |
| `weighted_value` | float | 是 | 折算后贡献值 |

### 7.4 指标定义 `summary.metric_definitions`

该字段更偏说明层，适合前端展示和文档，而不是计算。

| 字段 | 类型 | 计分 | 说明 |
|---|---|---:|---|
| `name` | string | 否 | 指标名称 |
| `category` | string | 否 | `计分 / 不计分` |
| `scoring` | string | 否 | `scored / unscored` |
| `formula` | string | 否 | 指标口径 |
| `why_it_matters` | string | 否 | 为什么重要 |
| `data_source` | string | 否 | 数据来源 |
| `platform_relevance` | array | 否 | 相关平台 |

### 7.5 说明性字段

| 字段 | 类型 | 计分 | 说明 | 备注 |
|---|---|---:|---|---|
| `summary.score_interpretation` | array | 否 | 分数解释 | 前端/文档展示 |
| `summary.observation` | object | 否 | 汇总层内 observation 镜像 | 与顶层 `observation` 存在重复 |

---

## 8. 当前样例暴露出的逻辑注意点

这些不是字段本身，而是基于当前返回样例看到的系统风险。

| 问题 | 说明 | 影响 |
|---|---|---|
| `discovery.schema_summary` 与 `schema` 模块结果冲突 | discovery 已识别到 `Article/Organization`，但 schema 模块得分为 `0` | 会导致 summary 误判“完全无结构化数据” |
| `citability` 字段前后口径冲突 | `findings.citability.score=49`，但 `page_scores.homepage=72`，且 `best_page_citability.page_key=homepage` | 结果解释会混乱 |
| `key_pages.article` 命中列表页 | 当前命中 `/zh/blog/` 而不是最佳文章详情页 | 内容质量与 E-E-A-T 可能被系统性低估 |
| 内容模块评估页过少 | `evaluated_pages=1`，而 snapshot 其实抓到了多篇文章详情页 | 内容结论偏弱 |
| 公司名识别误判风险 | `detected_company_name="智能专利撰写工具"` 更像描述语 | 品牌权威可能失真 |
| llms.txt 可能返回 HTML | `content_preview` 像网页 HTML，但仍得较高分 | llms 质量判断可能偏乐观 |
| `page_diagnostics` 不参与主分 | 文档和前端要明确说明 | 避免用户误以为逐页分会改变站点总分 |
| `observation` 顶层与 summary 内重复 | 结果结构有重复字段 | 后续最好统一主出口 |

---

## 9. 推荐给产品/前端的展示顺序

如果要把这些字段转成页面展示，我建议顺序如下：

1. `summary.composite_geo_score`
2. `summary.dimensions`
3. `summary.top_issues / quick_wins / prioritized_action_plan`
4. `visibility / technical / content / schema / platform`
5. `discovery.page_profiles + additional_page_profiles`
6. `page_diagnostics`
7. `observation`

这样最符合“先看结论，再看模块，再看证据”的阅读路径。
