# Claim: quick-kayinleong-014
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-06
- status: in-progress
- summary: fix bq CLI not found in rca_copilot_agent when launched via VS Code MCP (PATH stripped)

## What will change
- `rca_copilot_agent/tools/bigquery_tool.py`: add `_find_bq()` with fallback paths (mirrors `_find_gcloud()` pattern from gcloud_tool.py), update `_bq_cli_available()` and `_bq_cli_execute()` to use it

## What has changed
<!-- filled after work completes -->

## Verification
<!-- filled after testing -->
