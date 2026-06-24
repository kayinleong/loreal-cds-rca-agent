# Claim: phase-kayinleong-02
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-24
- status: in-progress
- summary: Build mockdata_copilot_agent — a Copilot-only agent that, on each prompt, ensures L'Oréal GCP login, generates mock INSERT rows for external_system_ids (seeded from a user-provided row + variation intent), looks up the consumer in consumer_pii and generates a mock consumer_pii row when absent, then writes the generated SQL to mockdata/<MMDDYYSS>.md and presents it to the user.

## What Will Change

Planning complete (2026-06-24) — 5 wave plans authored + verified READY TO EXECUTE by gsd-plan-checker (0 blocking issues). Code changes happen in /gsd-execute-phase.

Planning artifacts in this directory:
- `02-CONTEXT.md` — locked design decisions
- `02-RESEARCH.md` — reuse map, queries, pitfalls, assumptions A1–A9
- `02-PLAN-wave1.md` — Scaffold: `__init__.py`, `config.py` (MockDataConfig, DV defaults), `.gitignore += mockdata/`
- `02-PLAN-wave2.md` — Reuse tools: verbatim `gcloud_tool.py` + `bigquery_tool.py` (blocklist intact, DV routing via BQ_PROJECT, no edits)
- `02-PLAN-wave3.md` — Core: one-time live `external_system_ids` + `consumer_pii` schema fetch (`.docs/dv_columns.json`) + pure `mockdata_tool.py` (seed→N rows, BigQuery GoogleSQL INSERT SQL)
- `02-PLAN-wave4.md` — Surface: `mcp_server.py` (4 tools) + `run_tool.py` + `mockdata/<MMDDYYSS>.md` writer
- `02-PLAN-wave5.md` — Companions: `AGENTS.md`, `.claude/skills/mockdata-copilot/SKILL.md`, `.github/agents/mockdata_copilot.agent.md` + human-verify checkpoint (A1/A2/A3/A4)

Decisions confirmed by user 2026-06-24: A1 SQL dialect = **BigQuery GoogleSQL** (targets the DV dataset, not the `.docs` Postgres sample), A2/A3 = live INFORMATION_SCHEMA fetch of full DV column types for both tables, A4 consumer existence key = **lucid**.

## What Has Changed

Executed 2026-06-24 — all 5 waves built + committed (offline-verified). `mockdata_copilot_agent/`:
- **wave1** `812098cd` — `__init__.py` (×2), `config.py` (`MockDataConfig`: DV project/dataset + `output_dir`, no SNOW/SMTP), `mockdata/` added to `.gitignore`
- **wave2** `12933e25` — `tools/gcloud_tool.py` + `tools/bigquery_tool.py` copied byte-identical from ticketasg (blocklist intact; DV routing via `BQ_PROJECT`, no edits)
- **wave3** `29e5af44` — `tools/mockdata_tool.py` (pure, type-driven **GoogleSQL** generator: `generate_external_system_ids`, `generate_consumer_pii`, `build_lookup_sql`) + `.docs/dv_columns.json`
- **wave4** `8f7a498b` — `mcp_server.py` (4 tools: `ensure_login`, `lookup_consumer`, `generate_mockdata`, `save_mockdata_report`), `run_tool.py` (CLI; lazy auth — deviation, see below), collision-safe `mockdata/<MMDDYYSS>.md` writer
- **wave5** `141d2100` — `AGENTS.md`, `.claude/skills/mockdata-copilot/SKILL.md`, `.github/agents/mockdata_copilot.agent.md`

**Deviation (auto-applied):** `ensure_gcloud_auth` made **lazy** (only `ensure_login`/`lookup_consumer` invoke it) instead of unconditional startup, so `--help` and offline tools don't hang when ADC is absent. `BQ_PROJECT=DV` is still set from config before any auth.

## Status detail / outstanding

- **Live schema re-fetch pending:** `.docs/dv_columns.json` is `confirmed:false` (inferred types) — ADC was unavailable and the active gcloud account is `@accenture.com`. After `gcloud auth application-default login` with a `@loreal.com` account, re-run the `INFORMATION_SCHEMA.COLUMNS` fetch to upgrade to `confirmed:true`. (Generator is type-driven, so corrections propagate automatically.)
- **Human-verify checkpoint pending:** A1 GoogleSQL dialect, A2/A3 re-fetched columns, A4 `lucid` key — user sign-off.
- **Live `lookup_consumer` path untested** (no ADC).

## Verification

### What was tested (offline, no credentials)
- Independent orchestrator smoke from repo root: 21-column constant; `generate_external_system_ids` → fully-qualified backtick GoogleSQL `INSERT`, `TIMESTAMP '…+00'` literals, NO `::uuid`/`::timestamptz`, bare `NULL`, `MOCK_DATA`/`MANUAL`, 3 unique `extsystemidskey`.
- `build_lookup_sql(...)` passes `SafeBigQueryExecutor.validate_query`; an `INSERT` is **blocked** by the blocklist.
- `run_tool.py --help` exits 0; `_dispatch` routes the 4 tools and returns "Unknown tool" otherwise.
- `save_mockdata_report` writes a collision-safe `mockdata/<MMDDYYSS>.md`; `git check-ignore` confirms `mockdata/` is ignored.
- Per-wave `<verify>` blocks all green (waves 1–5).

### What passed
All offline verifies for waves 1–5 + the independent smoke.

### What was ruled out / not covered
- Live BigQuery read path (`lookup_consumer`, `INFORMATION_SCHEMA` fetch) — not run: ADC unavailable. Tracked under "outstanding".
- `bigquery_tool.py:71` retains a verbatim-copied prose comment referencing `ticketasg_copilot_agent/tools/` — cosmetic only (path resolves via `parent.parent.parent`); kept to preserve the byte-identical copy.

### Regression Report
- Surface touched: only NEW files under `mockdata_copilot_agent/` + additive `.gitignore`/`.claude/skills/`/`.github/agents/` entries. `rca_copilot_agent/` and `ticketasg_copilot_agent/` source NOT modified — `grep` confirms zero cross-package imports (the one hit is a comment, not an import). Pre-existing unrelated working-tree mods (`ticketasg_copilot_agent/retrieval_index.npz`, `email_tool.py`) were never staged. BigQuery blocklist unchanged and verified still blocking. No secrets introduced; `mockdata/` gitignored.

status remains `in-progress` until the live re-fetch + human checkpoint close out.
