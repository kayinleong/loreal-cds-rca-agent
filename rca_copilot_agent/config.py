"""
Configuration — BigQuery + ServiceNow.
No LLM configuration; GitHub Copilot provides the reasoning.

Required environment variables (or .env keys):
    COOKIE          Full Cookie header from an active ServiceNow browser session
    X_USERTOKEN     X-UserToken CSRF token from the same session

BigQuery variables (optional — BQ tools disabled if BQ_PROJECT is absent):
    BQ_PROJECT      GCP project ID
    BQ_DATASET      BigQuery dataset name
    BQ_MAX_BYTES    Hard scan limit in bytes (default: 500000000)
    BQ_TIMEOUT      Query timeout in seconds (default: 30)
    BQ_MAX_ROWS     Max rows returned per query (default: 100)

Other optional:
    SNOW_INSTANCE   ServiceNow base URL (default: https://loreal.service-now.com)
    REPORTS_DIR     Local directory for downloaded incident JSON (default: ./my_reports)
    ATTACHMENTS_DIR Local directory for downloaded attachments (default: ./attachments)
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


@dataclass
class BigQueryConfig:
    project: str
    dataset: str
    max_bytes: int
    timeout: float
    max_rows: int

    @property
    def enabled(self) -> bool:
        return bool(self.project and self.dataset)


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


def load_bq_config(env_file: str = ".env") -> BigQueryConfig:
    """
    Load BigQuery config from environment variables, falling back to a .env file.
    Returns a BigQueryConfig with project="" if BQ_PROJECT is not set (disabled state).
    """
    env_data = _find_env_data(env_file)

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_data.get(key, default)

    return BigQueryConfig(
        project=get("BQ_PROJECT"),
        dataset=get("BQ_DATASET"),
        max_bytes=int(get("BQ_MAX_BYTES", "500000000")),
        timeout=float(get("BQ_TIMEOUT", "30")),
        max_rows=int(get("BQ_MAX_ROWS", "100")),
    )
