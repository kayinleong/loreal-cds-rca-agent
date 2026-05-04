# Claim: quick-kayinleong-007
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Automate COOKIE and X_USERTOKEN capture for rca_copilot_agent — detect missing/expired credentials and auto-populate .env via browser automation

## What will change
- New `rca_copilot_agent/tools/auth_tool.py` — validates current credentials against SNOW and launches browser automation to capture fresh ones when needed
- `rca_copilot_agent/mcp_server.py` — call credential check at startup before tools are registered/used
- `rca_copilot_agent/AGENTS.md` — document the new auth_tool and the startup credential flow

## What has changed
(to be filled after execution)

## Verification
(to be filled after execution)
