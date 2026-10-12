"""
gcloud_tool.py — Automatic gcloud authentication check.
=========================================================
Handles gcloud user credentials (`gcloud auth login`), which the bq CLI uses
for every BigQuery query (query_bigquery in bigquery_tool.py calls bq directly,
macOS and Windows).
  Check:   active account is @loreal.com AND `gcloud auth print-access-token` works
  Fix:     `gcloud auth login` -> set account -> set project

Application Default Credentials (`gcloud auth application-default ...`) are not
needed and are never checked or triggered.

Note: gcloud stdout is redirected to stderr so it never pollutes tool output
on stdout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import logging


# ── Helpers ───────────────────────────────────────────────────────────────────

_GCLOUD_FALLBACK_PATHS = [
    # Google Cloud SDK installed in user's home Documents (common on macOS)
    os.path.expanduser("~/Documents/google-cloud-sdk/bin/gcloud"),
    os.path.expanduser("~/google-cloud-sdk/bin/gcloud"),
    # Homebrew (Intel and Apple Silicon)
    "/usr/local/bin/gcloud",
    "/opt/homebrew/bin/gcloud",
    "/snap/bin/gcloud",
]


def _windows_gcloud_candidates() -> list:
    """Windows Cloud SDK locations built from env vars at call time (unset ones skipped)."""
    out = []
    for var in ("LOCALAPPDATA", "ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(var)
        if base:
            out.append(os.path.join(base, "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd"))
    return out


def _is_usable(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    return True if os.name == "nt" else os.access(path, os.X_OK)


_logger = logging.getLogger(__name__)
_warned_overrides: set = set()


def _warn_bad_override(var: str, value: str) -> None:
    """Log (once per process, to stderr via logging) that an override is unusable."""
    if var in _warned_overrides:
        return
    _warned_overrides.add(var)
    _logger.warning("%s=%r is not a usable file; ignoring it and falling back to normal lookup", var, value)


def _find_gcloud() -> str:
    """
    Return the gcloud binary path.

    Order: GCLOUD_BIN override, shutil.which (PATHEXT-aware on Windows), then
    well-known SDK locations (VS Code and other GUI launchers strip shell PATH
    customisations, so PATH lookup alone often fails).
    """
    override = os.environ.get("GCLOUD_BIN")
    if override:
        if _is_usable(override):
            return override
        _warn_bad_override("GCLOUD_BIN", override)
    path = shutil.which("gcloud")
    if path:
        return path
    candidates = _windows_gcloud_candidates() if os.name == "nt" else _GCLOUD_FALLBACK_PATHS
    for candidate in candidates:
        if _is_usable(candidate):
            return candidate
    return "gcloud"  # let subprocess raise FileNotFoundError with a clear message


def _run_gcloud(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a gcloud command, capturing stdout and stderr."""
    return subprocess.run(
        [_find_gcloud(), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _interactive_gcloud(*args: str, timeout: int = 600) -> bool:
    """
    Run an interactive gcloud command (login flows).
    stdout/stderr forwarded to our stderr — never pollutes tool output on stdout.
    Returns True on exit code 0.
    """
    try:
        result = subprocess.run(
            [_find_gcloud(), *args],
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


# ── Top-level entry point ─────────────────────────────────────────────────────

def ensure_gcloud_auth(required_domain: str = "loreal.com") -> None:
    """
    Called from run_tool.py after ensure_credentials().

    Checks the active account is a loreal.com user account AND that
    `gcloud auth print-access-token` works. If either fails:
    gcloud auth login -> set account -> set project.

    Application Default Credentials are intentionally NOT checked: BigQuery
    runs through the bq CLI, which uses these user credentials.
    """
    _ensure_user_auth(required_domain)


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
