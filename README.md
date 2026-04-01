<div align="center">

# GEO Audit Service

## 出海站点救星

### 外贸独立站如何快速接入 AI，从“能被搜索”升级到“能被引用”

让品牌官网不只是上线可见，更能被 **ChatGPT、Google AI Mode、Google AI Overviews、Perplexity、Gemini 和 Grok** 访问、理解、提取、引用与信任。

**一个面向 GEO 时代的站点审计引擎**  
帮助出海品牌、外贸独立站、跨境 SaaS 和内容团队快速回答：

- 你的站点有没有被主流 AI crawler 放行
- 你的页面是不是足够适合被 AI 摘要、引用和复述
- 你的品牌实体、结构化数据和内容深度够不够支撑 AI 信任
- 你的官网距离“AI 可见、AI 可引用、AI 可推荐”还有多远

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[**Live Demo**](https://www.idtcpack.com/geo/brand-site-grader) · [Report Bug](https://github.com/your-org/geo-audit-service/issues) · [Request Feature](https://github.com/your-org/geo-audit-service/issues)

</div>

---

## 为什么不是传统 SEO 工具

传统 SEO 工具主要回答：

- 你有没有排名
- 关键词位置有没有变化

GEO Audit 关注的是另一层问题：

- AI 系统能不能访问你的内容
- AI 能不能理解你的实体、页面和关系
- 你的页面够不够适合被抽取、引用和复述
- 你的品牌是否足够可信，能作为答案来源被采用

对出海站点来说，这意味着你不只是“有页面”，而是要成为 **AI 产品中的可信答案源**。

---

## 核心能力

### 1. Site Snapshot 发现层

系统不再只抓首页，而是构建站点级快照：

- `homepage`
- `about`
- `service`
- `article/news`
- `case_study`

并为页面生成统一画像：

- `title / meta_description / canonical / lang`
- `headings / word_count`
- `has_faq / has_author / has_publish_date`
- `has_quantified_data / answer_first / has_tldr / has_update_log`
- `has_reference_section / has_inline_citations`
- `internal_link_count / external_link_count / descriptive_link_ratios`
- `heading_quality_score / information_density_score / chunk_structure_score`
- `json_ld_summary / entity_signals`

### 2. 5 个审计模块

- `visibility`
- `technical`
- `content`
- `schema`
- `platform`

### 3. 6 个汇总维度

| 维度 | 权重 | 说明 |
|---|---:|---|
| AI 可见性 | 25% | AI crawler 放行、citability、llms 指引、基础实体存在 |
| 品牌权威 | 20% | 外链质量、品牌提及、实体一致性、企业信息完整度 |
| 内容与 E-E-A-T | 20% | 内容深度、作者、日期、FAQ、数据点、证据引用、链接语义、结构质量 |
| 技术基础 | 15% | HTTPS、SSR、性能、Sitemap、安全头、图片、唯一 H1 与 freshness headers |
| 结构化数据 | 10% | JSON-LD、Organization、Article、Service、sameAs、机器日期、可见内容一致性 |
| 平台适配 | 10% | 面向 ChatGPT、Google AI、Perplexity、Gemini、Grok 的 readiness |

### 4. Full Audit 扩展诊断

除了站点级评分，系统还可以扩展采样更多页面，并返回：

- `page_diagnostics`

用于逐页查看：

- citability
- content
- technical
- schema
- overall score

### 5. AI 认知快照

`summary` 现在会额外返回一组不计分的站点级 AI 认知画像：

- `ai_perception.positive_percentage`
- `ai_perception.neutral_percentage`
- `ai_perception.controversial_percentage`
- `ai_perception.cognition_keywords`

用于描述 AI 可能如何“理解”该站点，例如更像：

- 行业先知
- 反应迅速
- 证据充分
- 结构清晰

### 6. Discovery Reuse

`audit_full` 支持直接复用传入的 `discovery`，避免重复抓取，方便：

- 批量任务
- 管道式处理
- 外部编排系统

### 7. 会员 AI 增强

`premium` 模式下可对以下模块做语义增强：

- `visibility`
- `content`
- `platform`
- `summary`

`technical` 和 `schema` 仍保持规则驱动，优先保证确定性。

### 8. 研究导向补强

在保持现有诊断层与表达层结构不变的前提下，v3 额外补充了几类更贴近论文观点的规则信号：

- `机器可读新鲜度`：响应头中的 `ETag / Last-Modified`，以及 Schema 中的 `datePublished / dateModified`
- `语义化 HTML`：唯一 `H1` 与标题层级质量联合判断
- `Schema 一致性`：JSON-LD 文本与页面可见内容的一致性评分
- `证据与引用`：参考资料区、内联引用、TL;DR、更新记录
- `RAG 友好链接`：内部/外部链接数量与描述性锚文本比例

---

## GEO Audit v3 的设计重点

### 从“首页检测”升级为“站点快照”

不再只看首页，而是围绕关键页面做判断，真正更像 GEO 审计引擎。

### 从“SEO 结构检查”升级为“AI 可引用性”

系统会输出：

- `homepage_citability`
- `best_page_citability`
- `citation_probability`

其中 `citation_probability` 为：

- `LOW`
- `MEDIUM`
- `HIGH`

### 从“基础结构化数据”升级为“机器可读一致性”

结构化数据不再只检查 `@type` 是否存在，还会额外关注：

- `BreadcrumbList`
- `datePublished / dateModified`
- `visible_alignment_score`

也就是：

- 机器是否能读到发布时间或更新时间
- Schema 中的名称、描述、FAQ 和主张是否和页面可见内容一致

这是一次必要的评分公式调整，但没有改变原有返回结构，只是补强了 `schema.checks / findings / recommendations` 的语义。

### 从“基础内容深度”升级为“证据与检索上下文”

内容层除了词数、FAQ、作者、日期、量化数据之外，还会补看：

- `has_reference_section`
- `has_inline_citations`
- `has_tldr`
- `has_update_log`
- `descriptive_internal_link_ratio`
- `descriptive_external_link_ratio`

这些信号用于更贴近论文中的：

- `Evidence & Citations`
- `RAG-friendly internal/external linking`
- `UX / microcontent / answer-first`

### 从“品牌存在”升级为“品牌权威”

品牌权威已经作为独立一级维度存在，并预留了：

- `BrandAuthorityService`

后续可以进一步拆成独立服务。

### 从“统一站点评分”升级为“平台适配”

当前支持 6 个 GEO 渠道视角：

- ChatGPT
- Google AI Mode
- Google AI Overviews
- Perplexity
- Gemini
- Grok

---

## Preview

### 1. Overview

![Overview](./preview/1%E3%80%81overview.png)

### 2. Summary

![Summary](./preview/2%E3%80%81summary.png)

### 3. Issues and TODO

![Issues and TODO](./preview/3%E3%80%81issue%26todo.png)

### 4. How to Fix

![How to Fix](./preview/4%E3%80%81how-to-fix.png)

### 5. Key Snapshot

![Key Snapshot](./preview/5%E3%80%81key-snapshot.png)

---

## 技术栈

- Python 3.10+
- FastAPI
- Pydantic
- Async task pipeline
- Optional OpenRouter LLM enhancement
- Optional Semrush backlink enrichment

---

## 运行方式

### 本地运行

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

访问：

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

---

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

---

## API

统一响应格式：

```json
{ "success": true, "data": {} }
{ "success": false, "message": "...", "errors": {} }
```

### 推荐：异步任务模式

提交任务：

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

查询任务：

```bash
curl http://127.0.0.1:8023/api/v1/tasks/{task_id}
```

完成后的 `result.summary` 会包含：

```json
{
  "composite_geo_score": 70,
  "status": "good",
  "summary": "...",
  "ai_perception": {
    "positive_percentage": 58,
    "neutral_percentage": 29,
    "controversial_percentage": 13,
    "cognition_keywords": ["Thought Leader", "Well-structured", "Evidence-led", "Trustworthy"]
  }
}
```

说明：

- `ai_perception` 不参与综合分计算
- 三个百分比相加恒为 `100`
- `cognition_keywords` 固定返回 4 个词
- `feedback_lang="zh"` 时，这些词会尽量中文化；JSON key 保持英文

导出报告：

```bash
curl -L http://127.0.0.1:8023/api/v1/tasks/{task_id}/report -o report.md
```

### 直接调用完整审计

```bash
curl -X POST http://127.0.0.1:8023/api/v1/audit/full \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

同步完整审计返回中同样包含 `summary.ai_perception`。

### 单独调用 discovery

```bash
curl -X POST http://127.0.0.1:8023/api/v1/discovery \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

---

## 适用场景

- 出海品牌官网 GEO 体检
- 外贸独立站 AI 可见性诊断
- 跨境 SaaS 官网内容与实体信号排查
- 代理商给客户做 GEO 报告
- 内部增长团队做站点 readiness 基线检查

---

## 一句话总结

**GEO Audit 不只是检查你的网站“有没有写对 SEO”，而是判断你的站点是否已经准备好进入 AI 搜索时代。**
