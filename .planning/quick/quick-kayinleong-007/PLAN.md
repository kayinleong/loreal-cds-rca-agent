---
phase: quick-kayinleong-007
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rca_copilot_agent/tools/auth_tool.py
  - rca_copilot_agent/tools/snow_reader.py
  - rca_copilot_agent/mcp_server.py
  - rca_copilot_agent/AGENTS.md
  - requirements.txt
autonomous: true
requirements:
  - auto-capture COOKIE and X_USERTOKEN via Playwright on missing/expired credentials
  - fix validate() in snow_reader.py to detect HTTP-200-but-HTML expired sessions
  - add playwright>=1.50 to requirements.txt
  - update AGENTS.md with auth_tool description

must_haves:
  truths:
    - "MCP server starts without crashing when COOKIE/X_USERTOKEN are absent from .env"
    - "On missing or stale credentials, a headed Chromium window opens and the user can complete SSO login"
    - "After SSO login, COOKIE and X_USERTOKEN are written back to .env without disturbing other keys"
    - "validate() returns False when ServiceNow responds with HTTP 200 + HTML (expired session)"
    - "validate() returns True only when response is JSON with a 'result' key"
    - "If playwright is not installed, ensure_credentials() prints instructions and returns without crashing"
    - "COOKIE and X_USERTOKEN values are never logged or printed; only byte-length is logged"
  artifacts:
    - path: "rca_copilot_agent/tools/auth_tool.py"
      provides: "is_session_valid(), capture_credentials_via_browser(), write_credentials_to_env(), ensure_credentials()"
    - path: "rca_copilot_agent/tools/snow_reader.py"
      provides: "validate() with Content-Type + JSON parse check"
    - path: "rca_copilot_agent/mcp_server.py"
      provides: "ensure_credentials() call in main() before asyncio.run(run())"
    - path: "requirements.txt"
      provides: "playwright>=1.50 entry with install note"
  key_links:
    - from: "rca_copilot_agent/mcp_server.py main()"
      to: "rca_copilot_agent/tools/auth_tool.py ensure_credentials()"
      via: "synchronous call before asyncio.run(run())"
    - from: "auth_tool.py ensure_credentials()"
      to: "snow_reader.py ServiceNowReader.validate()"
      via: "instantiates reader, calls validate()"
    - from: "auth_tool.py capture_credentials_via_browser()"
      to: ".env"
      via: "write_credentials_to_env() using dotenv.set_key()"
---

<objective>
Automate COOKIE + X_USERTOKEN capture for rca_copilot_agent: detect missing or expired
ServiceNow credentials at MCP server startup, launch a headed Chromium browser for SSO
login, extract cookies and window.g_ck, and write them back to .env. Also fix validate()
in snow_reader.py which currently passes on expired sessions (HTTP 200 + HTML body).

Purpose: Eliminate the manual DevTools workflow for credential renewal. The MCP server
becomes self-healing — if credentials are stale, it prompts the user to log in once via
the real browser window, then continues normally.

Output:
  - rca_copilot_agent/tools/auth_tool.py (new)
  - rca_copilot_agent/tools/snow_reader.py (validate() fix)
  - rca_copilot_agent/mcp_server.py (ensure_credentials hook in main())
  - rca_copilot_agent/AGENTS.md (auth_tool entry)
  - requirements.txt (playwright>=1.50)
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/rca_copilot_agent/mcp_server.py
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/rca_copilot_agent/config.py
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/rca_copilot_agent/tools/snow_reader.py
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/rca_copilot_agent/AGENTS.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/requirements.txt
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/quick/quick-kayinleong-007/RESEARCH.md

<interfaces>
<!-- Key contracts the executor needs. Extracted from codebase. -->

From rca_copilot_agent/config.py:
```python
@dataclass
class ServiceNowConfig:
    instance_url: str
    cookie: str
    x_user_token: str
    reports_dir: str
    attachments_dir: str

def load_config(env_file: str = ".env") -> ServiceNowConfig: ...
# _find_env_data reads from disk each call — calling load_config() again picks up freshly-written .env values
```

From rca_copilot_agent/tools/snow_reader.py:
```python
class ServiceNowReader:
    def __init__(self, instance_url: str): ...
    def authenticate(self, cookie: str, x_user_token: str) -> None: ...
    def validate(self) -> bool:
        # CURRENT (broken): returns True for HTTP 200 + HTML expired-session response
        resp = self.session.get(f"{self.instance}/api/now/table/incident",
                                params={"sysparm_limit": 1, "sysparm_fields": "sys_id"}, timeout=15)
        return resp.status_code == 200
```

From rca_copilot_agent/mcp_server.py — main():
```python
def main() -> None:
    # ... parse args, basicConfig, load_config, makedirs, init_from_schema, _auto_load_store ...
    try:
        import mcp
        import asyncio
        # ... create server, init_options ...
        async def run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, init_options)
        logger.info(f"[MCP] Starting MCP server. Reports dir: {reports_dir}")
        asyncio.run(run())   # <-- ensure_credentials() must run BEFORE this line
    except ImportError:
        _run_jsonrpc_fallback(reports_dir)
```

From python-dotenv 1.2.2 (installed):
```python
from dotenv import set_key, find_dotenv
# set_key(env_path, key, value, quote_mode="never") -> (success, key, value)
# Edits only the target key; all other lines preserved in place.
# find_dotenv() walks up from cwd to find .env
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create auth_tool.py with ensure_credentials() and fix validate() in snow_reader.py</name>
  <files>
    rca_copilot_agent/tools/auth_tool.py
    rca_copilot_agent/tools/snow_reader.py
  </files>
  <action>
Create rca_copilot_agent/tools/auth_tool.py as a pure-function module (no LLM calls, no async at module level). Implement four functions:

**is_session_valid(cookie: str, x_user_token: str, instance_url: str) -> bool**
- Return False immediately if cookie or x_user_token are empty strings.
- Instantiate a ServiceNowReader, call authenticate(), then call validate().
- Return the result. Catch all exceptions and return False.

**validate() fix in snow_reader.py** (lines 78-88):
Replace the existing body with:
```python
def validate(self) -> bool:
    try:
        resp = self.session.get(
            f"{self.instance}/api/now/table/{_INCIDENT_TABLE}",
            params={"sysparm_limit": 1, "sysparm_fields": "sys_id"},
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        ct = resp.headers.get("Content-Type", "")
        if "application/json" not in ct:
            return False
        data = resp.json()
        return "result" in data
    except Exception:
        return False
```

**capture_credentials_via_browser(instance_url: str) -> tuple[str, str]**
- Import threading and sys (module-level). All playwright imports are INSIDE this function.
- Wrap the Playwright async flow in a dedicated thread with its own event loop (see thread pattern in RESEARCH.md Section 5).
- In the async inner function:
  - Launch `p.chromium.launch(headless=False)`.
  - Create a new context and page.
  - Navigate to `instance_url` (e.g. "https://loreal.service-now.com/").
  - Print to stderr: `[AUTH] Browser opened — please log in via SSO. Waiting up to 10 minutes...`
  - Call `page.wait_for_url("**/now/nav/ui/classic**", timeout=600_000, wait_until="domcontentloaded")`.
  - After URL matches, call `page.wait_for_function("window.g_ck !== undefined && window.g_ck !== ''", timeout=30_000)` to guard against A2 assumption failure.
  - Extract `x_user_token = await page.evaluate("window.g_ck")`. If None or empty, raise RuntimeError("window.g_ck not found after login").
  - Extract cookies: `cookies = await context.cookies()`. Filter with `"loreal.service-now.com" in c["domain"]` (substring match, not equality — handles leading-dot domains per Pitfall 5). Build `cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in snow_cookies)`.
  - Print to stderr: `f"[AUTH] Captured credentials ({len(cookie_header)} bytes cookie, {len(x_user_token)} bytes token)"`. Never log the values.
  - Close browser and return `(cookie_header, x_user_token)`.
- Thread pattern: create `result = {}`, run thread with `asyncio.new_event_loop()` + `loop.run_until_complete(_inner())`, join thread, return values from result dict.
- Catch `ImportError` from playwright import and raise RuntimeError with message: "playwright not installed. Run: pip install playwright && playwright install chromium"

**write_credentials_to_env(env_path: str, cookie: str, x_user_token: str) -> None**
- Import `set_key` from dotenv (module-level import is fine — dotenv is always installed).
- Call `set_key(env_path, "COOKIE", cookie, quote_mode="never")`.
- Call `set_key(env_path, "X_USERTOKEN", x_user_token, quote_mode="never")`.
- Print to stderr: `f"[AUTH] Credentials written to {env_path}"`. Do NOT log credential values.

**ensure_credentials(instance_url: str = "https://loreal.service-now.com") -> None**
- Import `load_config` and `find_dotenv` at function scope (lazy, to pick up freshly-written .env if called again).
- Call `cfg = load_config()`.
- Call `is_session_valid(cfg.cookie, cfg.x_user_token, instance_url)`.
- If valid: print `"[AUTH] ServiceNow credentials valid."` to stderr and return.
- If not valid: print `"[AUTH] Credentials missing or expired — launching browser for SSO login..."` to stderr.
- Try: call `capture_credentials_via_browser(instance_url)` — returns `(cookie, token)`.
  - On ImportError/RuntimeError (playwright not installed): print the error message to stderr and return (non-fatal — let the server start; first SNOW tool call will raise the original RuntimeError from _build_reader).
- On success: call `env_path = find_dotenv(usecwd=True)`. If `env_path` is empty string (no .env found), use `str(Path.cwd() / ".env")` as fallback path.
- Call `write_credentials_to_env(env_path, cookie, token)`.
- Reload config to verify: call `load_config()` and check that cookie and x_user_token are now non-empty. If still empty, print warning to stderr.

Module-level imports for auth_tool.py (only stdlib + already-installed libs):
```python
from __future__ import annotations
import sys
import threading
from pathlib import Path
from dotenv import set_key, find_dotenv
```
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python -c "from rca_copilot_agent.tools.auth_tool import ensure_credentials, is_session_valid, write_credentials_to_env, capture_credentials_via_browser; print('auth_tool imports OK')"</automated>
  </verify>
  <done>
    - auth_tool.py exists with four exported functions: is_session_valid, capture_credentials_via_browser, write_credentials_to_env, ensure_credentials.
    - All playwright imports inside capture_credentials_via_browser (lazy, not module-level).
    - validate() in snow_reader.py checks status_code, Content-Type, and JSON parse before returning True.
    - No credential values logged anywhere; only byte-lengths logged.
    - Module imports cleanly with no errors.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire ensure_credentials() into mcp_server.main(), add playwright to requirements.txt, update AGENTS.md</name>
  <files>
    rca_copilot_agent/mcp_server.py
    requirements.txt
    rca_copilot_agent/AGENTS.md
  </files>
  <action>
**mcp_server.py — main() hook:**

In main(), after the `_auto_load_store(reports_dir)` call and BEFORE the `try: import mcp` block, insert:

```python
# Check / refresh ServiceNow credentials before starting the MCP event loop.
# Runs synchronously — no asyncio loop is active here yet.
try:
    from tools.auth_tool import ensure_credentials
    ensure_credentials(instance_url=cfg.instance_url)
except Exception as auth_err:
    logger.warning(f"[AUTH] Credential check failed: {type(auth_err).__name__}: {auth_err}")
```

The try/except is a safety net so a bug in auth_tool never prevents the server from starting. The warning is logged but startup continues.

**requirements.txt:**

Append after the existing `google-cloud-bigquery>=3.0` line:

```
# Browser automation for automatic ServiceNow session capture (optional)
# After installing, run: playwright install chromium
playwright>=1.50
```

**AGENTS.md — Tool Inventory table:**

Add a new row to the Tool Inventory table after the `send_rca_email` row:

```
| `auto_credential_refresh` | Automatic startup tool — not callable; runs at MCP server start to detect and renew stale ServiceNow session cookies via browser SSO |
```

Also add an **Environment Setup** section after the Tool Inventory table (if one does not already exist), noting the playwright dependency:

```markdown
## Environment Setup

### ServiceNow Credentials (auto-refreshed)

At startup the MCP server checks whether `COOKIE` and `X_USERTOKEN` in `.env` are valid.
If missing or expired, a Chromium browser window opens automatically for SSO login.
Credentials are written back to `.env` after login — no manual DevTools copy-paste needed.

**First-time setup (one-time only):**
```bash
pip install playwright
playwright install chromium
```

If playwright is not installed, the server falls back to the manual instructions in `.env.example`.
```
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python -c "
import ast, sys
with open('rca_copilot_agent/mcp_server.py') as f:
    src = f.read()
assert 'ensure_credentials' in src, 'ensure_credentials not wired into mcp_server.py'
assert 'playwright' in open('requirements.txt').read(), 'playwright missing from requirements.txt'
print('mcp_server + requirements OK')
"</automated>
  </verify>
  <done>
    - mcp_server.main() calls ensure_credentials(instance_url=cfg.instance_url) before asyncio.run(run()), wrapped in try/except that logs a warning on failure but does not abort startup.
    - requirements.txt contains playwright>=1.50 with install note comment.
    - AGENTS.md Tool Inventory table includes auto_credential_refresh row.
    - AGENTS.md has an Environment Setup section explaining the playwright dependency and first-time setup.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → .env | Playwright extracts live session tokens from authenticated browser context and writes to local .env |
| .env → mcp_server | Credentials loaded from .env at startup; stale values trigger the browser flow |
| mcp_server → ServiceNow REST | Session cookies and X-UserToken cross this boundary on every SNOW API call |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-007-01 | Information Disclosure | auth_tool.py logging | mitigate | Never log COOKIE or X_USERTOKEN values; log only byte-length. All print/logger calls audited before commit. |
| T-007-02 | Information Disclosure | .env file | accept | .env is gitignored; this is pre-existing project policy. No change to gitignore needed. |
| T-007-03 | Tampering | write_credentials_to_env set_key | accept | set_key only modifies COOKIE and X_USERTOKEN keys; all other .env lines are preserved. python-dotenv 1.2.2 behaviour verified. |
| T-007-04 | Denial of Service | capture_credentials_via_browser timeout | accept | 10-minute wait_for_url timeout prevents indefinite hang. Thread join() means server startup blocks at most 10 min — acceptable for interactive SSO. |
| T-007-05 | Elevation of Privilege | Playwright subprocess | accept | Playwright launches Chromium as current user only. No privilege escalation path. Subprocess inherits user's display session (macOS/Linux). |
</threat_model>

<verification>
1. Import check: `python -c "from rca_copilot_agent.tools.auth_tool import ensure_credentials"` — no errors.
2. validate() fix: construct a mock response with status=200 and Content-Type=text/html — confirm validate() returns False.
3. mcp_server wiring: grep mcp_server.py for "ensure_credentials" — confirm it appears before "asyncio.run(run())".
4. Secrets hygiene: grep auth_tool.py for any direct print of COOKIE or X_USERTOKEN variable values — must be zero matches.
5. requirements.txt: confirm `playwright>=1.50` is present.
</verification>

<success_criteria>
- `python rca_copilot_agent/mcp_server.py` starts without ImportError when playwright is absent (graceful fallback message printed to stderr, server continues).
- validate() in snow_reader.py rejects HTTP 200 + text/html responses (expired session simulation).
- ensure_credentials() is the first substantive action in main() (before asyncio.run(run())).
- No COOKIE or X_USERTOKEN values appear in any stderr/stdout output; only byte-lengths.
- playwright>=1.50 present in requirements.txt.
- AGENTS.md documents the new auth_tool and first-time playwright setup.
</success_criteria>

<output>
After completion, create `/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/quick/quick-kayinleong-007/quick-kayinleong-007-01-SUMMARY.md`
</output>
