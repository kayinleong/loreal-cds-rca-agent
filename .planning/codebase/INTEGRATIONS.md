# External Integrations

**Analysis Date:** 2026-04-24

## APIs & External Services

**LLM Providers (rca_agent only):**
- Anthropic Claude API — LLM reasoning for the autonomous ReAct agent loop
  - SDK/Client: `anthropic` >= 0.40.0 (lazy import in `rca_agent/llm_providers.py::AnthropicProvider`)
  - Auth: `ANTHROPIC_API_KEY` env var
  - Default model: `claude-sonnet-4-20250514`
  - Note: SDK not currently installed in `.venv`; install separately before use
- OpenAI GPT-4o — Alternative LLM backend
  - SDK/Client: `openai` >= 1.50.0 (lazy import in `rca_agent/llm_providers.py::OpenAIProvider`)
  - Auth: `OPENAI_API_KEY` env var
  - Default model: `gpt-4o`
  - Note: SDK not currently installed in `.venv`
- Google Gemini — Alternative LLM backend
  - SDK/Client: `google-generativeai` 0.8.6 (lazy import in `rca_agent/llm_providers.py::GoogleProvider`)
  - Auth: `GOOGLE_API_KEY` or `GEMINI_API_KEY` env var
  - Default model: `gemini-2.0-flash`
  - Note: This is the only LLM SDK currently installed in `.venv`
  - Known issue: Gemini has strict alternating-turn requirements; workaround implemented in `GoogleProvider._build_contents()`

**LLM switching:** All three providers implement the same `LLMProvider` ABC interface. Switch by setting `LLM_PROVIDER` env var. The `rca_copilot_agent` has NO LLM SDK — GitHub Copilot provides the reasoning via MCP tool calls.

## Data Storage

**Databases:**
- Google BigQuery — Read-only analytics queries against L'Oréal SPACE CDS dataset
  - Connection: GCP Application Default Credentials (`GOOGLE_APPLICATION_CREDENTIALS`) or service account key
  - Default project: `oa-apmena-spacecds-ap-pd`
  - Default dataset: `space_cds_b2c_ds_replica_ae2_pd_public`
  - Client: `google-cloud-bigquery` 3.41.0 (`google.cloud.bigquery.Client`)
  - Used in: `rca_agent/tools/bigquery_tool.py`, `rca_copilot_agent/tools/bigquery_tool.py`
  - Safety layers: keyword blocklist, dry-run validation, `maximum_bytes_billed` (500 MB default), row cap (100), timeout (30s)

**File Storage:**
- Local filesystem only
  - Incident JSON reports: `./my_reports/` — individual `INC*.json` + `_all_incidents.json`
  - OCR output: `./my_reports/_ocr_consolidated.json`, `./my_reports/_ocr_consolidated.txt`
  - Image attachments: `./attachments/` (per-incident subdirectories)
  - RCA reports: `./rca_reports/` (Markdown + JSON per investigation)
  - Wiki state: `./wiki/wiki_state.json` (agent's persistent scratchpad)

**Caching:**
- None (no Redis, Memcache, or similar)

## Authentication & Identity

**ServiceNow:**
- Auth Provider: Cookie-based session authentication (browser session cookies)
  - Implementation: Session cookies + CSRF token (`X-UserToken`) injected from `.env`
  - Keys: `COOKIE` (full Cookie header), `X_USERTOKEN` (CSRF token)
  - Source: Manually copied from browser DevTools Network tab — no OAuth/API key flow
  - CSRF bootstrap fallback: `GET /sn_devstudio_/v1/get_publish_info` endpoint
  - Retry logic: urllib3 `Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503])`
  - Implemented in: `rca_agent/snow_story_reader.py::ServiceNowReader.authenticate_from_env()`

**BigQuery / GCP:**
- Auth Provider: Google Application Default Credentials (ADC)
  - Implementation: `google.cloud.bigquery.Client(project=...)` — inherits ADC automatically
  - For CI/CD: `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to service account JSON key
  - IAM required: `roles/bigquery.dataViewer` + `roles/bigquery.jobUser` (read-only enforced)

**LLM APIs:**
- Anthropic: `ANTHROPIC_API_KEY` — passed directly to `anthropic.Anthropic(api_key=...)`
- OpenAI: `OPENAI_API_KEY` — passed directly to `openai.OpenAI(api_key=...)`
- Google Gemini: `GOOGLE_API_KEY` or `GEMINI_API_KEY` — passed to `genai.configure(api_key=...)`

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

**Logs:**
- `logging` stdlib at INFO level, written to stderr
- Structured log prefixes: `[BQ]`, `[MCP]`, `[SNOW]`, `[WIKI]`, `[AUTH]`, `[LLM]`
- Configured via `logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)`
- No log aggregation or persistence beyond terminal output

## CI/CD & Deployment

**Hosting:**
- No production hosting detected; runs locally or in developer environment

**CI Pipeline:**
- GitHub Actions workflows were deleted on the current branch (`feature/rca-agent`)
  - Deleted: `.github/workflows/lint.yml`, `test.yml`, `sonarqube.yml`, `release-to-qa.yml`, etc.
  - No active CI on this branch

**MCP Server integration (for IDE clients):**
- GitHub Copilot: `.github/agents/rca_copilot.agent.md` — references `rca_copilot_agent/mcp_server.py` via `.venv/bin/python`
- Claude Code: `claude_desktop_config.json` (not present in repo; documented in `rca_agent/mcp_server.py` docstring)

## Environment Configuration

**Required env vars (minimum viable):**
```
COOKIE          # ServiceNow browser session cookie
X_USERTOKEN     # ServiceNow CSRF token
BQ_PROJECT      # GCP project ID (or set in config.py default)
```

**Required for LLM-based agent (`rca_agent`):**
```
ANTHROPIC_API_KEY   # If using Claude (default)
GOOGLE_API_KEY      # If using Gemini
OPENAI_API_KEY      # If using GPT-4
```

**Secrets location:**
- `.env` files at project root and `rca_agent/` (git-ignored)
- GitHub Copilot agent uses `${{ secrets.SNOW_COOKIE }}` and `${{ secrets.SNOW_X_USERTOKEN }}` from GitHub repository secrets (defined in `.github/agents/rca_copilot.agent.md` frontmatter)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- ServiceNow comment posting: `PATCH /api/now/table/{table}/{sys_id}` — writes RCA report text as comment or work note
  - Implemented in: `rca_agent/snow_story_reader.py::ServiceNowReader.post_comment()`
  - Gated: Only called when user explicitly requests; `rca_copilot_agent` exposes as `post_comment` MCP tool
  - The `rca_agent` (standalone runner) does not automatically post comments; the pipeline script `rca_agent/run_pipeline.py` provides `--post-comment` flag

## ServiceNow API Endpoints Used

All calls target `https://loreal.service-now.com` (configurable via `SNOW_INSTANCE`):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/now/table/{table}/{sys_id}` | GET | Fetch single record |
| `/api/now/table/{table}` | GET | Search/list records with `sysparm_query` |
| `/api/now/table/sys_journal_field` | GET | Fetch comments and work notes |
| `/api/now/attachment` | GET | List attachments for a record |
| `/api/now/attachment/{sys_id}/file` | GET | Download attachment binary |
| `/api/now/table/sys_tiny_url` | GET | Resolve short list-view URLs |
| `/api/now/table/{table}/{sys_id}` | PATCH | Post comment or work note |
| `/sn_devstudio_/v1/get_publish_info` | GET | Bootstrap CSRF token |

Tables accessed: `incident`, `rm_story`, `sys_journal_field`, `attachment`, `sys_tiny_url`, `task_rel_task`

---

*Integration audit: 2026-04-24*
