# Claim: quick-kayinleong-015
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-06
- status: done
- summary: Fix rca_copilot_agent bq CLI auth failure — augment subprocess PATH so bq can find gcloud internally when launched from VS Code MCP

## What will change
- `rca_copilot_agent/tools/bigquery_tool.py`: add `_sdk_env()` helper that prepends the Cloud SDK `bin/` dir to PATH; pass it to `_bq_cli_execute()` subprocess call

## What has changed
- Added `_sdk_env()` to `rca_copilot_agent/tools/bigquery_tool.py` — builds a subprocess env dict with the Cloud SDK `bin/` dir prepended to PATH, derived from the already-resolved `_find_bq()` path
- Passed `env=_sdk_env()` to `subprocess.run()` in `_bq_cli_execute()` and `_bq_cli_available()`

## Verification
- Regression surface: only `_bq_cli_execute()` and `_bq_cli_available()` are changed; both are subprocess wrappers. Adding `env=` to a subprocess call cannot affect the parent process or any other code path.
- `_sdk_env()` falls back gracefully: if `_find_bq()` returns the bare string `"bq"` (binary not resolved to absolute path), no PATH mutation occurs — behaviour is identical to before.
- The fix is symmetric with the existing `gcloud_tool.py` fix for the same VS Code PATH-stripping issue.
- No new dependencies; no secrets introduced; no public surface changed.
