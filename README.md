# GEO Audit Service

> Open-source GEO / AI-SEO audit engine powering [idtcpack.com](https://www.idtcpack.com/) — analyze how well your site performs in AI-driven search (ChatGPT, Perplexity, Google AI Overviews, Gemini, and Bing Copilot).

**Python 3.11+ · FastAPI · Stateless · Docker-ready**

---

## What it does

Runs a full GEO audit pipeline against any URL and scores five dimensions:

| Module | What's measured |
|---|---|
| **Visibility** | AI crawler access, llms.txt, citability, brand authority |
| **Technical** | HTTPS, SSR, security headers, sitemap, meta/OG tags, image optimization |
| **Content** | Word depth, E-E-A-T signals, FAQ, author, publish date, answer-first structure |
| **Schema** | JSON-LD coverage — Organization, Article, FAQPage, Service, WebSite, sameAs |
| **Platform** | Per-platform readiness for Google AI Overviews, ChatGPT, Perplexity, Gemini, Bing Copilot |

Two execution modes:

- **`standard`** — deterministic rule/heuristic scoring, no external calls
- **`premium`** — rule baseline + LLM semantic enrichment via [OpenRouter](https://openrouter.ai/)

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/your-org/geo-audit-service.git
cd geo-audit-service
cp .env.example .env
```

Open `.env` and set the one required key:

```env
OPENROUTER_API_KEY=sk-or-xxxxx
```

### 2. Run

**Local (Python)**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8023
```

**Docker — Build from source**

```bash
docker build -t geo-audit-service .
docker run -d \
  --name geo-audit-service \
  -p 8023:8023 \
  --env-file .env \
  --restart unless-stopped \
  geo-audit-service:latest
```

**Docker — 国内服务器离线镜像（Linux amd64）**

```bash
wget http://dtcpack.cn/geo-audit-service-amd64.tar
docker load -i geo-audit-service-amd64.tar
docker run -d \
  --name geo-audit-service \
  -p 8023:8023 \
  --env-file /home/html/site-geo/.env \
  --restart unless-stopped \
  geo-audit-service:latest
```

**Docker — 国内服务器离线镜像（Mac arm64）**

```bash
wget http://dtcpack.cn/geo-audit-service-arm.tar
docker load -i geo-audit-service-arm.tar
docker run -d \
  --name geo-audit-service \
  -p 8023:8023 \
  --env-file /home/html/site-geo/.env \
  --restart unless-stopped \
  geo-audit-service:latest
```

Open the built-in demo UI: `http://127.0.0.1:8023`

---

## Environment Variables

Copy `.env.example` to `.env` and set:

```env
OPENROUTER_API_KEY=sk-or-xxxxx          # required for premium mode
DEFAULT_OPENROUTER_MODEL=openai/gpt-4.1
OPENROUTER_SITE_URL=http://127.0.0.1:8023
OPENROUTER_APP_NAME=geo-audit-service
```

Other available variables: `APP_ENV`, `APP_DEBUG`, `LOG_LEVEL`, `REQUEST_TIMEOUT_SECONDS`, `CACHE_TTL_DAYS`, `CACHE_DIR`, `MAX_SITEMAP_URLS`, `ALLOW_PLAYWRIGHT`.

---

## API

All responses use a unified envelope:

```json
{ "success": true, "data": {} }
{ "success": false, "message": "...", "errors": {} }
```

### Async task mode (recommended)

```bash
# 1. Create task
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'

# 2. Poll until status = "completed"
curl http://127.0.0.1:8023/api/v1/tasks/{task_id}

# 3. Export Markdown report
curl -L http://127.0.0.1:8023/api/v1/tasks/{task_id}/report -o report.md
```

Premium mode (LLM enrichment):

```bash
curl -X POST http://127.0.0.1:8023/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"premium","llm":{"provider":"openrouter","model":"openai/gpt-4.1"}}'
```

### Single-module endpoints

```
POST /api/v1/audit/visibility
POST /api/v1/audit/technical
POST /api/v1/audit/content
POST /api/v1/audit/schema
POST /api/v1/audit/platform
POST /api/v1/audit/full        # all modules + summary, synchronous
POST /api/v1/audit/summarize
POST /api/v1/discovery
POST /api/v1/report/export
```

### Task pipeline execution order

```
discovery → [visibility, technical, content, schema, platform] (parallel) → summary
```

Results are cached per domain for 7 days. Pass `force_refresh: true` to bypass.

---

## Scoring

Scores are 0–100, classified as:

`critical` (0–24) · `poor` (25–44) · `fair` (45–64) · `good` (65–84) · `strong` (85–100)

---

## Tests

```bash
pytest
```

---

## Hosted Version

Want a managed version with dashboard, history, and PDF reports?

**→ [idtcpack.com](https://www.idtcpack.com/)**

---

## License

MIT
