---
status: complete
---
## Goal
Make rca_copilot_agent CLI-only: move _dispatch to dispatcher.py, delete mcp_server.py, add venv re-exec + missing-package hint + unknown-tool rejection to run_tool.py, drop the ADC login from ensure_gcloud_auth.

## Changes Made
- `rca_copilot_agent/dispatcher.py` (new): TOOL_NAMES (15), TOOL_HELP, _build_reader, _dispatch, _REPORT_META_KEYS, _display_value, _ensure_store_loaded, _resolve_sys_id. _dispatch body identical to HEAD (only "[MCP]" log prefix -> "[RCA]"). _auto_load_store dropped (unused by _dispatch).
- `rca_copilot_agent/mcp_server.py`: git rm.
- `rca_copilot_agent/run_tool.py`: _reexec_in_repo_venv, _missing_package_hint, unknown-tool early reject, imports dispatcher, docstring.
- `rca_copilot_agent/tools/gcloud_tool.py`: ADC helpers/step removed; docstring updated.
- config.py, tools/auth_tool.py, tools/bigquery_tool.py: docstring/message fixes (MCP, ADC).
- Tests: test_dispatch_rca_flow.py (dispatcher), test_run_tool.py (+unknown tool, re-exec, missing module), test_bq_crossplatform.py (+no ADC).

## Verification
132 tests OK on scratchpad venv and bare 3.12; py_compile OK; /usr/bin/python3 (3.9) --help and unknown-tool smoke OK; grep -i mcp in rca_copilot_agent/*.py empty.

## Regression
_dispatch diff vs HEAD identical apart from log prefix; all dispatch-flow tests unchanged and passing.

## Blockers
None.
