---
status: complete
---
## Goal
Make rca_copilot_agent BigQuery (bq CLI) execution work on macOS and Windows (W1-W4, contract A); no cost guard.

## Changes Made
- `rca_copilot_agent/tools/bigquery_tool.py` — docstring made honest; Windows SDK dirs + `BQ_BIN` override + PATHEXT-aware `_find_bq`; `_sdk_env` uses `os.pathsep` and sets PYTHONUTF8/PYTHONIOENCODING/CLOUDSDK_CORE_DISABLE_PROMPTS; `_bq_cli_timeout()` (`BQ_CLI_TIMEOUT`, default 120); `_bq_cli_execute` sends SQL via stdin, adds `--headless`, utf-8 decoding; `_bq_cli_available` same env/encoding; new `query_bigquery_result()`; `query_bigquery()` wraps it.
- `rca_copilot_agent/tools/gcloud_tool.py` — `GCLOUD_BIN`, Windows `gcloud.cmd` fallbacks, no X_OK requirement on nt, utf-8 in `_run_gcloud`; interactive login calls unchanged.
- `rca_copilot_agent/tests/test_bq_crossplatform.py` — new, 19 offline tests.

## Verification
unittest discover on new file: 19 pass; full tests dir run; py_compile OK on both modules.

## Regression
Callers: mcp_server.py imports `query_bigquery` (signature unchanged); run_tool.py by name only. `_find_bq/_sdk_env/_find_gcloud/_run_gcloud` used only inside the two tool files. Blocklist/validate_query untouched.

## Blockers
Real Windows `.cmd` + stdin behaviour not run-verified (no Windows host).
