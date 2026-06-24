# Claim: phase-kayinleong-02
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-24
- status: in-progress
- summary: Build mockdata_copilot_agent — a Copilot-only agent that, on each prompt, ensures L'Oréal GCP login, generates mock INSERT rows for external_system_ids (seeded from a user-provided row + variation intent), looks up the consumer in consumer_pii and generates a mock consumer_pii row when absent, then writes the generated SQL to mockdata/<MMDDYYSS>.md and presents it to the user.

## What Will Change

Planning complete (2026-06-24) — 5 wave plans authored + verified READY TO EXECUTE by gsd-plan-checker (0 blocking issues). Code changes happen in /gsd-execute-phase.

Planning artifacts in this directory:
- `02-CONTEXT.md` — locked design decisions
- `02-RESEARCH.md` — reuse map, queries, pitfalls, assumptions A1–A9
- `02-PLAN-wave1.md` — Scaffold: `__init__.py`, `config.py` (MockDataConfig, DV defaults), `.gitignore += mockdata/`
- `02-PLAN-wave2.md` — Reuse tools: verbatim `gcloud_tool.py` + `bigquery_tool.py` (blocklist intact, DV routing via BQ_PROJECT, no edits)
- `02-PLAN-wave3.md` — Core: one-time live `consumer_pii` schema fetch + pure `mockdata_tool.py` (seed→N rows, Postgres-style INSERT SQL)
- `02-PLAN-wave4.md` — Surface: `mcp_server.py` (4 tools) + `run_tool.py` + `mockdata/<MMDDYYSS>.md` writer
- `02-PLAN-wave5.md` — Companions: `AGENTS.md`, `.claude/skills/mockdata-copilot/SKILL.md`, `.github/agents/mockdata_copilot.agent.md` + human-verify checkpoint (A1/A2/A3/A4)

Assumptions to confirm before/at execution: A1 SQL dialect (default: match `.docs` Postgres-style sample), A2/A3 full DV consumer_pii columns (live INFORMATION_SCHEMA fetch), A4 consumer existence key (default: lucid).

## What Has Changed

(filled during execution)

## Verification

(filled during execution — Regression Report required before done)
