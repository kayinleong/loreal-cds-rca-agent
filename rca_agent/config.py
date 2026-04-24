"""
RCA Agent Configuration
=======================
All tunables in one place. Override via environment variables or .env file.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field


def _load_env(env_path: Path = None):
    """Load .env file into os.environ (simple parser, no dependency)."""
    candidates = [
        env_path,
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in candidates:
        if p and p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip().strip("'\"")
                if key not in os.environ:  # Don't override real env vars
                    os.environ[key] = val
            return p
    return None


_load_env()


def _resolve_llm_api_key(provider: str) -> str:
    """Resolve API key using provider-specific env vars with safe fallbacks."""
    p = (provider or "").strip().lower()
    if p == "google":
        return os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if p == "openai":
        return os.getenv("OPENAI_API_KEY", "")
    # Default to Anthropic for unknown or explicit anthropic provider.
    return os.getenv("ANTHROPIC_API_KEY", "")


# ── LLM Provider ────────────────────────────────────────────────────────────

@dataclass
class LLMConfig:
    """Swappable LLM backend. Change provider to switch APIs."""
    provider: str = os.getenv("LLM_PROVIDER", "anthropic")   # "anthropic" | "openai" | "google"
    model: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
    api_key: str = ""
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    def __post_init__(self):
        # Respect explicit env override first, then provider-specific keys.
        self.api_key = os.getenv("LLM_API_KEY", "") or _resolve_llm_api_key(self.provider)


# ── BigQuery ─────────────────────────────────────────────────────────────────

@dataclass
class BigQueryConfig:
    project: str = os.getenv("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")
    dataset: str = os.getenv("BQ_DATASET", "space_cds_b2c_ds_replica_ae2_pd_public")
    max_bytes_billed: int = int(os.getenv("BQ_MAX_BYTES", "500000000"))  # 500MB
    timeout_seconds: float = float(os.getenv("BQ_TIMEOUT", "30"))
    max_rows: int = int(os.getenv("BQ_MAX_ROWS", "100"))

    @property
    def fully_qualified(self) -> str:
        return f"{self.project}.{self.dataset}"


# ── ServiceNow ───────────────────────────────────────────────────────────────

@dataclass
class ServiceNowConfig:
    instance_url: str = ""
    cookie: str = os.getenv("COOKIE", "")
    user_token: str = os.getenv("X_USERTOKEN", "")
    reports_dir: str = os.getenv("SNOW_REPORTS_DIR", "./my_reports")
    attachments_dir: str = os.getenv("SNOW_ATTACHMENTS_DIR", "./attachments")


# ── Agent ────────────────────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    max_iterations: int = int(os.getenv("AGENT_MAX_ITERATIONS", "15"))
    wiki_dir: str = os.getenv("AGENT_WIKI_DIR", "./wiki")
    output_dir: str = os.getenv("AGENT_OUTPUT_DIR", "./rca_reports")

    llm: LLMConfig = field(default_factory=LLMConfig)
    bq: BigQueryConfig = field(default_factory=BigQueryConfig)
    snow: ServiceNowConfig = field(default_factory=ServiceNowConfig)
