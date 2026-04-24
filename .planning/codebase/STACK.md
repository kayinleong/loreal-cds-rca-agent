# Technology Stack

**Analysis Date:** 2026-04-24

## Languages

**Primary:**
- Python 3.13 - All application code across both agents

**Secondary:**
- None detected

## Runtime

**Environment:**
- Python 3.13.7 (confirmed via `.venv`)

**Package Manager:**
- pip (via `.venv`)
- Lockfile: Not present (no `requirements.lock` or `poetry.lock`). Two separate `requirements.txt` files exist at project root and `rca_agent/`.

## Frameworks

**Core:**
- None (pure Python stdlib + third-party SDKs; no web framework)

**Data Validation:**
- `pydantic` 2.13.1 — Tool input/output models, RCA report schema (`rca_agent/models.py`)

**MCP Protocol:**
- `mcp` >=1.0.0 — Model Context Protocol SDK; stdio server for Copilot/Claude Code integration. Required by `rca_agent/mcp_server.py` and `rca_copilot_agent/mcp_server.py`. Falls back to raw JSON-RPC if not installed.

**Testing:**
- Not detected — no test files, no test framework installed

**Build/Dev:**
- No build tooling detected (no `pyproject.toml`, `setup.py`, `Makefile`)

## Key Dependencies

**LLM Provider SDKs (rca_agent only — swappable):**
- `anthropic` >=0.40.0 — Claude API; default provider (`claude-sonnet-4-20250514`)
- `openai` >=1.50.0 — GPT-4o support (listed in requirements but NOT installed in `.venv`)
- `google-generativeai` 0.8.6 — Gemini API (`gemini-2.0-flash` default); installed in `.venv`

Note: `anthropic` and `openai` SDKs are NOT installed in `.venv` despite being in `rca_agent/requirements.txt`. Only `google-generativeai` is present. The `AnthropicProvider` and `OpenAIProvider` classes in `rca_agent/llm_providers.py` use lazy imports and will fail at runtime if the respective SDK is missing.

**HTTP Client:**
- `requests` 2.33.1 — ServiceNow REST API calls (`rca_agent/snow_story_reader.py`, `rca_copilot_agent/tools/snow_reader.py`)
- `urllib3` 2.6.3 — Transitive dependency; used for retry logic via `requests.adapters.HTTPAdapter`

**Google Cloud:**
- `google-cloud-bigquery` 3.41.0 — Read-only BigQuery query execution (`rca_agent/tools/bigquery_tool.py`, `rca_copilot_agent/tools/bigquery_tool.py`)
- `google-auth` 2.49.2 — GCP authentication (ADC / service account)
- `google-api-core` 2.30.3, `google-cloud-core` 2.5.1 — Supporting Google Cloud libraries

**OCR (optional):**
- `pytesseract` 0.3.13 — OCR for ServiceNow image attachments (`rca_agent/snow_image_ocr_agent.py`)
- `Pillow` 12.2.0 — Image loading for OCR pipeline

**Serialization/Validation:**
- `pydantic-core` 2.46.1 — Rust-backed core for Pydantic 2

**Crypto/Auth:**
- `cryptography` 46.0.7 — Transitive dependency for Google auth

## Configuration

**Environment:**
- Config loaded from `.env` file (custom parser in `rca_agent/config.py::_load_env()`; no `python-dotenv` dependency)
- `.env` searched in: cwd, `rca_agent/`, project root
- Environment variables override `.env` values (explicit `os.environ` check)

**Key config env vars (`rca_agent`):**
```
LLM_PROVIDER         # "anthropic" | "openai" | "google" (default: anthropic)
LLM_MODEL            # Model name (default: claude-sonnet-4-20250514)
LLM_API_KEY          # Override; falls back to provider-specific key
ANTHROPIC_API_KEY    # Claude
OPENAI_API_KEY       # GPT-4
GOOGLE_API_KEY       # Gemini (also: GEMINI_API_KEY)
LLM_TEMPERATURE      # Default: 0.2
LLM_MAX_TOKENS       # Default: 4096
BQ_PROJECT           # Default: oa-apmena-spacecds-ap-pd
BQ_DATASET           # Default: space_cds_b2c_ds_replica_ae2_pd_public
BQ_MAX_BYTES         # Default: 500000000 (500 MB)
BQ_TIMEOUT           # Default: 30s
BQ_MAX_ROWS          # Default: 100
COOKIE               # ServiceNow session cookie
X_USERTOKEN          # ServiceNow CSRF token
SNOW_REPORTS_DIR     # Default: ./my_reports
SNOW_ATTACHMENTS_DIR # Default: ./attachments
AGENT_MAX_ITERATIONS # Default: 15
AGENT_WIKI_DIR       # Default: ./wiki
AGENT_OUTPUT_DIR     # Default: ./rca_reports
```

**Key config env vars (`rca_copilot_agent`):**
```
COOKIE          # ServiceNow session cookie
X_USERTOKEN     # ServiceNow CSRF token
SNOW_INSTANCE   # Default: https://loreal.service-now.com
REPORTS_DIR     # Default: ./my_reports
ATTACHMENTS_DIR # Default: ./attachments
BQ_PROJECT      # GCP project (BigQuery tools disabled if absent)
BQ_DATASET      # BigQuery dataset
```

**Build:**
- No build config files detected

## Platform Requirements

**Development:**
- Python 3.13+
- `.venv` virtual environment at project root
- Tesseract OCR binary (system-level) for OCR features: `/opt/homebrew/bin/tesseract` (macOS), `/usr/bin/tesseract` (Linux), or Windows path
- GCP Application Default Credentials or service account key for BigQuery

**Production / Deployment:**
- No containerization detected (no Dockerfile, no docker-compose)
- No CI/CD pipeline active (GitHub Actions workflows deleted on current branch)
- Intended to run as: stdio MCP server (for Copilot/Claude Code), or standalone CLI script

---

*Stack analysis: 2026-04-24*
