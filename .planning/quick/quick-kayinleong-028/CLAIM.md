# Claim: quick-kayinleong-028
- owner: kayinleong
- session: claude-code
- branch: feature/quick-kayinleong-028-easy-install (stacked on feature/phase-kayinleong-03-rca-copilot-xplat / PR #3)
- started: 2026-10-12
- status: done
- summary: One-command setup (macOS + Windows) that installs all 3 Copilot agents (rca_copilot, ticketasg, mockdata) with no missing libraries; clean requirements.txt; delete legacy rca_agent/; remove MCP-server mode from rca_copilot_agent (CLI-only); rewrite repo CLAUDE.md. Scope approved by user 2026-10-12.

## What will change

Research first (dependency audit per agent package + install-approach research), then:
- Minimal, complete dependency set for `rca_copilot_agent` (per-agent requirements file).
- Root `requirements.txt` cleaned to direct dependencies actually used (nothing other agents need is dropped).
- One-command setup for macOS and Windows + a dependency self-check so nothing is silently missing.
- Docs updated (Copilot agent, Claude skill, AGENTS.md for all 3 agents).
- User-approved deletions: `rca_agent/` (legacy standalone agent), `rca_copilot_agent/mcp_server.py` (dispatch moves to a plain module), `.vscode/mcp.json` (only registered that MCP server).
- User-approved rewrite of repo-root `CLAUDE.md` for the 3 Copilot agents.

## What has changed

Research: `research-deps.md` (per-agent dependency audit), `research-install.md` (install approach). Plan: `PLAN.md`.
Per-task detail: `SUMMARY-J/K/N/P/L1/L2/L3/Q/R.md`.

| Commit | Change |
|---|---|
| `1c99986` | Deleted `rca_agent/` (20 files), `.vscode/mcp.json`, `.vscode/settings.json` — user-approved |
| `a7af225` | rca_copilot CLI-only: `_dispatch` → `dispatcher.py` (+`TOOL_HELP`), `mcp_server.py` removed; `run_tool.py` unknown-tool early exit, auto re-exec into `<repo>/.venv`, missing-package hint; `ensure_gcloud_auth` no longer runs ADC checks/login |
| `30230b5` | 54-line pip-freeze `requirements.txt` → per-agent direct deps (rca_copilot/ticketasg: requests, urllib3, python-dotenv, playwright; ticketasg retrieval: sentence-transformers, numpy; mockdata: openpyxl; opt-in `requirements-mcp.txt` mcp<2); root `-r` includes; `scripts/tests/test_requirements_coverage.py` |
| `6fcce9c` | `setup.sh` / `setup.cmd` → `scripts/bootstrap.py` (per-agent install, binary wheels, proxy/index/wheelhouse flags), `scripts/doctor.py` (offline check), `scripts/_reqs.py`, `.vscode/tasks.json` |
| `ed7ae9d` | Same auto-venv re-exec + hint for ticketasg/mockdata `run_tool.py` |
| `847dc11`, `11ee933` | Agent/skill/AGENTS docs for all 3 agents: one-command setup, doctor, no activation |
| `6b67723` | Repo `CLAUDE.md` rewritten (user-approved), new root `README.md`, CHANGELOG entry |
| `a627c90` | `schema.json` `auth` hint: `gcloud auth login`, not ADC (was shown to the LLM by `list_bq_tables`) |
| `f066401` | run_tool re-exec: clear error for an unusable `.venv`, Ctrl-C → 130, signal rc mapping, real re-exec tests |
| `f435db2` | Setup hardening: `setup.cmd` without delayed expansion, pause only on Explorer double-click (never under VS Code/Copilot, Windows Terminal, Claude Code, CI); `.gitattributes` CRLF/LF; pip `--no-input`, stdin DEVNULL, `--retries 3 --timeout 30`, early stop on network failure, precise hints; xcode-select-stub guard; Windows long-path warning |

Net: 65 files, +3,482 / −6,404 lines (excl. `.planning`).

## Verification

**Real end-to-end on macOS (fresh `git archive HEAD` copy, real PyPI, Python 3.12, arm64):** `./setup.sh` →
all 3 agents `OK` in ~2 min (torch 2.14.1, sentence-transformers 5.7.0, playwright 1.63.0, …, all binary wheels);
doctor `0 failure(s), 2 warning(s)` (expected: local gcloud account is @accenture.com; no `.env` yet). Re-run is
idempotent (~3 s). From system Python 3.9 (`/usr/bin/python3`) `doctor.py` and `run_tool.py` re-exec into the venv.
Every tool module of all 3 agents imports in the fresh venv; heavy deps (torch, sentence_transformers, openpyxl,
playwright) import.

**Automated (offline):** `scripts/tests` 52 OK · `rca_copilot_agent/tests` 138 OK · `ticketasg_copilot_agent/tests` 14 OK ·
`mockdata_copilot_agent/tests` 14 OK — on a bare Python 3.12 and inside the fresh venv. `sh -n setup.sh` clean;
`setup.cmd` ASCII + CRLF (also after `git archive`). Requirements resolve to binary wheels for macOS arm64 and
`win_amd64` / Python 3.12 (`pip install --dry-run --only-binary=:all: --platform win_amd64`).

### Regression report
Two parallel reviewers (setup scripts/doctor/requirements; dispatcher move/re-exec/ADC removal):
- Dispatcher move: `_dispatch` branch bodies byte-identical to the old `mcp_server.py` (only `[MCP]`→`[RCA]` log
  prefix); no caller of the deleted file remains. Re-exec has no loop path; symlinked venv python detected.
- Setup: 3 must-fix (Explorer window closing, `!` mangling, pip credential-prompt hang) + `.gitattributes` + 8
  should-fix — all fixed in `f435db2`/`f066401`. Orchestrator additionally caught that the Explorer pause would
  also fire under PowerShell/VS Code terminals (Copilot would hang) and gated it on terminal/automation env vars.
- **Unchanged & confirmed:** every `_dispatch` behaviour; BigQuery path (bq CLI on `gcloud auth login`; blocklist,
  row cap, timeout); SNOW auth flow; ticketasg/mockdata tools and their MCP servers; RCA template/report/email flow.
- **Not verifiable here:** a live Windows run of `setup.cmd` / bootstrap (no Windows host — static checks + review
  only); live SNOW/BigQuery calls (local gcloud account is not @loreal.com); behaviour behind a real corporate
  proxy / SSL inspection (hints only).

### Known limitations / deferred
- `--arg` value `true`/`false` → boolean (documented). Doctor ignores PEP 508 markers (none used today).
- `requests` uses certifi, not the OS store: behind SSL inspection SNOW calls need `REQUESTS_CA_BUNDLE`
  (doctor + README hint; no runtime truststore injection).
- ticketasg/mockdata keep their own `bigquery_tool`/`gcloud_tool` copies without the phase-03 Windows fixes and
  still run the ADC check (separate follow-up already proposed).
