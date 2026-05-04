# Claim: quick-kayinleong-011
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Fix gcloud_tool to also check/run gcloud auth login (for bq CLI), then set account and project after login

## What will change
- `rca_copilot_agent/tools/gcloud_tool.py` — add user-credential check (bq CLI path) alongside existing ADC check

## What has changed
- Rewrote `gcloud_tool.py` to handle two separate credential stores:
  - **User credentials** (`gcloud auth login`) — used by bq CLI: checks account domain + `gcloud auth print-access-token`; on failure: `gcloud auth login` → `gcloud config set account` → `gcloud config set project`
  - **ADC** (`gcloud auth application-default login`) — used by Python client: unchanged logic + set-quota-project
- `ensure_gcloud_auth()` now calls `_ensure_user_auth()` then `_ensure_adc_auth()` in sequence
- Added helpers: `is_user_auth_valid()`, `run_user_login()`, `set_account()`, `set_project()`
- Extracted `_interactive_gcloud()` helper to avoid duplication

## Verification

### Regression Surface
Only `gcloud_tool.py` changed. `mcp_server.py` call site unchanged — still wraps in try/except.

### What was tested
- Import check passes
- Both `_ensure_user_auth` and `_ensure_adc_auth` paths cover: valid, expired, wrong-domain cases

### What was ruled out
- No SNOW auth, BQ query logic, or MCP server code changed
