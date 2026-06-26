"""
BigQuery Tool — Safe, Read-Only Executor with schema.json-driven initialization
================================================================================
Auth:   gcloud Application Default Credentials (ADC) — no BQ env vars required.
Schema: Reads schema.json from repo root for instant offline schema lookups.

Multi-layer safety:
  1. IAM: account must have roles/bigquery.dataViewer + jobUser only
  2. Keyword filter: block INSERT/UPDATE/DELETE/DROP/etc.
  3. Dry-run validation: check syntax + estimate cost before execution
  4. maximum_bytes_billed: hard cost ceiling per query
  5. Row limit: cap result set size for LLM context
  6. Timeout: kill long-running queries
"""

from __future__ import annotations
import json
import os
import re
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── bq CLI path resolution ────────────────────────────────────────────────────
# VS Code and other GUI launchers strip shell PATH customisations, so
# shutil.which("bq") often fails even when the SDK is installed. We supplement
# with well-known SDK locations — bq lives alongside gcloud in the same bin/.

_BQ_FALLBACK_PATHS = [
    os.path.expanduser("~/Documents/google-cloud-sdk/bin/bq"),
    os.path.expanduser("~/google-cloud-sdk/bin/bq"),
    "/usr/local/bin/bq",
    "/opt/homebrew/bin/bq",
    "/snap/bin/bq",
]


def _find_bq() -> str:
    path = shutil.which("bq")
    if path:
        return path
    for candidate in _BQ_FALLBACK_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "bq"  # let subprocess raise FileNotFoundError with a clear message


def _sdk_env() -> dict:
    """
    Return os.environ copy with the Cloud SDK bin/ dir prepended to PATH.

    VS Code (and other GUI launchers) strip shell PATH customisations, so even
    when bq is resolved via _find_bq(), bq itself calls gcloud internally for
    authentication and fails because gcloud is not on the stripped PATH.
    Prepending the SDK bin dir to the subprocess environment fixes this.
    """
    bq_binary = _find_bq()
    env = os.environ.copy()
    if bq_binary != "bq":
        bin_dir = os.path.dirname(os.path.abspath(bq_binary))
        existing = env.get("PATH", "")
        env["PATH"] = f"{bin_dir}:{existing}" if existing else bin_dir
    return env


# schema.json lives in the repo root (3 levels up from ticketasg_copilot_agent/tools/)
_SCHEMA_JSON = Path(__file__).resolve().parent.parent.parent / "schema.json"

# ── Blocklist ────────────────────────────────────────────────────────────────

DANGEROUS_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "MERGE", "GRANT", "REVOKE", "EXECUTE",
    "CALL", "EXPORT", "LOAD",
}


# ── Result container ─────────────────────────────────────────────────────────

@dataclass
class QueryResult:
    success: bool
    data: list[dict] = field(default_factory=list)
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    bytes_processed: Optional[int] = None
    error: Optional[str] = None
    sql: str = ""

    def to_llm_context(self, max_rows: int = 50) -> str:
        """Format result for LLM consumption — dense, not chatty."""
        if not self.success:
            return f"QUERY FAILED: {self.error}\nSQL: {self.sql}"

        if self.row_count == 0:
            return f"Query returned 0 rows.\nSQL: {self.sql}"

        lines = [f"Returned {self.row_count} row(s). Columns: {self.columns}"]
        for row in self.data[:max_rows]:
            lines.append(json.dumps(row, default=str))
        if self.row_count > max_rows:
            lines.append(f"...({self.row_count - max_rows} more rows truncated)")
        if self.bytes_processed:
            mb = self.bytes_processed / (1024 * 1024)
            lines.append(f"[Scanned {mb:.1f} MB]")
        return "\n".join(lines)


# ── Executor ─────────────────────────────────────────────────────────────────

class SafeBigQueryExecutor:
    """
    Read-only BigQuery client with guardrails.
    Uses gcloud Application Default Credentials — no explicit credentials needed.

    Usage:
        executor = SafeBigQueryExecutor(project="my-project")
        result = executor.execute("SELECT COUNT(*) FROM `dataset.table`")
        print(result.to_llm_context())
    """

    def __init__(
        self,
        project: str,
        max_bytes: int = 500_000_000,
        timeout: float = 30.0,
        max_rows: int = 100,
    ):
        self.project = project
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.max_rows = max_rows
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery
            self._client = bigquery.Client(project=self.project)
        return self._client

    # ── Validation ───────────────────────────

    def validate_query(self, sql: str) -> tuple[bool, Optional[str]]:
        """Check SQL for dangerous operations before sending to BQ."""
        if not sql or not sql.strip():
            return False, "Empty query"

        cleaned = re.sub(r"'[^']*'", "", sql.upper())
        cleaned = re.sub(r'"[^"]*"', "", cleaned)
        cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        for kw in DANGEROUS_KEYWORDS:
            if re.search(rf"\b{kw}\b", cleaned):
                return False, f"Blocked: '{kw}' statements are not allowed (read-only mode)"

        stripped = cleaned.strip().lstrip("(")
        if not (stripped.startswith("SELECT") or stripped.startswith("WITH")):
            return False, "Query must start with SELECT or WITH (read-only mode)"

        return True, None

    def dry_run(self, sql: str) -> tuple[bool, Optional[str], Optional[int]]:
        """Validate syntax and estimate bytes without executing."""
        try:
            from google.cloud import bigquery
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            job = self.client.query(sql, job_config=job_config)
            return True, None, job.total_bytes_processed
        except Exception as e:
            return False, str(e), None

    # ── Execution ────────────────────────────

    def execute(self, sql: str) -> QueryResult:
        """Validate → dry-run → execute with all safety bounds."""
        is_valid, error = self.validate_query(sql)
        if not is_valid:
            return QueryResult(success=False, error=error, sql=sql)

        try:
            from google.cloud import bigquery

            ok, dry_err, est_bytes = self.dry_run(sql)
            if not ok:
                return QueryResult(
                    success=False,
                    error=f"Syntax error: {dry_err}",
                    sql=sql,
                )
            if est_bytes and est_bytes > self.max_bytes:
                mb = est_bytes / (1024 * 1024)
                limit_mb = self.max_bytes / (1024 * 1024)
                return QueryResult(
                    success=False,
                    error=f"Query would scan {mb:.0f} MB, exceeding limit of {limit_mb:.0f} MB. "
                          "Add more filters or use a narrower query.",
                    sql=sql,
                )

            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=self.max_bytes,
            )
            job = self.client.query(sql, job_config=job_config)
            rows = job.result(timeout=self.timeout, max_results=self.max_rows)
            data = [dict(row) for row in rows]

            return QueryResult(
                success=True,
                data=data,
                row_count=job.total_rows or len(data),
                columns=[f.name for f in job.schema] if job.schema else [],
                bytes_processed=job.total_bytes_processed,
                sql=sql,
            )

        except Exception as e:
            return QueryResult(success=False, error=str(e), sql=sql)

    # ── Live Schema Introspection (fallback) ─────────────────────────────────

    def list_tables(self, dataset_id: str) -> list[dict]:
        """List all tables in a dataset with row counts."""
        tables = []
        for t in self.client.list_tables(f"{self.project}.{dataset_id}"):
            full = self.client.get_table(t.reference)
            tables.append({
                "table_id": t.table_id,
                "full_name": f"`{self.project}.{dataset_id}.{t.table_id}`",
                "num_rows": full.num_rows,
                "size_mb": round((full.num_bytes or 0) / (1024 * 1024), 1),
                "type": t.table_type,
            })
        return tables

    def get_schema(self, dataset_id: str, table_id: str) -> str:
        """Get table schema formatted for LLM context (live BQ call)."""
        ref = f"{self.project}.{dataset_id}.{table_id}"
        table = self.client.get_table(ref)
        lines = [
            f"TABLE: `{ref}`",
            f"Rows: ~{table.num_rows:,}  |  Size: {(table.num_bytes or 0) / (1024*1024):.1f} MB",
            f"Description: {table.description or '(none)'}",
            "",
            "COLUMNS:",
        ]
        for f in table.schema:
            desc = f"  -- {f.description}" if f.description else ""
            lines.append(f"  {f.name:<40} {f.field_type:<12} {f.mode:<10}{desc}")
            if f.field_type == "RECORD" and f.fields:
                for sub in f.fields:
                    lines.append(f"    .{sub.name:<38} {sub.field_type:<12} {sub.mode}")
        return "\n".join(lines)


# ── schema.json helpers ───────────────────────────────────────────────────────

def _load_schema_json() -> dict:
    """Load schema.json from repo root. Raises RuntimeError if missing."""
    if not _SCHEMA_JSON.exists():
        raise RuntimeError(
            f"schema.json not found at {_SCHEMA_JSON}. "
            "Ensure schema.json exists in the repo root."
        )
    return json.loads(_SCHEMA_JSON.read_text(encoding="utf-8"))


def get_schema_from_file(table_name: str = "") -> str:
    """
    Return schema info from schema.json (instant, no BQ cost).
    Empty table_name → list all tables (primary + additional datasets) with purpose.
    Named table_name → search primary tables first, then additional_datasets.
    """
    schema = _load_schema_json()
    tables = schema.get("tables", {})
    project = schema.get("project", "")
    dataset = schema.get("dataset", "")
    additional_datasets: dict = schema.get("additional_datasets", {})

    if not table_name:
        lines = [
            f"PRIMARY DATASET: `{project}.{dataset}`",
            f"DIALECT: {schema.get('dialect', 'GoogleSQL')}",
            f"AUTH: {schema.get('auth', 'gcloud ADC')}",
            "",
            f"PRIMARY TABLES ({len(tables)}) — B2C consumer, purchase, loyalty, care_case:",
        ]
        for name in sorted(tables.keys()):
            t = tables[name]
            purpose = t.get("purpose", t.get("description", ""))
            lines.append(f"  `{project}.{dataset}.{name}`  →  {purpose}")

        if additional_datasets:
            lines.append("")
            lines.append("ADDITIONAL DATASETS (B2B + DV replicas):")
            for ds_key, ds_info in additional_datasets.items():
                ds_tables = ds_info.get("tables", {})
                lines.append(f"  [{ds_key}]  {ds_info.get('description', '')}")
                lines.append(f"    Note: {ds_info.get('note', '')}")
                for tname in sorted(ds_tables.keys()):
                    t = ds_tables[tname]
                    lines.append(f"    `{ds_key}.{tname}`  →  {t.get('purpose', '')}")

        if schema.get("common_rca_patterns"):
            lines.append("")
            lines.append("COMMON RCA QUERY PATTERNS (fill in <PLACEHOLDER> values):")
            for pattern_name, sql in schema["common_rca_patterns"].items():
                lines.append(f"  [{pattern_name}]")
                lines.append(f"    {sql}")
        return "\n".join(lines)

    # ── Look up a specific table ──────────────────────────────────────────────
    # 1. Exact match in primary tables
    matched_name = table_name if table_name in tables else next(
        (k for k in tables if table_name.lower() in k.lower()), None
    )
    if matched_name:
        return _format_primary_table(schema, project, dataset, matched_name)

    # 2. Search additional_datasets
    for ds_key, ds_info in additional_datasets.items():
        ds_tables = ds_info.get("tables", {})
        matched_ds = table_name if table_name in ds_tables else next(
            (k for k in ds_tables if table_name.lower() in k.lower()), None
        )
        if matched_ds:
            return _format_additional_table(ds_key, ds_info, matched_ds)

    # 3. Not found
    all_primary = ", ".join(sorted(tables.keys()))
    all_extra = []
    for ds_key, ds_info in additional_datasets.items():
        for tname in ds_info.get("tables", {}):
            all_extra.append(f"{ds_key}.{tname}")
    hint = f"Primary tables: {all_primary}"
    if all_extra:
        hint += f"\n\nAdditional dataset tables: {', '.join(all_extra)}"
    return f"Table '{table_name}' not found in schema.json.\n\n{hint}"


def _format_primary_table(schema: dict, project: str, dataset: str, matched: str) -> str:
    """Format a primary-dataset table entry for LLM output."""
    t = schema["tables"][matched]
    lines = [
        f"TABLE: `{project}.{dataset}.{matched}`",
        f"Purpose: {t.get('purpose', '')}",
        f"Description: {t.get('description', '')}",
    ]
    if t.get("partitioned_by"):
        lines.append(f"Partitioned by: {t['partitioned_by']}")
    if t.get("clustered_by"):
        lines.append(f"Clustered by: {', '.join(t['clustered_by'])}")
    lines.append("")
    lines.append("COLUMNS:")
    for col in t.get("columns", []):
        desc = f"  -- {col['description']}" if col.get("description") else ""
        lines.append(f"  {col['name']:<45} {col['type']:<12}{desc}")
    if t.get("relationships"):
        lines.append("")
        lines.append("RELATIONSHIPS:")
        for rel in t["relationships"]:
            lines.append(f"  {rel}")
    patterns = schema.get("common_rca_patterns", {})
    relevant = {k: v for k, v in patterns.items() if matched.replace("_", "") in v.replace("_", "").lower()}
    if relevant:
        lines.append("")
        lines.append("COMMON QUERY PATTERNS:")
        for pname, sql in relevant.items():
            lines.append(f"  [{pname}]: {sql}")
    return "\n".join(lines)


def _format_additional_table(ds_key: str, ds_info: dict, matched: str) -> str:
    """Format an additional-dataset table entry for LLM output."""
    t = ds_info["tables"][matched]
    lines = [
        f"TABLE: `{ds_key}.{matched}`",
        f"Dataset: {ds_info.get('description', '')}",
        f"Note: {ds_info.get('note', '')}",
        f"Purpose: {t.get('purpose', '')}",
        "",
        "COLUMNS:",
    ]
    for col in t.get("columns", []):
        desc = f"  -- {col['description']}" if col.get("description") else ""
        lines.append(f"  {col['name']:<45} {col['type']:<12}{desc}")
    if t.get("relationships"):
        lines.append("")
        lines.append("RELATIONSHIPS:")
        for rel in t["relationships"]:
            lines.append(f"  {rel}")
    if t.get("common_queries"):
        lines.append("")
        lines.append("EXAMPLE QUERIES:")
        for q in t["common_queries"]:
            lines.append(f"  {q}")
    return "\n".join(lines)


# ── Module-level tool functions (used by MCP server) ─────────────────────────

# Keyed by GCP project ID — one executor per billing project.
_executors: dict[str, "SafeBigQueryExecutor"] = {}
_dataset: Optional[str] = None
_default_project: Optional[str] = None

_BQ_UNAVAILABLE = (
    "BigQuery is not available. Ensure schema.json exists in the repo root and "
    "gcloud ADC is configured (run: gcloud auth application-default login)."
)

# Regex to extract project IDs from backtick-quoted table refs, e.g.
# `oa-apmena-spacecds-ap-dv.dataset.table`
_PROJECT_RE = re.compile(r"`([a-z0-9_-]+)\.[^`]+`", re.IGNORECASE)


def init_from_schema() -> None:
    """
    Initialize one BQ executor per GCP project found in schema.json.
    Uses gcloud Application Default Credentials — no env vars required.

    One executor is created for the primary project and one for each
    distinct project referenced in additional_datasets, so that queries
    against DV tables are billed to the DV project (not the PD project).
    """
    global _executors, _dataset, _default_project
    schema = _load_schema_json()
    _default_project = schema["project"]
    _dataset = schema["dataset"]

    # Collect all distinct GCP projects mentioned in the schema
    projects: set[str] = {_default_project}
    for ds_key in schema.get("additional_datasets", {}):
        # ds_key format: "project-id.dataset_name"
        proj = ds_key.split(".")[0]
        projects.add(proj)

    _executors = {}
    for proj in projects:
        _executors[proj] = SafeBigQueryExecutor(
            project=proj,
            max_bytes=500_000_000,
            timeout=30.0,
            max_rows=100,
        )
        logger.info(f"[BQ] Initialized executor for project: {proj}")


def _pick_executor(sql: str) -> "SafeBigQueryExecutor":
    """
    Return the executor whose billing project matches the first backtick-quoted
    GCP project found in the SQL.  Falls back to the default project executor.
    """
    if not _executors:
        raise RuntimeError(_BQ_UNAVAILABLE)
    for match in _PROJECT_RE.finditer(sql):
        proj = match.group(1)
        if proj in _executors:
            return _executors[proj]
    if _default_project and _default_project in _executors:
        return _executors[_default_project]
    return next(iter(_executors.values()))


def _get_executor() -> "SafeBigQueryExecutor":
    if not _executors:
        raise RuntimeError(_BQ_UNAVAILABLE)
    if _default_project and _default_project in _executors:
        return _executors[_default_project]
    return next(iter(_executors.values()))


def is_enabled() -> bool:
    return bool(_executors)


def _bq_cli_available() -> bool:
    """True when the bq CLI binary is reachable (checks PATH and fallback locations)."""
    try:
        r = subprocess.run([_find_bq(), "version"], capture_output=True, timeout=5, env=_sdk_env())
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _bq_cli_execute(sql: str, project: str, max_rows: int = 100) -> QueryResult:
    """
    Execute a pre-validated SELECT query via the bq CLI subprocess.
    Uses gcloud auth login credentials, which often differ from ADC.
    """
    try:
        proc = subprocess.run(
            [
                _find_bq(),
                f"--project_id={project}",
                "--quiet",
                "query",
                "--nouse_legacy_sql",
                "--format=json",
                f"--max_rows={max_rows}",
                sql,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=_sdk_env(),
        )
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()

        if proc.returncode != 0:
            return QueryResult(success=False, error=stderr or stdout, sql=sql)

        if not stdout or stdout in ("[]", ""):
            return QueryResult(success=True, data=[], row_count=0, columns=[], sql=sql)

        rows = json.loads(stdout)
        if not isinstance(rows, list):
            return QueryResult(success=False, error=f"Unexpected bq output: {stdout[:200]}", sql=sql)

        columns = list(rows[0].keys()) if rows else []
        return QueryResult(
            success=True,
            data=rows,
            row_count=len(rows),
            columns=columns,
            sql=sql,
        )

    except subprocess.TimeoutExpired:
        return QueryResult(success=False, error="bq CLI query timed out (60s)", sql=sql)
    except json.JSONDecodeError as exc:
        return QueryResult(success=False, error=f"bq CLI returned non-JSON output: {exc}", sql=sql)
    except Exception as exc:
        return QueryResult(success=False, error=f"bq CLI error: {exc}", sql=sql)


def query_bigquery(sql: str, rationale: str = "") -> str:
    """Execute a read-only BigQuery query via bq CLI. Returns LLM-friendly result string."""
    if not _executors:
        raise RuntimeError(_BQ_UNAVAILABLE)
    executor = _pick_executor(sql)
    is_valid, error = executor.validate_query(sql)
    if not is_valid:
        return QueryResult(success=False, error=error, sql=sql).to_llm_context()
    logger.info(f"[BQ] billing_project={executor.project} | {rationale}\n  SQL: {sql[:200]}")
    result = _bq_cli_execute(sql, executor.project, max_rows=executor.max_rows)
    return result.to_llm_context()


def query_bigquery_rows(sql: str, rationale: str = "") -> tuple[list[dict], Optional[str]]:
    """Execute a read-only BigQuery SELECT and return structured rows.

    Same safety path as query_bigquery (blocklist validation + read-only bq CLI
    executor), but returns (rows, error) instead of an LLM-friendly string so
    callers that need the actual values (e.g. fetch_seed) don't have to re-parse
    a formatted blob. On success error is None; on failure rows is [] and error
    is set.
    """
    if not _executors:
        raise RuntimeError(_BQ_UNAVAILABLE)
    executor = _pick_executor(sql)
    is_valid, error = executor.validate_query(sql)
    if not is_valid:
        return [], error
    logger.info(f"[BQ] billing_project={executor.project} | {rationale}\n  SQL: {sql[:200]}")
    result = _bq_cli_execute(sql, executor.project, max_rows=executor.max_rows)
    if not result.success:
        return [], result.error
    return result.data, None


def lookup_schema(table_pattern: str = "") -> str:
    """Look up BigQuery table schemas from schema.json (fast) or live BQ (fallback)."""
    return get_schema_from_file(table_pattern)
