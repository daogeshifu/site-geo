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

GEO Audit Service is an open-source audit engine built for the **AI search era**. Traditional SEO tools measure Google rankings — GEO Audit measures how likely **ChatGPT, Perplexity, Google AI Overviews, and Gemini** are to cite your site.

It builds a full **Site Snapshot** across key pages, then scores your site across 6 GEO dimensions:

| Dimension | Weight | What it measures |
|---|---|---|
| AI Citability & Visibility | 25% | Crawler access, citability probability, llms.txt |
| Brand Authority Signals | 20% | Backlinks, entity consistency, brand mentions |
| Content Quality & E-E-A-T | 20% | Experience, Expertise, Authoritativeness, Trust |
| Technical Foundations | 15% | HTTPS, SSR, Core Web Vitals, security headers |
| Structured Data | 10% | JSON-LD coverage and schema quality |
| Platform Optimization | 10% | Per-platform readiness (ChatGPT, Perplexity, etc.) |

---

## Features

- **Site Snapshot** — crawls homepage, about, services, articles, and case studies in a single pass
- **5 Audit Modules** — visibility, technical, content, schema, platform
- **Async Task API** — submit jobs, poll status, export Markdown reports
- **Discovery Reuse** — decouple crawling from scoring for batch/pipeline workflows
- **AI Enhancement** — optional LLM-powered analysis for visibility, content, platform, and summary
- **Semrush Integration** — plug in backlink authority signals via the Semrush API
- **Docker ready** — single `docker run` to production

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
  -d '{"url": "https://example.com", "mode": "standard"}'
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
  -d '{"url": "https://example.com", "mode": "standard"}'
```

Pass an existing discovery result to skip re-crawling:

```json
{
  "url": "https://example.com",
  "mode": "standard",
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

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              API Layer (FastAPI)            │
│  /tasks  /audit/full  /discovery  /report  │
└────────────────────┬────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   DiscoveryService    │  ← Site Snapshot (v2)
         │  homepage / about /   │
         │  service / article /  │
         │  case_study           │
         └───────────┬───────────┘
                     │  page_profiles[]
         ┌───────────▼───────────────────────────┐
         │           Audit Modules               │
         │  visibility · technical · content     │
         │  schema · platform                    │
         └───────────┬───────────────────────────┘
                     │  module results + metadata
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
| ChatGPT Web Search | 30% |
| Google AI Overviews | 20% |
| Perplexity | 20% |
| Google Gemini | 15% |
| Bing Copilot | 15% |

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
