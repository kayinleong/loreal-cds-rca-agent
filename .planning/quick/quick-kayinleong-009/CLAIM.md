# Claim: quick-kayinleong-009
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Add gcloud ADC auth check at MCP startup — detect non-loreal.com account or missing ADC and trigger gcloud auth application-default login

## What will change
- New `rca_copilot_agent/tools/gcloud_tool.py` — check active gcloud account + ADC validity, trigger login if not loreal.com
- `rca_copilot_agent/mcp_server.py` — call ensure_gcloud_auth() after ensure_credentials()
- `rca_copilot_agent/AGENTS.md` — document gcloud check

## What has changed
- Created `rca_copilot_agent/tools/gcloud_tool.py` with four pure functions: `get_active_gcloud_account()`, `is_adc_configured()`, `run_adc_login()`, `ensure_gcloud_auth()`
- `rca_copilot_agent/mcp_server.py` — added `ensure_gcloud_auth()` call after `ensure_credentials()`, before `asyncio.run(run())`
- `rca_copilot_agent/AGENTS.md` — added `auto_gcloud_auth` row to Tool Inventory

## Verification

### Regression Surface
Only `gcloud_tool.py` (new), `mcp_server.py` (new try/except block), `AGENTS.md` (doc). No existing logic changed.

### What was tested
- `python3 -c "from rca_copilot_agent.tools.gcloud_tool import ensure_gcloud_auth; print('OK')"` — passes
- Confirmed ordering: ensure_credentials (L868) → ensure_gcloud_auth (L875) → asyncio.run (L904)
- gcloud stdout redirected to sys.stderr — MCP stdio protocol is not polluted
- try/except wraps both auth blocks — a bug in either never blocks server startup

### What was ruled out
- No BQ, SMTP, or SNOW tool code changed
- FileNotFoundError (gcloud not installed) handled gracefully in run_adc_login()
