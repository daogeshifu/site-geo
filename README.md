# GEO Audit Service

面向 GEO / AI Search 的网站审计服务，支持异步任务、规则评分、会员 AI 增强，以及可视化 Demo 报告页。

当前服务围绕 6 个汇总层输出最终综合分：

- AI 可见性 `25%`
- 品牌权威 `20%`
- 内容与 E-E-A-T `20%`
- 技术基础 `15%`
- 结构化数据 `10%`
- 平台适配 `10%`

## 核心能力

### 1. 发现层

自动抓取并汇总：

- 首页元数据、标题结构、图片、脚本、样式、JSON-LD
- `robots.txt`
- `llms.txt`
- `sitemap.xml`
- 关键页面识别：`about / service / contact / article / case_study`
- 站点品牌信号：公司名、电话、邮箱、地址、资质、sameAs
- 可选站外权威信号：Semrush Backlinks Overview

### 2. 审计层

并行执行 5 个审计模块：

- `visibility`
- `technical`
- `content`
- `schema`
- `platform`

### 3. 汇总层

将审计结果映射为 6 个业务维度综合分，而不是简单按 5 个模块平均。

## 评分口径

### AI 可见性 `25%`

原始分取自 `visibility.ai_visibility_score`。

公式：

```text
0.32 × AI crawler 放行率
+ 0.40 × citability
+ 0.12 × llms.txt 有效性
+ 0.16 × 基础实体存在
```

说明：

- `citability` 看 `title / meta / H1 / canonical / headings>=3 / 字数>=250`
- `llms.txt` 不只看存在，还看长度、品牌词、服务说明、machine-facing guidance
- `基础实体存在` 看公司名、about、contact、基础联系方式

### 品牌权威 `20%`

原始分取自 `visibility.brand_authority_score`。

公式：

```text
0.25 × 外链质量
+ 0.25 × 品牌提及覆盖
+ 0.25 × sameAs / Entity 一致性
+ 0.25 × 企业信息完整度
```

说明：

- 外链质量来自 Semrush Backlinks Overview，可选接入
- 若未配置 Semrush，不会直接扣分，而是跳过该项并按剩余项重算权重
- Entity 一致性会检查 sameAs、Organization schema、品牌名一致性、sitemap 与主域一致性

### 内容与 E-E-A-T `20%`

汇总层公式：

```text
(content_score + experience_score + expertise_score + authoritativeness_score + trustworthiness_score) / 5
```

内容模块主要覆盖：

- 服务页/文章页深度
- FAQ、作者、发布日期
- 量化数据、案例、answer-first
- 标题结构质量
- E-E-A-T 五类子分

### 技术基础 `15%`

原始分取自 `technical.technical_score`。

当前技术权重：

```text
HTTPS 8
SSR 10
Meta 5
Canonical 5
lang 4
viewport 4
Sitemap 8
robots Sitemap 指令 4
Performance 8
Render Blocking 8
Security Headers 16
Image Optimization 8
Open Graph 5
Twitter Card 3
hreflang 4
```

说明：

- `response_time_ms` 已纳入正式性能评分
- 图片优化按 `lazyload` 比例与显式尺寸比例各占 50%
- SSR 使用 HTML 长度与字数联合判断

### 结构化数据 `10%`

原始分取自 `schema.structured_data_score`。

当前规则：

```text
JSON-LD 20
Organization 20
LocalBusiness 10
Article 15
FAQPage 10
Service 10
WebSite 10
sameAs 5
```

### 平台适配 `10%`

原始分取自 `platform.platform_optimization_score`。

不再按 5 平台简单平均，而是按平台战略权重汇总：

```text
ChatGPT Web Search 30%
Google AI Overviews 20%
Perplexity 20%
Google Gemini 15%
Bing Copilot 15%
```

每个平台仍保留自己的 readiness 分数、主缺口和建议。

## 会员 AI 增强

`premium` 模式下会对以下模块执行规则结果增强：

- `visibility`
- `content`
- `platform`
- `summary`

`technical` 与 `schema` 仍保持规则制，优先保证可解释性与确定性。

## Semrush 外链接入

项目支持用 [Semrush Backlinks Overview](https://developer.semrush.com/api/seo/backlinks/#backlinks-overview) 作为品牌权威的站外信号源。

新增环境变量：

```env
SEMRUSH_ENABLED=true
SEMRUSH_API_KEY=
SEMRUSH_BASE_URL=https://api.semrush.com/
SEMRUSH_TARGET_TYPE=root_domain
```

当前使用字段：

- `ascore`
- `backlinks_num`
- `domains_num`
- `ips_num`
- `ipclass_c_num`
- `follows_num`
- `nofollows_num`
- `sponsored_num`
- `ugc_num`

外链质量评分主要参考：

- Authority Score
- Referring Domains
- Referring IP / C-Class 多样性
- Follow Ratio

## 运行

### 本地运行

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

打开 Demo：

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

基础：

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

AI 增强：

```env
LLM_REQUEST_TIMEOUT_SECONDS=30
DEFAULT_OPENROUTER_MODEL=openai/gpt-4.1
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=http://127.0.0.1:8023
OPENROUTER_APP_NAME=geo-audit-service
```

Semrush：

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

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

```bash
curl http://127.0.0.1:8023/api/v1/tasks/{task_id}
```

```bash
curl -L http://127.0.0.1:8023/api/v1/tasks/{task_id}/report -o report.md
```

会员模式：

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"premium","llm":{"provider":"openrouter","model":"openai/gpt-4.1"}}'
```

### 单模块接口

```text
POST /api/v1/discovery
POST /api/v1/audit/visibility
POST /api/v1/audit/technical
POST /api/v1/audit/content
POST /api/v1/audit/schema
POST /api/v1/audit/platform
POST /api/v1/audit/full
POST /api/v1/audit/summarize
POST /api/v1/report/export
```

### 执行顺序

```text
discovery -> [visibility, technical, content, schema, platform] -> summary
```

## 分级标准

```text
critical  0-24
poor      25-44
fair      45-64
good      65-84
strong    85-100
```

## 测试

```bash
pytest
```

如果本地环境未安装 `pytest`，请先安装依赖后再运行。

## License

MIT
