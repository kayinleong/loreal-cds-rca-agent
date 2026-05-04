"""
gcloud_tool.py — Automatic gcloud Application Default Credentials check.
=========================================================================
Detects whether the active gcloud account is a loreal.com account and
whether Application Default Credentials (ADC) are configured. If either
check fails, triggers `gcloud auth application-default login` interactively.

This module contains only pure functions — no LLM calls, no async at module level.
Uses subprocess (stdlib only) — no extra dependencies.

Note: gcloud stdout is redirected to stderr so it never pollutes the MCP
stdio protocol stream.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _run_gcloud(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a gcloud command, capturing stdout and stderr."""
    return subprocess.run(
        ["gcloud", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def get_active_gcloud_account() -> str | None:
    """
    Return the first active gcloud account, or None if gcloud is not installed
    or no account is active.
    """
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


def is_adc_configured() -> bool:
    """
    Return True if Application Default Credentials are configured and can
    produce a valid access token.
    """
    try:
        result = _run_gcloud("auth", "application-default", "print-access-token")
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def run_adc_login() -> bool:
    """
    Run `gcloud auth application-default login` interactively.

    gcloud stdout/stderr are forwarded to our stderr so the URL / browser
    prompt is visible in VS Code's Output panel without corrupting the MCP
    stdio protocol on stdout.

    Returns True if gcloud exited with code 0.
    """
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "login"],
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=600,  # 10 minutes for user to complete browser login
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("[GCLOUD] gcloud CLI not found. Install from https://cloud.google.com/sdk/", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("[GCLOUD] gcloud login timed out after 10 minutes.", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"[GCLOUD] Login failed: {exc}", file=sys.stderr)
        return False


def set_quota_project(project_id: str | None = None) -> None:
    """
    Run `gcloud auth application-default set-quota-project <project_id>`.

    Uses the BQ_PROJECT env var if project_id is not provided, falling back
    to oa-apmena-spacecds-ap-pd.
    """
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


def ensure_gcloud_auth(required_domain: str = "loreal.com") -> None:
    """
    Top-level entry point called from mcp_server.main() after ensure_credentials().

    Checks whether the active gcloud account belongs to required_domain and
    whether ADC is configured. Triggers `gcloud auth application-default login`
    if either check fails.

    Args:
        required_domain: Expected email domain (default: loreal.com)
    """
    account = get_active_gcloud_account()

    if account is None:
        print(
            "[GCLOUD] No active gcloud account detected — launching gcloud login...",
            file=sys.stderr,
        )
        if run_adc_login():
            set_quota_project()
        return

    if not account.lower().endswith(f"@{required_domain.lower()}"):
        print(
            f"[GCLOUD] Active account is not a {required_domain} account — "
            "launching gcloud login...",
            file=sys.stderr,
        )
        if run_adc_login():
            set_quota_project()
        return

    if not is_adc_configured():
        print(
            f"[GCLOUD] Account is correct but ADC is not configured — "
            "launching gcloud login...",
            file=sys.stderr,
        )
        if run_adc_login():
            set_quota_project()
        return

    print(f"[GCLOUD] gcloud ADC valid ({required_domain} account active).", file=sys.stderr)
