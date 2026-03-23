# GEO Audit Service

面向 GEO / AI Search 的站点审计服务。项目保持原有 API 风格不变，但内部已经从“传统 SEO 检测器”升级成“站点快照 + GEO 审计引擎”。

当前综合评分围绕 6 个汇总维度输出：

- AI 可见性 `25%`
- 品牌权威 `20%`
- 内容与 E-E-A-T `20%`
- 技术基础 `15%`
- 结构化数据 `10%`
- 平台适配 `10%`

## 核心设计

### 1. 发现层：Site Snapshot

`DiscoveryService` 不再只抓首页，而是构建站点级快照。

默认轻量抓取：

- `homepage`
- `about`
- `service`
- `article/news`
- `case_study`

每个页面都会输出统一 `page_profiles`：

- `final_url`
- `title`
- `meta_description`
- `canonical`
- `lang`
- `headings`
- `word_count`
- `has_faq`
- `has_author`
- `has_publish_date`
- `has_quantified_data`
- `answer_first`
- `heading_quality_score`
- `information_density_score`
- `chunk_structure_score`
- `json_ld_summary`
- `entity_signals`

发现层新增字段：

- `page_profiles`
- `site_snapshot_version`

当前版本号为：

- `snapshot-v2`

### 2. 审计层：5 个执行模块

系统仍保持 5 个审计模块，便于兼容现有 API 与任务编排：

- `visibility`
- `technical`
- `content`
- `schema`
- `platform`

所有模块统一新增元数据：

- `module_key`
- `input_pages`
- `duration_ms`
- `confidence`
- `processing_notes`

### 3. 汇总层：6 个 GEO 业务维度

汇总层不是简单把 5 个模块平均，而是按 GEO 业务口径重组：

- `AI Citability & Visibility`
- `Brand Authority Signals`
- `Content Quality & E-E-A-T`
- `Technical Foundations`
- `Structured Data`
- `Platform Optimization`

其中：

- `visibility` 被拆成 `AI 可见性` 和 `品牌权威`
- `content` 被汇总成 `内容与 E-E-A-T`
- 其余模块一对一映射到汇总维度

## Discovery 复用机制

`FullAuditService.audit_full(...)` 已支持可选 `discovery` 参数。

行为如下：

- 如果传入 `discovery`，则直接复用，不重复执行 `discover(url)`
- 如果未传入 `discovery`，才执行新的站点发现

这让异步任务、批量流程和外部编排系统可以把发现层与审计层解耦。

## GEO 评分口径

### AI 可见性 `25%`

来源字段：

- `visibility.ai_visibility_score`

当前公式：

```text
0.32 × AI crawler 放行率
+ 0.40 × snapshot citability
+ 0.12 × llms.txt 有效性
+ 0.16 × 基础实体存在
```

说明：

- `citability` 不再只看首页
- 会同时输出：
  - `homepage_citability`
  - `best_page_citability`
  - `citation_probability`
- `citation_probability` 取值：
  - `LOW`
  - `MEDIUM`
  - `HIGH`

### 品牌权威 `20%`

来源字段：

- `visibility.brand_authority_score`

当前公式：

```text
0.25 × 外链质量
+ 0.25 × 品牌提及覆盖
+ 0.25 × sameAs / Entity 一致性
+ 0.25 × 企业信息完整度
```

说明：

- 当前品牌权威仍由 `visibility` 输出
- 代码层已预留 `BrandAuthorityService`
- 这为后续独立品牌权威模块保留了服务边界

### 内容与 E-E-A-T `20%`

公式：

```text
(content_score + experience_score + expertise_score + authoritativeness_score + trustworthiness_score) / 5
```

内容评估优先复用 `discovery.page_profiles`，避免为了内容模块重复抓取同一批关键页面。

### 技术基础 `15%`

来源字段：

- `technical.technical_score`

已正式纳入：

- HTTPS
- SSR
- Meta / Canonical
- Sitemap / robots 指令
- `response_time_ms`
- render-blocking
- security headers
- image optimization
- Open Graph / Twitter Card / hreflang

### 结构化数据 `10%`

来源字段：

- `schema.structured_data_score`

优先复用 snapshot 中各页面的 JSON-LD 数据，而不是二次抓取。

### 平台适配 `10%`

来源字段：

- `platform.platform_optimization_score`

已从“简单平均”升级成“平台战略权重汇总”：

- ChatGPT Web Search `30%`
- Google AI Overviews `20%`
- Perplexity `20%`
- Google Gemini `15%`
- Bing Copilot `15%`

## Semrush Backlinks 接入

项目支持使用 [Semrush Backlinks Overview](https://developer.semrush.com/api/seo/backlinks/#backlinks-overview) 作为品牌权威的站外信号源。

环境变量：

```env
SEMRUSH_ENABLED=true
SEMRUSH_API_KEY=
SEMRUSH_BASE_URL=https://api.semrush.com/
SEMRUSH_TARGET_TYPE=root_domain
```

当前会用到的指标包括：

- `ascore`
- `backlinks_num`
- `domains_num`
- `ips_num`
- `ipclass_c_num`
- `follows_num`
- `nofollows_num`
- `sponsored_num`
- `ugc_num`

如果未配置 Semrush：

- 不会直接硬扣品牌权威总分
- 会跳过外链项，并对剩余品牌项重算权重

## 会员 AI 增强

`premium` 模式下会对以下模块执行规则结果增强：

- `visibility`
- `content`
- `platform`
- `summary`

以下模块仍保持规则制：

- `technical`
- `schema`

这样可以优先保证确定性与可解释性。

## 运行

### 本地运行

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

Demo 地址：

```text
http://127.0.0.1:8023
```

### Docker

```bash
docker build -t geo-audit-service .
docker run -d \
  --name geo-audit-service \
  -p 8023:8023 \
  --env-file .env \
  --restart unless-stopped \
  geo-audit-service:latest
```

## 环境变量

### 基础

```env
APP_ENV=development
APP_DEBUG=true
HOST=0.0.0.0
PORT=8023
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=15
REQUEST_RETRIES=3
MAX_SITEMAP_URLS=50
MAX_SITEMAP_INDEXES=10
CACHE_TTL_DAYS=7
CACHE_DIR=.cache/audits
DEFAULT_USER_AGENT=GEOAuditBot/1.0 (+https://example.com/bot)
ALLOW_PLAYWRIGHT=false
```

### AI 增强

```env
LLM_REQUEST_TIMEOUT_SECONDS=30
DEFAULT_OPENROUTER_MODEL=openai/gpt-4.1
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=http://127.0.0.1:8023
OPENROUTER_APP_NAME=geo-audit-service
```

### Semrush

```env
SEMRUSH_ENABLED=true
SEMRUSH_API_KEY=
SEMRUSH_BASE_URL=https://api.semrush.com/
SEMRUSH_TARGET_TYPE=root_domain
```

## API

统一响应包裹：

```json
{ "success": true, "data": {} }
{ "success": false, "message": "...", "errors": {} }
```

### 推荐：异步任务模式

提交审计任务：

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

查询任务：

```bash
curl http://127.0.0.1:8023/api/v1/tasks/{task_id}
```

导出报告：

```bash
curl -L http://127.0.0.1:8023/api/v1/tasks/{task_id}/report -o report.md
```

### 直接审计

完整审计：

```bash
curl -X POST http://127.0.0.1:8023/api/v1/audit/full \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

如果你已经持有 discovery 结果，也可以直接传入复用：

```json
{
  "url": "https://example.com",
  "mode": "standard",
  "discovery": {
    "...": "已有 discovery 结果"
  }
}
```

### 发现层

```bash
curl -X POST http://127.0.0.1:8023/api/v1/discovery \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

返回结果中会包含：

- `page_profiles`
- `site_snapshot_version`

## 当前状态

这套实现的目标不是替换现有 API，而是在保持兼容的前提下，让系统具备更强的 GEO 审计能力：

- 发现层从首页检查升级为站点快照
- 审计层统一模块元数据
- Citability 升级为可引用概率评估
- 品牌权威具备独立一级维度与独立服务预留
- 平台适配具备战略权重
- Demo 与 README 已同步为 GEO 报告口径
