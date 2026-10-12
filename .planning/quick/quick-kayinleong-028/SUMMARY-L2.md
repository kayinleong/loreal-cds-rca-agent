---
status: complete
---
## Goal
Document one-command setup (setup.sh / setup.cmd / VS Code task), doctor, auto-.venv re-exec, retrieval and MCP-optional notes in the ticketasg and mockdata agent docs.
## Changes Made
- ticketasg: `.github/agents/ticketasg_copilot.agent.md`, `.claude/skills/ticketasg-copilot/SKILL.md` (new Setup section after command pattern; Prerequisites item 1 no longer says activate venv), `ticketasg_copilot_agent/AGENTS.md` (Install block under Environment Setup; header tagline now mentions CLI or optional mcp_server).
- mockdata: `.github/agents/mockdata_copilot.agent.md` (Setup section), `.claude/skills/mockdata-copilot/SKILL.md` (Setup section + Prerequisites item 1), `mockdata_copilot_agent/AGENTS.md` (Setup section before "Running Without MCP").
## Verification
Code fences even in all 6 files. grep activate|pip install|mcp.json: only intentional "python -m pip install -r <pkg>/requirements.txt" manual fallbacks and unrelated "Mars ID inactivated" matches. Verified: assignment_tool.py sets retrieval_block available=False on retrieval error and continues (rules+keyword); openpyxl lazily imported in mockdata_tool.py; flags --skip-retrieval/--with-mcp exist; setup.sh, setup.cmd, scripts/doctor.py, requirements-mcp.txt, tasks "RCA: Setup (all agents)"/"RCA: Doctor" exist; Missing-package hint text matches rca run_tool.py.
## Regression
Docs only; workflow/tool content untouched.
## Blockers
None.
