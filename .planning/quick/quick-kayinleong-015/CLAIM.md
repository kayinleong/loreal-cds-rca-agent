# Claim: quick-kayinleong-015
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-06
- status: in-progress
- summary: Fix rca_copilot_agent bq CLI auth failure — augment subprocess PATH so bq can find gcloud internally when launched from VS Code MCP

## What will change
- `rca_copilot_agent/tools/bigquery_tool.py`: add `_sdk_env()` helper that prepends the Cloud SDK `bin/` dir to PATH; pass it to `_bq_cli_execute()` subprocess call

## What has changed
(filled during execution)

## Verification
(filled after fix)
