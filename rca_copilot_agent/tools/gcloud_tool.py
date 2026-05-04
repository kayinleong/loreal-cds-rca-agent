"""
gcloud_tool.py — Automatic gcloud authentication check.
=========================================================
Handles two separate credential stores that gcloud maintains:

  1. User credentials  (`gcloud auth login`)
     Used by: bq CLI — query_bigquery in bigquery_tool.py calls bq directly.
     Check:   `gcloud auth print-access-token`
     Fix:     `gcloud auth login` → set account → set project

  2. Application Default Credentials (`gcloud auth application-default login`)
     Used by: Python google-cloud-bigquery client library.
     Check:   `gcloud auth application-default print-access-token`
     Fix:     `gcloud auth application-default login` → set-quota-project

Both checks run at MCP server startup. Either failing triggers interactive login.

Note: gcloud stdout is redirected to stderr so it never pollutes the MCP
stdio protocol stream on stdout.
"""

from __future__ import annotations

import os
import subprocess
import sys


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_gcloud(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a gcloud command, capturing stdout and stderr."""
    return subprocess.run(
        ["gcloud", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _interactive_gcloud(*args: str, timeout: int = 600) -> bool:
    """
    Run an interactive gcloud command (login flows).
    stdout/stderr forwarded to our stderr — never pollutes MCP stdio.
    Returns True on exit code 0.
    """
    try:
        result = subprocess.run(
            ["gcloud", *args],
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=timeout,
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("[GCLOUD] gcloud CLI not found. Install from https://cloud.google.com/sdk/", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("[GCLOUD] gcloud login timed out after 10 minutes.", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"[GCLOUD] Command failed: {exc}", file=sys.stderr)
        return False


# ── Account helpers ───────────────────────────────────────────────────────────

def get_active_gcloud_account() -> str | None:
    """Return the first active gcloud account, or None."""
    try:
        result = _run_gcloud(
            "auth", "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None


# ── User credentials (bq CLI) ─────────────────────────────────────────────────

def is_user_auth_valid() -> bool:
    """Return True if gcloud user credentials can produce a valid access token."""
    try:
        result = _run_gcloud("auth", "print-access-token")
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def run_user_login() -> bool:
    """Run `gcloud auth login` interactively. Returns True on success."""
    print("[GCLOUD] Launching gcloud auth login...", file=sys.stderr)
    return _interactive_gcloud("auth", "login")


def set_account(account: str) -> None:
    """Run `gcloud config set account <account>`."""
    try:
        _run_gcloud("config", "set", "account", account)
    except Exception as exc:
        print(f"[GCLOUD] Could not set account: {exc}", file=sys.stderr)


def set_project(project_id: str | None = None) -> None:
    """Run `gcloud config set project <project_id>`. Reads BQ_PROJECT env var if not given."""
    if project_id is None:
        project_id = os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")
    try:
        _run_gcloud("config", "set", "project", project_id)
        print(f"[GCLOUD] Project set to {project_id}.", file=sys.stderr)
    except Exception as exc:
        print(f"[GCLOUD] Could not set project: {exc}", file=sys.stderr)


# ── Application Default Credentials (Python client) ──────────────────────────

def is_adc_configured() -> bool:
    """Return True if ADC can produce a valid access token."""
    try:
        result = _run_gcloud("auth", "application-default", "print-access-token")
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def run_adc_login() -> bool:
    """Run `gcloud auth application-default login` interactively. Returns True on success."""
    print("[GCLOUD] Launching gcloud auth application-default login...", file=sys.stderr)
    return _interactive_gcloud("auth", "application-default", "login")


def set_quota_project(project_id: str | None = None) -> None:
    """Run `gcloud auth application-default set-quota-project <project_id>`."""
    if project_id is None:
        project_id = os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")
    try:
        subprocess.run(
            ["gcloud", "auth", "application-default", "set-quota-project", project_id],
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=30,
        )
    except Exception as exc:
        print(f"[GCLOUD] Could not set quota project: {exc}", file=sys.stderr)


# ── Top-level entry point ─────────────────────────────────────────────────────

def ensure_gcloud_auth(required_domain: str = "loreal.com") -> None:
    """
    Called from mcp_server.main() after ensure_credentials().

    Step 1 — User credentials (bq CLI):
      Check active account is loreal.com AND `gcloud auth print-access-token` works.
      If either fails: gcloud auth login → set account → set project.

    Step 2 — ADC (Python BigQuery client):
      Check `gcloud auth application-default print-access-token` works.
      If fails: gcloud auth application-default login → set-quota-project.
    """
    _ensure_user_auth(required_domain)
    _ensure_adc_auth(required_domain)


def _ensure_user_auth(required_domain: str) -> None:
    account = get_active_gcloud_account()
    account_ok = account is not None and account.lower().endswith(f"@{required_domain.lower()}")
    token_ok = is_user_auth_valid()

    if account_ok and token_ok:
        print(f"[GCLOUD] User credentials valid ({required_domain} account active).", file=sys.stderr)
        return

    if not account_ok:
        print(
            f"[GCLOUD] Active account is not a {required_domain} account — "
            "launching gcloud auth login...",
            file=sys.stderr,
        )
    else:
        print("[GCLOUD] User credentials expired — launching gcloud auth login...", file=sys.stderr)

    if run_user_login():
        # After login, pick up the newly active account and configure it
        new_account = get_active_gcloud_account()
        if new_account:
            set_account(new_account)
        set_project()
    else:
        print("[GCLOUD] gcloud auth login failed or was cancelled.", file=sys.stderr)


def _ensure_adc_auth(required_domain: str) -> None:
    if is_adc_configured():
        print("[GCLOUD] ADC valid.", file=sys.stderr)
        return

    print("[GCLOUD] ADC not configured — launching gcloud auth application-default login...", file=sys.stderr)
    if run_adc_login():
        set_quota_project()
    else:
        print("[GCLOUD] ADC login failed or was cancelled.", file=sys.stderr)
