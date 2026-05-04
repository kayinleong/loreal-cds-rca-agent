"""
Configuration — ServiceNow + SMTP.
No LLM configuration; GitHub Copilot provides the reasoning.

Required environment variables (or .env keys):
    COOKIE          Full Cookie header from an active ServiceNow browser session
    X_USERTOKEN     X-UserToken CSRF token from the same session

Optional:
    SNOW_INSTANCE   ServiceNow base URL (default: https://loreal.service-now.com)
    REPORTS_DIR     Local directory for downloaded incident JSON (default: ./my_reports)
    ATTACHMENTS_DIR Local directory for downloaded attachments (default: ./attachments)

BigQuery: configured via schema.json in the repo root + gcloud ADC.
No BQ_* env vars required. Run: gcloud auth application-default login
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

# Absolute path to this package's directory — used for default data paths so
# files always land inside rca_copilot_agent/ regardless of launch CWD.
_PKG_DIR = Path(__file__).resolve().parent


def _load_env_file(env_path: Path) -> dict:
    """Load KEY=VALUE pairs from a .env file, ignoring comments and blanks."""
    data: dict[str, str] = {}
    if not env_path.exists():
        return data
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _find_env_data(env_file: str) -> dict[str, str]:
    """Search for .env in cwd then alongside this file."""
    for candidate in [Path.cwd() / env_file, Path(__file__).resolve().parent / env_file]:
        data = _load_env_file(candidate)
        if data:
            return data
    return {}


@dataclass
class ServiceNowConfig:
    instance_url: str
    cookie: str
    x_user_token: str
    reports_dir: str
    attachments_dir: str


def load_config(env_file: str = ".env") -> ServiceNowConfig:
    """
    Load ServiceNow config from environment variables, falling back to a .env file.
    Environment variables take precedence over .env values.
    """
    env_data = _find_env_data(env_file)

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_data.get(key, default)

    return ServiceNowConfig(
        instance_url=get("SNOW_INSTANCE", "https://loreal.service-now.com"),
        cookie=get("COOKIE"),
        x_user_token=(
            get("X_USERTOKEN")
            or get("X-UserToken")
            or get("X-usertoken")
        ),
        reports_dir=get("REPORTS_DIR", str(_PKG_DIR / "my_reports")),
        attachments_dir=get("ATTACHMENTS_DIR", str(_PKG_DIR / "attachments")),
    )


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    to_addrs: list
    use_tls: bool
    verify_ssl: bool

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.from_addr and self.to_addrs)


def load_smtp_config(env_file: str = ".env") -> SmtpConfig:
    """
    Load SMTP config from environment variables, falling back to a .env file.
    Returns a SmtpConfig with host="" if SMTP_HOST is not set (disabled state).
    """
    env_data = _find_env_data(env_file)

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_data.get(key, default)

    raw_to = get("SMTP_TO", "")
    to_addrs = [a.strip() for a in raw_to.split(",") if a.strip()]

    use_tls_raw = get("SMTP_USE_TLS", "true").lower()
    use_tls = use_tls_raw not in ("false", "0", "no")

    verify_ssl_raw = get("SMTP_VERIFY_SSL", "true").lower()
    verify_ssl = verify_ssl_raw not in ("false", "0", "no")

    return SmtpConfig(
        host=get("SMTP_HOST"),
        port=int(get("SMTP_PORT", "587")),
        user=get("SMTP_USER"),
        password=get("SMTP_PASSWORD"),
        from_addr=get("SMTP_FROM"),
        to_addrs=to_addrs,
        use_tls=use_tls,
        verify_ssl=verify_ssl,
    )
