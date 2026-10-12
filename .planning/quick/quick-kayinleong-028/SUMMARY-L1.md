---
status: complete
---
## Goal
Document the one-command setup, CLI-only mode and no-ADC flow in the RCA Copilot agent docs.
## Changes Made
- `.github/agents/rca_copilot.agent.md`: description, tool restriction (setup + doctor allowed), "Platform setup" replaced by "Setup and platform notes".
- `.claude/skills/rca-copilot/SKILL.md`: description/title/intro de-MCP'd, prerequisites, setup section, workflow heading.
- `rca_copilot_agent/AGENTS.md`: header, startup-tool rows, credentials section, setup section, "Running via the CLI" heading, ADC wording.
## Verification
grep for activate|mcp|application-default|ADC: only "no ADC" mentions remain (BigQuery bullets, AGENTS.md auto_gcloud_auth row and Auth line). Fences even (4/16/6). setup.sh, setup.cmd, scripts/doctor.py exist; flags match bootstrap --help.
## Regression
Tool tables, workflow, investigation rules and args-file guidance untouched.
## Blockers
None.
