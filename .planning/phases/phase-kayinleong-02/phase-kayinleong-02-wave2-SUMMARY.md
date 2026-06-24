---
phase: phase-kayinleong-02
wave: 2
subsystem: mockdata_copilot_agent — shared tool reuse
status: complete
tags: [bigquery, gcloud, reuse, verbatim-copy, blocklist]
requires:
  - wave1 (package scaffold + config.py with bq_project=DV)
provides:
  - mockdata_copilot_agent/tools/gcloud_tool.py (ensure_gcloud_auth, set_project, set_quota_project)
  - mockdata_copilot_agent/tools/bigquery_tool.py (query_bigquery, init_from_schema, SafeBigQueryExecutor, validate_query, _pick_executor, DANGEROUS_KEYWORDS)
affects:
  - wave3 (mockdata_tool.py) — depends on bigquery_tool consumer_pii lookup
  - wave4 (mcp_server.py / run_tool.py) — depends on both tools + BQ_PROJECT env default
tech-stack:
  added: []
  patterns: [verbatim-copy reuse, project-scoped BQ executor selection via _pick_executor, BQ_PROJECT env default for DV routing]
key-files:
  created:
    - mockdata_copilot_agent/tools/gcloud_tool.py
    - mockdata_copilot_agent/tools/bigquery_tool.py
  modified: []
decisions:
  - "Copied both shared tool files byte-for-byte (cp, not symlink) — phase-01 precedent keeps packages independent"
  - "Did NOT hardcode DV project inside either file — set_project keeps the PD literal default; DV is supplied at startup via BQ_PROJECT env (config) per CLAUDE.md 'no project outside config.py'"
metrics:
  duration: ~5 min
  completed: 2026-06-24
  tasks: 2
  files: 2
---

# Phase kayinleong-02 Wave 2: Reuse gcloud_tool + bigquery_tool Summary

Copied the two genuinely-reused tool modules — `gcloud_tool.py` (GCP/ADC auth) and `bigquery_tool.py` (read-only SELECT executor with the safety blocklist) — into `mockdata_copilot_agent/tools/` VERBATIM (SHA-256 identical to the ticketasg sources), with zero edits, so the entire BigQuery safety guarantee (SELECT-only, blocklist, dry-run, byte ceiling) is inherited for free and DV routing falls out of the `BQ_PROJECT` env default + `_pick_executor` without touching either file.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Copy gcloud_tool.py and bigquery_tool.py verbatim | 12933e25 | mockdata_copilot_agent/tools/{gcloud_tool.py, bigquery_tool.py} |
| 2 | Verify blocklist + DV routing without editing shared files | 12933e25 | (no file changes — verification only) |

## Verification Results

All `<verify><automated>` blocks were run with `python3` (this environment exposes `python3`, not `python`) from the repo root.

- **Task 1 verify — PASSED.** Imports of `ensure_gcloud_auth`, `set_project`, `set_quota_project`, `DANGEROUS_KEYWORDS`, `_pick_executor`, `init_from_schema`, `query_bigquery`, `SafeBigQueryExecutor`, `_SCHEMA_JSON` all succeed with `sys.path` including `mockdata_copilot_agent/`. The blocklist contains all 14 dangerous keywords (`INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, MERGE, GRANT, REVOKE, EXECUTE, CALL, EXPORT, LOAD`) — not weakened. `_SCHEMA_JSON` resolves to `/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/schema.json` (repo-root, filename `schema.json`, file exists) from the new package depth via `parent.parent.parent`.
- **Task 2 verify — PASSED.** `SafeBigQueryExecutor(project='oa-apmena-spacecds-ap-dv').validate_query(...)` returns `(True, None)` for the DV `consumer_pii` existence SELECT, and `(False, "Blocked: 'INSERT' statements are not allowed (read-only mode)")` for an INSERT against the same DV table. No edits were made to either shared file.
- **DV routing without edits — CONFIRMED.** `inspect.getsource(_pick_executor)` contains no hardcoded DV project — it routes by the first backtick-quoted project ref in the SQL. `set_project`/`set_quota_project` still read `os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")` (PD literal intact, no DV hardcode); DV becomes default purely via the `BQ_PROJECT` env set from config at Wave 4 startup.

## Byte-Identical Confirmation

`diff` returns no output for both pairs, and SHA-256 hashes match exactly:

| File | SHA-256 (new == source) |
| ---- | ----------------------- |
| gcloud_tool.py | `2278bd34cc13a4a97ba3ee9d4424d2c674008153ce8d2e4bfff8b240a80a63a3` |
| bigquery_tool.py | `136e78dbad905d1a32c9053e38beb5b67c90bb2f963032da23f6c47c4bdd8454` |

Both new files are byte-identical to `ticketasg_copilot_agent/tools/gcloud_tool.py` and `ticketasg_copilot_agent/tools/bigquery_tool.py` respectively.

## Deviations from Plan

None — the wave executed exactly as written. The only adaptation was running the plan's `python` verify commands with `python3` per the runtime note (this environment exposes `python3` only); no command logic was changed.

## Threat Mitigations (from plan threat_model)

- **T-wave2-01 (Tampering, blocklist):** mitigated — `DANGEROUS_KEYWORDS` copied verbatim; INSERT verified rejected before execution.
- **T-wave2-02 (DoS):** mitigated — `maximum_bytes_billed` ceiling + row cap + dry-run inherited verbatim.
- **T-wave2-03 (Info Disclosure, auth):** mitigated — gcloud stdout→stderr redirection, ADC-only, no credential files, copied verbatim.
- **T-wave2-04 (accidental BQ write):** mitigated — blocklist is the backstop; generated INSERTs are never routed through `query_bigquery` (Wave 4 writes them to the report file only).

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: mockdata_copilot_agent/tools/gcloud_tool.py
- FOUND: mockdata_copilot_agent/tools/bigquery_tool.py
- FOUND commit: 12933e25 (`feat(phase-kayinleong-02): wave2 reuse gcloud_tool + bigquery_tool (verbatim, blocklist intact)`)
- Both files byte-identical (SHA-256 + diff) to ticketasg sources
- Blocklist intact (14 keywords); DV SELECT passes, INSERT blocked
- Only the two wave2 files staged/committed; pre-existing mods (retrieval_index.npz, email_tool.py), .serena/, and .docs/ samples left unstaged

## EXECUTION COMPLETE
