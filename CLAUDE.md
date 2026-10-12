# CLAUDE.md — space-cds-etl-core

Extends `~/.claude/CLAUDE.md` (global rules). Read that first. This file adds project-specific context only.

---

## Project Overview

Three LLM-agnostic Copilot agents for L'Oréal SPACE CDS. The LLM lives in the client; this repo ships only instructions and pure-function tools.

| Package | Purpose |
|---------|---------|
| `rca_copilot_agent/` | Root-cause analysis of ServiceNow (SNOW) incidents, validated with BigQuery; writes RCA reports and emails them |
| `ticketasg_copilot_agent/` | Assignment-group recommendation for SNOW tickets (rules + optional kNN retrieval) |
| `mockdata_copilot_agent/` | Mock INSERT SQL for DV (dev/test) data |

Each agent is driven by GitHub Copilot (`.github/agents/*.agent.md`) or Claude Code (`.claude/skills/*/SKILL.md`), which call tools through `<pkg>/run_tool.py`. `rca_copilot_agent` is CLI-only (`dispatcher.py`, no MCP server). `ticketasg_copilot_agent` and `mockdata_copilot_agent` still ship optional MCP servers (`mcp_server.py`; install via `requirements-mcp.txt`, `mcp<2`).

**No LLM calls in tool code or MCP servers — ever.** Tools are pure functions.

---

## Stack

- **Python 3.10+, 64-bit** (3.12 recommended). One shared `.venv/` at the repo root.
- **Dependencies** — per-agent `requirements.txt` (direct deps only, major-bounded ranges, no `==`); root `requirements.txt` just `-r`-includes them. `ticketasg_copilot_agent/requirements-retrieval.txt` (sentence-transformers/torch) is optional (`--skip-retrieval`). `requirements-mcp.txt` is opt-in (`--with-mcp`).
- **BigQuery** — via the `bq` CLI on gcloud **user credentials** (`gcloud auth login` with an @loreal.com account). Not ADC, not the Python BigQuery client.
- **ServiceNow** — REST; cookie + `X-UserToken` auto-captured via Playwright driving the installed Microsoft Edge (`COOKIE` / `X_USERTOKEN` in `.env` still work as override).
- **SMTP** — HTML email on RCA completion.
- **`schema.json`** — repo root; keys `project`, `dataset`, `tables` (33 tables in the primary dataset), `all_datasets` (6), `additional_datasets` (4), `key_identifiers`, `common_rca_patterns`. Loaded by the tools — no live BQ calls for schema discovery. It is hand-curated; regeneration is a deliberate, separate action (see What Not To Do). Note its `auth` text still mentions ADC — stale, do not follow it.

---

## Directory Map

```
rca_copilot_agent/        RCA agent: run_tool.py (CLI entry), dispatcher.py (TOOL_NAMES/TOOL_HELP/_dispatch),
                          config.py, AGENTS.md, requirements.txt, tests/
  tools/                  auth_tool, bigquery_tool, email_tool, gcloud_tool, incident_store,
                          rca_report_tool (RCA template — single source of truth), snow_reader
ticketasg_copilot_agent/  Assignment agent: run_tool.py, mcp_server.py (optional), config.py, AGENTS.md,
                          assignment_rules.json, retrieval_index.npz, requirements*.txt
  tools/                  assignment_tool, auth_tool, bigquery_tool, email_tool, gcloud_tool,
                          incident_store, retrieval_tool, snow_reader
mockdata_copilot_agent/   Mock-data agent: run_tool.py, mcp_server.py (optional), config.py, AGENTS.md,
                          requirements.txt, .docs/
  tools/                  bigquery_tool, gcloud_tool, mockdata_tool
.github/agents/*.agent.md Copilot agent definitions (frontmatter name:)
.claude/skills/*/SKILL.md Claude Code skills (rca-copilot, ticketasg-copilot, mockdata-copilot)
.vscode/tasks.json        "RCA: Setup (all agents)", "RCA: Doctor"
scripts/                  bootstrap.py (venv + installs), doctor.py (offline env check), _reqs.py, tests/
setup.sh / setup.cmd      One-command setup (macOS/Linux / Windows) -> scripts/bootstrap.py
requirements*.txt         Root aggregate + opt-in MCP
schema.json               BQ schema reference
.env.example              Template, safe to commit (never read/commit .env)
my_reports/ attachments/ rca_reports/ mockdata/ .rca_tmp/   Generated/scratch output (gitignored)
```

---

## Setup

```bash
./setup.sh          # macOS/Linux      (Windows: setup.cmd)
gcloud auth login   # @loreal.com — needed for BigQuery
python3 scripts/doctor.py   # offline check; --json for machine output
```

Flags are forwarded to `scripts/bootstrap.py` (`--agents`, `--skip-retrieval`, `--with-mcp`, `--index-url`, `--wheelhouse`, `--proxy`, `--recreate`, `--no-doctor`; see `--help`). **No venv activation needed** — each `run_tool.py` re-execs itself inside `<repo>/.venv`. Copy `.env.example` to `.env` only for SMTP and optional overrides.

Run a tool (cross-platform): `python3 rca_copilot_agent/run_tool.py <tool> --json-file <path>` (or `--arg key=value`, `--json -`). Windows: `python` / `py -3`.

---

## Project-Specific Secrets & PII Rules

On top of global hygiene rules:

- **`COOKIE` and `X_USERTOKEN`** are live ServiceNow session tokens. Never log, echo, or commit them.
- **`my_reports/`, `attachments/`, `rca_reports/`, `mockdata/`, `.rca_tmp/`** are gitignored; they may hold real PII (consumer names, emails, order IDs). Never stage them. Check `.gitignore` before every `git add`.
- **`.rca_tmp/` args files** (`--json-file` scratch) may contain ticket text.
- **Evidence logs** in RCA reports store SQL text (never result rows); SQL may contain identifiers from tickets — treat reports as sensitive.
- `schema.json` holds table/column names only — safe to commit.
- A `*-credentials.json` or `firebase-adminsdk-*.json` appearing means something is wrong (auth is user-level gcloud) — stop and alert the user.

---

## BigQuery Rules

`rca_copilot_agent/tools/bigquery_tool.py` enforces (the other packages have their own `bigquery_tool.py`; keep them equivalent):

- **Read-only**: keyword blocklist (INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/MERGE/…) plus a SELECT/WITH-only check.
- **Row cap** (`bq --max_rows`) and **timeout** (`BQ_CLI_TIMEOUT`, default 120 s, process tree killed on expiry).
- **No dry-run and no `maximum_bytes_billed` cap — by user decision (2026-10-12).** Do not re-add a cost guard unasked.
- **SQL goes to `bq` on stdin** (Windows-safe). Do not put SQL in argv.
- Do not weaken the blocklist. Do not interpolate untrusted strings into SQL.
- Avoid hardcoding project/dataset IDs outside config / `schema.json`.

---

## Conventions

### Adding a tool

1. Create `<pkg>/tools/<name>_tool.py` — pure functions, no LLM calls.
2. Register it: for `rca_copilot_agent`, in `dispatcher.py` (`TOOL_NAMES`, `TOOL_HELP`, a branch in `_dispatch`); for ticketasg/mockdata, in that package's `mcp_server.py` dispatch (and `run_tool.py` if needed).
3. Declare any new third-party import in that package's `requirements.txt` — `scripts/tests/test_requirements_coverage.py` enforces this.
4. Add tunables to the package `config.py` with env-var override; update the package `AGENTS.md` (and the agent/skill files if the workflow changes).
5. Add tests.

### Tests (stdlib `unittest`, offline — no network, no real BQ/SNOW)

```bash
python3.12 -m unittest discover -s scripts/tests
(cd rca_copilot_agent && python3.12 -m unittest discover -s tests)
```

### RCA template

`rca_copilot_agent/tools/rca_report_tool.py` is the single source of truth for the template, rules and assignment-group table. Edit it there; instruction files should point to `get_rca_template`, not copy it.

### Cross-platform

UTF-8 for all file/console I/O; `os.pathsep` not `:`; no shell-quoted JSON in docs — use `--json-file` / `--arg`; Windows SDK shims (`bq.cmd`, `gcloud.cmd`) via `BQ_BIN` / `GCLOUD_BIN`.

---

## What Not To Do

- Do not add LLM API calls to any `tools/*.py`, `dispatcher.py` or `mcp_server.py`.
- Do not reintroduce an MCP server or `.vscode/mcp.json` for `rca_copilot_agent`, or the removed standalone `rca_agent` package.
- Do not weaken the BigQuery blocklist, put SQL in argv, or silently add a dry-run/bytes cap.
- Do not pin `==` or paste `pip freeze` output into requirements files.
- Do not commit generated output dirs, `.env`, credentials, or tokens.
- Do not add ADC / service-account key flows — auth is `gcloud auth login`.
- Do not stage `schema.json` alongside code changes — regenerating it is a separate, deliberate action.
