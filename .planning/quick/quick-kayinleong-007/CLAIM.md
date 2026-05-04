# Claim: quick-kayinleong-007
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Automate COOKIE and X_USERTOKEN capture for rca_copilot_agent — detect missing/expired credentials and auto-populate .env via browser automation

## What will change
- New `rca_copilot_agent/tools/auth_tool.py` — validates current credentials against SNOW and launches browser automation to capture fresh ones when needed
- `rca_copilot_agent/mcp_server.py` — call credential check at startup before tools are registered/used
- `rca_copilot_agent/AGENTS.md` — document the new auth_tool and the startup credential flow

## What has changed
- Created `rca_copilot_agent/tools/auth_tool.py` with four exported functions:
  - `is_session_valid()` — validates COOKIE + X_USERTOKEN via lightweight REST call
  - `capture_credentials_via_browser()` — opens headed Chromium for SSO, extracts cookies + window.g_ck
  - `write_credentials_to_env()` — writes COOKIE and X_USERTOKEN back to .env via dotenv set_key
  - `ensure_credentials()` — top-level entry point called at MCP server startup
- Fixed `validate()` in `rca_copilot_agent/tools/snow_reader.py` to reject HTTP 200 + HTML responses (expired sessions): now checks status_code, Content-Type contains application/json, and that resp.json() contains a 'result' key
- Added `ensure_credentials(instance_url=cfg.instance_url)` call in `mcp_server.main()` after `_auto_load_store()` and before `asyncio.run(run())`, wrapped in try/except
- Added `playwright>=1.50` to `requirements.txt` with install-chromium note
- Added `auto_credential_refresh` row to AGENTS.md Tool Inventory table
- Added Environment Setup section to AGENTS.md documenting playwright first-time setup

## Verification

### Regression Surface
The changes touch: `snow_reader.py validate()`, `mcp_server.py main()`, new file `auth_tool.py`, `requirements.txt`, `AGENTS.md`.

Regression risks identified:
1. `validate()` change: could affect any caller that relies on validate() returning True for legitimate responses. Verified: True path requires status 200 + application/json Content-Type + 'result' key — all valid SNOW REST responses satisfy this.
2. `mcp_server.main()` change: the ensure_credentials() call is wrapped in try/except that logs a warning but never raises — server startup cannot be blocked by this change.
3. `auth_tool.py` lazy playwright import: module imports cleanly without playwright installed (verified).

### What was tested
- `python3 -c "from rca_copilot_agent.tools.auth_tool import ensure_credentials, is_session_valid, write_credentials_to_env, capture_credentials_via_browser; print('OK')"` — passes
- validate() mock tests: HTTP 200 + text/html returns False; HTTP 200 + application/json + result key returns True; HTTP 401 returns False — all correct
- Wiring order verification: ensure_credentials appears before asyncio.run(run()) in mcp_server.py
- Secrets hygiene grep: no direct print of cookie or x_user_token values in auth_tool.py
- playwright>=1.50 present in requirements.txt

### What passed
All five verifications from PLAN.md verification section passed.

### What was ruled out and why
- No change to BQ blocklist (unrelated to auth flow)
- No change to incident store, email_tool, bigquery_tool (out of scope)
- The `_build_reader()` raise path is unchanged — still raises RuntimeError when credentials are absent, which is the correct fallback when playwright is not installed
