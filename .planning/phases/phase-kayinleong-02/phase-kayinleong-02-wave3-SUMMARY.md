---
phase: phase-kayinleong-02
wave: 3
subsystem: mockdata_copilot_agent
status: complete
tags: [bigquery, googlesql, mock-data, pure-function, dv-dataset]
requires: [wave1-scaffold, wave2-gcloud_tool, wave2-bigquery_tool]
provides:
  - mockdata_copilot_agent/.docs/dv_columns.json
  - mockdata_tool.generate_external_system_ids
  - mockdata_tool.generate_consumer_pii
  - mockdata_tool.build_lookup_sql
  - mockdata_tool.load_column_types
affects: [wave4-mcp_server, wave4-run_tool]
tech-stack:
  added: []
  patterns: [pure-function-tool, type-driven-sql-rendering, no-stdout-mcp-safety]
key-files:
  created:
    - mockdata_copilot_agent/.docs/dv_columns.json
    - mockdata_copilot_agent/tools/mockdata_tool.py
  modified: []
decisions: [A1-GoogleSQL, A2A3-types-from-dv_columns.json, A4-lucid-key, A5-uuid-family, A8-provenance-markers, A9-synthetic-pii]
metrics:
  duration: ~12m
  completed: 2026-06-24
  tasks: 2
  files: 2
---

# Phase kayinleong-02 Wave 3: mockdata_tool — GoogleSQL generator + DV column ref Summary

Built the single net-new domain module `mockdata_tool.py` — a pure-function seed→N-row BigQuery GoogleSQL generator — and pinned the full DV column metadata (`.docs/dv_columns.json`) for both `external_system_ids` (21 cols) and `consumer_pii` (19 cols). Value rendering is type-driven from the committed column reference.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Acquire and commit full DV column metadata for both tables | 29e5af44 | mockdata_copilot_agent/.docs/dv_columns.json |
| 2 | Create mockdata_tool.py (pure-function GoogleSQL generator + lookup builder) | 29e5af44 | mockdata_copilot_agent/tools/mockdata_tool.py |

(Both tasks share one wave commit per the orchestrator's single-commit instruction for this wave.)

## What Was Built

### Task 1 — `.docs/dv_columns.json` (FALLBACK, confirmed:false)
- Pins the full DV column metadata for both tables in ordinal order, each entry having `name`, `data_type`, `ordinal_position`.
- `external_system_ids`: 21 columns; `consumer_pii`: 19 columns.
- **`confirmed: false`** — live `INFORMATION_SCHEMA.COLUMNS` fetch was NOT performed because GCP ADC is unavailable in this environment (the active gcloud account is `@accenture.com`, not `@loreal.com`, and there is no application-default credential). Per the plan's documented ADC-UNAVAILABLE FALLBACK, the file was written with `confirmed:false`, the `[A2/A3]` note, and inferred column types (STRING for all key/id/code/marker/status columns + country_iso_3166_1 + consumersourcekey; TIMESTAMP for the four datetime columns; INT64 for recordstatus).
- No interactive `gcloud auth ... login` was run (would have hung the session). No live `bq show` was attempted because no instant non-prompting path was available.

### Task 2 — `mockdata_tool.py` (pure, TDD)
- Pure-function module: NO LLM calls, NO stdout prints (the only `print(` targets stderr via `_stderr`, line 90), NO I/O beyond reading `.docs/dv_columns.json`.
- Exports: `generate_external_system_ids`, `generate_consumer_pii`, `build_lookup_sql`, `load_column_types`, `parse_seed_xlsx` (optional, lazy openpyxl import), plus constants `EXTERNAL_SYSTEM_IDS_COLUMNS` (21-tuple), `_DV_PROJECT`, `_DV_DATASET`.
- Type-driven `_render_value`: None/"" → bare `NULL`; STRING/BYTES/unknown → single-quoted (embedded `'` doubled); TIMESTAMP → `TIMESTAMP 'YYYY-MM-DD HH:MM:SS[.ffffff]+00'`; DATE/DATETIME handled; numeric types unquoted; BOOL → true/false. NO Postgres `::uuid`/`::timestamptz` casts.
- `generate_external_system_ids`: clones seed `count` times; ALWAYS varies `extsystemidskey` by incrementing the trailing 12-digit counter (A5) so every PK is unique; applies `vary` strategies (list = cycle by row index, scalar = constant); non-varied columns equal the seed. Returns `{sql, rows, lucids, consumerkeys}`.
- `generate_consumer_pii`: emits obviously-fake synthetic PII (`firstname='Mock'`, `lastname='Tester'`, `email='mock+<id>@example.com'`, `consumertype='MOCK_DATA'`) across the committed consumer_pii column list (A9).
- `build_lookup_sql`: read-only `SELECT ... FROM \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii\` WHERE lucid = '...'` (+ optional disambiguators), `LIMIT 5`, all literals single-quoted; passes `SafeBigQueryExecutor.validate_query` (blocklist-clean, read-only).

## Verifications Run (all PASS)

| # | Check | Result |
| - | ----- | ------ |
| Task 1 automated | dv_columns.json: 21 esi cols, 19 cpi cols, required names present, every col has data_type | PASS — `confirmed: False \| esi cols: 21 \| cpi cols: 19` |
| Task 2 automated (inline) | 3 unique extsystemidskey; signature varied to ['45','01','24']; other cols == seed; SQL starts with FQ backtick external_system_ids ref; no `::uuid`/`::timestamptz`; MOCK_DATA/MANUAL present; `TIMESTAMP '2026-06-19 00:00:00+00'`; bare NULL; single-quoted uuid; consumer_pii synthetic mock+...@example.com; build_lookup_sql passes validate_query | PASS — `ALL mockdata_tool GoogleSQL tests PASS` |
| verification 1 | import + `len(EXTERNAL_SYSTEM_IDS_COLUMNS)==21` | PASS — `1 OK` |
| verification 2 | dv_columns.json counts + confirmed flag | PASS — `2 confirmed= False` |
| verification 3 | single-row gen: no `::uuid`, has `TIMESTAMP ` | PASS — `3 GoogleSQL OK` |
| verification 4 | `grep print(` returns only stderr-targeted print | PASS — only line 90 `print(msg, file=sys.stderr)` |

## Deviations from Plan

None — plan executed exactly as written. Task 1 followed the plan's documented ADC-UNAVAILABLE FALLBACK branch (not a deviation; an explicit plan-provided path).

## Known Stubs / Follow-ups

- **`dv_columns.json` is `confirmed: false`** (ADC unavailable). The inferred types are best-guess per the plan's fallback list. **Action required:** after GCP login (`@loreal.com` user account + `gcloud auth application-default login`), re-run the `INFORMATION_SCHEMA.COLUMNS` query for both tables and overwrite `dv_columns.json` with `confirmed: true`. The Wave 5 checkpoint should surface this. Because `mockdata_tool` is type-driven from this file, type corrections propagate automatically once the file is re-fetched.

## Threat Surface

No new security surface introduced beyond the plan's threat model. `mockdata_tool` generates text only; the sole live-DB SQL (`build_lookup_sql`) is read-only and verified blocklist-clean. Synthetic PII is hardcoded obviously-fake (T-wave3-01 mitigated).

## Self-Check: PASSED
- FOUND: mockdata_copilot_agent/.docs/dv_columns.json
- FOUND: mockdata_copilot_agent/tools/mockdata_tool.py
- FOUND commit: 29e5af44

## EXECUTION COMPLETE
