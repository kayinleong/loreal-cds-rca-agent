---
status: complete
---
## Goal
Wire wave-1 modules (bigquery result, rca_report_tool, email report_entries) into rca_copilot_agent/mcp_server.py (MCP + run_tool dispatch).

## Changes Made
- `rca_copilot_agent/mcp_server.py` — TOOL_NAMES (15) + JSON-RPC fallback uses it; query_bigquery `incident_number` evidence logging (non-fatal); new `get_rca_template`; save_rca_report via `rca_report_tool.save_report` with store metadata (`_display_value`, `_REPORT_META_KEYS`), `✗ RCA report NOT saved` on ValueError; send_rca_email `incident_numbers` + pending_reports/mark_emailed; post_comment `confirmed` gate (preview before any reader build); schemas/descriptions/docstring updated; removed `register_report` use.
- `rca_copilot_agent/run_tool.py` — docstring tool list only.
- `rca_copilot_agent/tests/test_dispatch_rca_flow.py` — 17 new offline tests.

## Verification
`python -m unittest discover -s rca_copilot_agent/tests`: 81 tests OK (64 existing + 17 new). py_compile OK; `run_tool.py --help` OK; create_mcp_server list_tools returns 15 names == TOOL_NAMES.

## Regression
Diff shows only one new `name ==` branch (get_rca_template); other branches untouched except the four intended bodies.

## Blockers
None. No wave-1 bugs found.
