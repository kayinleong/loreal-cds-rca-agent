# Claim: quick-kayinleong-008
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Switch auth_tool.py browser from Chromium to system-installed Edge (channel="msedge")

## What will change
- `rca_copilot_agent/tools/auth_tool.py` — change `p.chromium.launch(headless=False)` to `p.chromium.launch(channel="msedge", headless=False)`
- `requirements.txt` — update comment: Edge is already installed, no `playwright install chromium` needed
- `rca_copilot_agent/AGENTS.md` — update Environment Setup section to reference Edge

## What has changed
- `rca_copilot_agent/tools/auth_tool.py` — `p.chromium.launch(headless=False)` → `p.chromium.launch(channel="msedge", headless=False)`; fallback error message updated (no longer references `playwright install chromium`)
- `requirements.txt` — comment updated: Edge is system-installed, no separate browser download needed
- `rca_copilot_agent/AGENTS.md` — Environment Setup updated to reference Edge and remove `playwright install chromium` step

## Verification

### Regression Surface
Only `auth_tool.py`, `requirements.txt`, `AGENTS.md` touched. No logic changes — single parameter addition `channel="msedge"` in the Playwright launch call.

### What was tested
- `python3 -c "from rca_copilot_agent.tools.auth_tool import ensure_credentials; print('OK')"` — passes (no import-time playwright dependency)
- grep confirms `channel="msedge"` is present and no stale `playwright install chromium` references remain in auth_tool.py

### What passed
Import check passes. Diff is minimal — single parameter change.

### What was ruled out
- No BQ, SMTP, or incident store code touched
