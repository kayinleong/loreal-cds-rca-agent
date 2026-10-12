---
status: complete
---
## Goal
Fix review findings in bq/gcloud execution: Windows timeout kill, CRLF translation, silent invalid overrides.

## Changes Made
- `rca_copilot_agent/tools/bigquery_tool.py` — `_kill_process_tree` (taskkill /T /F on nt; killpg/kill on POSIX; bounded reap), `_bq_cli_execute` rewritten to Popen + bytes stdin/stdout (utf-8 decode, errors=replace), `start_new_session=True` on POSIX, `_warn_bad_override` (once per process) in `_find_bq`, `_bq_cli_available` now bytes-mode.
- `rca_copilot_agent/tools/gcloud_tool.py` — `_warn_bad_override` + logger warning in `_find_gcloud`.
- `rca_copilot_agent/tests/test_bq_crossplatform.py` — tests moved to Popen API; added timeout/taskkill/killpg/fallback/second-timeout/override-warning/stderr-replacement tests.

## Verification
py_compile OK on both modules; full suite: 91 tests OK.

## Regression
Signatures of query_bigquery / query_bigquery_result unchanged; QueryResult shapes and error strings unchanged; no cost guard added.

## Blockers
None.
