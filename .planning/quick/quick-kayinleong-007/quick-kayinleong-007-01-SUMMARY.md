---
phase: quick-kayinleong-007
plan: "01"
subsystem: rca_copilot_agent/tools
tags: [auth, playwright, servicenow, credentials, mcp-server]
dependency_graph:
  requires: [rca_copilot_agent/config.py, rca_copilot_agent/tools/snow_reader.py]
  provides: [rca_copilot_agent/tools/auth_tool.py]
  affects: [rca_copilot_agent/mcp_server.py]
tech_stack:
  added: [playwright>=1.50 (optional, browser automation)]
  patterns: [lazy-import for optional dependency, thread-per-event-loop for playwright async API]
key_files:
  created: [rca_copilot_agent/tools/auth_tool.py]
  modified:
    - rca_copilot_agent/tools/snow_reader.py
    - rca_copilot_agent/mcp_server.py
    - requirements.txt
    - rca_copilot_agent/AGENTS.md
decisions:
  - "Playwright imports are lazy (inside capture_credentials_via_browser function body) so auth_tool.py imports cleanly without playwright installed"
  - "ensure_credentials() call in mcp_server.main() is wrapped in try/except so no auth_tool bug can block server startup"
  - "validate() fix uses Content-Type + JSON parse check per ServiceNow KB0966965 (HTTP 200 + HTML for expired sessions)"
  - "Thread pattern with own asyncio event loop isolates Playwright from MCP server's asyncio loop"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-04T05:43:35Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 5
---

# Phase quick-kayinleong-007 Plan 01: Auto-capture COOKIE + X_USERTOKEN via Playwright SSO Summary

**One-liner:** Playwright-based ServiceNow SSO credential auto-capture with validate() fix for HTTP-200-but-HTML expired sessions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create auth_tool.py and fix validate() in snow_reader.py | 4482a51f | rca_copilot_agent/tools/auth_tool.py (created), rca_copilot_agent/tools/snow_reader.py |
| 2 | Wire ensure_credentials() into mcp_server.main(), add playwright to requirements.txt, update AGENTS.md | 30ac7438 | rca_copilot_agent/mcp_server.py, requirements.txt, rca_copilot_agent/AGENTS.md |

## What Was Built

### auth_tool.py (new)

Four pure functions:

- **`is_session_valid(cookie, x_user_token, instance_url)`** — returns False immediately for empty credentials; otherwise instantiates ServiceNowReader, calls authenticate() and validate(); catches all exceptions and returns False.
- **`capture_credentials_via_browser(instance_url)`** — opens headed Chromium via playwright.async_api, navigates to instance_url, waits up to 10 minutes for SSO login completion (URL matches `**/now/nav/ui/classic**`), guards against window.g_ck being undefined, extracts cookies (filtered to loreal.service-now.com domain with substring match) and window.g_ck, returns (cookie_header, x_user_token). Playwright imports are lazy. Runs in a dedicated thread with its own asyncio event loop.
- **`write_credentials_to_env(env_path, cookie, x_user_token)`** — uses dotenv.set_key() to write only COOKIE and X_USERTOKEN; all other .env lines preserved. Never logs credential values.
- **`ensure_credentials(instance_url)`** — top-level entry: loads config, checks validity, triggers browser flow if needed, writes back to .env, reloads and verifies. ImportError/RuntimeError from playwright are caught and printed non-fatally.

### validate() fix in snow_reader.py

Replaced the single-check `return resp.status_code == 200` with a three-step check:
1. status_code != 200 → return False
2. Content-Type does not contain application/json → return False (detects HTML login pages)
3. resp.json() raises or 'result' not in data → return False

This resolves ServiceNow KB0966965: expired sessions return HTTP 200 + HTML body.

### mcp_server.py wiring

Added after `_auto_load_store()`, before `asyncio.run(run())`:
```python
try:
    from tools.auth_tool import ensure_credentials
    ensure_credentials(instance_url=cfg.instance_url)
except Exception as auth_err:
    logger.warning(f"[AUTH] Credential check failed: ...")
```

### requirements.txt

Added `playwright>=1.50` with comment explaining it is optional and requires `playwright install chromium`.

### AGENTS.md

- Added `auto_credential_refresh` row to Tool Inventory table.
- Added Environment Setup section with first-time playwright install instructions.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

All mitigations from the plan's STRIDE threat register are implemented:

| T-ID | Status |
|------|--------|
| T-007-01 Information Disclosure: never log credential values | Implemented — only byte-lengths logged |
| T-007-02 .env gitignore | Pre-existing; no change needed |
| T-007-03 set_key preserves other .env lines | Implemented — set_key() used with quote_mode="never" |
| T-007-04 10-minute timeout | Implemented — wait_for_url timeout=600_000ms |
| T-007-05 Playwright subprocess privilege | Accepted — no escalation path |

No new threat surface introduced beyond what the plan documented.

## Self-Check: PASSED

- auth_tool.py exists: FOUND
- snow_reader.py validate() updated: FOUND (three-step check at lines 78-101)
- mcp_server.py ensure_credentials wiring: FOUND (before asyncio.run(run()))
- playwright>=1.50 in requirements.txt: FOUND
- AGENTS.md auto_credential_refresh row: FOUND
- AGENTS.md Environment Setup section: FOUND
- Task 1 commit 4482a51f: FOUND
- Task 2 commit 30ac7438: FOUND
