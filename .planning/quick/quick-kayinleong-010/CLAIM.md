# Claim: quick-kayinleong-010
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: After gcloud ADC login, set quota project to oa-apmena-spacecds-ap-pd to fix serviceusage permission warning

## What will change
- `rca_copilot_agent/tools/gcloud_tool.py` — add `set_quota_project()` and call it after every successful `run_adc_login()`

## What has changed
- Added `set_quota_project(project_id)` — runs `gcloud auth application-default set-quota-project`; reads project from `BQ_PROJECT` env var, defaults to `oa-apmena-spacecds-ap-pd`
- All three `run_adc_login()` call sites in `ensure_gcloud_auth()` now call `set_quota_project()` on success

## Verification

### Regression Surface
Only `gcloud_tool.py` touched. `set_quota_project` is called only after a successful login — no change to the happy path when credentials are already valid.

### What was tested
- Import check passes
- `set_quota_project` reads `BQ_PROJECT` env var with correct fallback

### What was ruled out
- No SNOW auth, BQ, or MCP server logic changed
