# Claim: quick-kayinleong-004
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Fix my_reports/ and attachments/ not being created at project root when using MCP server

## What will change
- `.vscode/mcp.json` — add REPORTS_DIR and ATTACHMENTS_DIR env vars pointing to workspace root
- `rca_copilot_agent/mcp_server.py` — fix docstring that incorrectly states default is `./my_reports`

## Root Cause
`rca_copilot_agent/config.py` uses `_PKG_DIR / "my_reports"` as the default path (absolute, inside the package dir at `rca_copilot_agent/my_reports/`). `.vscode/mcp.json` didn't set REPORTS_DIR or ATTACHMENTS_DIR, so dirs were created inside `rca_copilot_agent/` instead of the project root. The `.github/agents/rca_copilot.agent.md` agent spec already correctly sets `REPORTS_DIR: ./my_reports`, but VS Code's mcp.json did not.

## What changed
- `.vscode/mcp.json`: added `"REPORTS_DIR": "${workspaceFolder}/my_reports"` and `"ATTACHMENTS_DIR": "${workspaceFolder}/attachments"` — these explicit env vars override the `_PKG_DIR`-based config default so dirs land at the project root.
- `rca_copilot_agent/mcp_server.py`: corrected docstring comment to reflect the actual default resolution path.

## Verification
- Config logic confirmed: `REPORTS_DIR` env var takes priority over `_PKG_DIR`-based default in `load_config()` (`os.environ.get(key) or env_data.get(key, default)` — env var wins).
- Regression surface: no code logic changed, only configuration and docstring. No other features touch directory creation path.
- The `.github/agents/rca_copilot.agent.md` spec already had the correct `REPORTS_DIR: ./my_reports`; `.vscode/mcp.json` is now consistent with it.
