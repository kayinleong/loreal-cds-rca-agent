# AGENTS.md — Mock Data Copilot Agent

> Instruction schema for GitHub Copilot (or any MCP-aware LLM client).
> All LLM reasoning stays in the client. This server exposes only pure-function tools.

## Purpose

Generate mock `external_system_ids` rows (and, conditionally, synthetic `consumer_pii` rows)
as **BigQuery GoogleSQL** `INSERT` statements for the L'Oreal CDS B2C DV (SEA) replica dataset,
and **PRESENT** them for a human to review and run manually.

**The agent NEVER executes writes.** It produces `INSERT` text only. The only live BigQuery
access in the whole package is read-only: the `consumer_pii` existence lookup (`lookup_consumer`)
and the `external_system_ids` seed fetch (`fetch_seed`) — both blocklist-clean `SELECT`s that
never touch the generated `INSERT`s.

GCP target:

- **Project:** `oa-apmena-spacecds-ap-dv` (the **DV** project — differs from the rca/ticketasg PD default)
- **Dataset:** `space_cds_b2c_ds_replica_ase1_dv_public`

There is no ServiceNow integration and no SMTP/email in this package. The only credential
mechanism is gcloud Application Default Credentials (ADC).

## Tool Inventory

| Tool | When to use |
|------|-------------|
| `ensure_login` | Ensure the L'Oreal GCP login is valid (gcloud user credentials + ADC); defaults the billing project to the DV project. Call once before `fetch_seed` / `lookup_consumer`. |
| `fetch_seed` | Read-only — fetch a live `external_system_ids` row to use as the generation seed, so the agent never has to ask the user to paste one. Runs a bounded `SELECT` of the 18 live columns (never `SELECT *`) with optional whitelisted filters (`isocountry`/`signature`/`sourcesystemid`/`lucid`) and a clamped `limit` (1-25). Returns `{seed, rows, row_count, sql}`; never executes an `INSERT`. |
| `generate_mockdata` | **CORE** — clone a seed row into N `external_system_ids` rows from a variation spec; optionally add synthetic `consumer_pii` rows for `absent_lucids` the agent has already confirmed missing. Returns the `INSERT` SQL as TEXT only. Never executes SQL, never calls `lookup_consumer`. |
| `lookup_consumer` | Read-only `consumer_pii` existence check against the DV dataset. Keyed on `lucid` (+ optional `consumerkey`/`signature`/`isocountry`). Touches a live database (read-only); it never executes an `INSERT`. |
| `save_mockdata_report` | **MANDATORY** — write `mockdata/<MMDDYYSS>.md` (collision-safe) echoing the prompt, the `external_system_ids` INSERT, the optional `consumer_pii` INSERT, a summary, and the "review & run manually / does not execute writes" reminder. Returns the saved path. |

## GCP Target

- **Project:** `oa-apmena-spacecds-ap-dv`
- **Dataset:** `space_cds_b2c_ds_replica_ase1_dv_public`
- **Auth:** gcloud ADC only — run once per session:
  ```bash
  gcloud auth application-default login
  ```
  Use a `@loreal.com` account so the read-only lookup can reach the DV dataset.
- **No `COOKIE` / `X_USERTOKEN`** (no ServiceNow). **No SMTP** (no email). The only env vars are
  `BQ_PROJECT`, `BQ_DATASET`, and `MOCKDATA_OUTPUT_DIR` — all optional, all defaulted in
  `config.py`.

The offline tools (`generate_mockdata`, `save_mockdata_report`) need **zero credentials** and run
fully offline. Only `ensure_login` and `lookup_consumer` trigger the gcloud auth check, and they
do so lazily.

## Mock-Data Workflow (Mandatory Sequence — no exceptions)

1. **`ensure_login`** — GCP login (gcloud user creds + ADC); default project = the DV project.
2. **`fetch_seed`** *(when no seed was pasted)* — read-only fetch of a live `external_system_ids`
   row to use as the seed; pass any country/brand hints as filters. Skip only if the user pasted
   seed JSON. Never ask the user to paste a seed.
3. **`generate_mockdata`** — clone the seed into N `external_system_ids` rows; returns the INSERT
   SQL plus the row data, including the distinct `lucids` and `consumerkeys`.
4. **`lookup_consumer` per distinct `lucid`** — read-only existence check against `consumer_pii`;
   collect the lucids that come back `exists: false`.
5. **`generate_mockdata` again with `absent_lucids`** — re-run with the collected absent lucids so
   the response adds a synthetic `consumer_pii_sql` block for those consumers only.
6. **`save_mockdata_report`** — write `mockdata/<MMDDYYSS>.md` with both INSERT blocks and the
   summary.
7. **Present the SQL** with the reminder: review and run the INSERTs manually against the
   BigQuery DV dataset. The agent never executes writes.

Do not skip steps 1, 6, or 7.

## Running Without MCP (Skills / CLI Mode)

L'Oreal's environment does not allow MCP servers. Use `run_tool.py` instead:

```bash
# 1. Ensure GCP login (gcloud user creds + ADC; default project = DV)
python mockdata_copilot_agent/run_tool.py ensure_login --json '{}'

# 1b. Fetch a live seed row (read-only) when the user did not paste one
python mockdata_copilot_agent/run_tool.py fetch_seed --json '{"isocountry": "AU", "signature": "YSL", "limit": 1}'

# 2. Generate N external_system_ids rows from a seed + variation spec (CORE)
python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {"extsystemidskey":"1b48bdbb-bdbb-7b6f-0003-000000000033","consumerkey":"6d74baaa-baaa-7a19-899c-000000000032","isocountry":"ID","signature":"01","lucid":"C2ID00000000010","sourceconsumerid":"ID011000000001C","createddatetime":"1900-01-01T00:00:00Z","createdsourcesystemid":"MOCK_DATA","lastupdatedsourcesystemid":"MANUAL"}, "vary": {"signature": ["45","01","24"]}, "count": 3}'

# 3. Read-only consumer_pii existence check
python mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "C2ID00000000010"}'

# 4. Re-generate with confirmed-absent lucids to add synthetic consumer_pii rows
python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {...}, "vary": {"signature": ["45","01"]}, "count": 2, "absent_lucids": ["C2ID00000000010"]}'

# 5. Save report (MANDATORY) and present the SQL
python mockdata_copilot_agent/run_tool.py save_mockdata_report --json '{"prompt": "create 3 mock rows varying signature", "external_sql": "<external_system_ids_sql>", "consumer_sql": "<consumer_pii_sql>", "summary": "3 rows; varied signature; 1 absent consumer_pii row"}'
```

**For Claude Code users:** invoke the `/mockdata-copilot` skill
(`.claude/skills/mockdata-copilot/SKILL.md`).

**For GitHub Copilot users:** the `.github/agents/mockdata_copilot.agent.md` agent definition uses
`run_in_terminal` to call `run_tool.py` — no MCP server required.

### Variation (`vary`) contract

`vary` maps a column name to one of:
- a **list of values** — cycled by row index (use a single-element list for a constant);
- the string **`"increment"`** — auto-bumps the seed value's trailing number or letter per row
  (e.g. `ID011000000001C → …D → …E`, or `ID0370 → ID0371`).

Any other bare string raises a `ValueError` (so a typo like `"incrment"` fails loudly instead of
being emitted as a literal value). `extsystemidskey` is always auto-incremented regardless of
`vary` to keep the PK unique.

## Confirmed Decisions

All confirmed by the user on **2026-06-24**:

- **[A1] Dialect = BigQuery GoogleSQL** targeting the DV dataset
  `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public`. Generated `INSERT`s use
  fully-qualified backtick table refs, single-quoted STRING literals,
  `TIMESTAMP 'YYYY-MM-DD HH:MM:SS+00'` literals, unquoted INT64/NUMERIC/FLOAT64, `true`/`false`
  BOOL, and bare `NULL` for empty cells. **No** Postgres `::uuid` / `::timestamptz` casts. The
  generated SQL is run **manually** against BigQuery; the agent only presents it.
- **[A2 / A3] DV column types** are TYPE-DRIVEN from `.docs/dv_columns.json`, acquired via the
  live `INFORMATION_SCHEMA.COLUMNS` fetch (`confirmed: true`, 2026-06-24, under a `@loreal.com`
  account): **18** `external_system_ids` columns + **32** `consumer_pii` columns (including a
  `datastream_metadata` STRUCT, which renders as `NULL`). Re-run the fetch if the DV schema
  changes.
- **[Schema match — "Match BQ + warn"]** Generation is driven by the live `external_system_ids`
  schema (18 cols). Seed keys not in that table — `recordstatus` and `country_iso_3166_1` (both
  live on `consumer_pii`) and `consumersourcekey` (in neither) — are **dropped** from the INSERT
  and listed in a leading `-- Dropped seed column(s)…` comment so the user sees what was removed.
- **[A4] Existence key = `lucid`** (+ optional `consumerkey`/`signature`/`isocountry`
  disambiguators), because `lucid` is not unique across brands.

---

**This agent presents SQL only.** Review and run the generated `INSERT`s manually against the
BigQuery DV dataset (`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public`).
`mockdata/` is gitignored — never stage it.
