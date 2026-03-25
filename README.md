<div align="center">

# 🔍 GEO Audit Service

**Generative Engine Optimization audit engine for AI-powered search visibility**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[**Live Demo →**](https://www.idtcpack.com/geo/brand-site-grader) · [Report Bug](https://github.com/your-org/geo-audit-service/issues) · [Request Feature](https://github.com/your-org/geo-audit-service/issues)

</div>

---

## What is GEO Audit?

GEO Audit Service is an open-source audit engine built for the **AI search era**. Traditional SEO tools measure Google rankings. GEO Audit v3 measures how ready your site is to be cited, extracted, and trusted by **ChatGPT, Google AI Mode, Google AI Overviews, Perplexity, Gemini, and Grok**.

It builds a full **Site Snapshot** across key pages, then scores your site across 6 GEO dimensions while keeping external observation data optional and unscored:

| Dimension | Weight | What it measures |
|---|---|---|
| AI Citability & Visibility | 25% | Crawler access, citability probability, llms.txt |
| Brand Authority Signals | 20% | Backlinks, entity consistency, brand mentions |
| Content Quality & E-E-A-T | 20% | Experience, Expertise, Authoritativeness, Trust |
| Technical Foundations | 15% | HTTPS, SSR, Core Web Vitals, security headers |
| Structured Data | 10% | JSON-LD coverage, entity graph quality, and relationship richness |
| Platform Optimization | 10% | Per-platform readiness across 6 GEO channels |

Optional observation layer:

- **Observation Layer (unscored)** — upload GA4, logs, or manual citation observations for reporting only; no upload is required, and the GEO score is unchanged when it is missing

---

## Features

- **GEO Audit v3** — separates scored readiness from optional observation metrics and adds full-audit page diagnostics
- **Site Snapshot v3** — crawls homepage, about, services, articles, and case studies in a single pass, then optionally expands to more internal pages
- **5 Audit Modules** — visibility, technical, content, schema, platform
- **6 Platform Views** — ChatGPT, Google AI Mode, Google AI Overviews, Perplexity, Gemini, and Grok
- **Entity Graph Signals** — evaluates JSON-LD coverage, stable `@id`, `sameAs`, `DefinedTerm`, and relationship richness
- **Full Audit Mode** — crawl up to `max_pages` internal pages and return `page_diagnostics` for each page
- **Scope Notice** — if the input URL is not a homepage or language homepage, the result returns a bias warning instead of force-rewriting the URL
- **Scoped Crawling** — discovery and full audit are restricted by exact `host` and locale path scope, so `www.ecoflow.com/de/` and `de.ecoflow.com/` are treated as different sites
- **Async Task API** — submit jobs, poll status, export Markdown reports
- **Discovery Reuse** — decouple crawling from scoring for batch/pipeline workflows
- **Optional Observation Layer** — attach GA4 / source breakdown / citation observations without affecting score
- **AI Enhancement** — optional LLM-powered analysis for visibility, content, platform, and summary
- **Semrush Integration** — plug in backlink authority signals via the Semrush API
- **Docker ready** — single `docker run` to production

---

## Preview

A quick look at the GEO Audit workflow and report screens:

### 1. Overview

![Overview](./preview/1%E3%80%81overview.png)

### 2. Summary

![Summary](./preview/2%E3%80%81summary.png)

### 3. Issues & TODO

![Issues and TODO](./preview/3%E3%80%81issue%26todo.png)

### 4. How to Fix

![How to Fix](./preview/4%E3%80%81how-to-fix.png)

### 5. Key Snapshot

![Key Snapshot](./preview/5%E3%80%81key-snapshot.png)

### 6. Platform

![Platform](./preview/6%E3%80%81platform.png)

### 7. Score Rule

![Score Rule](./preview/7%E3%80%81score-rule.png)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Git

Clone the repository:

```bash
git clone https://github.com/your-org/geo-audit-service.git
cd geo-audit-service
cp .env.example .env
```

---

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

---

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

---

### Windows

**Command Prompt (cmd)**
 
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

**PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

> If you see a PowerShell execution policy error, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---


### Docker

#### Option A — Load pre-built image (no Docker Hub required)

> This is useful if you cannot access Docker Hub from your network.

**Linux / AMD64**

```bash
wget https://www.idtcpack.com/geo-audit-service-amd64.tar
docker load -i geo-audit-service-amd64.tar
```

**macOS / ARM (Apple Silicon)**

```bash
wget https://www.idtcpack.com/geo-audit-service-arm.tar
docker load -i geo-audit-service-arm.tar
```

#### Option B — Build from source

```bash
docker build -t geo-audit-service .
```

#### Run

After loading or building the image:

```bash
docker run -d \
  --name geo-audit-service \
  -p 8023:8023 \
  --env-file .env \
  --restart unless-stopped \
  geo-audit-service:latest
```

Once running, open [http://127.0.0.1:8023/docs](http://127.0.0.1:8023/docs) to explore the interactive API docs.

---

## Configuration

Copy `.env.example` to `.env` and fill in the values you need.

### Core

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

### AI Enhancement (optional)

Enables LLM-powered analysis for visibility, content, platform, and summary modules.

```env
LLM_REQUEST_TIMEOUT_SECONDS=30
DEFAULT_OPENROUTER_MODEL=openai/gpt-4.1
OPENROUTER_API_KEY=your_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=http://127.0.0.1:8023
OPENROUTER_APP_NAME=geo-audit-service
```

### Semrush Backlinks (optional)

Adds external backlink authority signals to the Brand Authority score.

```env
SEMRUSH_ENABLED=true
SEMRUSH_API_KEY=your_key_here
SEMRUSH_BASE_URL=https://api.semrush.com/
SEMRUSH_TARGET_TYPE=root_domain
```

> When `SEMRUSH_ENABLED=false`, the backlink sub-score is skipped and remaining brand authority weights are redistributed automatically.

---

## API Reference

All responses use a unified envelope:

```json
{ "success": true, "data": { ... } }
{ "success": false, "message": "...", "errors": { ... } }
```

### Recommended: Async Task Mode

**Submit an audit job**

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "mode": "standard", "full_audit": true, "max_pages": 12}'
```

Full `tasks/audit` example:

```json
{
  "url": "https://www.ecoflow.com/de/",
  "mode": "premium",
  "full_audit": true,
  "max_pages": 20,
  "force_refresh": false,
  "llm": {
    "provider": "openrouter",
    "model": "openai/gpt-4.1"
  }
}
```

**Poll for status**

```bash
curl http://127.0.0.1:8023/api/v1/tasks/{task_id}
```

**Export Markdown report**

```bash
curl -L http://127.0.0.1:8023/api/v1/tasks/{task_id}/report -o report.md
```

---

### Direct Audit (synchronous)

```bash
curl -X POST http://127.0.0.1:8023/api/v1/audit/full \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "mode": "standard", "full_audit": true, "max_pages": 12}'
```

Full `audit/full` example:

```json
{
  "url": "https://www.ecoflow.com/de/",
  "mode": "standard",
  "full_audit": true,
  "max_pages": 12
}
```

Pass an existing discovery result to skip re-crawling:

```json
{
  "url": "https://example.com",
  "mode": "standard",
  "full_audit": true,
  "max_pages": 12,
  "discovery": { "...": "existing discovery payload" }
}
```

---

### Discovery Only

Run just the site snapshot layer without a full audit:

```bash
curl -X POST http://127.0.0.1:8023/api/v1/discovery \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

Response includes `page_profiles` and `site_snapshot_version` for all crawled pages.

### Full Audit Mode

Full audit is optional. Most users only need:

```json
{ "url": "https://example.com", "mode": "standard" }
```

If you want page-level diagnostics, enable `full_audit` and set `max_pages`:

```json
{
  "url": "https://example.com",
  "mode": "standard",
  "full_audit": true,
  "max_pages": 12
}
```

When enabled, the response adds:

- `discovery.full_audit_enabled`
- `discovery.profiled_page_count`
- `discovery.additional_page_profiles`
- `discovery.scope_root_url`
- `result.page_diagnostics[]`

If the input URL is not a homepage or a language-homepage path such as `/en` or `/zh-cn`, the result also returns `discovery.input_scope_warning` and `summary.notices[]` to indicate that site-level scores may be biased.

### Crawl Scope Rules

Discovery and full audit do not crawl the whole registrable domain. They stay inside one crawl scope:

- exact `host` must match
- if the input starts with a locale prefix such as `/de/`, `/en/`, or `/zh-cn/`, crawling stays inside that prefix

Examples:

- `https://de.ecoflow.com/` only crawls `de.ecoflow.com`
- `https://www.ecoflow.com/de/` only crawls `www.ecoflow.com/de/`
- `https://www.ecoflow.com/de/` will not crawl `https://de.ecoflow.com/`
- `https://www.ecoflow.com/de/` will not crawl `https://www.ecoflow.com/fr/`

### Optional Observation Input

Observation data is optional. Most users only need:

```json
{ "url": "https://example.com" }
```

If you have measurement data, you can attach it to `tasks/audit`, `audit/full`, or `audit/summarize`:

```json
{
  "url": "https://example.com",
  "observation": {
    "data_period": "2026-Q1",
    "ga4_ai_sessions": 240,
    "ga4_ai_conversions": 12,
    "source_breakdown": [
      { "platform": "chatgpt", "sessions": 110, "conversions": 7 },
      { "platform": "perplexity", "sessions": 45, "conversions": 2 }
    ],
    "citation_observations": [
      { "platform": "chatgpt", "query": "best geo audit tools", "cited": true, "position": 2 }
    ]
  }
}
```

This data is displayed in the report as an **Observation Layer** and does **not** change the composite GEO score.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              API Layer (FastAPI)            │
│  /tasks  /audit/full  /discovery  /report  │
└────────────────────┬────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   DiscoveryService    │  ← Site Snapshot (v3)
         │  homepage / about /   │
         │  service / article /  │
         │  case_study / extras  │
         └───────────┬───────────┘
                     │  page_profiles[] + optional page_diagnostics
         ┌───────────▼───────────────────────────┐
         │           Audit Modules               │
         │  visibility · technical · content     │
         │  schema · platform                    │
         └───────────┬───────────────────────────┘
                     │  module results + metadata
         ┌───────────▼───────────┐
         │ Observation Layer     │  ← Optional, unscored
         │ GA4 / logs / manual   │
         │ citation evidence     │
         └───────────┬───────────┘
                     │  contextual metrics only
         ┌───────────▼───────────┐
         │    Summary Engine     │  ← 6 GEO dimensions
         │    + AI Enhancement   │    (premium mode)
         └───────────────────────┘
```

### Scoring — AI Visibility (25%)

```
0.32 × AI crawler allowance
+ 0.40 × snapshot citability (multi-page)
+ 0.12 × llms.txt validity
+ 0.16 × entity signal presence
```

Citability outputs: `homepage_citability`, `best_page_citability`, `citation_probability` (`LOW` / `MEDIUM` / `HIGH`)

### Scoring — Brand Authority (20%)

```
0.25 × backlink quality (Semrush)
+ 0.25 × brand mention coverage
+ 0.25 × sameAs / entity consistency
+ 0.25 × business information completeness
```

### Scoring — Platform Optimization (10%)

| Platform | Weight |
|---|---|
| ChatGPT | 22% |
| Google AI Mode | 18% |
| Google AI Overviews | 18% |
| Perplexity | 16% |
| Gemini | 13% |
| Grok | 13% |

### Scoring — Structured Data & Entity Graph (10%)

The structured-data module in v3 goes beyond simple Schema presence checks. It now considers:

- JSON-LD baseline coverage
- `Organization`, `WebSite`, `Service`, `Article`, `FAQPage`, `Product`, `DefinedTerm`
- `sameAs` coverage
- stable entity `@id`
- relationship richness such as `brand`, `manufacturer`, `hasPart`, `offers`, `about`, `contactPoint`

### Observation Layer (Unscored)

When provided, the observation layer can display:

- GA4 AI-attributed sessions / conversions / revenue
- source-platform traffic breakdown
- manual or system-recorded citation observations

It is **never included** in the GEO composite score.

---

## Audit Modes

| Mode | Description |
|---|---|
| `standard` | Rule-based scoring across all 5 modules |
| `premium` | Standard + LLM enhancement for visibility, content, platform, and summary |

`technical` and `schema` modules always use deterministic rule-based scoring for consistency.

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit your changes (`git commit -m 'feat: add your feature'`)
4. Push and open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for the AI search era · [Live Demo](https://www.idtcpack.com/geo/brand-site-grader)

</div>
