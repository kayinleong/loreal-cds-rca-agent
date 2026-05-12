# Claim: quick-kayinleong-017
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-12
- status: done
- summary: Convert rca_copilot_agent MCP tools to skills — create Python CLI, Claude Code skill files, and update GitHub Copilot agent definition to work without MCP server

## What Will Change

1. `rca_copilot_agent/run_tool.py` — new unified CLI entry point wrapping all tool functions
2. `.claude/skills/rca-copilot/SKILL.md` — new Claude Code skill teaching the full RCA workflow via Bash
3. `.github/agents/rca_copilot.agent.md` — updated to remove `mcp-servers:` and `tools:` MCP references, replaced with terminal-based instructions
4. `rca_copilot_agent/AGENTS.md` — updated with "Without MCP (Skills/CLI)" section

## What Changed

1. **`rca_copilot_agent/run_tool.py`** (new) — unified CLI that dispatches all 14 tool calls via
   `_dispatch()` from `mcp_server.py`. Accepts `--json '{...}'` arguments. Runs the same startup
   sequence as the MCP server (BQ init, incident store load, SNOW auth check, gcloud check).

2. **`.claude/skills/rca-copilot/SKILL.md`** (new) — Claude Code skill with YAML frontmatter,
   full tool invocation reference table, and complete RCA workflow using Bash commands.

3. **`.github/agents/rca_copilot.agent.md`** (updated) — frontmatter changed from
   `tools: [snow-mcp/*]` + `mcp-servers:` block to `tools: [run_in_terminal, read_file]`.
   ABSOLUTE TOOL RESTRICTION section rewritten with CLI mapping table. Tool Use Rules updated.
   Zero `snow-mcp/` or `mcp-servers:` references remain.

4. **`rca_copilot_agent/AGENTS.md`** (updated) — inserted "Running Without MCP (Skills / CLI Mode)"
   section between Environment Setup and Investigation Workflow. Documents all 14 CLI tool names,
   example commands, and references the Claude Code skill.

5. **`rca_copilot_agent/mcp_server.py`** — unchanged (backward compatibility preserved).

## Verification

### What was tested
- `python rca_copilot_agent/run_tool.py --help` — prints usage with all 14 tool names ✓
- `python rca_copilot_agent/run_tool.py list_incidents --json '{}'` — runs correctly, loads 1 incident,
  auth checks pass (ServiceNow credentials valid, gcloud ADC valid) ✓
- `grep -c 'snow-mcp/' .github/agents/rca_copilot.agent.md` → 0 ✓
- `grep -c 'mcp-servers:' .github/agents/rca_copilot.agent.md` → 0 ✓
- `grep 'run_in_terminal' .github/agents/rca_copilot.agent.md` — present in frontmatter ✓
- SKILL.md has valid YAML frontmatter with `name`, `description`, `invocation` fields ✓

### What passed
All 4 acceptance criteria met. CLI functional with live auth.

### What was ruled out and why
- `mcp_server.py` was not modified — not in scope; existing MCP users unaffected
- No new credentials or secrets introduced — run_tool.py reads from `.env` same as before
- Regression surface: `mcp_server.py` and `tools/` are untouched; only new files added plus
  documentation updates in two existing `.md` files
