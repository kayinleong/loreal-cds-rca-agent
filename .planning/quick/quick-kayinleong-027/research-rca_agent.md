---
status: complete
package: rca_agent
---
<!-- quick-kayinleong-027 | read-only static analysis of rca_agent/ (2026-10-12). No code run, no .env read. -->

## Purpose & entry points

`rca_agent` is the "full" variant. It is an **offline, file-based pipeline**: a separate scraper pulls SNOW data to JSON on disk, and the RCA step reads only that JSON plus live BigQuery. Nothing in the RCA loop or MCP server talks to SNOW.

| Entry point | Command (run from inside `rca_agent/` — run_pipeline uses relative paths + `cwd=rca_agent/`, `run_pipeline.py:48`) | What it does |
|---|---|---|
| `snow_story_reader.py` | `--snow-instance <url> (--list-link URL \| --incident-link URL \| --story sys_id \| --search q) [--download] [--report-dir] [--limit] [--env-file]` (`snow_story_reader.py:1091-1118`) | Live SNOW REST pull, writes `INC*.json` + `_all_incidents.json` |
| `snow_image_ocr_agent.py` | `--input _all_incidents.json --attachments-root ./attachments` (`:327-348`) | Local Tesseract OCR, writes `_ocr_consolidated.json/.txt` |
| `agent_runner.py` | `--incident INC… [--incidents-file] [--ocr-file] [--provider] [--model] [--max-steps] [--output]` (`agent_runner.py:441-457`) | Standalone ReAct RCA with a direct LLM API call |
| `run_pipeline.py` | `--incident X \| --all [--list-link] [--fetch\|--fetch-only] [--post-comment] [--provider/--model/--max-steps]` (`run_pipeline.py:255-291`) | Orchestrates the steps as subprocesses, can post the RCA back to SNOW |
| `mcp_server.py` | `--incidents <json> [--ocr] [--bq-project] [--bq-dataset]` (`mcp_server.py:390-399`) | stdio MCP server, LLM-agnostic (brings no LLM of its own) |

**Not registered anywhere:** `.vscode/mcp.json` registers only `rca_copilot_agent/mcp_server.py` (as `snow-mcp`). Nothing under `.github/agents/`, `.claude/` or `.vscode/` references `rca_agent`. The README cites `.github/agents/rca-investigator.md`, but that file does not exist.

## Flow table

| Step | Status | How it works today | Key code (file:line) | Config / env | Gaps & risks |
|---|---|---|---|---|---|
| **1a SNOW auth** | Partial (manual) | The user copies the browser `Cookie` header and `X-UserToken` from DevTools into `.env`. `authenticate_from_env` reads `.env` from **cwd or `rca_agent/` only**, then puts the cookies into a `requests.Session` and sets the `X-UserToken` header. `validate()` sends `GET /api/now/table/rm_story?sysparm_limit=1` and checks for 200. A 401 or 403 on any `_get` raises `PermissionError` ("Log into ServiceNow… re-run"). There is no refresh and no expiry detection beyond the 401. Retry policy: 3 retries on 429/5xx. | `snow_story_reader.py:88-130` (env load), `:132-159` (session), `:205-223` (validate), `:227-243` (401/403), `:65` (retry); invoked by `run_pipeline.py:87-91,212-216` | `COOKIE`, `X_USERTOKEN` (also accepts `X-UserToken`), `--env-file`, `--snow-instance` | Manual and session-bound, so it breaks whenever the browser session expires. `_bootstrap_csrf_token` (`:161-203`) is dead code (never called). `config.ServiceNowConfig` (`config.py:81-87`) is never used. Real env vars are ignored because the reader parses the file itself. A missing `.env` calls `sys.exit(1)` (`:109-127`). |
| **1b GCP auth** | Implemented (implicit) | Python `google-cloud-bigquery` `bigquery.Client(project=BQ_PROJECT)` is created **lazily on the first query** with Application Default Credentials (ADC). There is no `gcloud`/`bq` subprocess and no auth pre-check at startup. | `tools/bigquery_tool.py:87-92` | `BQ_PROJECT` (default `oa-apmena-spacecds-ap-pd`) `config.py:68`. Doc strings and README still suggest `GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json` (`mcp_server.py:32`, README) | Auth or IAM failures appear only at the first `query_bigquery`. `dry_run` catches **every** exception, so an auth error is reported as `"Syntax error: …"` (`bigquery_tool.py:117-125,141-146`). The prompt tells the LLM to pivot to ticket text on Access Denied (`agent_runner.py:87-94`). The key-file guidance contradicts CLAUDE.md, which says ADC only. |
| **2 Read tickets** | Implemented (scraper) / file-only (agent) | **Scraper:** a list URL is parsed (`parse_list_url`, with `sysparm_tiny` resolved via `sys_tiny_url`). `search_records` pages through `/api/now/table/{table}` 100 at a time. Terminal states are dropped. For each record, `get_full_incident_report` fetches the record, `sys_journal_field` (comments and work_notes, falling back to inline fields), `/api/now/attachment` (split into images and files), downloads via `/attachment/{id}/file` when `--download` is set, and related `rm_story` records via `parent` and `task_rel_task`. Output is written to `INC*.json` + `_all_incidents.json`. A single incident by number is upserted. **OCR:** Tesseract runs on `downloaded_files` images only and writes `_ocr_consolidated.json`. **Agent/MCP:** `IncidentLoader` loads the JSON and auto-merges the OCR file. It offers keyword substring search, a summary capped at 20 comments, 20 notes and 500 chars each, and regex identifier extraction (order, user, EAN, email). | reader `:671-725`, `:326-379`, `:727-832`, `:888-996`, `:393-455`, `:459-527`, `:834-886`, `:624-643`, `:1032-1084`; OCR `snow_image_ocr_agent.py:136-215`; loader `tools/snow_tool.py:40-79,85-154,169-240,242-302` | `--report-dir` (default `./my_reports`), `DOWNLOAD_DIR="./attachments"` hard-coded (`reader:39,919`), `SNOW_REPORTS_DIR` / `SNOW_ATTACHMENTS_DIR` defined but unused | Data is a **stale snapshot**: the agent cannot refresh or fetch a ticket itself. `--list-link` **overwrites** `_all_incidents.json` (`:818-820`). The `run_pipeline --attachments-dir` value is not passed to the reader. OCR runs only if `--download` was used. The OCR output path is fixed to `./my_reports` even with a custom `--reports-dir`. Non-image files (PDF, xlsx) are never parsed. PII stays on local disk. |
| **3 Access BQ** | Implemented | The **LLM writes free-form SQL**; there are no templates. `SafeBigQueryExecutor.execute` checks safety in this order: (1) keyword blocklist after stripping literals and comments, plus a SELECT/WITH prefix check; (2) a dry run that rejects queries over `max_bytes`; (3) a real run with `maximum_bytes_billed`, `result(timeout, max_results=max_rows)`. `to_llm_context` shows at most 50 rows. `lookup_schema` uses **live BQ metadata** (`list_tables` + `get_table` for each table), **not `schema.json`**. | blocklist `bigquery_tool.py:24-28,96-115`; execute `:129-175`; schema `:179-239,273-291`; tool fn `:265-270`; init `agent_runner.py:476-482`, `mcp_server.py:73-82` | `BQ_PROJECT`, `BQ_DATASET`, `BQ_MAX_BYTES`=500 MB, `BQ_TIMEOUT`=30 s, `BQ_MAX_ROWS`=100 (`config.py:66-76`) | The "IAM SA" layer 1 exists only in a docstring (`:5`). The timeout stops the client wait but does not cancel the job. Empty `lookup_schema` costs N+1 API calls. Repo `schema.json` is unused here (CLAUDE.md is stale on this point). AGENTS.md rules (DV fallback project, `status='Active'`, no `recordstatus`) live only in markdown that is **not loaded into the prompt**. No parameterised queries: the LLM inlines IDs. |
| **4 Give RCA** | Implemented (agent_runner only) | `RCAAgentRunner.investigate` puts the incident summary and extracted IDs into the user prompt and uses a large system prompt (OBSERVE/THINK/ACT/REFLECT plus the 4-section format). The ReAct loop runs up to `AGENT_MAX_ITERATIONS`=15 and dispatches 5 tools from `TOOL_FUNCTIONS`. It stops when the LLM returns no tool calls. When the cap is hit, it sends one forced "produce report" call. The free text is parsed by header search into the Pydantic `RCAReport` (what_happened, checks[], what_we_found, what_we_need, queries_executed, raw_findings = wiki). The provider is configurable (Anthropic, OpenAI or Gemini) through `llm_providers.create_provider`. | prompt `agent_runner.py:52-142`; tools `:148-198`; loop `:273-354`; parse `:356-436`; models `models.py:67-132`; providers `llm_providers.py:70-156,161-223,226-418,423-443` | `LLM_PROVIDER` (default anthropic), `LLM_MODEL` (default `claude-sonnet-4-20250514`), `LLM_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY`\|`GEMINI_API_KEY`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `AGENT_MAX_ITERATIONS`, `AGENT_WIKI_DIR` (`config.py:37-62,92-100`) | **Wiki leaks across incidents**: `init_wiki` reloads `wiki/wiki_state.json` and nothing ever clears it (`wiki_tool.py:146-152,128-138`), so old findings bleed into new reports and batch runs. An LLM error `break`s yet still saves a (possibly empty) report and exits 0 (`:284-287`). The forced final call passes tools, so the reply may be a tool call with no text. Header parsing is brittle. `openai` is not in requirements, and the root `requirements.txt` has no LLM SDKs. |
| **5 Output / delivery** | Partial | `agent_runner` writes `RCA_<INC>_<ts>.md` + `.json` to `AGENT_OUTPUT_DIR` (`./rca_reports`) or `--output`. With `run_pipeline --post-comment`, the markdown is converted to plain text with the appendix stripped, the `sys_id` is read from `<reports>/<INC>.json`, the client re-authenticates, and `PATCH /api/now/table/{incident\|sc_req_item}/{sys_id}` is sent with `{"comments": …}`. That is a **customer-visible comment**, not a work note. Batch mode (`--all`) loops over non-terminal records in sequence. | save `agent_runner.py:491-511`; pipeline `run_pipeline.py:120-144,147-172,175-218,232-252,332-359`; PATCH `snow_story_reader.py:998-1030` | `AGENT_OUTPUT_DIR`, `--output-dir`, `--post-comment` | **No email/SMTP anywhere in `rca_agent/`** (grep: 0 hits), even though CLAUDE.md lists SMTP vars. Comments post with `as_work_note=False`, so there is a public-visibility risk with no human review gate. Subprocesses run with `cwd=rca_agent/` while the existence checks use the caller's cwd, so a run from the repo root silently skips OCR or comment posting (`run_pipeline.py:48,104,177`). |

## Tool inventory

MCP tools (`mcp_server.py`, SDK `Server("rca-agent")`, stdio). The list is at `:101-264` and dispatch at `:266-327`:

| Tool | Purpose | file:line (schema / dispatch → impl) |
|---|---|---|
| `query_bigquery` | Read-only SQL through the safe executor | `mcp_server.py:104-125 / 270-275` → `tools/bigquery_tool.py:265` |
| `search_incident` | Keyword search across description, comments, work_notes, OCR in loaded JSON | `:126-148 / 277-282` → `tools/snow_tool.py:325` |
| `update_findings` | Append a finding to the wiki (category enum, confidence) | `:149-181 / 284-291` → `tools/wiki_tool.py:162` |
| `read_wiki` | Read wiki pages | `:182-198 / 293-295` → `tools/wiki_tool.py:168` |
| `lookup_schema` | Live BQ table list or columns | `:199-215 / 297-301` → `tools/bigquery_tool.py:273` |
| `get_incident_summary` | Condensed incident text for one INC | `:216-232 / 303-307` → `tools/snow_tool.py:85` |
| `list_incidents` | Brief list of loaded incidents | `:233-246 / 309-313` → `tools/snow_tool.py:156` |
| `extract_identifiers` | Regex IDs from incident text | `:247-263 / 315-318` → `tools/snow_tool.py:242` |

No MCP tool authenticates to, fetches from, or writes to SNOW, and none runs OCR. The JSON-RPC fallback without the SDK (`:334-385`) exposes only the first 5 tools and does not implement `initialize`.

## Orchestration (who drives the loop, sequencing, LLM-agnostic or not)

- **Shared tool layer: yes, partly.** `agent_runner` and `mcp_server` import the same `tools/*` module singletons (`init_loader`, `init_executor`, `init_wiki`; `agent_runner.py:43-45,471-485` and `mcp_server.py:61-88`). `agent_runner` exposes only 5 of the 8 tools: the summary and IDs are injected into the prompt instead (`:229-255`). The tool schemas are defined twice (Pydantic in `models.py:16-44` vs hand-written in `mcp_server.py`), so they can drift. `BQQueryInput.rationale` is required in the agent but optional in MCP.
- **agent_runner:** a Python-driven ReAct loop. It is LLM-agnostic only across 3 hard-coded SDKs and needs an LLM API key, so it does **not** use Copilot or Claude Code.
- **mcp_server:** truly LLM-agnostic. The client LLM drives the reasoning, with no protocol or prompt shipped (AGENTS.md is not served as a resource or prompt).
- **run_pipeline:** linear subprocess chain: fetch → OCR (non-fatal) → ensure incident → investigate → optional post. There is no parallelism, and it re-authenticates per post.
- **SNOW live access** happens only in `snow_story_reader.ServiceNowReader`, used by the CLI and `run_pipeline`. It is never used by the agent loop or MCP.

## Gaps vs target flow (auth SNOW+GCP → read tickets → BQ → RCA)

1. **No unified auth step.** SNOW auth is a hand-pasted browser cookie in `.env` with no refresh or login flow. GCP is implicit lazy ADC with no pre-flight, and auth errors are mislabelled "Syntax error". Neither is checked up front by `agent_runner` or `mcp_server`.
2. **Reading tickets is decoupled from RCA.** The agent and MCP only see a pre-scraped `_all_incidents.json` snapshot. There is no "fetch ticket live" tool, and `--list-link` overwrites the snapshot.
3. **Wiki state is global and persistent.** It is not scoped per incident and is never cleared, which contaminates RCA output, especially in `--all` batch mode.
4. **Domain query rules are not enforced.** AGENTS.md rules and `schema.json` are not wired in. Schema discovery hits live BQ.
5. **Delivery gaps.** There is no email. The SNOW write-back is a public comment with no approval gate. Relative-path and cwd mismatches in `run_pipeline` can silently skip steps.
6. **Not wired to Copilot or VS Code.** `.vscode/mcp.json` points at `rca_copilot_agent`, and the referenced Copilot agent file does not exist.

## Open questions

- Is `rca_agent` still a live target, or superseded by `rca_copilot_agent` (the only one registered in `.vscode/mcp.json`)?
- Should the SNOW write-back be a work note (internal) rather than `comments`, and should it require human approval?
- Is SMTP email expected in `rca_agent`? CLAUDE.md implies it, but the code has none (it may live in a sibling package).
- Should `lookup_schema` move to the committed `schema.json`, as CLAUDE.md describes?
- Is there an approved SNOW auth path (OAuth or service account) to replace cookie scraping?
