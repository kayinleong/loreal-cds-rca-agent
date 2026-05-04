# Claim: quick-kayinleong-008
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Switch auth_tool.py browser from Chromium to system-installed Edge (channel="msedge")

## What will change
- `rca_copilot_agent/tools/auth_tool.py` — change `p.chromium.launch(headless=False)` to `p.chromium.launch(channel="msedge", headless=False)`
- `requirements.txt` — update comment: Edge is already installed, no `playwright install chromium` needed
- `rca_copilot_agent/AGENTS.md` — update Environment Setup section to reference Edge

## What has changed
(to be filled)

## Verification
(to be filled)
