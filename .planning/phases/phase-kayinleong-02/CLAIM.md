# Claim: phase-kayinleong-02
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-24
- status: done
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

## Post-execution refinement (2026-06-24, after `@loreal.com` login)

- **Live schema fetched (`confirmed:true`):** ran `INFORMATION_SCHEMA.COLUMNS` against the DV
  dataset; `.docs/dv_columns.json` now holds the real schema — **18** `external_system_ids`
  columns + **32** `consumer_pii` columns (incl. a `datastream_metadata` STRUCT).
- **Discovery + user decision:** the live `external_system_ids` table has 18 cols, but the
  `.docs` sample has 21 — `recordstatus`/`country_iso_3166_1` live on `consumer_pii`,
  `consumersourcekey` is in neither. User chose **"Match BQ + warn"**.
- **Generator refactored:** `mockdata_tool.py` is now schema-driven from `dv_columns.json` — emits
  the live 18 esi columns, drops sample-only columns with a leading `-- Dropped seed column(s)…`
  comment, normalizes parameterized types (`STRING(50)`→STRING), and renders STRUCT/complex
  columns as `NULL`.
- **All confirmed:** A1 GoogleSQL ✓, A2/A3 live columns ✓, A4 `lucid` ✓, Match-BQ+warn ✓.

## Verification

### Live paths verified (post @loreal.com login)
- `INFORMATION_SCHEMA.COLUMNS` fetch against the DV dataset succeeded → real schema written to `dv_columns.json` (`confirmed:true`).
- Live `consumer_pii` existence lookup (`build_lookup_sql` → `query_bigquery`) executed against the real DV table, returned "Query returned 0 rows" → absence correctly detected (would trigger `consumer_pii` generation). Read path + absence heuristic confirmed end-to-end.
- Refactored generator re-verified: 18-col esi INSERT with 3 sample-only columns dropped + warned, 32-col `consumer_pii` INSERT with `datastream_metadata` STRUCT → NULL, `TIMESTAMP '…'` literals, no `::` casts, lookup blocklist-clean; CLI `generate_mockdata` end-to-end PASS.

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

Phase `done`: agent built, live DV schema fetched + applied, all user decisions (A1/A2/A3/A4 + Match-BQ) resolved, and all paths (offline generation, live schema fetch, live lookup, blocklist, CLI) verified. Optional follow-up: dry-run a generated INSERT in BigQuery before bulk use.
