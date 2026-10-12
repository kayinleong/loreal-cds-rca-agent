# Claim: phase-kayinleong-03
- owner: kayinleong
- session: claude-code
- branch: feature/phase-kayinleong-03-rca-copilot-xplat
- started: 2026-10-12
- status: done
- summary: rca_copilot_agent — make every BigQuery query run on macOS and Windows (bq via stdin, Windows SDK paths, UTF-8, shell-safe run_tool args) and improve RCA production (canonical template, validation, query evidence appendix) and delivery (persistent report registry so email attaches reports in CLI mode, escaped HTML with RCA summary, code-enforced post_comment confirmation). No cost guard (user decision).

## What will change

See `03-PLAN.md` (waves, interface contracts, file ownership). Research basis:
`.planning/quick/quick-kayinleong-027/quick-kayinleong-027-RESEARCH.md`.

## What has changed

All in `rca_copilot_agent/` unless noted. Per-task detail: `03-SUMMARY-A.md` … `03-SUMMARY-I.md`.

| Wave | Commit | Change |
|---|---|---|
| 1-A | `cbfa30e` | `tools/bigquery_tool.py`, `tools/gcloud_tool.py`: SQL to `bq` via stdin, `--headless`, Windows `bq.cmd`/`gcloud.cmd` SDK paths + `BQ_BIN`/`GCLOUD_BIN`, `os.pathsep`, UTF-8 I/O + `PYTHONUTF8`/`PYTHONIOENCODING`/`CLOUDSDK_CORE_DISABLE_PROMPTS` for bq, `BQ_CLI_TIMEOUT` (120 s), `query_bigquery_result()` |
| 1-B | `90391ec` | `run_tool.py`: `--json-file`, `--json -`, `--arg k=v`, UTF-8 stdout/stderr; `.gitignore` += `.rca_tmp/` |
| 1-C | `790cc98` | NEW `tools/rca_report_tool.py`: canonical template, section parse/validate, query evidence JSONL, report render (metadata header + evidence appendix), on-disk registry |
| 1-D | `70fb6f3` | `tools/email_tool.py`: escaped HTML, summary table, inline RCA, `text/markdown` attachments from registry entries, RFC-encoded headers |
| 2-E | `b91f3fa` | `mcp_server.py`: `query_bigquery(incident_number)` evidence, `get_rca_template`, validated `save_rca_report`, registry-fed `send_rca_email`, `post_comment(confirmed)` gate, `TOOL_NAMES` (15) for JSON-RPC fallback |
| 2-F | `dad9aaf` | `.github/agents/rca_copilot.agent.md`, `.claude/skills/rca-copilot/SKILL.md`, `AGENTS.md`: cross-platform invocation, macOS/Windows setup, `get_rca_template`, new params, de-duplicated template; Copilot frontmatter += `read/readFile`, `edit/createFile`, `edit/editFiles` |
| fix | `a26a01f` | raw `run_tool.py` docstring (Windows example rendered as escapes in `--help`) |
| fix-G | `8cd407c` | `rca_report_tool`: str/CSV `incident_numbers`, tolerant headings (numbered/emoji/bold/plain/trailing text/NEED-DID variants), `RCA_SESSION_WINDOW_HOURS` evidence + pending window, registry lock, absolute paths, sanitised title |
| fix-H | `e255345` | `bigquery_tool`: Popen + process-tree kill on timeout (`taskkill /T /F` on Windows, `killpg` on POSIX), SQL as UTF-8 bytes (no CRLF translation), warn on bad overrides |
| fix-I | `64e6ea6` | `mcp_server`/`email_tool`/docs: `Attached incidents:` line, `mark_emailed` failure tolerated, subject CR/LF sanitised, `incident_numbers` guidance |

Root `CHANGELOG.md` created with the breaking changes (post_comment gate, save validation, email_tool API).

## Verification

**Automated (offline, Python 3.12 scratch venv with project requirements):**
`python -m unittest discover -s rca_copilot_agent/tests` → **119 tests, all pass** (test_rca_report_tool 42,
test_bq_crossplatform 29, test_dispatch_rca_flow 20, test_email_tool 14, test_run_tool 14). `py_compile` clean on
every module. `run_tool.py --help` renders (incl. Windows example). MCP `list_tools` builds 15 tools == `TOOL_NAMES`.

**Facts verified against the installed Cloud SDK source:** `bq query` with no positional query reads
`sys.stdin.read()` (`platform/bq/frontend/command_query.py:466-468`); `--headless` is a global flag (`bq_flags.py:250`).

**Orchestrator probes:** realistic CRLF/bold/numbered/emoji/plain heading variants validate with no errors;
string and comma-separated `incident_numbers` filters match; registry stores absolute paths; shortform warning
fires on `CDS L3 team` but not on canonical `APAC - CHN - SPACE Loyalty L3 Support`.

### Regression report
Two parallel reviewers (BQ/CLI surface; report/email/dispatch/docs surface) reviewed `8786862..a26a01f`:
0 blocking on BQ/CLI; 1 must-fix on report flow (string `incident_numbers` matched nothing) + 5 should-fix —
all fixed in `8cd407c`/`e255345`/`64e6ea6` and re-verified (suite 81 → 119).

- **Tested & passed:** bq argv never contains SQL; stdin bytes == UTF-8 SQL with `%"'<>|&^`, newlines, non-ASCII;
  Windows `.cmd` discovery (simulated `os.name="nt"` + env dirs); `os.pathsep`; timeout tree-kill paths; run_tool
  arg forms incl. BOM + stdin; template/validation/evidence/registry/supersede/lock; escaped email, attachments,
  non-ASCII headers; dispatch flow save → send → mark_emailed; post_comment preview makes no SNOW call.
- **Unchanged & confirmed:** BQ keyword blocklist, `validate_query`, `_pick_executor`, schema tools; `run_tool.py`
  startup sequence (config → BQ init → store preload → SNOW auth → gcloud auth → `_dispatch`); all other
  `_dispatch` branches (fetch/get/analyze/search/extract/download/schema); interactive `gcloud auth login`
  (no env override); `ticketasg_copilot_agent`, `mockdata_copilot_agent`, `rca_agent` untouched.
- **Ruled out / not testable here:**
  - Live Windows run — no Windows host; covered by mocks + SDK-source reading. Needs a user smoke test.
  - Live BigQuery on macOS — the local gcloud account is not @loreal.com, so a real query would trigger
    interactive login; not executed. Needs a user smoke test.
  - Copilot tool IDs `read/readFile`, `edit/createFile`, `edit/editFiles` not verified against the user's VS Code.

### Known limitations / deferred
- `--arg` turns any value exactly `true`/`false` into a boolean (documented).
- Same Windows issues still exist in the `ticketasg_copilot_agent` / `mockdata_copilot_agent` copies (separate claim).
- Repo-root `CLAUDE.md` "BigQuery Safety" still describes dry-run / `maximum_bytes_billed` and ADC — contradicts
  the user's no-cost-guard decision and the bq-CLI path; needs a user-approved edit (not changed silently).
- Step 1/2 gaps from quick-kayinleong-027 (per-call auth re-checks, attachment OCR, filename sanitising) untouched.
