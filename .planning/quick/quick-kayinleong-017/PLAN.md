# Plan: quick-kayinleong-017 — MCP Tools → Skills Conversion

**Goal:** Convert `rca_copilot_agent` from requiring a running MCP server to a skills-based
approach that L'Oréal's environment allows. Deliver:
1. A Python CLI (`run_tool.py`) that wraps every tool function — no server required
2. A Claude Code skill file (`.claude/skills/rca-copilot/SKILL.md`) for Claude Code users
3. An updated GitHub Copilot agent definition that uses VS Code built-in skills instead of MCP
4. An updated `AGENTS.md` documenting both the MCP path (for environments that allow it) and
   the new skills/CLI path

**The MCP server is preserved unchanged** — users who CAN use MCP keep the existing workflow.
This plan only adds the skills alternative.

---

## Wave 1 — Python CLI entry point

### Task 1.1 — Create `rca_copilot_agent/run_tool.py`

**Read first:**
- `rca_copilot_agent/mcp_server.py` — `_dispatch()` function and argument names per tool
- `rca_copilot_agent/config.py` — `load_config()`, `load_smtp_config()`
- `rca_copilot_agent/tools/bigquery_tool.py` — `is_enabled()`, `query_bigquery()`, `get_schema_from_file()`, `init_from_schema()`
- `rca_copilot_agent/tools/incident_store.py` — `load_store()`, `get_store()`
- `rca_copilot_agent/tools/email_tool.py` — `register_report()`, `send_rca_email()`

**Action:**

Create `rca_copilot_agent/run_tool.py` with the following structure and logic:

```python
#!/usr/bin/env python3
"""
run_tool.py — Unified CLI for rca_copilot_agent tools (no MCP server required).

Usage:
    python rca_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'

Examples:
    python rca_copilot_agent/run_tool.py list_incidents --json '{}'
    python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'
    python rca_copilot_agent/run_tool.py query_bigquery --json '{"sql": "SELECT 1", "rationale": "test"}'
    python rca_copilot_agent/run_tool.py get_schema --json '{"table_name": "purchase"}'
    python rca_copilot_agent/run_tool.py save_rca_report --json '{"incident_number": "INC123", "report_text": "..."}'
    python rca_copilot_agent/run_tool.py send_rca_email --json '{"session_summary": "Investigated INC123"}'

Tool names:
    fetch_incidents       Download all incidents from a SNOW list-view URL
    get_incident          Fetch a single incident from SNOW by number
    get_incident_summary  Read a locally cached incident's full text
    list_incidents        List all locally cached incidents
    analyze_incident      ONE-STOP: fetch + attachments + identifiers for one incident
    search_incidents      Keyword-search across all local incidents
    post_comment          Post a comment or work note to SNOW (confirm before calling)
    extract_identifiers   Extract order IDs / emails / EAN codes from an incident
    download_attachments  Download attachment files for an incident
    query_bigquery        Run a read-only SELECT query against SPACE CDS BigQuery
    get_schema            Get BQ table schema (from local schema.json)
    list_bq_tables        List all BQ tables with RCA purpose
    save_rca_report       Save a completed RCA report to disk
    send_rca_email        Send HTML email notification with attached reports
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root: `python rca_copilot_agent/run_tool.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def _get_reports_dir(cfg=None) -> str:
    if cfg is None:
        from config import load_config
        cfg = load_config()
    return os.environ.get("REPORTS_DIR") or cfg.reports_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an rca_copilot_agent tool without starting an MCP server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", help="Tool name (see list above)")
    parser.add_argument(
        "--json",
        metavar="ARGS",
        default="{}",
        help='JSON object of tool arguments, e.g. \'{"incident_number": "INC123"}\'',
    )
    args = parser.parse_args()

    try:
        arguments = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"Error: --json is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Inline import to avoid circular deps at module level
    from config import load_config
    cfg = load_config()
    reports_dir = _get_reports_dir(cfg)

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cfg.attachments_dir, exist_ok=True)

    # Initialize BigQuery schema (non-fatal)
    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except Exception as e:
        logger.warning(f"[BQ] Not available: {e}")

    # Pre-load incident store if _all_incidents.json exists
    combined = os.path.join(reports_dir, "_all_incidents.json")
    if os.path.exists(combined):
        from tools.incident_store import load_store
        load_store(combined)

    # Dispatch — reuse _dispatch from mcp_server to avoid duplicating logic
    # Import the dispatch function that already handles all routing
    from mcp_server import _dispatch

    try:
        result = asyncio.run(_dispatch(args.tool, arguments, reports_dir))
        print(result)
    except Exception as e:
        print(f"Tool error ({args.tool}): {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Key design choices:**
- Reuses `_dispatch()` from `mcp_server.py` — no logic duplication
- Requires `--json '{}'` even for tools with no required args (explicit, machine-readable)
- Errors to stderr, tool output to stdout — clean for piping and Claude's Bash tool
- Initializes BQ and incident store at startup same way the MCP server does

**Acceptance criteria:**
- `python rca_copilot_agent/run_tool.py --help` prints usage with tool list
- `python rca_copilot_agent/run_tool.py list_incidents --json '{}'` runs without error (returns "No incidents" if none loaded)
- `python rca_copilot_agent/run_tool.py get_schema --json '{"table_name": "purchase"}'` returns schema text
- `python rca_copilot_agent/run_tool.py list_bq_tables --json '{}'` lists BQ tables from schema.json
- File exists at `rca_copilot_agent/run_tool.py`

---

## Wave 2 — Claude Code skill

### Task 2.1 — Create `.claude/skills/rca-copilot/SKILL.md`

**Read first:**
- `rca_copilot_agent/AGENTS.md` — full workflow to replicate using Bash commands
- `.github/agents/rca_copilot.agent.md` — tool list and RCA workflow

**Action:**

Create directory `.claude/skills/rca-copilot/` and write `SKILL.md` with the content below.
The skill translates every `snow-mcp/<tool>` call into a `python rca_copilot_agent/run_tool.py <tool> --json '...'` Bash call.

Content structure for the SKILL.md:

```markdown
---
name: rca-copilot
description: >
  Root Cause Analysis agent for L'Oréal SPACE CDS ServiceNow incidents.
  Uses Bash tool to call rca_copilot_agent/run_tool.py — no MCP server required.
  Replaces snow-mcp/* MCP tool calls for environments where MCP is not allowed.
invocation: /rca-copilot
---

# RCA Copilot Skill — No-MCP Mode

Use this skill when the rca_copilot_agent MCP server is not available.
All tool calls become Bash invocations against `run_tool.py`.

## Prerequisites

1. Python virtual environment activated: `source .venv/bin/activate`
2. `.env` file present with `COOKIE` and `X_USERTOKEN` set
3. gcloud ADC configured: `gcloud auth application-default login`
4. schema.json present in repo root (run `make schema` or see CLAUDE.md)

## Tool Invocation Reference

| Former MCP call | Bash equivalent |
|----------------|----------------|
| `snow-mcp/list_incidents({})` | `python rca_copilot_agent/run_tool.py list_incidents --json '{}'` |
| `snow-mcp/analyze_incident({"incident_number": "INCx"})` | `python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INCx"}'` |
| `snow-mcp/fetch_incidents({"list_url": "..."})` | `python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "..."}'` |
| `snow-mcp/get_incident({"incident_number": "INCx"})` | `python rca_copilot_agent/run_tool.py get_incident --json '{"incident_number": "INCx"}'` |
| `snow-mcp/get_incident_summary({"incident_number": "INCx"})` | `python rca_copilot_agent/run_tool.py get_incident_summary --json '{"incident_number": "INCx"}'` |
| `snow-mcp/search_incidents({"keyword": "..."})` | `python rca_copilot_agent/run_tool.py search_incidents --json '{"keyword": "...", "section": "all"}'` |
| `snow-mcp/extract_identifiers({"incident_number": "INCx"})` | `python rca_copilot_agent/run_tool.py extract_identifiers --json '{"incident_number": "INCx"}'` |
| `snow-mcp/download_attachments({"incident_number": "INCx"})` | `python rca_copilot_agent/run_tool.py download_attachments --json '{"incident_number": "INCx"}'` |
| `snow-mcp/post_comment({"incident_number": "INCx", "text": "..."})` | `python rca_copilot_agent/run_tool.py post_comment --json '{"incident_number": "INCx", "text": "...", "as_work_note": false}'` |
| `snow-mcp/list_bq_tables({})` | `python rca_copilot_agent/run_tool.py list_bq_tables --json '{}'` |
| `snow-mcp/get_schema({"table_name": "purchase"})` | `python rca_copilot_agent/run_tool.py get_schema --json '{"table_name": "purchase"}'` |
| `snow-mcp/query_bigquery({"sql": "...", "rationale": "..."})` | `python rca_copilot_agent/run_tool.py query_bigquery --json '{"sql": "...", "rationale": "..."}'` |
| `snow-mcp/save_rca_report({"incident_number": "...", "report_text": "..."})` | `python rca_copilot_agent/run_tool.py save_rca_report --json '{"incident_number": "...", "report_text": "..."}'` |
| `snow-mcp/send_rca_email({"session_summary": "..."})` | `python rca_copilot_agent/run_tool.py send_rca_email --json '{"session_summary": "...", "subject": "RCA Complete"}'` |

## Workflow (No-MCP)

### Step 0 — Detect intent from the user's prompt
Same as AGENTS.md: classify the prompt as FETCH, single-ticket, batch, or post-comment.

### Step 1 — Ensure incident data is available

**If prompt contains a ServiceNow URL:**
```bash
python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "<URL>", "download_attachments": false, "limit": 500}'
```

**If no URL:**
```bash
python rca_copilot_agent/run_tool.py list_incidents --json '{}'
```
If output says "No incidents", tell user to provide a list-view URL.

### Step 2 — Analyse incidents

**Single-ticket:**
```bash
python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "<INCx>"}'
```
This returns: full summary + extracted identifiers + attachment download status.

**If identifiers found, query BigQuery:**
```bash
python rca_copilot_agent/run_tool.py list_bq_tables --json '{}'
python rca_copilot_agent/run_tool.py get_schema --json '{"table_name": "<table>"}'
python rca_copilot_agent/run_tool.py query_bigquery --json '{"sql": "<SQL with LIMIT>", "rationale": "<why>"}'
```

**Save report (MANDATORY after each incident):**
```bash
python rca_copilot_agent/run_tool.py save_rca_report --json '{"incident_number": "<INCx>", "report_text": "<full report text>"}'
```

**Send email (MANDATORY once, after all reports saved):**
```bash
python rca_copilot_agent/run_tool.py send_rca_email --json '{"session_summary": "<plain text summary>", "subject": "RCA Complete — <INCx>"}'
```

**Batch mode:** Same pattern but loop over each incident from `list_incidents` output.

### Step 3 — Post comment (only when user expressed post-comment intent)
Show the RCA first. Ask for confirmation. Then:
```bash
python rca_copilot_agent/run_tool.py post_comment --json '{"incident_number": "<INCx>", "text": "<RCA text>", "as_work_note": false}'
```

## RCA Report Format (unchanged)

(Same format as AGENTS.md — WHAT HAPPENED / WHAT WE CHECKED / WHAT WE FOUND / WHAT WE NEED / DID)

## Rules (unchanged from AGENTS.md)

- Never write Python scripts or shell commands beyond the Bash calls above
- Never invent facts, timestamps, or error messages
- Never post comments without user confirmation
- Never skip save_rca_report
- Never ask user for verification before send_rca_email — the email IS the notification
```

**Acceptance criteria:**
- File exists at `.claude/skills/rca-copilot/SKILL.md`
- File has valid YAML frontmatter with `name`, `description`, `invocation` fields
- Tool invocation table lists all 14 tools with correct `run_tool.py` syntax
- Workflow section mirrors AGENTS.md steps but with Bash commands

---

## Wave 3 — Update GitHub Copilot agent definition

### Task 3.1 — Rewrite `.github/agents/rca_copilot.agent.md`

**Read first:**
- `.github/agents/rca_copilot.agent.md` — current frontmatter and body

**Action:**

Replace the frontmatter to remove `tools:` (MCP list) and `mcp-servers:` entirely.
Add VS Code built-in skills that Copilot can use to run terminal commands.
Update the "ABSOLUTE TOOL RESTRICTION" section to reference CLI commands.

**New frontmatter** (replace the existing `---...---` block at top of file):

```yaml
---
name: RCA Copilot Agent
description: >
  Root Cause Analysis agent for L'Oréal SPACE CDS ServiceNow incidents.
  Downloads incident data from ServiceNow, queries BigQuery for order/pipeline data,
  analyses comments and attachments, and generates structured RCA reports.
  Can post findings back as comments.
  Uses run_tool.py CLI — no MCP server required.
tools:
  - run_in_terminal
  - read_file
---
```

**Updated "ABSOLUTE TOOL RESTRICTION" section** (replace the existing block):

```markdown
## ABSOLUTE TOOL RESTRICTION (READ THIS FIRST)

You MUST use `run_in_terminal` to call `rca_copilot_agent/run_tool.py` for all data operations.
The command pattern is:

```
python rca_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'
```

**Mandatory sequence — no exceptions:**

1. Call `analyze_incident` (not `get_incident_summary`) for any single ticket:
   `python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INCx"}'`
2. Write the RCA report.
3. Call `save_rca_report` BEFORE outputting the RCA. If you skip this call, you have failed.
   `python rca_copilot_agent/run_tool.py save_rca_report --json '{"incident_number": "INCx", "report_text": "..."}'`
4. After ALL `save_rca_report` calls for the session, call `send_rca_email` ONCE:
   `python rca_copilot_agent/run_tool.py send_rca_email --json '{"session_summary": "...", "subject": "..."}'`

**Tool name → CLI mapping:**

| Task | Command |
|------|---------|
| List local incidents | `run_tool.py list_incidents --json '{}'` |
| Fetch from SNOW URL | `run_tool.py fetch_incidents --json '{"list_url": "..."}'` |
| Fetch single incident | `run_tool.py get_incident --json '{"incident_number": "INCx"}'` |
| Full analysis (use this) | `run_tool.py analyze_incident --json '{"incident_number": "INCx"}'` |
| Search local incidents | `run_tool.py search_incidents --json '{"keyword": "..."}'` |
| Extract identifiers | `run_tool.py extract_identifiers --json '{"incident_number": "INCx"}'` |
| Download attachments | `run_tool.py download_attachments --json '{"incident_number": "INCx"}'` |
| Post comment | `run_tool.py post_comment --json '{"incident_number": "INCx", "text": "..."}'` |
| List BQ tables | `run_tool.py list_bq_tables --json '{}'` |
| Get table schema | `run_tool.py get_schema --json '{"table_name": "purchase"}'` |
| Query BigQuery | `run_tool.py query_bigquery --json '{"sql": "SELECT...", "rationale": "..."}'` |
| Save RCA report | `run_tool.py save_rca_report --json '{"incident_number": "INCx", "report_text": "..."}'` |
| Send email | `run_tool.py send_rca_email --json '{"session_summary": "...", "subject": "..."}'` |

You MUST NOT use:
- Direct Python/pip/bash invocations beyond the `run_tool.py` pattern above
- `read_file` for anything other than reading saved RCA reports
- Any tool not in the `tools:` frontmatter
```

All remaining sections of the file (Core Workflow, BigQuery usage guidelines, RCA Report Format,
Tool Use Rules, Output Rules, Analysis Rules) stay **unchanged** — only MCP tool call syntax
changes to `run_tool.py` invocations.

**Search the body for every `snow-mcp/` reference** and replace with the equivalent
`python rca_copilot_agent/run_tool.py <tool>` syntax following the mapping table above.
There should be no `snow-mcp/` strings remaining after this replacement.

**Acceptance criteria:**
- `grep 'snow-mcp/' .github/agents/rca_copilot.agent.md` returns no output
- `grep 'mcp-servers:' .github/agents/rca_copilot.agent.md` returns no output
- Frontmatter contains `tools: [run_in_terminal, read_file]`
- Frontmatter does NOT contain `mcp-servers:` key
- File still contains RCA report format section with WHAT HAPPENED / WHAT WE CHECKED / WHAT WE FOUND / WHAT WE NEED
- All `run_tool.py` commands in the body use correct tool names from the 14-tool list

---

## Wave 4 — Update AGENTS.md documentation

### Task 4.1 — Update `rca_copilot_agent/AGENTS.md`

**Read first:**
- `rca_copilot_agent/AGENTS.md` — current structure (Tool Inventory, Environment Setup, Investigation Workflow, Report Template, BigQuery sections)

**Action:**

Insert a new section **immediately after the `## Environment Setup` section** and **before the `## Investigation Workflow` section**:

```markdown
## Running Without MCP (Skills / CLI Mode)

L'Oréal's environment does not allow MCP servers. Use `run_tool.py` instead:

```bash
# One-stop analysis for a single incident
python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'

# List locally cached incidents
python rca_copilot_agent/run_tool.py list_incidents --json '{}'

# Fetch all incidents from a SNOW list URL
python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "https://loreal.service-now.com/..."}'

# Run a BigQuery query
python rca_copilot_agent/run_tool.py query_bigquery \
    --json '{"sql": "SELECT * FROM `oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public.purchase` WHERE sourceordernumber = \"ORD123\" LIMIT 5", "rationale": "Look up order status"}'

# Save an RCA report to disk
python rca_copilot_agent/run_tool.py save_rca_report \
    --json '{"incident_number": "INC10403788", "report_text": "### WHAT HAPPENED\n..."}'

# Send email notification
python rca_copilot_agent/run_tool.py send_rca_email \
    --json '{"session_summary": "Investigated INC10403788 — root cause: missing MARSID", "subject": "RCA Complete — INC10403788"}'
```

**For Claude Code users:** invoke the `/rca-copilot` skill which orchestrates the full workflow
using these CLI commands automatically. See `.claude/skills/rca-copilot/SKILL.md`.

**For GitHub Copilot users:** the `.github/agents/rca_copilot.agent.md` agent definition no
longer requires an MCP server — it uses `run_in_terminal` to call `run_tool.py` directly.

**All 14 tool names** (valid for `--json` calls):

| Tool | Description |
|------|-------------|
| `list_incidents` | List locally cached incidents |
| `fetch_incidents` | Download from SNOW list URL |
| `get_incident` | Fetch single incident from SNOW by number |
| `get_incident_summary` | Read locally cached incident text |
| `analyze_incident` | ONE-STOP: fetch + attachments + identifiers |
| `search_incidents` | Keyword-search local incidents |
| `extract_identifiers` | Pull order IDs / emails / EANs from an incident |
| `download_attachments` | Download attachment files for an incident |
| `post_comment` | Post comment / work note to SNOW |
| `list_bq_tables` | List all BQ tables with RCA purpose |
| `get_schema` | Get column names and query patterns for a table |
| `query_bigquery` | Run a read-only SELECT query |
| `save_rca_report` | **MANDATORY** — save completed RCA to disk |
| `send_rca_email` | **MANDATORY** — notify reviewer when session done |
```

Also update the `auto_credential_refresh` and `auto_gcloud_auth` rows in the **Tool Inventory** table — add a note "(also runs at CLI startup via run_tool.py)" so users know startup checks still run.

**Acceptance criteria:**
- `rca_copilot_agent/AGENTS.md` contains `## Running Without MCP (Skills / CLI Mode)` section header
- Section shows `run_tool.py` examples for analyze_incident, list_incidents, fetch_incidents, query_bigquery, save_rca_report, send_rca_email
- Section mentions `/rca-copilot` skill for Claude Code users
- Tool inventory table still has all 14 tools listed
- File still has all existing BigQuery sections intact

---

## Acceptance Criteria (Phase-level)

- [ ] `rca_copilot_agent/run_tool.py` created — dispatches all 14 tools via `_dispatch()`
- [ ] `python rca_copilot_agent/run_tool.py --help` shows usage
- [ ] `python rca_copilot_agent/run_tool.py list_bq_tables --json '{}'` returns BQ table list
- [ ] `.claude/skills/rca-copilot/SKILL.md` created — full workflow with CLI commands
- [ ] `.github/agents/rca_copilot.agent.md` has no `snow-mcp/` or `mcp-servers:` references
- [ ] `rca_copilot_agent/AGENTS.md` has "Running Without MCP" section
- [ ] `mcp_server.py` is unchanged (backward compat)
- [ ] No new secrets or credentials introduced

## Regression Report

(to be filled after execution)

### What was tested
### What passed
### What was ruled out and why
