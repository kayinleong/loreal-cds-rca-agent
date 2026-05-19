---
name: rca-copilot
description: >
  Root Cause Analysis agent for L'Oréal SPACE CDS ServiceNow incidents.
  Uses Bash tool to call rca_copilot_agent/run_tool.py — no MCP server required.
  Replaces snow-mcp/* MCP tool calls for environments where MCP is not allowed.
invocation: /rca-copilot
---

# RCA Copilot Skill — No-MCP Mode

Use this skill when the `rca_copilot_agent` MCP server is not available (e.g. L'Oréal's environment).
All tool calls become `Bash` invocations against `run_tool.py`.

## Prerequisites

1. Python virtual environment activated: `source .venv/bin/activate`
2. `.env` file present with `COOKIE` and `X_USERTOKEN` set (see `.env.example`)
3. gcloud ADC configured: `gcloud auth application-default login`
4. `schema.json` present in repo root

## Tool Invocation Reference

Every former `snow-mcp/<tool>` MCP call maps to a `run_tool.py` Bash call:

| Task | Bash command |
|------|-------------|
| List local incidents | `python rca_copilot_agent/run_tool.py list_incidents --json '{}'` |
| Fetch from SNOW URL | `python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "..."}'` |
| Fetch single incident | `python rca_copilot_agent/run_tool.py get_incident --json '{"incident_number": "INCx"}'` |
| Read local incident text | `python rca_copilot_agent/run_tool.py get_incident_summary --json '{"incident_number": "INCx"}'` |
| **Full analysis (use this)** | `python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INCx"}'` |
| Search local incidents | `python rca_copilot_agent/run_tool.py search_incidents --json '{"keyword": "...", "section": "all"}'` |
| Extract identifiers | `python rca_copilot_agent/run_tool.py extract_identifiers --json '{"incident_number": "INCx"}'` |
| Download attachments | `python rca_copilot_agent/run_tool.py download_attachments --json '{"incident_number": "INCx"}'` |
| Post comment to SNOW | `python rca_copilot_agent/run_tool.py post_comment --json '{"incident_number": "INCx", "text": "...", "as_work_note": false}'` |
| List BQ tables | `python rca_copilot_agent/run_tool.py list_bq_tables --json '{}'` |
| Get table schema | `python rca_copilot_agent/run_tool.py get_schema --json '{"table_name": "purchase"}'` |
| Query BigQuery | `python rca_copilot_agent/run_tool.py query_bigquery --json '{"sql": "SELECT ... LIMIT 10", "rationale": "..."}'` |
| **Save RCA report (MANDATORY)** | `python rca_copilot_agent/run_tool.py save_rca_report --json '{"incident_number": "INCx", "report_text": "..."}'` |
| **Send email (MANDATORY, once)** | `python rca_copilot_agent/run_tool.py send_rca_email --json '{"session_summary": "...", "subject": "RCA Complete — INCx"}'` |

## RCA Workflow (No-MCP)

### Step 0 — Detect intent

Read the user's message and classify:

| Signal | Intent |
|--------|--------|
| Contains a ServiceNow URL | FETCH then analyse |
| Contains a ticket number (`INC\d+`) | Analyse that specific ticket |
| "all", "all incidents", no ticket | Batch — analyse all local |
| "post comment", "post to" | Analyse + post back |

### Step 1 — Ensure incident data is available

**If prompt contains a ServiceNow URL:**
```bash
python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "<URL>", "download_attachments": false, "limit": 500}'
```

**If no URL — check what is already downloaded:**
```bash
python rca_copilot_agent/run_tool.py list_incidents --json '{}'
```
If output says no incidents found, ask user to provide a SNOW list-view URL.

### Step 2 — Analyse incidents

**Single-ticket mode:**

```bash
python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "<INCx>"}'
```

This one call returns: full incident summary + extracted identifiers + attachment download status.
Do NOT call `get_incident_summary`, `extract_identifiers`, and `download_attachments` separately.

Read the result carefully: description, comments, work notes, attachment paths, identifiers found.

**If ANY identifiers found** (order IDs, customer codes, phone numbers, emails, EANs, LUCID):

```bash
# Discover which table to query (reads schema.json — instant, no BQ cost)
python rca_copilot_agent/run_tool.py list_bq_tables --json '{}'

# Get column names and query patterns for the target table
python rca_copilot_agent/run_tool.py get_schema --json '{"table_name": "<table>"}'

# Run the query — always include LIMIT
python rca_copilot_agent/run_tool.py query_bigquery --json '{"sql": "<SQL with LIMIT>", "rationale": "<why>"}'
```

Refer to `rca_copilot_agent/AGENTS.md` for the identifier → table mapping and query rules.

**Write the RCA report** (format: WHAT HAPPENED / WHAT WE CHECKED / WHAT WE FOUND / WHAT WE NEED).

**Save the report — MANDATORY:**
```bash
python rca_copilot_agent/run_tool.py save_rca_report --json '{"incident_number": "<INCx>", "report_text": "<full report text>"}'
```

**Send email — MANDATORY, once per session, after ALL reports are saved:**
```bash
python rca_copilot_agent/run_tool.py send_rca_email --json '{"session_summary": "<plain text: which incidents, key findings>", "subject": "RCA Complete — <INCx>"}'
```

Do NOT ask the user for verification before calling `send_rca_email`. The email IS the notification.

**Batch mode:** call `list_incidents` to get all tickets, then loop the single-ticket steps for each
open incident. Call `send_rca_email` once at the end with all incidents in the `session_summary`.

### Step 3 — Post comment (only when post-comment intent detected)

Show all RCA reports to the user first. Ask: "Ready to post the above RCA(s) as comments. Confirm?"

On confirmation:
```bash
python rca_copilot_agent/run_tool.py post_comment --json '{"incident_number": "<INCx>", "text": "<RCA text>", "as_work_note": false}'
```

Never post without confirmation. The `post_comment` tool writes live to ServiceNow.

## RCA Report Format (MANDATORY)

```
### WHAT HAPPENED
One sentence — the symptom as reported by the user, not the root cause.

### WHAT WE CHECKED
→ Checked [source] — [what you found]
→ Checked [source] — [what you found]

### WHAT WE FOUND
One or two sentences stating the root cause with evidence.
If unclear, state what is known vs. unknown.

### WHAT WE NEED / DID
- Bullet list of action items with owner if named in the ticket
```

### Rule: FULL canonical assignment-group names — never shortforms

When the report references a SNOW assignment group (action items in `### WHAT WE NEED / DID`, evidence in `### WHAT WE CHECKED`, etc.), **always write the verbatim canonical group name as it appears in ServiceNow.** Never use operator shortforms (`CDS L3`, `LOY`, `MARS team`, `iBeauty`, `NGL`, etc.) — they're ambiguous outside the team and they don't match the SNOW Reassign-Group picker.

Example:
- ✓ "Assign to `APAC - SGP - SPACE CDS SAPMENA L3 Support` as the issue is tracked in DFCT0268807."
- ✗ "Assign to CDS L3 team as the issue is tracked in DFCT0268807."

Use this shortform → canonical mapping to translate work-note shorthand to the full SNOW group name:

| Shorthand seen in work-notes | Full canonical SNOW group |
|---|---|
| `CDS L2`, `CDS L2 team`, `SAPMENA CDS group` | `APAC - SGP - SPACE CDS SAPMENA L2 Support` |
| `CDS L3`, `CDS L3 team` | `APAC - SGP - SPACE CDS SAPMENA L3 Support` |
| `LOY`, `LOY team`, `Loyalty`, `Loyalty team` (loyalty backend) | `APAC - ZN - O+O.NGLORA - L2` |
| `LOY L3`, `Loyalty L3` | `APAC - CHN - SPACE Loyalty L3 Support` |
| `MARS`, `MARS team`, `MARS Ops`, `MARS Operations`, `retail Ops team` | `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2` |
| `iBeauty`, `iBeauty team`, `IBeauty team`, `iBeauty L2` | `APAC - ZN - iBeauty 2.0 - Retail - L2` |
| `SFCC`, `SFCC L2` | `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2` |
| `CRM`, `SFMC team`, `SFDC team`, `CE team`, `CE Ops team` | `APAC - ZN - O+O.CRM - L2` |
| `NGL`, `NGL L2`, `NGLORA` | `APAC - ZN - O+O.NGLORA - L2` |
| `Operations`, `Ops`, `OPS team` (only when no more specific match) | `APAC - ZN - O+O.OPERATIONS - L2` |
| `Hypercare`, `Hypercare team`, `Hypercare group`, `LS team`, `LS Hypercare`, `Aesop hypercare` | `APAC - ZN - SPACE B2C Hypercare` |
| `HIP`, `HIP team`, `Infrastructure team`, `Azure team` (HIP-adjacent) | `TECH FNDN - WW - HIP INCIDENT L2` |
| `THN Retail`, `Thailand Retail` | `APAC - THN - Retail IT` |

L3 / specialised groups that appear in real work-notes (also use full names):
- `APAC - SGP - SPACE CDS SAPMENA L3 Support`
- `APAC - CHN - SPACE Loyalty L3 Support`
- `APAC - SGP - SPACE Loyalty L3 Support`
- `INFRA - WW - Linux Unix ACN - L3`

If the right canonical group is uncertain, pick the closest match and add `[USER-CONFIRM]` after it in the report so the reviewer knows to verify.

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
