# Claim: quick-kayinleong-004
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Fix my_reports/ and attachments/ not being created at project root when using MCP server

## What will change
- `.vscode/mcp.json` — add REPORTS_DIR and ATTACHMENTS_DIR env vars pointing to workspace root
- `rca_copilot_agent/mcp_server.py` — fix docstring that incorrectly states default is `./my_reports`

## Root Cause
`rca_copilot_agent/config.py` uses `_PKG_DIR / "my_reports"` as the default path (absolute, inside the package dir at `rca_copilot_agent/my_reports/`). `.vscode/mcp.json` doesn't set REPORTS_DIR or ATTACHMENTS_DIR, so dirs are created inside `rca_copilot_agent/` instead of the project root. The `.github/agents/rca_copilot.agent.md` agent spec already correctly sets `REPORTS_DIR: ./my_reports`, but VS Code's mcp.json does not.
