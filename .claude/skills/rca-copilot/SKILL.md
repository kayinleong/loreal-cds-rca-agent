---
name: rca-copilot
description: >
  Root Cause Analysis agent for L'Oréal SPACE CDS ServiceNow incidents.
  Uses the Bash tool to call rca_copilot_agent/run_tool.py (CLI only).
  Works on macOS and Windows.
invocation: /rca-copilot
---

# RCA Copilot Skill — CLI Mode

Use this skill to investigate SPACE CDS incidents with `rca_copilot_agent`.
All tool calls are `Bash` invocations against `run_tool.py`.

## Prerequisites

1. One-time setup done (`./setup.sh` / `setup.cmd`; see "Setup" below). No venv activation needed
2. `.env` file present (see `.env.example`); `COOKIE` / `X_USERTOKEN` are refreshed automatically via Edge SSO at startup
3. gcloud user login with an @loreal.com account: `gcloud auth login` (BigQuery runs through the `bq` CLI; nothing else needed)
4. `schema.json` present in repo root

## Setup and platform notes (macOS / Windows)

- **Prerequisites:** Python 3.10+ (64-bit), Google Cloud SDK (`gcloud`, `bq`), Microsoft Edge, git.
- **One-command setup** (from the repo root, once per machine): macOS/Linux `./setup.sh`; Windows `setup.cmd` (double-click, or run in cmd/PowerShell); or the VS Code task "RCA: Setup (all agents)". It finds Python >= 3.10, creates `<repo>/.venv`, installs all three Copilot agents (per-agent: one failing does not block the others), then runs the doctor. Optional flags (passed through to `scripts/bootstrap.py`): `--agents`, `--skip-retrieval`, `--index-url`, `--proxy`, `--wheelhouse`, `--recreate`.
- **Self-check (offline):** macOS/Linux `python3 scripts/doctor.py`; Windows `py -3 scripts\doctor.py`; or the VS Code task "RCA: Doctor". Checks packages, gcloud/bq, Edge, gcloud account domain, `schema.json` and `.env` presence.
- **No venv activation needed:** `run_tool.py` re-runs itself inside `<repo>/.venv` automatically. Invoke it as `python rca_copilot_agent/run_tool.py …` (macOS: `python3`; Windows: `python` or `py -3`; forward slashes are fine on Windows).
- **Missing package:** if `run_tool.py` prints "Missing Python package … Run ./setup.sh … or setup.cmd" (or any `ModuleNotFoundError`), run the setup command for the platform, then retry the failed command once. If setup reports failures, show the doctor output to the user and stop.
- **Unknown tool name:** `run_tool.py` lists the valid tools.
- **Dependencies:** `rca_copilot_agent/requirements.txt` (requests, urllib3, python-dotenv, playwright; no `playwright install` — the installed Edge is used). Manual fallback inside the venv: `python -m pip install -r rca_copilot_agent/requirements.txt`.
- **Creating the args file:** prefer the `Write` tool. Terminal fallback —
  macOS/Linux: `mkdir -p .rca_tmp && cat > .rca_tmp/q.json <<'EOF'` … `EOF`;
  Windows PowerShell: `New-Item -ItemType Directory -Force .rca_tmp | Out-Null` then `Set-Content -Encoding utf8 -Path .rca_tmp\q.json -Value @'` … `'@` (single-quoted here-string is literal; the closing `'@` must start its own line).
- **BigQuery** runs through the `bq` CLI using gcloud user credentials: only `gcloud auth login` with an @loreal.com account is needed (checked automatically at startup; no ADC / `application-default login`). The Google Cloud SDK is auto-detected (PATH and standard install dirs, incl. Windows `%LOCALAPPDATA%\Google\Cloud SDK\…`); override with `BQ_BIN` / `GCLOUD_BIN`. Query timeout: `BQ_CLI_TIMEOUT` (default 120 s).
- Output is UTF-8 on all platforms.

## How to pass arguments (cross-platform)

- **Simple values — `--arg key=value`** (repeatable; `true`/`false` become booleans). Works in zsh/bash, PowerShell and cmd.
- **Free text — args file + `--json-file` (RECOMMENDED).** Use the `Write` tool to create `.rca_tmp/<tool>.json` (repo root, gitignored; UTF-8, BOM tolerated) containing a JSON object of the arguments, then run `python rca_copilot_agent/run_tool.py <tool> --json-file .rca_tmp/<tool>.json`. **Required** for `query_bigquery`, `save_rca_report`, `send_rca_email`, `post_comment`, `search_incidents`, `fetch_incidents` (URLs contain `&`, `%`).
- `--json -` reads JSON from stdin. **Do NOT use `--json '<JSON>'`** — POSIX-shell-only and breaks on apostrophes.

## Tool Invocation Reference (15 tools)

`RT` = `python rca_copilot_agent/run_tool.py`

| Task | Command |
|------|---------|
| List local incidents | `RT list_incidents` |
| Fetch from SNOW URL | args file `{"list_url": "<URL>", "download_attachments": false, "limit": 500}` → `RT fetch_incidents --json-file .rca_tmp/fetch_incidents.json` |
| Fetch single incident | `RT get_incident --arg incident_number=INCx` |
| Read local incident text | `RT get_incident_summary --arg incident_number=INCx` |
| **Full analysis (use this)** | `RT analyze_incident --arg incident_number=INCx` |
| Search local incidents | args file `{"keyword": "...", "section": "all"}` → `RT search_incidents --json-file .rca_tmp/search_incidents.json` |
| Extract identifiers | `RT extract_identifiers --arg incident_number=INCx` |
| Download attachments | `RT download_attachments --arg incident_number=INCx` |
| Post comment to SNOW (gated) | args file `{"incident_number": "INCx", "text": "...", "as_work_note": false}` → `RT post_comment --json-file .rca_tmp/post_comment.json` (preview first; add `"confirmed": true` only after user approval) |
| List BQ tables | `RT list_bq_tables` |
| Get table schema | `RT get_schema --arg table_name=purchase` |
| Query BigQuery | args file `{"sql": "SELECT ... LIMIT 10", "rationale": "...", "incident_number": "INCx"}` → `RT query_bigquery --json-file .rca_tmp/query_bigquery.json` |
| **Get RCA template** | `RT get_rca_template` (no args; once per session) |
| **Save RCA report (MANDATORY)** | args file `{"incident_number": "INCx", "report_text": "<full report>"}` → `RT save_rca_report --json-file .rca_tmp/save_rca_report.json` |
| **Send email (MANDATORY, once)** | args file `{"session_summary": "...", "subject": "RCA Complete — INCx"}` → `RT send_rca_email --json-file .rca_tmp/send_rca_email.json` (optional `incident_numbers` list) |

## RCA Workflow

Mandatory sequence: `analyze_incident` → `get_rca_template` (once per session) → `list_bq_tables` / `get_schema` / `query_bigquery` (with `incident_number`) → write RCA → `save_rca_report` (fix & retry on `✗`) → `send_rca_email` once.

### Step 0 — Detect intent

Read the user's message and classify:

| Signal | Intent |
|--------|--------|
| Contains a ServiceNow URL | FETCH then analyse |
| Contains a ticket number (`INC\d+`) | Analyse that specific ticket |
| "all", "all incidents", no ticket | Batch — analyse all local |
| "post comment", "post to" | Analyse + post back |

### Step 1 — Ensure incident data is available

**If prompt contains a ServiceNow URL:** write `.rca_tmp/fetch_incidents.json` = `{"list_url": "<URL>", "download_attachments": false, "limit": 500}`, then:
```bash
python rca_copilot_agent/run_tool.py fetch_incidents --json-file .rca_tmp/fetch_incidents.json
```

**If no URL — check what is already downloaded:**
```bash
python rca_copilot_agent/run_tool.py list_incidents
```
If output says no incidents found, ask user to provide a SNOW list-view URL.

### Step 2 — Analyse incidents

**Single-ticket mode:**

```bash
python rca_copilot_agent/run_tool.py analyze_incident --arg incident_number=<INCx>
```

This one call returns: full incident summary + extracted identifiers + attachment download status.
Do NOT call `get_incident_summary`, `extract_identifiers`, and `download_attachments` separately.

Read the result carefully: description, comments, work notes, attachment paths, identifiers found.

**Get the RCA template — once per session, before writing the first RCA:**
```bash
python rca_copilot_agent/run_tool.py get_rca_template
```

**If ANY identifiers found** (order IDs, customer codes, phone numbers, emails, EANs, LUCID):

```bash
# Discover which table to query (reads schema.json — instant, no BQ cost)
python rca_copilot_agent/run_tool.py list_bq_tables

# Get column names and query patterns for the target table
python rca_copilot_agent/run_tool.py get_schema --arg table_name=<table>

# Run the query (args file with sql incl. LIMIT, rationale, incident_number)
python rca_copilot_agent/run_tool.py query_bigquery --json-file .rca_tmp/query_bigquery.json
```

**ALWAYS pass `incident_number` in the `query_bigquery` args during an RCA.** The query (SQL, rationale, row count / error — never result rows) is recorded and appended to the saved report as "## Evidence — BigQuery queries run".

Refer to `rca_copilot_agent/AGENTS.md` for the identifier → table mapping and query rules.

**Write the RCA report** in the format returned by `get_rca_template` (see "RCA Report Format" below).

**Save the report — MANDATORY:** write `.rca_tmp/save_rca_report.json` = `{"incident_number": "<INCx>", "report_text": "<full report text>"}`, then:
```bash
python rca_copilot_agent/run_tool.py save_rca_report --json-file .rca_tmp/save_rca_report.json
```
`save_rca_report` validates the report. If it returns `✗ RCA report NOT saved …`, fix the missing/empty sections and call again. Warnings (shortform group names, placeholders, no `→ Checked` lines) don't block but should be fixed. The ticket metadata header and the BigQuery evidence appendix are added automatically — never write them yourself. `save_rca_report` accepts common heading variants, but still use the exact `###` headings from `get_rca_template`. Evidence for a report covers queries recorded since the incident's last emailed report, within `RCA_SESSION_WINDOW_HOURS` (default 24); re-saving before emailing keeps it.

**Send email — MANDATORY, once per session, after ALL reports are saved:** write `.rca_tmp/send_rca_email.json` = `{"session_summary": "<plain text: which incidents, key findings>", "subject": "RCA Complete — <INCx>"}`, then:
```bash
python rca_copilot_agent/run_tool.py send_rca_email --json-file .rca_tmp/send_rca_email.json
```
It attaches saved, not-yet-emailed reports (latest per incident). Pass `incident_numbers` = the incidents investigated in this session (args file `{"session_summary": "...", "subject": "...", "incident_numbers": ["INC1","INC2"]}`); without it, all saved-but-unsent reports from the last `RCA_SESSION_WINDOW_HOURS` hours (default 24) are attached. The result ends with `Attached incidents: ...` — check it matches what you investigated. Works across separate CLI calls.

Do NOT ask the user for verification before calling `send_rca_email`. The email IS the notification.

**Batch mode:** call `list_incidents` to get all tickets, then loop the single-ticket steps for each
open incident. Call `send_rca_email` once at the end with all incidents in the `session_summary`.

### Step 3 — Post comment (only when post-comment intent detected)

`post_comment` has a code-enforced gate: without `"confirmed": true` it returns a preview and posts nothing.

1. Call `post_comment` without `confirmed` for each incident to get the preview.
2. Show the RCA reports/previews to the user. Ask: "Ready to post the above RCA(s) as comments. Confirm?"
3. Only after explicit approval, call `post_comment` again with `"confirmed": true`.

Never post without confirmation. The `post_comment` tool writes live to ServiceNow.

## RCA Report Format (MANDATORY)

**Single source of truth: the `get_rca_template` tool** (defined in `rca_copilot_agent/tools/rca_report_tool.py`). It returns the exact template, writing rules and the full canonical assignment-group table — always use FULL canonical group names, never shortforms (`CDS L3`, `LOY`, `MARS team`, ...).

Skeleton reminder — four `###` sections, none empty:

```
### WHAT HAPPENED
### WHAT WE CHECKED        (→ Checked [source] — [finding] lines)
### WHAT WE FOUND
### WHAT WE NEED / DID
```

## Output Rules

- Output ONLY the RCA report block. Start directly with `### WHAT HAPPENED`.
- After the RCA, append exactly: `Report saved: <path>` then `Email sent.` (or the error).
- In batch mode, separate blocks with `---`, each followed by `Report saved: <path>`.
  After all blocks, append `Email sent.`. Nothing else.
- After posting a comment: `Posted comment to [INC number].` only. No other text.

## Analysis Rules

- Only use data from Bash tool outputs. Never invent facts, timestamps, or error messages.
- Quote directly from comments and work notes.
- Acknowledge gaps — if evidence is insufficient, say so explicitly.
- A failed BQ query (0 rows) is a finding, not a failure — interpret and explain it.
