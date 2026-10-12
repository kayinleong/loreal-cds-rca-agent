---
status: complete
---
## Goal
Review-fix wave executor I: harden send_rca_email dispatch and email subject handling; update docs.

## Changes Made
- `rca_copilot_agent/mcp_server.py` (send_rca_email branch): incident_numbers normalised (list/str -> non-empty stripped list or None); subject falls back to default if empty; mark_emailed wrapped in try/except with warning line; `Attached incidents:` line appended on success; `import re` added.
- `rca_copilot_agent/tools/email_tool.py`: `_clean_subject` + `DEFAULT_SUBJECT`; Subject header sanitised (CR/LF runs -> space). To/From come from config, not caller input.
- Tests: `test_dispatch_rca_flow.py` (+3), `test_email_tool.py` (+2).
- Docs: `.github/agents/rca_copilot.agent.md`, `.claude/skills/rca-copilot/SKILL.md`, `rca_copilot_agent/AGENTS.md` (send email, evidence window, heading tolerance; AGENTS.md privacy note).

## Verification
Full suite: 96 tests OK. py_compile OK. Code fences even; `--json '` count 1 per doc.

## Regression
Existing SendEmailTests (pending/marked, filter, failure-does-not-mark, SMTP disabled) pass; failure path unchanged (no Attached line on ✗).

## Blockers
None.
