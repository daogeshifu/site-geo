# GEO Audit Service

Python 3.11+ FastAPI service for GEO / AI SEO auditing. This service is stateless and is designed to be called by Laravel for discovery, modular audits, and final synthesis.

## Features

- Async discovery pipeline for homepage, robots.txt, sitemap.xml, llms.txt, and metadata extraction
- Independent audit endpoints for `visibility`, `technical`, `content`, `schema`, and `platform`
- Full audit endpoint that runs discovery, concurrent module audits, and final synthesis
- Dual execution modes:
  - `standard`: rules-only, deterministic scoring
  - `premium`: rules + optional LLM semantic enrichment
- Premium mode uses OpenRouter as the unified LLM gateway
- Model switching is done by changing the OpenRouter model id, without changing provider integrations
- Unified JSON response envelope for Laravel polling and step-by-step rendering
- Clear service layering for maintainability and future external scanner integrations
- Dockerfile and pytest samples for local and CI execution

## Project Structure

```text
project_root/
  app/
    main.py
    core/
      config.py
      logging.py
      exceptions.py
    api/
      routes/
        health.py
        discovery.py
        audit.py
    models/
      requests.py
      responses.py
      discovery.py
      audit.py
    services/
      discovery_service.py
      audit_service.py
      visibility_service.py
      technical_service.py
      content_service.py
      schema_service.py
      platform_service.py
      scoring_service.py
      summarizer_service.py
    utils/
      url_utils.py
      fetcher.py
      html_parser.py
      robots_parser.py
      sitemap_parser.py
      llms_parser.py
      schema_extractor.py
      text_analyzer.py
      security_headers.py
      heuristics.py
  tests/
  requirements.txt
  Dockerfile
  README.md
```

## Requirements

- Python 3.11+
- pip

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Default base URL:

```text
http://127.0.0.1:8000
```

## Docker Run

```bash
docker build -t geo-audit-service .
docker run --rm -p 8000:8000 geo-audit-service
```

## Test

```bash
pytest
```

## API Overview

All endpoints return a unified envelope.

Successful response:

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

Error response:

```json
{
  "success": false,
  "message": "error message",
  "errors": {}
}
```

Endpoints:

- `GET /`
- `GET /health`
- `POST /api/v1/discovery`
- `POST /api/v1/audit/visibility`
- `POST /api/v1/audit/technical`
- `POST /api/v1/audit/content`
- `POST /api/v1/audit/schema`
- `POST /api/v1/audit/platform`
- `POST /api/v1/audit/full`
- `POST /api/v1/audit/summarize`
- `POST /api/v1/tasks/audit`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/report/export`
- `GET /api/v1/tasks/{task_id}/report`

## Execution Modes

All request models now support:

```json
{
  "url": "https://example.com",
  "mode": "standard"
}
```

Premium mode:

```json
{
  "url": "https://example.com",
  "mode": "premium",
  "llm": {
    "provider": "openrouter",
    "model": "openai/gpt-4.1"
  }
}
```

Behavior:

- `standard`: only parser/rule/heuristic logic is used
- `premium`: rule engine runs first, then semantic-heavy modules are enriched with LLM analysis
- Premium mode calls OpenRouter only
- If premium is requested but OpenRouter is not configured, the API falls back gracefully and returns `llm_enhanced: false` plus `processing_notes`

Recommended premium models currently exposed in the demo page:

- `openai/gpt-4.1`
- `deepseek/deepseek-v3.2`
- `anthropic/claude-sonnet-4.6`

Current premium LLM enrichment scope:

- `visibility`
- `content`
- `platform`
- `summarize`

Current deterministic-only modules:

- `technical`
- `schema`

## Laravel Integration

Recommended step-by-step flow:

1. Laravel calls `POST /api/v1/discovery`.
2. Laravel stores the returned discovery JSON.
3. Laravel calls each audit endpoint independently with `url` and optional `discovery`.
4. As each module finishes, Laravel can render that result directly on the frontend.
5. After collecting all module outputs, Laravel calls `POST /api/v1/audit/summarize`.

Alternative one-shot flow:

1. Laravel calls `POST /api/v1/audit/full`.
2. Laravel stores the full payload and renders the final report.

Important notes:

- All endpoints are stateless.
- Laravel should persist discovery and audit results.
- Laravel can poll the service or dispatch background queue jobs per step.
- The Python service does not implement WebSocket streaming.

## Async Task Mode

The service now includes a background task mode for browser demos or polling-based integrations.

Design choice:

- Poll by `task_id`, not by domain
- Reason: a domain may have concurrent runs, force-refresh runs, standard and premium runs, or different premium providers/models
  - In the current implementation, premium cache separation is primarily by OpenRouter model id

Task behavior:

- `POST /api/v1/tasks/audit` creates a background task
- `GET /api/v1/tasks/{task_id}` returns live step progress
- Execution order:
  - discovery
  - visibility / technical / content / schema / platform in parallel
  - summary
- If the same domain has a valid cache entry within 7 days, the task is returned immediately as completed
- If `force_refresh=true`, cache is ignored and a new task is executed

Task request example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{
    "url":"https://example.com",
    "mode":"standard",
    "force_refresh":false
  }'
```

Premium task example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/audit \
  -H "Content-Type: application/json" \
  -d '{
    "url":"https://example.com",
    "mode":"premium",
    "force_refresh":true,
    "llm":{"provider":"openrouter","model":"openai/gpt-4.1"}
  }'
```

There is also a built-in demo page at `GET /`:

- choose normal or premium mode
- enter a URL
- optionally force refresh
- click start
- the page polls the task endpoint and renders step-by-step results dynamically
- once the task completes, click `导出报告` to download a Markdown report

## Report Export

The export report feature is designed to cover every major dimension present in the reference `geo-seo-claude` client report, including:

- Executive Summary
- Score Dashboard
- AI Platform Readiness
- Critical Findings
- Strengths to Build On
- E-E-A-T Assessment
- Technical Audit Summary
- Prioritized Action Plan
- Implementation Roadmap
- Projected Score After Full Implementation
- Appendix: Site Facts

Export by completed task:

```bash
curl -L http://127.0.0.1:8000/api/v1/tasks/<task_id>/report -o geo-report.md
```

Export from existing saved JSON payloads:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/report/export \
  -H "Content-Type: application/json" \
  -d @report-payload.json
```

The `POST /api/v1/report/export` response returns:

- `filename`
- `markdown`

## Example Requests

Discovery:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/discovery \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

Full audit:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/audit/full \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","mode":"standard"}'
```

Premium full audit with OpenRouter:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/audit/full \
  -H "Content-Type: application/json" \
  -d '{
    "url":"https://example.com",
    "mode":"premium",
    "llm":{"provider":"openrouter","model":"openai/gpt-4.1"}
  }'
```

Premium examples for other model families through OpenRouter:

```json
{"provider":"openrouter","model":"anthropic/claude-3.5-sonnet"}
{"provider":"openrouter","model":"google/gemini-2.0-flash-001"}
{"provider":"openrouter","model":"meta-llama/llama-3.1-70b-instruct"}
```

## .env Setup

The service now supports `.env` directly. The config layer auto-loads `.env` at startup.

1. Copy the example file:

```bash
cp .env.example .env
```

2. Edit `.env` and set your OpenRouter key:

```env
OPENROUTER_API_KEY=sk-or-xxxxx
DEFAULT_OPENROUTER_MODEL=openai/gpt-4.1
OPENROUTER_SITE_URL=http://127.0.0.1:8000
OPENROUTER_APP_NAME=geo-audit-service
```

3. Start the server:

```bash
.venv/bin/uvicorn app.main:app --reload
```

## OpenRouter Key Setup By Environment Variable

If you do not want to use `.env`, you can still export variables in the current shell:

```bash
export OPENROUTER_API_KEY="sk-or-xxxxx"
export OPENROUTER_SITE_URL="http://127.0.0.1:8000"
export OPENROUTER_APP_NAME="geo-audit-service"
```

If you want it to persist across terminal sessions, add it to `~/.zshrc`:

```bash
echo 'export OPENROUTER_API_KEY="sk-or-xxxxx"' >> ~/.zshrc
echo 'export OPENROUTER_SITE_URL="http://127.0.0.1:8000"' >> ~/.zshrc
echo 'export OPENROUTER_APP_NAME="geo-audit-service"' >> ~/.zshrc
source ~/.zshrc
```

Validation:

```bash
cat .env
```

Or, if using exported env vars:

```bash
echo $OPENROUTER_API_KEY
```

## Environment Variables

- `APP_NAME`
- `APP_ENV`
- `APP_DEBUG`
- `HOST`
- `PORT`
- `LOG_LEVEL`
- `REQUEST_TIMEOUT_SECONDS`
- `REQUEST_RETRIES`
- `MAX_SITEMAP_URLS`
- `MAX_SITEMAP_INDEXES`
- `CACHE_TTL_DAYS`
- `CACHE_DIR`
- `DEFAULT_USER_AGENT`
- `ALLOW_PLAYWRIGHT`
- `LLM_REQUEST_TIMEOUT_SECONDS`
- `DEFAULT_OPENROUTER_MODEL`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_SITE_URL`
- `OPENROUTER_APP_NAME`

## Implementation Notes

- Playwright is intentionally not enabled in the first version, but the config flag is reserved for future rendering support.
- Business type detection, SSR detection, brand authority scoring, answer-first detection, and platform readiness are heuristic-first implementations.
- Premium mode is implemented as LLM enrichment on top of rule outputs, which keeps the service stateless and preserves explainable baseline scoring.
- Premium mode now routes through OpenRouter as the single LLM gateway, so model switching only requires changing `llm.model`.
- The service is structured so external enrichments can be added later without changing the API shape.
