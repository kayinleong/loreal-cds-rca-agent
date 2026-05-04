# CLAUDE.md — space-cds-etl-core / RCA Agent

Extends `~/.claude/CLAUDE.md` (global rules). Read that first. This file adds project-specific context only.

---

## Project Overview

An AI-powered Root Cause Analysis (RCA) agent for L'Oréal's ServiceNow incidents. It correlates ticket data (comments, attachments, OCR'd images) with BigQuery pipeline data to produce structured RCA reports.

Two entry points share the same MCP tool layer:

| Entry point | File | LLM |
|-------------|------|-----|
| Standalone ReAct agent | `rca_agent/agent_runner.py` | Configurable (Anthropic / OpenAI) |
| MCP server (LLM-agnostic) | `rca_agent/mcp_server.py` | GitHub Copilot, Claude Code, Cursor, etc. |

The MCP server is **LLM-agnostic** — it exposes tools as pure functions. Never add LLM calls to the MCP server or its tools.

---

## Stack

- **Python 3.11+** — no build step, `pip install -r requirements.txt`
- **MCP SDK** (`mcp>=1.0.0`) — stdio transport
- **BigQuery** — `google-cloud-bigquery>=3.0`, auth via gcloud ADC (no key files)
- **ServiceNow** — REST API, cookie-based auth (no OAuth)
- **SMTP** — HTML email notifications on RCA completion
- **Schema** — `schema.json` in repo root; 45 BQ tables, loaded at startup

---

## Directory Map

```
rca_agent/              Main agent package
  agent_runner.py       Standalone ReAct loop (wiki-pattern)
  mcp_server.py         MCP server — all tools exposed here
  config.py             All tunables; loaded from .env
  tools/
    bigquery_tool.py    Read-only BQ executor (multi-layer safety)
    snow_tool.py        ServiceNow incident loader & search
    wiki_tool.py        Persistent wiki accumulator for findings
rca_copilot_agent/      Lightweight Copilot-only variant (no LLM calls)
  mcp_server.py
  tools/
attachments/            Downloaded SNOW attachments (gitignored)
my_reports/             Generated RCA reports (gitignored)
schema.json             BQ table schemas (committed, regenerated via bq ls)
.env                    Local secrets — never commit (gitignored)
.env.example            Template — no real values, always safe to commit
```

---

## Environment Setup

Copy `.env.example` to `.env` and fill in real values. Required variables:

| Variable | Source | Notes |
|----------|--------|-------|
| `COOKIE` | Chrome DevTools → Network → any SNOW request → Request Headers | Full Cookie header value |
| `X_USERTOKEN` | Same request headers | CSRF token |
| `SMTP_USER` | Your email address | Gmail: use App Password |
| `SMTP_PASSWORD` | App password or SMTP credential | Never a real account password |
| `SMTP_TO` | Recipient list | Comma-separated |

BigQuery needs no env vars — uses gcloud ADC. Run once:
```bash
gcloud auth application-default login
```

---

## Project-Specific Secrets Rules

On top of global hygiene rules:

- **`COOKIE` and `X_USERTOKEN`** are live ServiceNow session tokens. Treat them like passwords. Never log, echo, or commit them. They expire but can be replayed while active.
- **`schema.json`** contains table names and column names only — no data, safe to commit.
- **`my_reports/`** and `attachments/` are gitignored. Never stage these directories. They may contain real PII (consumer names, emails, order IDs from SNOW tickets).
- **`rca_agent/rca_reports/`** — also gitignored, same reason.
- If you see a `*-credentials.json` or `firebase-adminsdk-*.json` appear — stop and alert the user immediately. This project uses ADC, not service account key files.

---

## BigQuery Safety

`bigquery_tool.py` already enforces multiple layers. Do not bypass or weaken them:

- **Blocklist** — INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/MERGE and others are blocked before execution
- **Dry-run** — syntax and cost estimation before every real query
- **`maximum_bytes_billed`** — hard ceiling per query (see `config.py`)
- **Row limit** — cap result size for LLM context
- **Timeout** — kill long-running queries

When adding new BQ queries: always use parameterised queries or the existing `QueryResult` pattern. Never interpolate user-supplied strings directly into SQL.

---

## Architecture Patterns

### Adding a new tool

1. Create `rca_agent/tools/<name>_tool.py` — pure functions, no LLM calls, no side effects beyond the tool's declared purpose.
2. Register it in `rca_agent/mcp_server.py` using the existing `@mcp.tool()` decorator pattern.
3. If the tool needs config, add the tunables to `rca_agent/config.py` with an env-var override.
4. Update `rca_agent/AGENTS.md` with the tool's name, description, and expected inputs/outputs.

### Wiki pattern (agent_runner.py)

The standalone agent accumulates findings into a persistent wiki across ReAct iterations. New investigation steps should write findings to the wiki rather than returning them only in the response. This is the intentional design — don't refactor it away.

### schema.json

Regenerate with:
```bash
bq ls --format=json --project_id=oa-apmena-spacecds-ap-pd space_cds_b2c_ds_replica_ae2_pd_public > schema.json
```
Commit the updated file. The MCP tools load it at startup — no live BQ calls for schema discovery.

---

## Running the Agent

```bash
# Install dependencies
pip install -r requirements.txt

# MCP server (for Claude Code / Copilot)
python rca_agent/mcp_server.py

# Standalone ReAct agent
python rca_agent/agent_runner.py --incident INC0012345 \
    --incidents-file ./my_reports/_all_incidents.json

# Copilot-only MCP variant
python rca_copilot_agent/mcp_server.py
```

---

## What Not To Do

- Do not add LLM API calls inside `mcp_server.py` or any `tools/*.py`. The MCP layer is intentionally LLM-agnostic.
- Do not commit `my_reports/`, `attachments/`, or `rca_agent/rca_reports/`. Check `.gitignore` before every `git add`.
- Do not weaken or bypass the BigQuery blocklist in `bigquery_tool.py`.
- Do not hardcode the BQ project ID or dataset name outside `config.py`.
- Do not add `*.json` credential files to the repo — gcloud ADC is the auth mechanism.
- Do not stage `schema.json` alongside code changes in the same commit — schema regeneration is a separate, deliberate action.
