# Claim: quick-kayinleong-005
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Remove Python client fallback in rca_copilot_agent bigquery_tool — use bq CLI directly, no retry

## What will change
- `rca_copilot_agent/tools/bigquery_tool.py`: modify `query_bigquery` to skip the Python client execution step and call `_bq_cli_execute` directly
- Remove `_is_permission_error` helper (no longer needed)
- Keep `validate_query` (blocklist safety) and `_pick_executor` (billing project routing)
- Keep `SafeBigQueryExecutor` class but stop calling its `execute()` / `dry_run()` from `query_bigquery`

## What has changed
(to be filled)

## Verification
(to be filled)
