# Codebase Concerns

**Analysis Date:** 2026-04-24

---

## Security Considerations

**[CRITICAL] Session credentials stored via browser cookie extraction:**
- Risk: COOKIE and X_USERTOKEN values from a live browser session are pasted into `.env`. These are short-lived session tokens, not API keys. When they expire (typically hours), all SNOW operations silently return 401 errors.
- Files: `rca_agent/config.py` (lines 84–85), `rca_copilot_agent/config.py` (lines 82–96)
- Current mitigation: `.env` is in `.gitignore`; `.env.example` documents setup
- Recommendations: Add a session-validity probe on startup and produce a human-readable expiry warning rather than runtime 401 errors buried in the HTTP response

**[HIGH] Production GCP project and dataset hardcoded as default fallback values:**
- Risk: `oa-apmena-spacecds-ap-pd` and `space_cds_b2c_ds_replica_ae2_pd_public` are used as `os.getenv(...)` default arguments. A developer who forgets to set `BQ_PROJECT`/`BQ_DATASET` will query production silently.
- Files: `rca_agent/config.py` (lines 68–69)
- Current mitigation: None — the defaults are production values
- Recommendations: Remove hardcoded defaults; raise `ValueError` if env vars are absent, or default to an empty string that fails `BigQueryConfig.enabled`

**[HIGH] No authentication validation before the investigation starts:**
- Risk: If SNOW session has expired, `agent_runner.py` silently proceeds through the full ReAct loop, calling `search_incident` against a stale dataset instead of aborting with a clear error.
- Files: `rca_agent/agent_runner.py` (`investigate()` method, line 220+)
- Current mitigation: `ServiceNowReader.validate()` exists in the copilot variant but is never called from `agent_runner.py`
- Recommendations: Call the validate probe in `init_loader()` or at the start of `investigate()`

**[MEDIUM] `.github/agents/rca_copilot.agent.md` references `${{ secrets.SNOW_COOKIE }}` and `${{ secrets.SNOW_X_USERTOKEN }}`:**
- Risk: If this agent file is executed in a non-GitHub Copilot context (e.g., Claude Code), those secret references will be passed as literal strings `${{ secrets.SNOW_COOKIE }}`, causing silent auth failure.
- Files: `.github/agents/rca_copilot.agent.md` (lines 26–27)
- Current mitigation: None
- Recommendations: Document that these secret references are Copilot-specific and do not work in other MCP clients

---

## Known Bugs / Broken Functionality

**[HIGH] Gemini (Google) tool-calling is structurally fragile:**
- Problem: `GoogleProvider.chat()` silently swallows all parsing errors in two nested bare `except Exception:` blocks. When Gemini returns a tool call, the response parser falls through to `response.text`, discarding the tool calls and causing the agent to produce a report without any data.
- Files: `rca_agent/llm_providers.py` (lines 372–387)
- Trigger: Any Gemini response that contains a `function_call` part mixed with a blocked/safety-filtered response, or when `response.parts` raises an attribute error
- Workaround: Use `LLM_PROVIDER=anthropic` (default) or `LLM_PROVIDER=openai`
- Fix approach: Separate the text-parsing fallback from the tool-call parsing; log exceptions rather than swallowing them

**[HIGH] `rca_agent/run_pipeline.py` imports from `snow_story_reader.ServiceNowReader` which has a different API than `rca_copilot_agent/tools/snow_reader.ServiceNowReader`:**
- Problem: `run_pipeline.py` calls `client.authenticate_from_env()` (lines 88, 213) and `client.get_incident_by_number(incident_number, reports_dir=...)` (line 94), but `rca_agent/snow_story_reader.py`'s `ServiceNowReader` may have diverged from the copilot variant. Two parallel implementations with different method signatures exist.
- Files: `rca_agent/run_pipeline.py` (lines 85, 94, 208, 226), `rca_agent/snow_story_reader.py`, `rca_copilot_agent/tools/snow_reader.py`
- Impact: Running `run_pipeline.py --fetch` may fail at the `authenticate_from_env()` call if `snow_story_reader.ServiceNowReader` does not expose that method signature

**[MEDIUM] `resolve_path()` in `snow_image_ocr_agent.py` returns `None` on failure but callers check `if not resolved:`:**
- Problem: `resolve_path()` (line 123) returns `None` when the file is not found. This is correct, but the return type annotation is absent and the function has multiple early-exit paths that silently fall through. If paths contain mixed slashes (Windows/Unix), the stripping logic `lstrip("./").lstrip(".\\")`  is executed sequentially not simultaneously, potentially missing some patterns.
- Files: `rca_agent/snow_image_ocr_agent.py` (lines 91–123)
- Impact: Low — produces `[FILE NOT FOUND]` in the OCR report rather than crashing

**[MEDIUM] Silent fail in `agent_runner.py` when hitting max iterations:**
- Problem: The forced-report call at max iterations swallows all exceptions with `except Exception: pass` (line 353). If the final LLM call fails, `final_content` remains empty and the produced `RCAReport` will have empty `what_happened`, `what_we_found`, and `what_we_need` fields.
- Files: `rca_agent/agent_runner.py` (lines 345–354)
- Impact: Silently produces an empty RCA report that looks valid but has no content

---

## Technical Debt

**[HIGH] Massive code duplication between `rca_agent/` and `rca_copilot_agent/`:**
- Issue: `bigquery_tool.py` is byte-for-byte identical across both packages (291 vs 297 lines, same logic). `snow_tool.py` and `rca_copilot_agent/tools/incident_store.py` implement the same in-memory incident index with the same search/extract logic. `config.py` in each package solves the same problem differently.
- Files: `rca_agent/tools/bigquery_tool.py` vs `rca_copilot_agent/tools/bigquery_tool.py`, `rca_agent/tools/snow_tool.py` vs `rca_copilot_agent/tools/incident_store.py`
- Impact: Any bug fix must be applied in two places; divergence is already occurring (copilot variant has `is_enabled()` and `_BQ_UNAVAILABLE` sentinel; agent variant does not)
- Fix approach: Extract a shared `rca_shared/` package and import from both agents

**[MEDIUM] `rca_agent/mcp_server.py` and `rca_copilot_agent/mcp_server.py` are parallel MCP servers for the same tools:**
- Issue: Two MCP servers expose overlapping capabilities. `rca_agent/mcp_server.py` is the "full" server (includes wiki + BQ + SNOW tools). `rca_copilot_agent/mcp_server.py` is the "copilot" server (SNOW + BQ, no wiki). These are growing apart without a clear deprecation plan.
- Files: `rca_agent/mcp_server.py`, `rca_copilot_agent/mcp_server.py`
- Impact: Unclear which server to use; `.github/agents/rca_copilot.agent.md` points to `rca_copilot_agent/mcp_server.py`

**[LOW] `rca_agent/snow_story_reader.py` is a 1,224-line legacy monolith:**
- Issue: `snow_story_reader.py` predates the refactor into `rca_copilot_agent/tools/snow_reader.py`. It is still imported by `run_pipeline.py` (3 import sites). Its `ServiceNowReader` class has a different authentication interface (`authenticate_from_env()`) than the refactored version (`authenticate(cookie, x_user_token)`).
- Files: `rca_agent/snow_story_reader.py`, `rca_agent/run_pipeline.py`
- Impact: Maintenance burden; risk of regression when one implementation is updated without the other

**[LOW] Unversioned `google-generativeai` in requirements:**
- Issue: `rca_agent/requirements.txt` specifies `google-generativeai` with no version pin. The `google-generativeai` package API changes frequently between minor versions.
- Files: `rca_agent/requirements.txt` (line 12)
- Impact: `pip install` may resolve to a version that breaks `protos.FunctionDeclaration` or `protos.Schema` usage

---

## Incomplete Implementations

**[HIGH] `rca_copilot_agent/` was formerly an empty placeholder; it now has content but is still missing `tools/__init__.py` content:**
- Status: The directory is NOT empty — it contains `mcp_server.py`, `config.py`, `__init__.py`, and `tools/` (with `bigquery_tool.py`, `incident_store.py`, `snow_reader.py`). The `tools/__init__.py` is empty (1 line). Memory item "empty placeholder" is outdated.
- Files: `rca_copilot_agent/tools/__init__.py`
- Impact: Low — tools are imported directly by `mcp_server.py` using explicit module paths

**[MEDIUM] OCR pipeline is optional and undocumented as a hard dependency:**
- Issue: `pytesseract` and `Pillow` are commented out in `rca_agent/requirements.txt` (lines 21–22). The OCR step in `run_pipeline.py` is marked "non-fatal" and skipped on failure. However, if OCR is unavailable, the RCA agent has no access to image attachment text, which may be the primary evidence in many incidents.
- Files: `rca_agent/requirements.txt`, `rca_agent/run_pipeline.py` (lines 101–117)
- Impact: Silent degradation — agent runs without error but produces lower-quality RCA when attachments contain key evidence

**[MEDIUM] No tests exist anywhere in the project:**
- Issue: Zero test files found (`test_*.py`, `*_test.py`, `conftest.py`). No `pytest.ini`, `setup.cfg [tool:pytest]`, or `pyproject.toml`. The BigQuery query safety validator (`validate_query`), Gemini tool-call parsing, and incident identifier extraction regex are completely untested.
- Files: All source files — no corresponding test coverage
- Impact: Regressions in the keyword blocklist, regex extractors, or LLM provider adapters will not be caught before production

**[LOW] `rca_agent/mcp_server.py` BQ init runs unconditionally:**
- Issue: At startup, `mcp_server.py` calls `init_executor()` even when BQ credentials are absent, causing a `RuntimeError` on the first BQ tool call rather than a graceful "BQ not configured" message. The copilot variant has the `is_enabled()` guard; the agent variant does not.
- Files: `rca_agent/mcp_server.py` (lines 62–86)

---

## Fragile Areas

**[HIGH] Global module-level singletons prevent concurrent use and testing:**
- What's fragile: `_loader`, `_executor`, `_wiki`, `_store` are process-level globals. Calling `init_loader()` replaces the loader for all in-flight requests. If `batch` mode in `run_pipeline.py` (or an async MCP server) runs multiple investigations concurrently, they share and overwrite the same wiki state.
- Files: `rca_agent/tools/snow_tool.py` (line 307), `rca_agent/tools/bigquery_tool.py` (line 244), `rca_agent/tools/wiki_tool.py` (line 143), `rca_copilot_agent/tools/incident_store.py` (line 287)
- Safe modification: Always reinitialize via `init_*()` before each investigation; never run concurrent investigations in the same process

**[MEDIUM] TOOL_SCHEMAS in `agent_runner.py` uses `model_json_schema()` at import time:**
- What's fragile: `BQQueryInput.model_json_schema()`, `IncidentSearchInput.model_json_schema()`, etc. are called at module load (lines 148–189). If Pydantic's schema format changes between versions or a model has a field with an unsupported type, import fails silently or produces malformed schemas.
- Files: `rca_agent/agent_runner.py` (lines 148–189)

**[MEDIUM] `rca_agent/snow_image_ocr_agent.py` uses `sys.exit()` inside library functions:**
- What's fragile: `configure_tesseract()` calls `sys.exit(1)` (line 84). If `snow_image_ocr_agent` is imported as a module (rather than run as a script), any caller that invokes `configure_tesseract()` will kill the entire process on missing Tesseract.
- Files: `rca_agent/snow_image_ocr_agent.py` (lines 67–84)

**[LOW] `_get_related_stories()` in `snow_reader.py` silently swallows all SNOW errors:**
- What's fragile: The `except Exception: pass` at line 499 in `rca_copilot_agent/tools/snow_reader.py` means a 401/403 or network error during story lookup is silently dropped. Related stories will appear as an empty list in the RCA even if the SNOW session has expired.
- Files: `rca_copilot_agent/tools/snow_reader.py` (lines 477–502)

---

## Scalability Concerns

**[MEDIUM] Entire incident dataset loaded into memory as a Python list:**
- Problem: `IncidentLoader.load()` and `IncidentStore.load()` read `_all_incidents.json` into `self.incidents: list[dict]`. With hundreds of incidents, each with full comments/work_notes/attachments, this list can grow to several hundred MB.
- Files: `rca_agent/tools/snow_tool.py` (line 48), `rca_copilot_agent/tools/incident_store.py` (line 52)
- Limit: Untested beyond ~500 incidents; search is O(n × fields) linear scan
- Scaling path: Replace with SQLite FTS or DuckDB for large incident archives

**[MEDIUM] BigQuery `list_tables()` calls `client.get_table()` for every table:**
- Problem: `SafeBigQueryExecutor.list_tables()` issues one `get_table()` API call per table to retrieve row counts and size (lines 179–190). On a dataset with 50+ tables, this is 50+ serial API calls, taking 30–60 seconds.
- Files: `rca_agent/tools/bigquery_tool.py` (lines 179–190), `rca_copilot_agent/tools/bigquery_tool.py` (lines 179–190)
- Scaling path: Use `INFORMATION_SCHEMA.PARTITIONS` or `__TABLES__` meta-table via a single query

---

## Operational Concerns

**[HIGH] No logging to file or structured log output:**
- Problem: `logging.basicConfig(level=logging.INFO, format="%(message)s")` writes to stdout/stderr. In production or batch mode, logs are lost unless the caller captures them. There is no log rotation, no JSON log format, no correlation ID per investigation.
- Files: `rca_agent/agent_runner.py` (line 460), `rca_agent/mcp_server.py`
- Impact: Debugging failed investigations requires reproducing them locally

**[HIGH] No retry or rate-limit handling for LLM API calls:**
- Problem: `AnthropicProvider.chat()`, `OpenAIProvider.chat()`, and `GoogleProvider.chat()` make a single API call. On rate-limit (HTTP 429) or transient network error, the agent loop catches the exception, prints it, and aborts the investigation at that step.
- Files: `rca_agent/llm_providers.py` (lines 79–120, 169–198, 351–393)
- Fix approach: Add exponential backoff using `tenacity` or manual retry with `time.sleep()` on `429` responses

**[MEDIUM] Generated reports written to relative paths (`./rca_reports/`, `./wiki/`):**
- Problem: `AgentConfig.output_dir` defaults to `"./rca_reports"` and `wiki_dir` to `"./wiki"`. When `agent_runner.py` is invoked from different working directories (e.g., as part of `run_pipeline.py` via `subprocess.run(cwd=Path(__file__).parent)`), reports land in unexpected locations.
- Files: `rca_agent/config.py` (lines 95–96), `rca_agent/run_pipeline.py` (line 48)

**[MEDIUM] `post_comment` tool in copilot MCP has no confirmation guard at the API level:**
- Problem: `rca_copilot_agent/mcp_server.py` calls `reader.post_comment()` immediately when the tool is invoked (line 421). The agent prompt instructs the LLM to "confirm with user before calling," but there is no server-side guard. A misbehaving LLM could post comments to production incidents without user approval.
- Files: `rca_copilot_agent/mcp_server.py` (lines 421–440)

---

## Test Coverage Gaps

**[CRITICAL] Zero test coverage across the entire project:**
- What's not tested: Query safety validator keyword blocklist, identifier extraction regexes, Gemini tool-call parsing, `resolve_path()` path normalization, `_extract_section()` markdown parser, `upsert_incident_report()` merge logic, all LLM provider adapters
- Files: `rca_agent/tools/bigquery_tool.py`, `rca_agent/llm_providers.py`, `rca_agent/snow_image_ocr_agent.py`, `rca_agent/agent_runner.py`, `rca_copilot_agent/tools/incident_store.py`
- Risk: A query like `SELECT * FROM table WHERE name = 'DROP TABLE'` could break the keyword filter (the filter strips string literals but the `re.sub` order matters); untested
- Priority: HIGH — add `pytest` with unit tests for `validate_query()`, `extract_identifiers()`, and `_extract_section()` at minimum

---

*Concerns audit: 2026-04-24*
