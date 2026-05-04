# Claim: quick-kayinleong-003
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Fix BQ multi-project billing (bigquery.jobs.create denied for DV project), improve rca_copilot_agent AGENTS.md with deeper B2B investigation guidance

## What will change
1. `rca_copilot_agent/tools/bigquery_tool.py` — maintain one executor per project (pd + dv); detect billing project from SQL backtick refs so B2B DV queries run against the correct project
2. `rca_copilot_agent/AGENTS.md` — add B2B customer-search diagnostic workflow, strengthen multi-query investigation guidance, add "cannot search customer" root cause patterns

## What has changed
(updated on completion)

## Verification
(updated on completion)
