"""
auth_tool.py — Automatic ServiceNow credential refresh.
========================================================
Detects missing or expired COOKIE / X_USERTOKEN at MCP server startup.
If credentials are stale, opens a headed Chromium browser window for SSO login,
extracts cookies and window.g_ck, and writes them back to .env.

This module contains only pure functions — no LLM calls, no async at module level.
All playwright imports are lazy (inside capture_credentials_via_browser) so the module
imports cleanly even when playwright is not installed.

Security note: COOKIE and X_USERTOKEN values are never logged or printed.
Only byte-lengths are emitted to stderr.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from dotenv import set_key, find_dotenv


def is_session_valid(cookie: str, x_user_token: str, instance_url: str) -> bool:
    """
    Validate existing credentials with a lightweight REST call to the ServiceNow API.

    Returns:
        True  — credentials are present and the session is authenticated (JSON + 'result' key).
        False — credentials are missing, expired, or the request failed for any reason.
    """
    if not cookie or not x_user_token:
        return False

    try:
        from tools.snow_reader import ServiceNowReader  # noqa: PLC0415

        reader = ServiceNowReader(instance_url=instance_url)
        reader.authenticate(cookie=cookie, x_user_token=x_user_token)
        return reader.validate()
    except Exception:
        return False


def capture_credentials_via_browser(instance_url: str) -> tuple[str, str]:
    """
    Launch a headed Chromium browser, wait for the user to complete SSO login,
    extract cookies and window.g_ck, and return (cookie_header, x_user_token).

    This function blocks the calling thread until the user logs in (up to 10 minutes).

    All playwright imports are inside this function body (lazy) so the module imports
    cleanly when playwright is not installed. An ImportError is re-raised as RuntimeError
    with install instructions.

    Args:
        instance_url: ServiceNow base URL, e.g. "https://loreal.service-now.com"

    Returns:
        (cookie_header, x_user_token) — both are non-empty strings on success.

    Raises:
        RuntimeError: playwright not installed, or window.g_ck was not found after login.
    """
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    import asyncio  # noqa: PLC0415

    result: dict[str, str] = {}
    thread_error: list[Exception] = []

    def _thread_target() -> None:
        """Runs in a dedicated thread with its own asyncio event loop."""

        async def _inner() -> None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()

                await page.goto(instance_url)
                print(
                    "[AUTH] Browser opened — please log in via SSO. Waiting up to 10 minutes...",
                    file=sys.stderr,
                )

                # Wait for the user to complete SSO and land on the SNOW portal
                await page.wait_for_url(
                    "**/now/nav/ui/classic**",
                    timeout=600_000,  # 10 minutes
                    wait_until="domcontentloaded",
                )

                # Guard against A2 assumption: wait until window.g_ck is populated
                await page.wait_for_function(
                    "window.g_ck !== undefined && window.g_ck !== ''",
                    timeout=30_000,
                )

                # Extract CSRF token — never log the value, only the length
                x_user_token = await page.evaluate("window.g_ck")
                if not x_user_token:
                    raise RuntimeError("window.g_ck not found after login")

                # Extract cookies — filter to the ServiceNow domain
                # Use substring match to handle both "loreal.service-now.com"
                # and ".loreal.service-now.com" (leading-dot domains, Pitfall 5)
                cookies = await context.cookies()
                snow_cookies = [
                    c for c in cookies if "loreal.service-now.com" in c["domain"]
                ]
                cookie_header = "; ".join(
                    f"{c['name']}={c['value']}" for c in snow_cookies
                )

                print(
                    f"[AUTH] Captured credentials "
                    f"({len(cookie_header)} bytes cookie, {len(x_user_token)} bytes token)",
                    file=sys.stderr,
                )

                await browser.close()

                result["cookie"] = cookie_header
                result["x_user_token"] = x_user_token

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_inner())
        except Exception as exc:
            thread_error.append(exc)
        finally:
            loop.close()

    t = threading.Thread(target=_thread_target, daemon=False)
    t.start()
    t.join()

    if thread_error:
        raise thread_error[0]

    return result["cookie"], result["x_user_token"]


def write_credentials_to_env(env_path: str, cookie: str, x_user_token: str) -> None:
    """
    Write COOKIE and X_USERTOKEN to a .env file using python-dotenv set_key().

    Only the two target keys are modified — all other .env lines are preserved in place.
    Credential values are never logged; only the destination path is printed.

    Args:
        env_path:     Absolute path to the .env file.
        cookie:       Full Cookie header string.
        x_user_token: X-UserToken / g_ck CSRF token string.
    """
    set_key(env_path, "COOKIE", cookie, quote_mode="never")
    set_key(env_path, "X_USERTOKEN", x_user_token, quote_mode="never")
    print(f"[AUTH] Credentials written to {env_path}", file=sys.stderr)


def ensure_credentials(
    instance_url: str = "https://loreal.service-now.com",
) -> None:
    """
    Top-level entry point called from mcp_server.main() before asyncio.run().

    Checks whether the current COOKIE and X_USERTOKEN in .env are valid.
    If missing or stale, launches a browser for SSO login and writes the new
    credentials back to .env.

    If playwright is not installed, prints install instructions and returns
    without crashing — the server continues and the first SNOW tool call will
    raise the original RuntimeError from _build_reader().

    Args:
        instance_url: ServiceNow base URL (default: https://loreal.service-now.com)
    """
    # Lazy imports to pick up freshly-written .env if called multiple times
    from config import load_config  # noqa: PLC0415

    cfg = load_config()

    if is_session_valid(cfg.cookie, cfg.x_user_token, instance_url):
        print("[AUTH] ServiceNow credentials valid.", file=sys.stderr)
        return

    print(
        "[AUTH] Credentials missing or expired — launching browser for SSO login...",
        file=sys.stderr,
    )

    try:
        cookie, token = capture_credentials_via_browser(instance_url)
    except (ImportError, RuntimeError) as exc:
        print(f"[AUTH] {exc}", file=sys.stderr)
        return  # non-fatal — let the server start; first SNOW call will raise

    # Find or create .env path
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        env_path = str(Path.cwd() / ".env")

    write_credentials_to_env(env_path, cookie, token)

    # Verify the write-back succeeded by reloading config from disk
    cfg_after = load_config()
    if not cfg_after.cookie or not cfg_after.x_user_token:
        print(
            "[AUTH] Warning: credentials were written to .env but could not be read back. "
            "Check file permissions and .env location.",
            file=sys.stderr,
        )
