# Claim: quick-kayinleong-005
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Remove Python client fallback in rca_copilot_agent bigquery_tool — use bq CLI directly, no retry

## What will change
- `rca_copilot_agent/tools/bigquery_tool.py`: modify `query_bigquery` to skip the Python client execution step and call `_bq_cli_execute` directly
- Remove `_is_permission_error` helper (no longer needed)
- Keep `validate_query` (blocklist safety) and `_pick_executor` (billing project routing)
- Keep `SafeBigQueryExecutor` class but stop calling its `execute()` / `dry_run()` from `query_bigquery`

## What has changed
- Removed `_is_permission_error` helper (no longer needed)
- Modified `query_bigquery` to call `executor.validate_query` then `_bq_cli_execute` directly — no Python client attempt, no fallback retry
- The "[BQ] Python client permission denied — retrying with bq CLI" log line is gone

## Verification
- Regression surface: only `query_bigquery` call path changed; `lookup_schema`, `init_from_schema`, and `is_enabled` are untouched
- `validate_query` still runs before bq CLI — blocklist safety preserved
- `_pick_executor` still routes to the correct billing project — multi-project behaviour unchanged
- No new dependencies introduced
- Manual check: diff confirms removal of retry block and `_is_permission_error`
