# Claim: quick-kayinleong-003
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Fix BQ multi-project billing (bigquery.jobs.create denied for DV project), improve rca_copilot_agent AGENTS.md with deeper B2B investigation guidance

## What will change
1. `rca_copilot_agent/tools/bigquery_tool.py` — maintain one executor per project (pd + dv); detect billing project from SQL backtick refs so B2B DV queries run against the correct project
2. `rca_copilot_agent/AGENTS.md` — add B2B customer-search diagnostic workflow, strengthen multi-query investigation guidance, add "cannot search customer" root cause patterns

## What has changed
1. `rca_copilot_agent/tools/bigquery_tool.py`:
   - Replaced single `_executor` with `_executors: dict[str, SafeBigQueryExecutor]`
   - `init_from_schema()` now creates one executor per distinct GCP project in schema.json (`oa-apmena-spacecds-ap-pd` and `oa-apmena-spacecds-ap-dv`)
   - Added `_pick_executor(sql)` that detects the billing project from backtick table refs in the SQL and routes to the correct executor
   - `query_bigquery()` now uses `_pick_executor()` instead of the single executor
   - All existing exports (`is_enabled`, `_get_executor`, `query_bigquery`, `lookup_schema`) preserved

2. `rca_copilot_agent/AGENTS.md`:
   - Added Phase 3b "B2B Customer Cannot Search / Cannot Create Checklist" with 5 ready-to-run SQL patterns covering: exist-by-customercode, phone fuzzy search, CFS profile lookup, CFS-customer affiliation, store prefix search
   - Added interpretation table mapping query results to root causes
   - Added guidance that 0 rows IS a finding, not a failure
   - Clarified that a failed BQ query is not the same as "no root cause"
   - Updated table refs to include full `project.dataset.table` form
   - Added B2B-specific root causes 7-13 to the Common Root Causes section

## Verification
- Unit tests: `_pick_executor()` tested for B2B DV SQL → `oa-apmena-spacecds-ap-dv`, B2C PD SQL → `oa-apmena-spacecds-ap-pd`, plain SQL → default project. All 3 pass.
- Syntax: `ast.parse()` on bigquery_tool.py passes
- Regression: `is_enabled()`, `_get_executor()`, `query_bigquery()`, `get_schema_from_file()` signatures and behaviour unchanged; mcp_server.py calls `is_enabled()` and `query_bigquery()` which both use `_executors` dict — no caller changes required
- No secrets introduced; no `.env` changes; no schema.json changes
