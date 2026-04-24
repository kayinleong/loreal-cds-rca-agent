"""
BigQuery Tool — Safe, Read-Only Executor
=========================================
Multi-layer safety:
  1. IAM: service account with roles/bigquery.dataViewer + jobUser only
  2. Keyword filter: block INSERT/UPDATE/DELETE/DROP/etc.
  3. Dry-run validation: check syntax + estimate cost before execution
  4. maximum_bytes_billed: hard cost ceiling per query
  5. Row limit: cap result set size for LLM context
  6. Timeout: kill long-running queries
"""

from __future__ import annotations
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

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

        # Strip string literals and comments before keyword check
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
        # Step 1: Keyword validation
        is_valid, error = self.validate_query(sql)
        if not is_valid:
            return QueryResult(success=False, error=error, sql=sql)

        try:
            from google.cloud import bigquery

            # Step 2: Dry-run (syntax check + cost estimate)
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

            # Step 3: Execute with hard limits
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

    # ── Schema Introspection ─────────────────

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
        """Get table schema formatted for LLM context."""
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

    def build_schema_context(self, dataset_id: str, table_names: list[str] = None) -> str:
        """
        Build full schema context for the LLM system prompt.
        If table_names is None, lists all tables.
        """
        parts = [
            f"DATABASE: BigQuery `{self.project}.{dataset_id}`",
            "DIALECT: GoogleSQL",
            "  - Use backticks for table/dataset refs: `project.dataset.table`",
            "  - Use SAFE_DIVIDE() for division",
            "  - Use UNNEST() for arrays, STRUCT dot notation for nested fields",
            "  - Use COUNTIF(), IFNULL(), COALESCE()",
            "  - Date functions: DATE(), TIMESTAMP(), CURRENT_TIMESTAMP()",
            "  - Always add LIMIT clause",
            "",
        ]

        if table_names is None:
            tables = self.list_tables(dataset_id)
            parts.append(f"AVAILABLE TABLES ({len(tables)}):")
            for t in sorted(tables, key=lambda x: x["table_id"]):
                parts.append(f"  {t['full_name']}  ({t['num_rows']:,} rows, {t['size_mb']} MB)")
            return "\n".join(parts)

        for name in table_names:
            parts.append(self.get_schema(dataset_id, name))
            parts.append("")
        return "\n".join(parts)


# ── Module-level tool functions (used by MCP server + agent) ─────────────────

_executor: Optional[SafeBigQueryExecutor] = None
_dataset: Optional[str] = None


def init_executor(project: str, dataset: str, **kwargs):
    """Initialize the global executor. Called once during agent/server setup."""
    global _executor, _dataset
    _dataset = dataset
    _executor = SafeBigQueryExecutor(project=project, **kwargs)


def _get_executor() -> SafeBigQueryExecutor:
    global _executor
    if _executor is None:
        raise RuntimeError(
            "BigQuery executor not initialized. "
            "Call init_executor(project, dataset) first."
        )
    return _executor


def query_bigquery(sql: str, rationale: str = "") -> str:
    """Execute a read-only BigQuery query. Returns LLM-friendly result string."""
    executor = _get_executor()
    logger.info(f"[BQ] {rationale}\n  SQL: {sql[:200]}")
    result = executor.execute(sql)
    return result.to_llm_context()


def lookup_schema(table_pattern: str = "") -> str:
    """Look up BigQuery table schemas. Empty pattern lists all tables."""
    executor = _get_executor()
    dataset = _dataset

    if not table_pattern:
        return executor.build_schema_context(dataset)
    else:
        try:
            return executor.get_schema(dataset, table_pattern)
        except Exception:
            tables = executor.list_tables(dataset)
            matches = [t for t in tables if table_pattern.lower() in t["table_id"].lower()]
            if matches:
                lines = [f"Tables matching '{table_pattern}':"]
                for t in matches:
                    lines.append(f"  {t['full_name']}  ({t['num_rows']:,} rows)")
                return "\n".join(lines)
            return f"No tables matching '{table_pattern}' found in {dataset}"
