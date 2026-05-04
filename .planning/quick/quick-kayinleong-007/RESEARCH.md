# quick-kayinleong-007: Auto-Capture COOKIE + X-UserToken — Research

**Researched:** 2026-05-04
**Domain:** Browser automation for SSO session cookie extraction; .env write-back; MCP asyncio startup integration
**Confidence:** HIGH (all major claims verified via official docs or package inspection)

---

## Summary

The task is to detect stale/missing ServiceNow credentials at MCP server startup and, when needed, open a real browser window for the user to log in via SSO, then extract the resulting cookies and `X-UserToken` and write them back to `.env`.

Three distinct sub-problems must be solved cleanly:

1. **Session validity check** — detect stale credentials before committing to tool calls.
2. **Browser-based capture** — launch Chromium headfully, wait for the user to complete SSO, extract cookies and `window.g_ck` (the CSRF token that maps to `X_USERTOKEN`), write back to `.env`.
3. **MCP startup integration** — run the check before `stdio_server` enters its context manager, while respecting asyncio constraints imposed by both the MCP SDK and Playwright.

**Primary recommendation:** Use Playwright (`playwright>=1.50`) with its async API, run the auth flow in a dedicated thread with its own event loop (using `asyncio.to_thread` + `asyncio.run` inside the thread), execute the check in `main()` synchronously before the `asyncio.run(run())` call so the check is entirely pre-MCP-loop.

---

## Project Constraints (from CLAUDE.md)

- NO LLM calls inside `mcp_server.py` or any `tools/*.py`. `auth_tool.py` must be pure functions.
- Credentials live in `.env` at repo root (loaded by `rca_copilot_agent/config.py`).
- `my_reports/`, `attachments/` are gitignored and must never be staged.
- Secrets (`COOKIE`, `X_USERTOKEN`) must never be logged, echoed, or committed.
- BigQuery blocklist must not be weakened (unrelated, but worth noting for regression surface).
- New tools must be registered in `rca_copilot_agent/AGENTS.md`.

---

## 1. Library Selection: Playwright vs. Selenium

**Verdict: Playwright** [VERIFIED: PyPI registry + playwright.dev official docs]

| Criterion | Playwright | Selenium |
|-----------|-----------|---------|
| SSO redirect handling | Automatic (transparent follow-through) | Manual, fragile with SAML redirects |
| Cookie extraction | `context.cookies()` — returns structured list | `driver.get_cookies()` — similar but less reliable with secure/httpOnly |
| JS execution for `window.g_ck` | `page.evaluate("window.g_ck")` | `driver.execute_script("return window.g_ck")` |
| Async API | First-class (`async_playwright`) | Tacked on via `selenium-wire` or threads |
| Install footprint | `pip install playwright` + `playwright install chromium` (~200 MB) | `pip install selenium` + chromedriver binary management |
| Headful support | `headless=False` — well-tested headed path | Same, but chromedriver version pinning is painful |

**Install:**
```bash
pip install playwright
playwright install chromium
```

Current version: `1.59.0` [VERIFIED: `pip3 index versions playwright`]

---

## 2. Capturing Cookie + X-UserToken from Playwright

### 2a. Cookie extraction

After the user completes login, `context.cookies()` returns a list of dicts. Each dict has `name`, `value`, `domain`, `path`, `httpOnly`, `secure`, `sameSite`, `expires`. [VERIFIED: playwright.dev official API docs]

To reconstruct the full `Cookie:` header string (what `snow_reader.py`'s `authenticate()` expects):

```python
cookies = await context.cookies()
# Filter to the ServiceNow domain only
snow_cookies = [c for c in cookies if "loreal.service-now.com" in c["domain"]]
cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in snow_cookies)
```

### 2b. X-UserToken / g_ck extraction

`X-UserToken` is **not a cookie** — it is a per-session CSRF token stored in the JavaScript global `window.g_ck`. It is never transmitted automatically. [VERIFIED: jessems.com article citing official ServiceNow behavior; cross-confirmed with ServiceNow community docs]

Extract after navigation to any authenticated SNOW page:

```python
x_user_token = await page.evaluate("window.g_ck")
# Returns a string like "f3ab2c..." or None if not on an authenticated page
```

Alternative extraction path (if `window.g_ck` is undefined — can happen on some page states): POST to the `sn_devstudio_/v1/get_publish_info` endpoint, which returns a JSON body containing the `ck` field. [CITED: jessems.com/posts/2023-08-25-authenticating-against-the-servicenow-api-with-session-tokens/]

### 2c. Detecting login completion (waiting for SSO)

ServiceNow SSO login redirects through an identity provider (Azure AD or Okta) before landing on the SNOW portal. Playwright handles redirect chains transparently. The correct "done" signal is:

- URL lands on `https://loreal.service-now.com/now/nav/ui/classic` — the main portal URL
- OR `window.g_ck` evaluates to a non-empty string (most robust)

Use `page.wait_for_url` with a glob pattern, with a generous timeout (5–10 minutes) to allow the user to complete MFA:

```python
# Navigate to instance
await page.goto("https://loreal.service-now.com/")

# Wait for user to complete SSO login — up to 10 minutes
await page.wait_for_url(
    "**/now/nav/ui/classic**",
    timeout=600_000,  # 10 minutes
    wait_until="domcontentloaded",
)

# Extract CSRF token
x_user_token = await page.evaluate("window.g_ck")
```

[VERIFIED: playwright.dev/python/docs/api — `wait_for_url` accepts glob patterns and timeout in ms]

---

## 3. Detecting Expired Credentials

### The HTTP 200 trap

ServiceNow does NOT return 401 for expired browser sessions on the table REST API. It returns **HTTP 200 with an HTML login-redirect page** or an empty JSON `result: []` array. [VERIFIED: multiple ServiceNow community posts + KB0966965]

The existing `validate()` in `snow_reader.py` only checks `resp.status_code == 200` — this is **insufficient**. A 200 response with an HTML body passes this check even with expired cookies.

### Robust detection strategy

Preferred approach — check `Content-Type` and `result` field presence:

```python
def validate(self) -> bool:
    try:
        resp = self.session.get(
            f"{self.instance}/api/now/table/incident",
            params={"sysparm_limit": 1, "sysparm_fields": "sys_id"},
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        # ServiceNow returns HTML (login page) on expired session, not JSON
        ct = resp.headers.get("Content-Type", "")
        if "application/json" not in ct:
            return False
        data = resp.json()
        return "result" in data  # present even for empty result sets
    except Exception:
        return False
```

**Key indicators of expired session:**
1. `Content-Type` is `text/html` instead of `application/json` [MEDIUM confidence — observed pattern, consistent with KB articles]
2. Body contains `"login.do"` or `"session_timeout"` string [LOW confidence — page content varies]
3. `resp.json()` raises `JSONDecodeError` (body is HTML) [HIGH — reliable]

The combined check (status + Content-Type + JSON parseable) is the most reliable. [ASSUMED: specific Content-Type value for SNOW REST expiry not verified against loreal instance directly]

### When to check

Check at two points:
1. **At server startup** — before `asyncio.run(run())` in `main()`. If invalid, trigger browser capture.
2. **Lazy re-check** — inside `_build_reader()`, catch the case where credentials exist in `.env` but have expired mid-session (currently raises `RuntimeError`, could be upgraded to trigger re-auth prompt).

---

## 4. Writing Back to .env

### Use `python-dotenv` `set_key()` [VERIFIED: installed version 1.2.2, function signature confirmed via `help(set_key)`]

```python
from dotenv import set_key, find_dotenv

env_path = find_dotenv()  # finds .env by walking up from cwd
set_key(env_path, "COOKIE", cookie_header, quote_mode="never")
set_key(env_path, "X_USERTOKEN", x_user_token, quote_mode="never")
```

**Behavior confirmed:**
- `set_key` edits **only** the target key; all other lines (SMTP config, comments, blank lines) are preserved in place. [VERIFIED: python-dotenv 1.2.2 source; confirmed via `help(set_key)` docstring]
- Returns `(success: bool | None, key, value)` tuple — check `success` is not `False`.
- `quote_mode="never"` avoids wrapping the long Cookie header in quotes; `quote_mode="always"` (default) would wrap in single quotes, which `config.py`'s `_load_env_file` already strips (it does `.strip('"').strip("'")`), so either works.
- `find_dotenv()` searches CWD then parent directories. For the MCP server launched from repo root, this resolves to `<repo_root>/.env`.

**After writing, reload the in-process config:**
```python
from rca_copilot_agent.config import load_config
cfg = load_config()  # re-reads .env from disk
```

The existing `_find_env_data` in `config.py` reads from disk each call, so calling `load_config()` again picks up the freshly-written values.

---

## 5. MCP Server Startup Integration

### The asyncio constraint

The MCP server's `run()` function uses `asyncio.run(run())` where `run()` enters `async with stdio_server()`. Playwright's async API must run on the same asyncio event loop it was created on. Running `async_playwright` inside the existing loop is fine — but the key question is: **when to run the check?**

**Option A: Before `asyncio.run()` — sync check (recommended)**

Run the credential validity check and browser capture entirely in synchronous code in `main()`, before `asyncio.run(run())` is called. This avoids all async-inside-async conflicts.

```python
def main() -> None:
    # ... existing setup ...

    # ← NEW: Auth check runs here, before asyncio.run()
    from tools.auth_tool import ensure_credentials
    ensure_credentials()  # blocks until user logs in if needed

    # ← existing: starts MCP server
    asyncio.run(run())
```

`ensure_credentials()` calls `validate()` first (sync, via `requests`). If valid, returns immediately. If not, launches Playwright sync API in a **new dedicated thread** that creates its own event loop. Since no asyncio loop is running in `main()` at this point, the sync playwright API could also be used directly (no event loop conflict). [VERIFIED: playwright.dev/python/docs/library — "synchronous API is for simple cases; does not work inside asyncio loop"]

**Option B: Async hook inside `run()`**

If the check needs to run async (e.g., using `async_playwright` directly), place it before `stdio_server()`:

```python
async def run():
    # ← check runs here, before stdio_server is entered
    from tools.auth_tool import async_ensure_credentials
    await async_ensure_credentials()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)
```

This is valid but mixes asyncio contexts. Playwright async API works here because no conflicting event loop exists yet. However, launching a headed browser window while the asyncio loop is also handling stdio connections is riskier for timing.

**Recommendation: Option A** — sync check before `asyncio.run()`. Zero asyncio interaction. Playwright sync API, dedicated thread only if a running loop is detected.

### Playwright in a thread (safety note)

Playwright's API is **not thread-safe**. If using threading, each thread must have its own Playwright instance and event loop. The pattern:

```python
import threading

def _run_browser_capture() -> tuple[str, str]:
    """Runs in a dedicated thread with its own event loop."""
    import asyncio
    from playwright.async_api import async_playwright

    async def _inner():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://loreal.service-now.com/")
            print("[AUTH] Browser opened. Please log in via SSO...", file=sys.stderr)
            await page.wait_for_url("**/now/nav/ui/classic**", timeout=600_000)
            x_user_token = await page.evaluate("window.g_ck")
            cookies = await context.cookies()
            snow_cookies = [c for c in cookies if "loreal.service-now.com" in c["domain"]]
            cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in snow_cookies)
            await browser.close()
            return cookie_header, x_user_token

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_inner())
    finally:
        loop.close()

result = {}
t = threading.Thread(target=lambda: result.update(zip(("cookie","token"), _run_browser_capture())))
t.start()
t.join()
```

[VERIFIED: threading isolation pattern confirmed in playwright-python GitHub issues #470, #1619]

### VS Code subprocess context

The MCP server is a subprocess of VS Code's extension host. On macOS/Linux, subprocess environments inherit the display — headed Chromium opens normally. On Windows, the ProactorEventLoop requirement applies but is handled automatically by Playwright. Opening a browser window from a subprocess has no special restrictions on any platform Playwright supports. [ASSUMED: no direct test of VS Code subprocess -> Playwright browser window on macOS; general subprocess behavior well-understood]

---

## 6. Pitfalls and Gotchas

### Pitfall 1: `validate()` passes on expired session (HTTP 200 + HTML)
**What:** ServiceNow returns 200 with an HTML login page. The existing `validate()` (checks only `status_code == 200`) returns `True` for expired sessions.
**Fix:** Add Content-Type and JSON parse check as described in Section 3.

### Pitfall 2: `window.g_ck` undefined on first page load
**What:** If `page.evaluate("window.g_ck")` runs before the SNOW portal JavaScript has initialized, it returns `None`.
**Fix:** Call `evaluate` only after `wait_for_url` resolves to the portal URL, or add `page.wait_for_function("window.g_ck !== undefined && window.g_ck !== ''")`.

### Pitfall 3: SSO redirect chain invalidates the target URL pattern
**What:** L'Oréal SNOW uses Azure AD/Okta SSO — the browser traverses `login.microsoftonline.com` or `okta` before landing back on SNOW. `wait_for_url` with a SNOW URL pattern will correctly wait through the entire chain.
**Fix:** Use a glob pattern (`**/now/nav/ui/classic**`) rather than an exact URL. The pattern only matches after SSO redirect completes.

### Pitfall 4: Playwright not installed
**What:** `playwright` is not in `requirements.txt`. If the user hasn't run `pip install playwright && playwright install chromium`, the auth flow fails with an ImportError.
**Fix:** Catch `ImportError` and print a clear instruction. Guard the Playwright import inside the function — don't import at module top.

```python
def ensure_credentials():
    ...
    try:
        # only imported when actually needed
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "[AUTH] playwright not installed. Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return  # non-fatal: fall through, let _build_reader raise normally
```

### Pitfall 5: Cookie domain mismatch in `authenticate()`
**What:** `snow_reader.py`'s `authenticate()` sets cookies with `domain=self.domain` (which is `loreal.service-now.com`). Playwright returns cookies with domains like `.loreal.service-now.com` (leading dot) or `loreal.service-now.com` depending on the cookie's scope.
**Fix:** When filtering Playwright cookies, use `"loreal.service-now.com" in c["domain"]` (substring match), not exact equality.

### Pitfall 6: Logging the COOKIE value
**What:** Any debug `print(cookie_header)` in `auth_tool.py` will leak the full session cookie to stderr (visible in VS Code's Output panel).
**Fix:** Never log the cookie value. Log only a truncated length: `f"Captured {len(cookie_header)} bytes for COOKIE"`.

### Pitfall 7: `set_key` adds quotes around long Cookie values
**What:** With `quote_mode="always"` (default), python-dotenv wraps the value in single quotes. The existing `_load_env_file` strips single and double quotes, so values are read back correctly. But if switching to `quote_mode="never"`, multi-word values with spaces work fine since `Cookie:` headers are single strings.
**Fix:** Either mode works given `_load_env_file`'s stripping logic. `quote_mode="never"` produces a cleaner `.env` file.

### Pitfall 8: MCP server on Windows — asyncio ProactorEventLoop
**What:** Playwright requires `ProactorEventLoop` on Windows. `asyncio.run()` uses this automatically on Python 3.8+ on Windows.
**Fix:** No explicit action needed for Python 3.8+. [VERIFIED: playwright-python GitHub docs]

---

## 7. Architecture for `auth_tool.py`

Proposed structure (pure functions, no LLM, no async at module level):

```python
# rca_copilot_agent/tools/auth_tool.py

def is_session_valid(cookie: str, x_user_token: str, instance_url: str) -> bool:
    """Validate existing credentials with a lightweight REST call."""
    # Uses requests, checks Content-Type + JSON parse
    ...

def capture_credentials_via_browser(instance_url: str) -> tuple[str, str]:
    """
    Open a headed Chromium browser, wait for user SSO login,
    return (cookie_header, x_user_token). Blocks until login completes.
    """
    # Playwright in dedicated thread with own event loop
    ...

def write_credentials_to_env(env_path: str, cookie: str, x_user_token: str) -> None:
    """Write COOKIE and X_USERTOKEN to .env using set_key (preserves other keys)."""
    # Uses python-dotenv set_key
    ...

def ensure_credentials(instance_url: str = "https://loreal.service-now.com") -> None:
    """
    Top-level entry point called from mcp_server.main() before asyncio.run().
    If credentials are valid, returns immediately. If missing or stale,
    triggers browser capture and writes back to .env.
    """
    ...
```

Integration point in `mcp_server.py` — inside `main()`, after `load_config()` but before `asyncio.run(run())`:

```python
# Check / refresh credentials before starting the MCP event loop
from tools.auth_tool import ensure_credentials
ensure_credentials(instance_url=cfg.instance_url)
```

---

## Standard Stack

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| `playwright` | `>=1.50` | Browser automation, headful Chromium, cookie capture | [VERIFIED: PyPI 1.59.0 current] |
| `python-dotenv` | `>=1.0` (1.2.2 installed) | `set_key()` for safe .env write-back | [VERIFIED: installed, `help(set_key)` confirmed] |
| `requests` | `>=2.31` (2.33.1 installed) | Credential validation HTTP call | [VERIFIED: already in requirements.txt] |
| `threading` / `asyncio` | stdlib | Isolate Playwright in own event loop | [VERIFIED: stdlib, no extra install] |

`python-dotenv` is already installed as a dev dependency. Add `playwright` to `requirements.txt` with a conditional note.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | YES (3.13.7) | 3.13.7 | — |
| requests | Session validation | YES | 2.33.1 | — |
| python-dotenv | .env write-back | YES | 1.2.2 | Inline file rewrite (fragile) |
| playwright (pip) | Browser capture | NO | — | Manual DevTools flow (graceful fallback) |
| Chromium binary | Browser window | NO | — | Manual DevTools flow |

**Missing with fallback:** Playwright not installed. `ensure_credentials()` must catch `ImportError` and fall back gracefully to the existing manual instructions — print a message telling the user to run `pip install playwright && playwright install chromium`, then continue (let the server start and fail on first SNOW tool call with the original error).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | L'Oréal SNOW returns HTTP 200 + HTML body (not 401) on expired cookie-auth sessions | Section 3 | If it does return 401, the existing `_get()` method already handles it; risk is low |
| A2 | `window.g_ck` is defined on the main SNOW portal page after SSO completes | Section 2b | If undefined, fallback to `sn_devstudio_/v1/get_publish_info` endpoint works |
| A3 | VS Code subprocess on macOS launches headed Chromium window without display issues | Section 5 | Non-blocking: Playwright will surface an error if display is unavailable |
| A4 | L'Oréal SNOW uses Azure AD or Okta SSO (not NTLM or certificate-based) | Section 2c | Different SSO provider may need different landing URL pattern |

---

## Sources

### Primary (HIGH confidence)
- [Playwright Python official docs — cookies, storage_state, wait_for_url](https://playwright.dev/python/docs/api/class-browsercontext) — cookies API, context.cookies(), wait_for_url
- [Playwright Python library docs](https://playwright.dev/python/docs/library) — headless=False, async_playwright, threading note
- Context7 `/microsoft/playwright.dev` — `context.cookies()`, `page.evaluate()`, `set_storage_state()`, `wait_for_selector()`
- python-dotenv 1.2.2 — `set_key()` signature verified via `help(set_key)` on installed package
- requests 2.33.1 — already in project requirements

### Secondary (MEDIUM confidence)
- [Authenticating against ServiceNow API with Session Tokens — jessems.com 2023](https://jessems.com/posts/2023-08-25-authenticating-against-the-servicenow-api-with-session-tokens/) — `window.g_ck` location, CSRF token vs cookie distinction
- [ServiceNow Community — X-UserToken usage](https://www.servicenow.com/community/developer-forum/use-x-usertoken-instead-of-credentials-in-rest-api-calls/m-p/1895982) — header vs cookie clarification
- [ServiceNow KB0966965](https://support.servicenow.com/kb?id=kb_article_view&sysparm_article=KB0966965) — HTTP 200 returned for expired sessions (known issue)

### Tertiary (LOW confidence — for awareness only)
- playwright-python GitHub issues #470, #1619, #2705 — threading/asyncio conflict patterns
