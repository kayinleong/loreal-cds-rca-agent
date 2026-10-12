# Claim: quick-kayinleong-028
- owner: kayinleong
- session: claude-code
- branch: feature/quick-kayinleong-028-easy-install (stacked on feature/phase-kayinleong-03-rca-copilot-xplat / PR #3)
- started: 2026-10-12
- status: in-progress
- summary: One-command setup (macOS + Windows) that installs all 3 Copilot agents (rca_copilot, ticketasg, mockdata) with no missing libraries; clean requirements.txt; delete legacy rca_agent/; remove MCP-server mode from rca_copilot_agent (CLI-only); rewrite repo CLAUDE.md. Scope approved by user 2026-10-12.

## What will change

Research first (dependency audit per agent package + install-approach research), then:
- Minimal, complete dependency set for `rca_copilot_agent` (per-agent requirements file).
- Root `requirements.txt` cleaned to direct dependencies actually used (nothing other agents need is dropped).
- One-command setup for macOS and Windows + a dependency self-check so nothing is silently missing.
- Docs updated (Copilot agent, Claude skill, AGENTS.md for all 3 agents).
- User-approved deletions: `rca_agent/` (legacy standalone agent), `rca_copilot_agent/mcp_server.py` (dispatch moves to a plain module), `.vscode/mcp.json` (only registered that MCP server).
- User-approved rewrite of repo-root `CLAUDE.md` for the 3 Copilot agents.

## What has changed

_(pending)_

## Verification

_(pending)_
