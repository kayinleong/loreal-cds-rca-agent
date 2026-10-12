---
status: complete
claim: quick-kayinleong-027
date: 2026-10-12
---

# Research: how the agents work today vs the target flow

**Target flow:** (1) authenticate on L'Oréal SNOW + GCP → (2) read tickets → (3) access BQ → (4) give RCA.

This is read-only static analysis. No code was run against SNOW, BQ, gcloud, SMTP, or any LLM. Per-package detail with `file:line` citations is in the four partial files linked at the bottom. The headline claims were re-checked against source by the orchestrator.

## Which agent is "the" RCA agent?

| Package | What it is | Who drives reasoning | How it's invoked today | Status |
|---|---|---|---|---|
| `rca_copilot_agent` | LLM-agnostic tool layer for RCA (14 tools) | Host LLM (Copilot / Claude Code) via `.github/agents/rca_copilot.agent.md` + `.claude/skills/rca-copilot/SKILL.md` | **`run_tool.py` CLI**: one process per tool call ("L'Oréal env does not allow MCP servers"). Also registered as `snow-mcp` in `.vscode/mcp.json`, but no instruction file uses it. | **Primary, live path.** Closest to the target flow. |
| `rca_agent` | Standalone ReAct agent + MCP server (8 tools) + SNOW scraper + OCR | Own LLM loop (`agent_runner.py`, Anthropic/OpenAI/Gemini) | CLI `agent_runner.py`, `run_pipeline.py`; MCP server not registered anywhere | Older/offline. Reads a JSON snapshot only. |
| `ticketasg_copilot_agent` | Ticket-assignment recommender + RCA section | Host LLM via its agent.md / SKILL.md | `run_tool.py` CLI; not in `mcp.json` | Live; recommend-only (no SNOW write-back) |
| `mockdata_copilot_agent` | Mock INSERT SQL generator for DV testing | Host LLM | `run_tool.py` CLI | Not part of the RCA flow (no SNOW, no tickets) |

## The table: target flow step × agent

| Step | `rca_copilot_agent` (primary) | `rca_agent` | `ticketasg_copilot_agent` | `mockdata_copilot_agent` |
|---|---|---|---|---|
| **1a SNOW auth** | ✅ **Auto, startup only.** A REST probe tests the session. If it is invalid, Playwright opens **Edge (hard-coded)** for SSO (≤10 min), captures `g_ck` + cookies, and writes `COOKIE`/`X_USERTOKEN` to `.env`. This is not a callable tool, and failures are only logged as warnings. It re-runs on **every** CLI call, and nothing refreshes the session mid-run. | ⚠️ **Manual.** The user pastes a browser cookie + token into `.env`. One validation GET, no refresh. | ✅ Same code as rca_copilot (byte-identical `auth_tool.py`) | N/A |
| **1b GCP auth** | ✅ **Auto, startup.** `gcloud auth list` must be `@loreal.com`, then `print-access-token`, else interactive `gcloud auth login`. Also checks ADC, but **ADC is never used** (queries go through the `bq` CLI on user creds). The domain is **not re-checked after login**. Non-fatal. | ✅ **Implicit ADC.** The python BQ client is created on the first query. No pre-check, so auth errors surface as "Syntax error: …". | ✅ Same as rca_copilot (identical `gcloud_tool.py`) | ✅ Lazy, before BQ tools only. `ensure_login` always reports `adc: checked`. |
| **2 Read tickets** | ✅ **Live.** Bulk: `fetch_incidents(list_url)` parses the SNOW list URL (incl. tiny URLs), pages `/api/now/table`, and drops closed states. Single: `get_incident` / `analyze_incident` (INC/RITM/TASK). Pulls journal comments + work notes, attachment metadata, and related stories. Caches to `_all_incidents.json`. Attachments are downloaded but **never read/OCR'd**. **No assignment-group filter** beyond the URL. Bulk fetch **overwrites** the cache. | ⚠️ **Offline.** A separate scraper (`snow_story_reader.py`) writes `INC*.json` + `_all_incidents.json`, with Tesseract OCR on images. The agent/MCP only search that snapshot and have **no live fetch tool**. | ✅ Same reader as rca_copilot (2-line diff). `analyze_incident` never refreshes a cached ticket. | N/A (seed row from paste / `fetch_seed` / xlsx) |
| **3 Access BQ** | ⚠️ **Host LLM writes SQL.** Schema comes offline from `schema.json`. `query_bigquery` runs **`bq` CLI** with keyword blocklist + `--max_rows=100` + 60 s timeout. **No dry-run, no `maximum_bytes_billed`.** The guarded `SafeBigQueryExecutor.execute()` is dead code. `BQ_*` env vars in `mcp.json` are ignored (limits hard-coded). | ✅ **Fully guarded.** Python client: blocklist + SELECT check → dry-run (500 MB cap) → `maximum_bytes_billed`, 30 s timeout, 100 rows. LLM writes SQL. `lookup_schema` hits live BQ metadata, not `schema.json`. | ⚠️ Same unguarded `bq` CLI path. BQ feeds only the RCA section, not routing. | ⚠️ Same unguarded path (`fetch_seed`, `lookup_consumer`). A failed query is treated as "consumer absent". |
| **4 Give RCA** | ⚠️ **Prompt-only.** The host LLM writes a 4-section RCA (*What happened / What we checked / What we found / What we need/did*) plus a canonical assignment-group table. No code validation. The template is copied in 3 files and **already drifting**. | ✅ **Own ReAct loop.** 15 steps, 5 tools, default `claude-sonnet-4-20250514`. Parsed into a 4-section `RCAReport` model. The wiki **persists across incidents and is never cleared**, so findings leak between reports. | ✅ **Assignment recommendation + RCA section.** Order: hard-rule regex (0.95) → L3 escalation (0.85) → kNN (MiniLM, 378-ticket index) → keyword scorer. Host LLM judges. | N/A (generates INSERT SQL) |
| **5 Delivery** | ⚠️ `save_rca_report` → `.md`. `send_rca_email` → SMTP HTML, but **attaches nothing in CLI mode** (in-memory report list, new process per call). `post_comment` live-PATCHes SNOW, with confirmation enforced by the prompt only. RCA text in `--json '…'` **breaks on apostrophes** ("L'Oréal"). | ⚠️ `.md` + `.json` reports. `run_pipeline --post-comment` writes a customer-visible comment with **no approval gate**. **No email.** | ⚠️ `.md` + SMTP email (same attachment bug) + optional comment. **No reassignment write-back.** | ✅ Report to `mockdata/` (gitignored); never executes writes |

Legend: ✅ works as designed · ⚠️ works with notable gaps · N/A not applicable.

## Orchestration: who enforces the flow order?

- **Copilot agents (rca_copilot / ticketasg / mockdata):** the **prompt only**. `_dispatch` is stateless and accepts any tool in any order. Code enforces just two things: auth runs as a process-start side effect, and `analyze_incident` sequences fetch → summary → identifiers → attachments. "Run BQ when identifiers exist", "schema before query", "save before output", "confirm before post", and the RCA template all rely on the host LLM obeying instructions.
- **`rca_agent`:** its own ReAct loop drives everything, but it never touches live SNOW.

## Cross-cutting risks

1. **BQ cost guardrails are bypassed in 3 of 4 packages.** Only `rca_agent` enforces dry-run + `maximum_bytes_billed`. This contradicts the repo `CLAUDE.md` "BigQuery Safety" section.
2. **The CLI-per-call model breaks stateful features.** It re-runs auth checks (and possibly the Edge/gcloud popups) on every call, and email attachments are lost.
3. **Code duplication with drift.** `bigquery_tool.py` has 4 divergent copies. `auth_tool`/`gcloud_tool` are identical copies. `snow_reader`/`incident_store`/`email_tool` are near-identical. There's no shared module, only one test file (`ticketasg_copilot_agent/test_config.py`, 3/3 pass), and no CI.
4. **Stale docs/config.**
   - Repo `CLAUDE.md` says 45 BQ tables; `schema.json` has 82 (33 primary + 49 additional).
   - The documented regeneration command can't reproduce `schema.json`.
   - The documented MCP-first architecture is no longer how agents run (they use the CLI).
   - `.vscode/settings.json:3` points at an old folder.
   - Project IDs are hard-coded outside `config.py`.
5. **Security smalls.** Attachment filenames are unsanitised (path traversal). Email HTML is not escaped. The ticketasg index is loaded with `np.load(allow_pickle=True)`. SNOW session cookies are kept in plaintext `.env`.
6. **Bugs found in passing.**
   - ticketasg `find_similar_incidents` with an incident number crashes on a missing import (`mcp_server.py:800`).
   - `analyze_incident` fails entirely if an attachment download fails.
   - The `rca_agent` LLM failure path still saves an (empty) report and exits 0.

## Gaps vs target flow (rca_copilot_agent as the baseline)

| Target step | Gap |
|---|---|
| 1 Authenticate | Not an explicit step or tool. Re-runs per CLI call, fails silently, no mid-session refresh, Edge-only, post-login domain not re-checked. |
| 2 Read tickets | No assignment-group targeting. Attachment content (images/screenshots) never analysed. Bulk fetch clobbers the cache. |
| 3 Access BQ | No cost guard (dry-run / bytes cap). Config env vars ignored. |
| 4 Give RCA | Template enforced by prompt only. 3 drifting copies. No structured validation. |
| (5) Deliver | Email attachments broken in CLI mode. Shell-quoting breaks on apostrophes. |

## Open questions for the user

1. **Which package is the target?** Extend `rca_copilot_agent` (live, Copilot-driven) or revive `rca_agent` (own LLM loop, guarded BQ, OCR, but offline)? Or merge them into one shared tool layer?
2. **CLI vs MCP:** is CLI-only (`run_tool.py`) the permanent constraint on L'Oréal machines? That decides how auth caching and email attachments get fixed.
3. **Auth step:** make it an explicit `check_auth` tool, run once per session, with a clear failure the host LLM must stop on?
4. **BQ path:** switch `query_bigquery` back to the python client (ADC + dry-run + bytes cap), or add `--dry_run` / `--maximum_bytes_billed` to the `bq` CLI call? (The researcher didn't verify CLI flag support; check it before planning.)
5. **Tickets:** which assignment groups/queues should "read tickets" target by default? Should attachments/screenshots be OCR'd or vision-read?
6. **Browser:** is Edge guaranteed on all analyst machines, including macOS?

## Partial research files

- [research-rca_copilot_agent.md](research-rca_copilot_agent.md): primary path, full flow table, 14-tool inventory
- [research-rca_agent.md](research-rca_agent.md): standalone ReAct agent, scraper, OCR, guarded BQ
- [research-ticketasg_copilot_agent.md](research-ticketasg_copilot_agent.md): assignment engine, retrieval index
- [research-mockdata_and_shared.md](research-mockdata_and_shared.md): mockdata agent + duplicated-module diff, config, tests, schema.json
