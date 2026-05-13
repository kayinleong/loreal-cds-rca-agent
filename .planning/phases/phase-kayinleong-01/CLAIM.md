# Claim: phase-kayinleong-01
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-13
- status: done
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

1. **`ticketasg_copilot_agent/`** — complete new agent package:
   - `__init__.py`, `tools/__init__.py` — package markers
   - `config.py` — ServiceNowConfig + SmtpConfig extended with `assignment_rules_file` field
   - `mcp_server.py` — 11 tools: 7 SNOW tools + 4 assignment tools (`get_assignment_rules`, `recommend_assignment`, `save_assignment_report`, `send_assignment_email`)
   - `run_tool.py` — CLI entry point dispatching via `mcp_server._dispatch()`
   - `assignment_rules.json` — routing matrix with 10 L2 groups and keyword arrays
   - `tools/assignment_tool.py` — keyword-scoring routing engine (pure functions, no LLM)
   - `tools/snow_reader.py`, `incident_store.py`, `auth_tool.py`, `gcloud_tool.py`, `bigquery_tool.py` — adapted copies from rca_copilot_agent
   - `tools/email_tool.py` — copy with Ticket Assignment branding (3 string changes), `send_rca_email` name preserved
   - `AGENTS.md` — tool inventory, mandatory sequence, report format

2. **`.claude/skills/ticketasg-copilot/SKILL.md`** — Claude Code skill with full workflow, tool mapping table, YAML frontmatter

3. **`.github/agents/ticketasg_copilot.agent.md`** — GitHub Copilot agent definition, no MCP

## Verification

### What was tested

1. `python ticketasg_copilot_agent/run_tool.py --help` → exit 0 ✓
2. `recommend_assignment` SAP test → `APAC - SGP - SPACE CDS SAPMENA L2 Support`, confidence=0.8, `reassignment_needed=True` ✓
3. `recommend_assignment` THN test → `APAC - THN - Retail IT`, `reassignment_needed=False` ✓
4. `recommend_assignment` no-signal test → fallback group, `reassignment_needed=False`, 3 alternatives ✓
5. `get_assignment_rules` → returns string with all 10 canonical group names ✓
6. `grep -r rca_copilot_agent ticketasg_copilot_agent/` → empty (no cross-package imports) ✓
7. SKILL.md YAML frontmatter valid (name, invocation fields present) ✓
8. agent.md YAML frontmatter valid (name, tools fields present) ✓

### What passed
All 6 smoke tests and 4 inline unit tests passed without SNOW/BQ credentials.

### What was ruled out and why
- BigQuery enrichment not included in initial version — assignment uses keyword scoring only (sufficient for routing logic)
- SharePoint URL required corporate SSO — routing keywords are inferred and flagged `[USER-CONFIRM]`
- `mcp_server.py` is created as importable module, not a running server — the CLI pattern requires no server process

### Regression Report
- `rca_copilot_agent/` was not modified — zero regression surface
- No shared files between packages (no symlinks, no imports across packages)
- New `ticketasg_copilot_agent/` is additive only
