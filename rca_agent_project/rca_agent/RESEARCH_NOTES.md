# RCA Agent — Research Notes

**Date:** 2026-04-17  
**Author:** Investigation via Claude Code  
**Purpose:** Reference guide for running the RCA pipeline — scraping ServiceNow + analysing with Gemini LLM.

---

## 1. Code That Scrapes L'Oréal ServiceNow Comments & Attachments

**File:** `snow_story_reader.py`

The `ServiceNowReader` class handles all ServiceNow interaction:

| Method | What it does |
|--------|-------------|
| `authenticate_from_env()` | Loads `COOKIE` + `X_USERTOKEN` from `.env` |
| `get_full_incident_report(sys_id)` | Fetches incident details, comments, work notes, attachments in one call |
| `get_comments(sys_id)` | Fetches structured journal entries (comments + work notes) via `sys_journal_field` API |
| `get_attachments_for(table, sys_id)` | Lists all attachments for a record |
| `download_all_attachments(sys_id)` | Downloads attachment files to `./attachments/<incident_number>/` |
| `process_incident_list(list_url)` | Bulk-scrapes all incidents from a ServiceNow list-view URL |

**Run — single incident:**
```bash
python snow_story_reader.py \
  --incident-link "https://loreal.service-now.com/incident.do?sys_id=<sys_id>" \
  --download \
  --report-dir ./my_reports
```

**Run — bulk from a list URL:**
```bash
python snow_story_reader.py \
  --list-link "https://loreal.service-now.com/now/nav/ui/classic/params/target/incident_list.do..." \
  --download \
  --report-dir ./my_reports \
  --limit 200
```

Output: one `INC*.json` per incident + `_all_incidents.json` combined file.

---

## 2. LLM Analysis with Gemini to Generate RCA

**File:** `agent_runner.py`

The `RCAAgentRunner` class runs a ReAct (Reason + Act) loop:

1. **OBSERVE** — reads incident data, extracts identifiers
2. **THINK** — forms hypotheses about root cause
3. **ACT** — calls tools (BQ queries, incident search, wiki updates)
4. **REFLECT** — evaluates results, decides if more investigation needed
5. **COMPILE** — produces the final structured RCA report

**Run with Gemini:**
```bash
python agent_runner.py \
  --incident INC0012345 \
  --incidents-file ./my_reports/_all_incidents.json \
  --provider google \
  --model gemini-2.0-flash \
  --output ./rca_reports/INC0012345_rca.md
```

**Supported LLM providers:**

| Provider | `--provider` value | Default model |
|----------|-------------------|---------------|
| Google Gemini | `google` | `gemini-2.0-flash` |
| Anthropic Claude | `anthropic` | `claude-sonnet-4-20250514` |
| OpenAI GPT-4 | `openai` | `gpt-4o` |

**RCA output format** (hardcoded in `agent_runner.py` system prompt, line 97–121):

```
### WHAT HAPPENED
One sentence. The symptom, not the cause.

### WHAT WE CHECKED
→ Checked <system> — <result>

### WHAT WE FOUND
The conclusion from your checks. One or two sentences.

### WHAT WE NEED / DID
If resolved: what you did. If pending: who needs to do what, by when.
```

---

## 3. Configuration — What to Set and Where

All config is read from a `.env` file.

**File to create:** `rca_agent_project/rca_agent/.env`  
(The loader in `config.py:_load_env()` searches `./` and `../` automatically.)

```ini
# ── LLM: Switch to Gemini ─────────────────────────────────
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash          # or gemini-1.5-pro for stronger reasoning
GOOGLE_API_KEY=AIza...              # From Google AI Studio → Get API Key

# ── ServiceNow Authentication ─────────────────────────────
# Get from browser DevTools while logged in:
# Network tab → any SNOW request → Headers → copy Cookie & X-UserToken
COOKIE=JSESSIONID=...; glide_user_session=...
X_USERTOKEN=abc123...

# ── BigQuery (optional — for deep data validation queries) ─
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
BQ_PROJECT=oa-apmena-spacecds-ap-pd
BQ_DATASET=space_cds_b2c_ds_replica_ae2_pd_public

# ── Optional tuning ───────────────────────────────────────
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096
AGENT_MAX_ITERATIONS=15
BQ_MAX_BYTES=500000000              # 500MB scan limit per query
BQ_MAX_ROWS=100
```

**Config class reference:** `config.py`

| Class | Controls |
|-------|---------|
| `LLMConfig` (line 51) | Provider, model, API key, temperature, max tokens |
| `ServiceNowConfig` (line 82) | SNOW instance URL, cookie, user token, output dirs |
| `BigQueryConfig` (line 66) | BQ project, dataset, cost/timeout/row limits |
| `AgentConfig` (line 93) | Max iterations, wiki dir, output dir; nests all above |

---

## 4. End-to-End Workflow

```bash
cd rca_agent_project/rca_agent

# Step 1: Scrape incidents from ServiceNow
python snow_story_reader.py \
  --list-link "<SNOW_LIST_URL>" \
  --download \
  --report-dir ./my_reports \
  --limit 200

# Step 2 (optional): OCR screenshots/images in attachments
python snow_image_ocr_agent.py \
  --input ./my_reports/_all_incidents.json \
  --attachments-root ./attachments

# Step 3: Run RCA investigation with Gemini
python agent_runner.py \
  --incident INC0012345 \
  --incidents-file ./my_reports/_all_incidents.json \
  --provider google \
  --model gemini-2.0-flash \
  --output ./rca_reports/INC0012345_rca.md
```

---

## 5. Known Gap — Gemini Tool-Calling Not Fully Wired

**File:** `llm_providers.py`, `GoogleProvider.chat()`, line 262

The Gemini provider currently returns `tool_calls=[]` — it does text generation only.
This means when using `--provider google`, the agent **cannot** call tools mid-investigation
(BQ queries, incident search, wiki updates). It will skip straight to text generation.

**Impact:** The final RCA report is generated from the initial incident data only — no BQ validation queries run.

**Fix required (if full ReAct loop with Gemini is needed):**
Update `GoogleProvider.chat()` to:
1. Pass `tools=` to `genai.GenerativeModel()`
2. Parse `response.candidates[0].content.parts` for `FunctionCall` parts
3. Return populated `tool_calls` list in `LLMResponse`

This is a self-contained change in `llm_providers.py` — no other files need to change.

---

## 6. Project Structure Reference

```
rca_agent_project/rca_agent/
├── .env                     ← CREATE THIS (credentials + config)
├── snow_story_reader.py     ← SNOW scraper (comments + attachments)
├── snow_image_ocr_agent.py  ← OCR images in attachments
├── agent_runner.py          ← RCA agent (ReAct loop + report generation)
├── llm_providers.py         ← Pluggable LLM backends (Anthropic/OpenAI/Gemini)
├── config.py                ← All config (reads from .env)
├── models.py                ← Pydantic models for tool I/O + RCA report
├── mcp_server.py            ← MCP server (for Claude Code / Copilot integration)
├── tools/
│   ├── bigquery_tool.py     ← Read-only BQ executor
│   ├── snow_tool.py         ← Incident loader + search
│   └── wiki_tool.py         ← Investigation wiki (persistent scratchpad)
├── my_reports/              ← SNOW scrape output (auto-created)
├── attachments/             ← Downloaded attachment files (auto-created)
├── rca_reports/             ← Generated RCA markdown reports (auto-created)
└── wiki/                    ← Persisted investigation wiki state (auto-created)
```
