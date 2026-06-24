"""
Configuration — Mock Data Copilot Agent (GCP / BigQuery DV only).
No LLM configuration; GitHub Copilot / Claude provides the reasoning.
No ServiceNow, no SMTP.

Optional environment variables (or .env keys):
    BQ_PROJECT            GCP project for the read-only consumer_pii lookup
                          (default: oa-apmena-spacecds-ap-dv  — the DV project)
    BQ_DATASET            DV dataset name
                          (default: space_cds_b2c_ds_replica_ase1_dv_public)
    MOCKDATA_OUTPUT_DIR   Directory for generated mockdata/<MMDDYYSS>.md files
                          (default: <pkg_dir>/mockdata)

BigQuery uses gcloud ADC — no credential files. Run once:
    gcloud auth application-default login
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

# Absolute path to this package's directory — used for default data paths so
# files always land inside mockdata_copilot_agent/ regardless of launch CWD.
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
class MockDataConfig:
    bq_project: str   # DV project — differs from rca/ticketasg PD default
    bq_dataset: str
    output_dir: str   # generated mockdata/<MMDDYYSS>.md land here


def load_mockdata_config(env_file: str = ".env") -> MockDataConfig:
    """Load mock-data config from env vars, falling back to a .env file.
    Environment variables take precedence over .env values."""
    env_data = _find_env_data(env_file)

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_data.get(key, default)

    return MockDataConfig(
        bq_project=get("BQ_PROJECT", "oa-apmena-spacecds-ap-dv"),
        bq_dataset=get("BQ_DATASET", "space_cds_b2c_ds_replica_ase1_dv_public"),
        output_dir=get("MOCKDATA_OUTPUT_DIR", str(_PKG_DIR / "mockdata")),
    )
