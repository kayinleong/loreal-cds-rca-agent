# Claim: phase-kayinleong-01
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-13
- status: in-progress
- summary: Create Ticket Assignment Agent (ticketasg_copilot_agent) — skills-based agent that analyses ServiceNow incidents and recommends the correct L2 assignment group based on ticket content, comments, attachments, and RCA findings

## What Will Change

1. `ticketasg_copilot_agent/` — new agent package mirroring `rca_copilot_agent` structure
   - `__init__.py`
   - `config.py` — shared config (reuses SNOW + SMTP vars, adds assignment-specific tunables)
   - `run_tool.py` — CLI entry point for all tools
   - `tools/`
     - `assignment_tool.py` — core group assignment logic; maps ticket signals to groups
     - `incident_store.py` — reused from rca_copilot_agent (or symlinked)
     - `snow_reader.py` — ServiceNow ticket fetcher (reused/adapted)
2. `.claude/skills/ticketasg-copilot/SKILL.md` — Claude Code skill (skills-based, no MCP)
3. `.github/agents/ticketasg_copilot.agent.md` — GitHub Copilot agent definition
4. `ticketasg_copilot_agent/AGENTS.md` — documentation for the agent's tools and workflow

## What Has Changed

(filled after execution)

## Verification

(filled after execution)
