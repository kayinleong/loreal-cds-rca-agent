---
status: complete
---
## Goal
Update the three RCA Copilot instruction files for the cross-platform invocation (--arg / --json-file), get_rca_template, validated save, evidence recording, gated post_comment, macOS/Windows setup.

## Changes Made
- `.github/agents/rca_copilot.agent.md` — frontmatter tools (+read/readFile, edit/createFile, edit/editFiles); tool restriction, invocation, 15-tool table, mandatory sequence, new "Platform setup" section, Steps 1-3 (gated post_comment), BigQuery rationale/incident_number, template section replaced by get_rca_template pointer + 4-heading skeleton, tool-use/analysis rules.
- `.claude/skills/rca-copilot/SKILL.md` — prerequisites (gcloud auth login, no ADC), Platform setup, argument-passing section, 15-tool table, workflow with get_rca_template / incident_number / validation retry / gated post_comment, template + group tables replaced by pointer + skeleton.
- `rca_copilot_agent/AGENTS.md` — tool inventory (get_rca_template, fixed list_bq_tables, gated post_comment), new Platform Setup + CLI section (15 tools), Phase 2/3/4 updates, Report Template replaced by source-of-truth pointer (`rca_report_tool.py`), BigQuery access/auth lines fixed (bq CLI, gcloud auth login, BQ_BIN/GCLOUD_BIN/BQ_CLI_TIMEOUT).

## Verification
- No `--json '` except one "do not use" mention per file; no ADC references except "ADC is not used".
- All referenced tool names exist in mcp_server.py (incl. get_rca_template); flags checked against run_tool.py --help.
- 4 example arg forms parsed via _load_arguments (apostrophe + non-ASCII file, --arg, --arg+file). Code fences even in all files.

## Regression
Docs only; investigation rules, B2B checklist, identifier maps, root-cause catalogue untouched.

## Blockers
Copilot tool IDs (read/readFile, edit/createFile, edit/editFiles) unverified against the user's VS Code version.
