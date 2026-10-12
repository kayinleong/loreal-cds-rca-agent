# Plan: phase-kayinleong-03 — rca_copilot_agent: cross-platform BigQuery + better RCA & delivery

Source: user decision 2026-10-12 after quick-kayinleong-027 research.
- Target package: **`rca_copilot_agent`** only (do NOT touch rca_agent / ticketasg / mockdata copies).
- **No cost guard** (no dry-run / maximum_bytes_billed work).
- **Step 3:** every BigQuery query must run on **macOS and Windows**.
- **Steps 4 & 5:** improve RCA production and delivery.

Keep the `bq` CLI execution path (deliberate since quick-kayinleong-005: ADC permission errors on L'Oréal accounts).

## Root causes being fixed

| # | Problem | Where |
|---|---|---|
| W1 | SQL passed as a positional argv to `bq` → on Windows `bq.cmd` runs through `cmd.exe`, which truncates at newlines and mangles `% ^ & \| < > "` | `tools/bigquery_tool.py::_bq_cli_execute` |
| W2 | Fallback SDK paths are POSIX-only; no `bq.cmd` / `gcloud.cmd` locations | `bigquery_tool._BQ_FALLBACK_PATHS`, `gcloud_tool._GCLOUD_FALLBACK_PATHS` |
| W3 | PATH joined with `:` (wrong on Windows — must be `os.pathsep`) | `bigquery_tool._sdk_env` |
| W4 | `text=True` decodes with locale code page (cp1252 on Windows) → crashes / mojibake on non-ASCII results (APMENA names, L'Oréal) | `bigquery_tool`, `gcloud_tool` subprocess calls |
| W5 | `run_tool.py --json '<JSON>'`: cmd.exe has no single quotes; PowerShell 5.1 strips embedded `"` when calling native exes; any apostrophe breaks POSIX shells | `run_tool.py`, all instruction files |
| W6 | Printing non-ASCII to a Windows console (cp1252) raises `UnicodeEncodeError` | `run_tool.py` stdout |
| R1 | RCA template is prompt-only, duplicated in 3 files, already drifting; no validation | agent.md / SKILL.md / AGENTS.md, `save_rca_report` |
| R2 | RCA has no audit trail of which queries were actually run | `query_bigquery` → nothing recorded |
| D1 | Email attaches nothing in CLI mode (in-memory `_session_reports`, new process per call) | `tools/email_tool.py`, `mcp_server.save_rca_report` |
| D2 | Email HTML not escaped | `email_tool._build_html` |
| D3 | `post_comment` confirmation only prompt-enforced | `mcp_server` `post_comment` branch |
| D4 | JSON-RPC fallback tool list has 10 of 14 tools | `mcp_server.py` fallback |

## Interface contracts (wave 2 codes against these — wave 1 MUST implement exactly)

### A — `tools/bigquery_tool.py`
```python
def query_bigquery_result(sql: str, rationale: str = "") -> QueryResult   # NEW: validate + execute, structured
def query_bigquery(sql: str, rationale: str = "") -> str                  # unchanged signature; == query_bigquery_result(...).to_llm_context()
```
`QueryResult` fields unchanged (`success, data, row_count, columns, error, sql`).

### B — `run_tool.py`
CLI forms (all produce the same `arguments` dict):
```
run_tool.py <tool>                                   # {}
run_tool.py <tool> --json '<JSON object>'            # existing, kept
run_tool.py <tool> --json-file <path>                # NEW: UTF-8 (BOM tolerated)
run_tool.py <tool> --json -                          # NEW: JSON from stdin (UTF-8)
run_tool.py <tool> --arg key=value [--arg k2=v2 ...] # NEW: string values; "true"/"false" → bool; merged over JSON
```
Scratch dir for args files: `.rca_tmp/` at repo root (gitignored).

### C — `tools/rca_report_tool.py` (NEW, pure + filesystem only, no network, no LLM)
```python
RCA_SECTIONS: tuple[str, ...] = ("WHAT HAPPENED", "WHAT WE CHECKED", "WHAT WE FOUND", "WHAT WE NEED / DID")
EVIDENCE_HEADING = "## Evidence — BigQuery queries run"

def get_rca_template() -> str
def parse_sections(report_text: str) -> dict[str, str]                    # canonical section name -> body
def validate_rca_report(report_text: str) -> tuple[list[str], list[str]]  # (errors, warnings)
def record_query(reports_dir: str, incident_number: str, *, sql: str, rationale: str,
                 success: bool, row_count: int, error: str | None) -> None
def load_evidence(reports_dir: str, incident_number: str) -> list[dict]
def render_report(incident_number: str, report_text: str,
                  incident_meta: dict[str, str] | None, evidence: list[dict]) -> str
def save_report(reports_dir: str, incident_number: str, report_text: str,
                incident_meta: dict[str, str] | None = None) -> dict
    # -> {"path", "json_path", "warnings": [...], "evidence_count": int}; also registers in registry
def pending_reports(reports_dir: str, incident_numbers: list[str] | None = None) -> list[dict]
    # registry entries not yet emailed whose file exists:
    # {"incident_number","path","saved_at","short_description","root_cause"}
def mark_emailed(reports_dir: str, paths: list[str]) -> None
```
Storage: `<reports_dir>/rca_reports/<SAFE_INC>_rca_<YYYYmmdd_HHMMSS>.md` (+ `.json`),
`<reports_dir>/rca_reports/.evidence/<SAFE_INC>.jsonl`, `<reports_dir>/rca_reports/.registry.json`.

### D — `tools/email_tool.py`
```python
def send_rca_email(smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_to, use_tls,
                   subject, session_summary, report_entries: list[dict] | None = None,
                   verify_ssl: bool = True) -> str
# report_entries items: {"incident_number","path","short_description","root_cause"} (as from pending_reports)
```
`_session_reports` / `register_report` / `get_session_reports` are removed (sole caller is `mcp_server`, rewired in wave 2).

## Waves

| Wave | Task | Owner files (exclusive) | Depends on |
|---|---|---|---|
| 1 | **A** cross-platform BQ + gcloud (W1–W4) | `rca_copilot_agent/tools/bigquery_tool.py`, `rca_copilot_agent/tools/gcloud_tool.py`, `rca_copilot_agent/tests/test_bq_crossplatform.py` | — |
| 1 | **B** shell-safe CLI (W5–W6) | `rca_copilot_agent/run_tool.py`, `.gitignore`, `rca_copilot_agent/tests/test_run_tool.py` | — |
| 1 | **C** RCA template / validation / evidence / registry (R1, R2, D1 storage) | `rca_copilot_agent/tools/rca_report_tool.py` (new), `rca_copilot_agent/tests/test_rca_report_tool.py` | — |
| 1 | **D** email rendering + attachments (D1, D2) | `rca_copilot_agent/tools/email_tool.py`, `rca_copilot_agent/tests/test_email_tool.py` | — |
| 2 | **E** wire dispatch: `query_bigquery(incident_number)` evidence, `get_rca_template` tool, validated `save_rca_report`, registry-based `send_rca_email`, `post_comment(confirmed)` gate, full fallback list (D3, D4) | `rca_copilot_agent/mcp_server.py`, `rca_copilot_agent/tests/test_dispatch_rca_flow.py` | A, C, D |
| 2 | **F** docs: new invocation (args file / `--arg`), macOS + Windows setup, canonical template via `get_rca_template`, new params | `.github/agents/rca_copilot.agent.md`, `.claude/skills/rca-copilot/SKILL.md`, `rca_copilot_agent/AGENTS.md` | A–E contracts |
| 3 | Verify: full offline test suite + py_compile (3.12), 2 parallel regression reviewers (BQ/CLI surface; report/email/dispatch surface) | read-only | 1, 2 |

Rules for every agent: no git writes (orchestrator commits one commit per task at wave end); no `.env` reads; no network calls to SNOW / BQ / SMTP; tests are stdlib `unittest`, offline, mock `subprocess` / `smtplib` / SNOW reader; tests insert `rca_copilot_agent/` on `sys.path`; do not create `tests/__init__.py`.

Test command: `$VENV/bin/python -m unittest discover -s rca_copilot_agent/tests -v`
(`$VENV` = orchestrator scratch venv, Python 3.12 + requirements minus sentence-transformers.)

## Out of scope (deferred)
- Same fixes in `ticketasg_copilot_agent` / `mockdata_copilot_agent` copies (shared-module refactor = separate claim).
- Step 1/2 issues (auth per-call re-checks, attachment OCR, filename sanitising, cache overwrite).
- Repo-root `CLAUDE.md` staleness (table count, MCP-first description).
- Live Windows run — cannot be executed from this macOS session; covered by mocked tests + user smoke test.
