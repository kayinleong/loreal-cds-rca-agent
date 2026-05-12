# Claim: quick-kayinleong-017
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-12
- status: in-progress
- summary: Convert rca_copilot_agent MCP tools to skills — create Python CLI, Claude Code skill files, and update GitHub Copilot agent definition to work without MCP server

## What Will Change

1. `rca_copilot_agent/run_tool.py` — new unified CLI entry point wrapping all tool functions
2. `.claude/skills/rca-copilot/SKILL.md` — new Claude Code skill teaching the full RCA workflow via Bash
3. `.github/agents/rca_copilot.agent.md` — updated to remove `mcp-servers:` and `tools:` MCP references, replaced with terminal-based instructions
4. `rca_copilot_agent/AGENTS.md` — updated with "Without MCP (Skills/CLI)" section

## What Changed

(to be filled after execution)

## Verification

(to be filled after execution)
