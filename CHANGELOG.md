# Changelog

## phase-kayinleong-03 — 2026-10-12 — `rca_copilot_agent`

### Breaking
- **`post_comment` requires `confirmed: true`.** Without it the tool returns a preview and posts nothing.
  Migration: show the preview to the user, then call again with the same arguments plus `confirmed: true`
  (CLI: `--arg confirmed=true`). Instruction files are updated.
- **`save_rca_report` validates the report.** Missing or empty sections (`WHAT HAPPENED`, `WHAT WE CHECKED`,
  `WHAT WE FOUND`, `WHAT WE NEED / DID`) → `✗ RCA report NOT saved`. Migration: call `get_rca_template` and follow it.
- **`tools/email_tool.py`:** `register_report` / `get_session_reports` removed; `send_rca_email` takes
  `report_entries` instead of `report_paths`. Internal API — the only caller (`mcp_server.py`) is updated.

### Added
- `get_rca_template` tool (canonical template + rules + assignment-group table; single source of truth in
  `tools/rca_report_tool.py`).
- `query_bigquery(incident_number=…)` records each query (SQL, rationale, row count / error; never result rows)
  and `save_rca_report` appends it as `## Evidence — BigQuery queries run`, plus a ticket metadata header.
- On-disk report registry: `send_rca_email` attaches saved, not-yet-emailed reports across separate CLI calls;
  optional `incident_numbers` filter; result lists `Attached incidents:`.
- `run_tool.py`: `--json-file <path>`, `--json -` (stdin), `--arg key=value`; UTF-8 console output.
- Env vars: `BQ_BIN`, `GCLOUD_BIN`, `BQ_CLI_TIMEOUT` (default 120 s), `RCA_SESSION_WINDOW_HOURS` (default 24).

### Changed
- BigQuery runs on macOS and Windows: SQL is sent to `bq` on stdin, `--headless`, Windows SDK paths
  (`bq.cmd` / `gcloud.cmd`), `os.pathsep`, UTF-8 I/O, process-tree kill on timeout.
- RCA email: HTML-escaped, summary table, each RCA inline, `.md` attachments.
- `--json '<JSON>'` still works but is POSIX-shell-only; docs now use `--arg` / `--json-file`.
