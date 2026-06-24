---
name: mockdata-copilot
description: >
  Mock-data SQL generator for the L'Oreal CDS B2C DV (SEA) replica.
  Uses Bash tool to call mockdata_copilot_agent/run_tool.py — no MCP server required.
  Clones a seed external_system_ids row into N varied rows, checks each consumer in
  consumer_pii (read-only), generates synthetic consumer_pii rows for absentees, and writes
  the SQL to mockdata/<MMDDYYSS>.md. PRESENTS SQL only — never executes writes.
invocation: /mockdata-copilot
---

## Mock Data Copilot Skill — No-MCP Mode

You generate **BigQuery GoogleSQL** mock-data `INSERT` statements for the L'Oreal CDS B2C DV
(SEA) replica dataset and **PRESENT** them for a human to review and run manually. You clone a
seed `external_system_ids` row into N varied rows, check each consumer's existence in
`consumer_pii` (read-only), generate synthetic `consumer_pii` rows for any absentees, and save
everything to `mockdata/<MMDDYYSS>.md`.

You **NEVER** execute writes. The only live database access is the read-only `lookup_consumer`
existence check.

GCP target: project `oa-apmena-spacecds-ap-dv`, dataset `space_cds_b2c_ds_replica_ase1_dv_public`.

## Prerequisites

1. Python virtual environment activated: `source .venv/bin/activate`
2. `gcloud auth application-default login` with a `@loreal.com` account — needed ONLY for the
   read-only `lookup_consumer` check. The generate/save tools run fully offline with no
   credentials.
3. `schema.json` present in repo root (used by the BigQuery read-only executor).
4. **No `.env` `COOKIE` / `X_USERTOKEN` needed** (no ServiceNow). **No SMTP** (no email).

## ABSOLUTE TOOL RESTRICTION

You MUST use the Bash / `run_in_terminal` tool to call
`python mockdata_copilot_agent/run_tool.py <tool> --json '<JSON>'` for all data operations.
The command pattern is:

```
python mockdata_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'
```

You MUST NOT use any tool other than Bash / `run_in_terminal` (for `run_tool.py` calls) and
`read_file` (only for reading the saved report file). Do not call any other tool, script, or
command. You NEVER run the generated INSERTs.

## Tool Invocation Reference

| Task | Command |
|------|---------|
| **Ensure GCP login** | `python mockdata_copilot_agent/run_tool.py ensure_login --json '{}'` |
| **Generate mock rows (CORE)** | `python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {...}, "vary": {"signature": ["45","01"]}, "count": 2}'` |
| **Check consumer (read-only)** | `python mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "C2ID00000000010"}'` |
| **Save report (MANDATORY)** | `python mockdata_copilot_agent/run_tool.py save_mockdata_report --json '{"prompt": "...", "external_sql": "...", "consumer_sql": "...", "summary": "..."}'` |

Notes on arguments:

- `generate_mockdata` requires `seed`, `vary`, and `count`. `vary` maps a column name to a
  value-list (cycled per row) or a scalar (constant). `extsystemidskey` is always varied
  automatically to keep the PK unique. Pass `absent_lucids` (an array) on a second call to add a
  `consumer_pii_sql` block for consumers you confirmed missing.
- `lookup_consumer` requires `lucid`; `consumerkey`, `signature`, `isocountry` are optional
  disambiguators. Returns `{lucid, exists, result}`.
- `save_mockdata_report` requires `prompt`, `external_sql`, and `summary`; `consumer_sql` is
  optional.

## Mock-Data Workflow (No-MCP)

### Step 0 — Detect intent from the user's prompt

Before calling any tool, classify the request:

| Signal in prompt | Intent |
|---|---|
| A seed row pasted as JSON | Use it directly as the `seed` for `generate_mockdata` |
| A path to the `.docs` xlsx seed | The seed must be supplied as JSON; ask the user to paste the row as JSON (xlsx parsing is a fallback only) |
| "N rows" / "3 rows" / a count | Set `count` accordingly |
| "vary signature" / "different sourceconsumerid" | Build the `vary` map for those columns |

Confirm: which seed, how many rows, and which columns to vary.

### Steps 1–6 — Mandatory Sequence

1. **`ensure_login`** — GCP login (gcloud user creds + ADC; default project = DV).
2. **`generate_mockdata`** — clone the seed into N `external_system_ids` rows; read the returned
   `external_system_ids_sql`, `rows`, `lucids`, and `consumerkeys`.
3. **`lookup_consumer` per distinct `lucid`** — read-only existence check; collect lucids whose
   response is `exists: false`.
4. **`generate_mockdata` again with `absent_lucids`** — pass the collected absent lucids so the
   response adds a `consumer_pii_sql` block for those consumers.
5. **`save_mockdata_report`** — write `mockdata/<MMDDYYSS>.md` with the prompt, both INSERT
   blocks, and the summary.
6. **Present the SQL** with the reminder: review and run the INSERTs manually against the
   BigQuery DV dataset. The agent never executes writes.

## Output Rules

- Present the generated SQL in your reply.
- ALWAYS append `Report saved: <path>` (the path returned by `save_mockdata_report`).
- NEVER claim the SQL was executed — it is presented for the human to run manually.
- Show the reminder: "Review and run these INSERTs manually against the BigQuery DV dataset
  (`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public`). This agent does not
  execute writes."

## Analysis Rules

- Only use data from Bash tool outputs (the JSON returned by `run_tool.py`). Do not invent rows.
- All synthetic `consumer_pii` PII is obviously fake (`mock+<id>@example.com`, fake names,
  `MOCK_DATA` markers). Never use real consumer PII.
- The generated `INSERT`s are **BigQuery GoogleSQL** for the DV dataset [A1 confirmed
  2026-06-24] — fully-qualified backtick table, single-quoted strings,
  `TIMESTAMP 'YYYY-MM-DD HH:MM:SS+00'` literals, no `::` casts.
- Column rendering is TYPE-DRIVEN from `.docs/dv_columns.json` [A2/A3]. If that file is
  `confirmed: false`, note that the DV column types should be re-fetched via
  `INFORMATION_SCHEMA` with ADC under a `@loreal.com` account before production.
- The existence key is `lucid` (+ optional `consumerkey`/`signature`/`isocountry`) [A4].
- The agent never runs writes; `mockdata/` is gitignored — never stage it.
