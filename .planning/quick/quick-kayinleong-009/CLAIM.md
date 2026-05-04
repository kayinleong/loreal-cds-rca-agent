# Claim: quick-kayinleong-009
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Add gcloud ADC auth check at MCP startup — detect non-loreal.com account or missing ADC and trigger gcloud auth application-default login

## What will change
- New `rca_copilot_agent/tools/gcloud_tool.py` — check active gcloud account + ADC validity, trigger login if not loreal.com
- `rca_copilot_agent/mcp_server.py` — call ensure_gcloud_auth() after ensure_credentials()
- `rca_copilot_agent/AGENTS.md` — document gcloud check

## What has changed
(to be filled)

## Verification
(to be filled)
