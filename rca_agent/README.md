# RCA Agent — Wiki-Based Root Cause Analysis

Investigates ServiceNow incidents by analyzing incident data and validating
hypotheses against BigQuery. Built on Karpathy's [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
with a ReAct (Reason + Act) agent loop.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  YOUR LLM CLIENT                      │
│  (Copilot / Claude Code / Cursor / agent_runner.py)  │
│                                                      │
│  Brings its own LLM:  Claude | GPT-4 | Gemini       │
└──────────────┬───────────────────────────────────────┘
               │ MCP Protocol (or direct function calls)
               ▼
┌──────────────────────────────────────────────────────┐
│                   MCP SERVER                          │
│                  mcp_server.py                        │
│                                                      │
│  Tools (pure functions, LLM-agnostic):               │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ BigQuery    │ │ ServiceNow   │ │ Investigation│  │
│  │ Executor    │ │ Search       │ │ Wiki         │  │
│  │             │ │              │ │              │  │
│  │• query_bq   │ │• search_inc  │ │• update      │  │
│  │• lookup     │ │• get_summary │ │• read        │  │
│  │  schema     │ │• extract_ids │ │• persist     │  │
│  └─────────────┘ └──────────────┘ └──────────────┘  │
└──────────────────────────────────────────────────────┘
```

**Key principle**: Tools are in the MCP server, LLM reasoning is in the client.
Swap the LLM by changing one config value — tools don't change.

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Set up credentials

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-...          # Or OPENAI_API_KEY for GPT-4
LLM_PROVIDER=anthropic                 # anthropic | openai | google
LLM_MODEL=claude-sonnet-4-20250514

# BigQuery (use gcloud auth or service account)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json

# ServiceNow (from existing .env)
COOKIE=...
X_USERTOKEN=...
```

### 3. Fetch incidents (using existing snow_story_reader.py)

```bash
python snow_story_reader.py \
  --list-link "https://loreal.service-now.com/..." \
  --download --report-dir ./my_reports --limit 200

# Optional: OCR on attachments
python snow_image_ocr_agent.py \
  --input ./my_reports/_all_incidents.json \
  --attachments-root ./attachments
```

### 4. Run investigation

```bash
# Standalone agent (uses agent_runner.py + any LLM)
python agent_runner.py --incident INC0012345

# With specific provider
python agent_runner.py --incident INC0012345 --provider openai --model gpt-4o

# Output to specific file
python agent_runner.py --incident INC0012345 --output ./reports/INC0012345_rca.md
```

## Usage: MCP Server (for Copilot / Claude Code / Cursor)

### GitHub Copilot

The `.github/agents/rca-investigator.md` file auto-registers the agent.
In Copilot Chat:

```
@rca-investigator investigate INC0012345
```

### Claude Code

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rca-agent": {
      "command": "python",
      "args": ["rca_agent/mcp_server.py", "--incidents", "./my_reports/_all_incidents.json"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/sa-key.json"
      }
    }
  }
}
```

Then in Claude Code:
```
Use the rca-agent tools to investigate INC0012345. Start with 
get_incident_summary, then lookup_schema, then validate with 
query_bigquery. Produce the standard RCA report.
```

### Run MCP Server Directly

```bash
python mcp_server.py --incidents ./my_reports/_all_incidents.json
```

## Swapping LLM Providers

The whole point of MCP is that tools and reasoning are decoupled:

| Provider | Config | Model |
|----------|--------|-------|
| Anthropic | `LLM_PROVIDER=anthropic` | `claude-sonnet-4-20250514` |
| OpenAI | `LLM_PROVIDER=openai` | `gpt-4o` |
| Google | `LLM_PROVIDER=google` | `gemini-2.0-flash` |

Change `LLM_PROVIDER` in `.env` — the MCP server and tools stay identical.

When running via Copilot or Claude Code, the client brings its own LLM.
The MCP server is completely LLM-agnostic.

## Investigation Protocol

Based on Karpathy's wiki-compilation pattern:

1. **OBSERVE** — Read incident data, extract identifiers
2. **THINK** — Form hypotheses about root cause
3. **ACT** — Run BQ queries, search incident text, record findings
4. **REFLECT** — Evaluate results, decide if more investigation needed
5. **COMPILE** — Produce structured RCA report

Findings accumulate in the **investigation wiki** (not lost between iterations).

## Report Format

```
## WHAT HAPPENED
Order YSLMY0153902 not visible in Order DB for user C5MY79060411672.

## WHAT WE CHECKED
→ Checked Order DB — not found
→ Checked LOY — purchase records exist
→ Checked User Profile — MARSID field is empty

## WHAT WE FOUND
MARSID is empty in profile. Without it, orders cannot be matched.

## WHAT WE NEED / DID
CDS to confirm if MARSID was received at ingestion — by 28 Mar.
```

## Project Structure

```
rca_agent/
├── AGENTS.md                    # Karpathy's schema file (investigation protocol)
├── agent_runner.py              # Standalone ReAct agent (swappable LLM)
├── mcp_server.py                # MCP server (tools for any client)
├── llm_providers.py             # Pluggable LLM backends
├── models.py                    # Pydantic models (tool I/O, RCA report)
├── config.py                    # Configuration (env vars / .env)
├── tools/
│   ├── bigquery_tool.py         # Safe read-only BQ executor
│   ├── snow_tool.py             # Incident loader & search
│   └── wiki_tool.py             # Investigation wiki (persistent scratchpad)
├── .github/agents/
│   └── rca-investigator.md      # GitHub Copilot custom agent
├── wiki/                        # Persisted wiki state (auto-created)
├── requirements.txt
└── README.md
```

## Safety Guardrails

- **BigQuery**: Keyword filter → dry-run → `maximum_bytes_billed` → timeout → row limit
- **Read-only**: Only SELECT/WITH queries pass validation
- **Cost cap**: 500MB scan limit per query (configurable via `BQ_MAX_BYTES`)
- **Timeout**: 30s per query (configurable via `BQ_TIMEOUT`)
- **Row limit**: Max 100 rows returned (configurable via `BQ_MAX_ROWS`)
