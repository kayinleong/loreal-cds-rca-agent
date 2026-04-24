# Architecture

**Analysis Date:** 2026-04-24

## Pattern Overview

**Overall:** Tool-augmented LLM agent with dual deployment modes (autonomous + copilot)

**Key Characteristics:**
- ReAct (Reason + Act) loop drives autonomous investigation — the LLM thinks, acts via tools, observes results, repeats
- Karpathy wiki-compilation pattern: findings accumulate in a persistent scratchpad (`InvestigationWiki`) so knowledge compounds across loop iterations instead of evaporating
- LLM-agnostic design: all provider-specific formatting is isolated in `llm_providers.py`; tools are pure functions callable from any entry point
- Two deployment surfaces for the same tool set: (1) `agent_runner.py` runs its own LLM loop, (2) `mcp_server.py` exposes tools over MCP so an external LLM client (Claude Code, GitHub Copilot, Cursor) does the reasoning
- Read-only by design: BigQuery enforces SELECT-only at three layers (keyword blocklist, dry-run, IAM); ServiceNow uses session cookies (no write unless `post_comment` is called)

## Layers

**Data Ingestion (snow_story_reader.py):**
- Purpose: Fetch incident data from ServiceNow REST API and persist locally as JSON
- Location: `rca_agent/snow_story_reader.py`
- Contains: `ServiceNowReader` class — authentication, incident/story fetching, comment/attachment downloading, list-view URL processing, comment posting
- Depends on: `requests` library, `.env` credentials
- Used by: `run_pipeline.py` (step 1), `rca_copilot_agent/tools/snow_reader.py` (refactored copy)

**OCR (snow_image_ocr_agent.py):**
- Purpose: Extract text from image attachments using Tesseract OCR
- Location: `rca_agent/snow_image_ocr_agent.py`
- Contains: Reads `_all_incidents.json`, scans `./attachments/` for images, outputs `_ocr_consolidated.json`
- Depends on: `pytesseract`, `Pillow`, Tesseract binary
- Used by: `run_pipeline.py` (step 2)

**Tool Layer:**
- Purpose: Pure functions wrapping BigQuery, ServiceNow search, and the investigation wiki
- Location: `rca_agent/tools/`
- Contains: `bigquery_tool.py` (SafeBigQueryExecutor + module-level functions), `snow_tool.py` (IncidentLoader + module-level functions), `wiki_tool.py` (InvestigationWiki + module-level functions)
- Depends on: `google-cloud-bigquery`, loaded JSON from snow_story_reader
- Used by: `agent_runner.py` (direct function calls), `mcp_server.py` (via MCP protocol)

**LLM Abstraction Layer:**
- Purpose: Normalize Anthropic / OpenAI / Google APIs to a single interface
- Location: `rca_agent/llm_providers.py`
- Contains: `LLMProvider` ABC, `AnthropicProvider`, `OpenAIProvider`, `GoogleProvider`, `create_provider()` factory, `LLMResponse` and `ToolCall` dataclasses
- Depends on: `anthropic`, `openai`, `google-generativeai` (loaded lazily)
- Used by: `agent_runner.py` only

**Agent Orchestration:**
- Purpose: Drive the ReAct investigation loop and produce the structured RCA report
- Location: `rca_agent/agent_runner.py`
- Contains: `RCAAgentRunner`, `RCA_SYSTEM_PROMPT`, `TOOL_SCHEMAS`, `TOOL_FUNCTIONS`, CLI `main()`
- Depends on: all layers above
- Used by: `run_pipeline.py` (step 3), importable as a module

**Pipeline Orchestrator:**
- Purpose: Chain all four steps (fetch → OCR → investigate → post comment) via subprocess or direct import
- Location: `rca_agent/run_pipeline.py`
- Contains: `main()` with step functions, batch mode for all active incidents
- Depends on: `snow_story_reader.py`, `snow_image_ocr_agent.py`, `agent_runner.py`
- Used by: end users directly from CLI

**MCP Server (rca_agent):**
- Purpose: Expose the same tool functions over Model Context Protocol for external LLM clients
- Location: `rca_agent/mcp_server.py`
- Contains: `create_mcp_server()`, `run_jsonrpc_fallback()` (no MCP SDK), `main()`
- Depends on: tool layer only (no LLM calls here)
- Used by: Claude Code, GitHub Copilot via MCP config

**MCP Server (rca_copilot_agent):**
- Purpose: GitHub Copilot-oriented MCP server — same tools, refactored into a standalone package with no `agent_runner` dependency
- Location: `rca_copilot_agent/mcp_server.py`
- Contains: extended tool set (adds `fetch_incidents`, `get_incident`, `list_incidents`, `post_comment`, `list_bq_tables`)
- Depends on: `rca_copilot_agent/tools/` (refactored copies of snow_tool, bigquery_tool) and `rca_copilot_agent/tools/incident_store.py`
- Used by: GitHub Copilot agent via `.github/agents/` definition

## Data Flow

**End-to-End Pipeline (run_pipeline.py):**

1. `snow_story_reader.py` calls ServiceNow REST API → downloads incidents as `my_reports/_all_incidents.json` + per-incident `INC*.json`
2. `snow_image_ocr_agent.py` reads image attachments from `./attachments/` → writes `my_reports/_ocr_consolidated.json`
3. `agent_runner.py` loads both JSON files, initializes wiki and BigQuery executor, then runs the ReAct loop
4. ReAct loop: LLM → tool call → result appended to message history → next LLM call → repeat up to 15 iterations
5. Loop terminates when LLM produces no tool calls; final assistant message is parsed into `RCAReport`
6. Report written as `.md` + `.json` to `./rca_reports/`
7. (Optional) `ServiceNowReader.post_comment()` patches the RCA text back onto the ServiceNow ticket

**ReAct Loop Detail:**

1. Initial prompt constructed: system prompt + incident summary + extracted identifiers + BQ dataset reference
2. `provider.chat(messages, tools=TOOL_SCHEMAS)` → `LLMResponse`
3. If `response.tool_calls` is non-empty: each tool is dispatched via `TOOL_FUNCTIONS[tc.name](**tc.arguments)`
4. Tool result formatted as provider-specific message and appended to `state.messages`
5. Wiki tool calls (`update_findings`, `read_wiki`) write/read `InvestigationWiki.pages` in memory
6. `query_bigquery` calls are also logged to `state.queries_executed` for report appendix
7. Loop exits when LLM returns text only (no tool calls) — up to `max_iterations` (default 15)

**State Management:**
- `AgentState` (dataclass): holds `messages` list (full conversation history), `iteration` counter, `queries_executed` log, `done` flag
- `InvestigationWiki` (class singleton): holds categorized finding pages (`timeline`, `evidence`, `hypothesis`, `conclusion`, `action_item`) and operation log; optionally persisted to `wiki/wiki_state.json`
- `IncidentLoader._loader` (module singleton): indexes loaded incidents by number for O(1) lookup
- `SafeBigQueryExecutor._executor` (module singleton): shared BQ client reused across tool calls

## Key Abstractions

**RCA_SYSTEM_PROMPT:**
- Purpose: Encodes the investigation protocol, output format, and rules for the LLM
- Location: `rca_agent/agent_runner.py` lines 52–142
- Pattern: Structured markdown prompt with numbered protocol, format requirements, examples of good/bad report sections

**TOOL_SCHEMAS:**
- Purpose: Provider-agnostic tool definitions (JSON Schema); converted to provider-specific format by each `LLMProvider`
- Location: `rca_agent/agent_runner.py` lines 148–189
- Pattern: Each schema references a Pydantic model's `model_json_schema()` for parameter validation

**LLMProvider ABC:**
- Purpose: Defines the contract that all LLM backends must satisfy
- Location: `rca_agent/llm_providers.py`
- Pattern: Three abstract methods: `chat()`, `format_tool_result()`, `format_assistant_message()`; concrete classes normalize provider API differences

**InvestigationWiki:**
- Purpose: Persistent scratchpad implementing the Karpathy wiki pattern — findings survive across tool calls in a single investigation
- Location: `rca_agent/tools/wiki_tool.py`
- Pattern: In-memory dict of category → list of entries; optional JSON persistence to `wiki/wiki_state.json` for crash recovery

**SafeBigQueryExecutor:**
- Purpose: Read-only BQ client with three-layer safety (keyword filter → dry-run → `maximum_bytes_billed`)
- Location: `rca_agent/tools/bigquery_tool.py`
- Pattern: Lazy client initialization; separate `validate_query()`, `dry_run()`, `execute()` methods

**RCAReport (Pydantic model):**
- Purpose: Typed container for the final investigation output; `to_markdown()` renders it as structured Markdown
- Location: `rca_agent/models.py`
- Pattern: Four required narrative sections (`what_happened`, `checks`, `what_we_found`, `what_we_need`) plus raw data for traceability (`queries_executed`, `raw_findings`)

## Entry Points

**`rca_agent/run_pipeline.py`:**
- Location: `rca_agent/run_pipeline.py`
- Triggers: CLI — `python run_pipeline.py --incident INC0012345 [--fetch] [--post-comment]`
- Responsibilities: Orchestrates all four pipeline steps; supports single-incident and batch (`--all`) modes

**`rca_agent/agent_runner.py`:**
- Location: `rca_agent/agent_runner.py`
- Triggers: CLI (`python agent_runner.py --incident INC0012345 --incidents-file ...`) or `from agent_runner import RCAAgentRunner`
- Responsibilities: Runs the ReAct loop for a single incident; outputs `.md` + `.json` report

**`rca_agent/mcp_server.py`:**
- Location: `rca_agent/mcp_server.py`
- Triggers: `python mcp_server.py` (stdio MCP server for Claude Code/Copilot)
- Responsibilities: Exposes 7 tools over MCP; no LLM calls; falls back to JSON-RPC if MCP SDK missing

**`rca_agent/snow_story_reader.py`:**
- Location: `rca_agent/snow_story_reader.py`
- Triggers: CLI (`python snow_story_reader.py --snow-instance ... --list-link ...`) or imported by `run_pipeline.py`
- Responsibilities: Fetches, structures, and persists ServiceNow incident data

**`rca_copilot_agent/mcp_server.py`:**
- Location: `rca_copilot_agent/mcp_server.py`
- Triggers: `python rca_copilot_agent/mcp_server.py` (MCP server for GitHub Copilot)
- Responsibilities: Exposes 10 tools over MCP including live fetch and comment posting; no LLM calls; intended for GitHub Copilot agent context

## Error Handling

**Strategy:** Fail-soft with explicit degradation — BigQuery access failures do not halt investigation; OCR failures are non-fatal; max iterations forces report with available data

**Patterns:**
- BigQuery access denied → LLM instructed to pivot to `search_incident` only (via system prompt instruction)
- Tool call exceptions caught in `agent_runner.py` ReAct loop; result becomes `"Tool error: <type>: <message>"` string fed back to LLM
- Max iterations hit → forced final-report prompt appended, one additional LLM call made
- ServiceNow auth failure → `sys.exit(1)` in `snow_story_reader.py`; checked via `client.validate()` in pipeline steps
- Pydantic `ValidationError` on tool arguments caught and returned as error string to LLM

## Cross-Cutting Concerns

**Logging:** Standard `logging` module with `logger = logging.getLogger(__name__)` in each module; CLI entry points configure `basicConfig(level=INFO)`. Print statements used for human-readable step progress in `run_pipeline.py`.

**Validation:** Pydantic models (`BQQueryInput`, `IncidentSearchInput`, `FindingInput`, `SchemaLookupInput`) validate tool arguments at call time. BigQuery SQL validated with regex blocklist + dry-run before execution.

**Authentication:** ServiceNow uses browser session cookies + CSRF token (`COOKIE` + `X_USERTOKEN` env vars); BigQuery uses `google.cloud.bigquery.Client` ADC (Application Default Credentials) or service account key via `GOOGLE_APPLICATION_CREDENTIALS`.

**Configuration:** All tunables in `rca_agent/config.py` (`AgentConfig`, `LLMConfig`, `BigQueryConfig`, `ServiceNowConfig`); read from env vars with `.env` file fallback using a custom `_load_env()` parser (no dotenv dependency). `rca_copilot_agent/config.py` is a separate, slimmer equivalent with no LLM section.

---

*Architecture analysis: 2026-04-24*
