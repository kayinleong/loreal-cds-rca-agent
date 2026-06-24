---
phase: phase-kayinleong-02
wave: 5
subsystem: mockdata_copilot_agent
tags: [companion-docs, agents-md, skill, github-agent, integration-smoke, mock-data, bigquery, googlesql]
requires:
  - wave1 (scaffold, .gitignore mockdata/, .docs/dv_columns.json)
  - wave2 (gcloud_tool.py, bigquery_tool.py — verbatim reused tools)
  - wave3 (tools/mockdata_tool.py — pure GoogleSQL generator)
  - wave4 (mcp_server.py 4-tool _dispatch, run_tool.py CLI)
provides:
  - mockdata_copilot_agent/AGENTS.md
  - .claude/skills/mockdata-copilot/SKILL.md
  - .github/agents/mockdata_copilot.agent.md
affects:
  - Claude Code (discoverable via /mockdata-copilot)
  - GitHub Copilot (via .github/agents/mockdata_copilot.agent.md)
tech-stack:
  added: []
  patterns: [companion-docs-mirror-phase01-ticketasg, no-MCP-run_tool.py-CLI, presents-SQL-never-executes-writes]
key-files:
  created:
    - mockdata_copilot_agent/AGENTS.md
    - .claude/skills/mockdata-copilot/SKILL.md
    - .github/agents/mockdata_copilot.agent.md
  modified: []
decisions:
  - "A1: generated SQL is BigQuery GoogleSQL targeting the DV dataset; agent presents only, never executes writes"
  - "A2/A3: DV column types are type-driven from .docs/dv_columns.json (currently confirmed:false fallback — re-fetch needed after @loreal.com ADC login)"
  - "A4: consumer existence key = lucid (+ optional consumerkey/signature/isocountry)"
metrics:
  duration: ~12m
  completed: 2026-06-24
  tasks_completed: 2
  files_created: 3
status: complete
---

# Phase phase-kayinleong-02 Wave 5: Companion Definitions + Final Integration Smoke Summary

Authored the three companion definitions (`AGENTS.md`, Claude `SKILL.md`, GitHub `agent.md`)
that let Claude Code and GitHub Copilot drive the Wave 3–4 `mockdata_copilot_agent` tool layer,
mirroring the phase-01 ticketasg companions but adapted for offline BigQuery-GoogleSQL mock-data
generation; ran the full offline integration smoke (generate → save round-trip, collision suffix,
gitignore enforcement, no cross-package code imports) — all offline verifies pass.

## What Was Built

| File | What it is |
|------|------------|
| `mockdata_copilot_agent/AGENTS.md` | Instruction schema: Purpose, 4-tool Inventory, GCP Target (DV project/dataset, ADC only), 6-step Mandatory Sequence, `run_tool.py` CLI examples, Confirmed Decisions (A1/A2-A3/A4), "presents SQL / never executes writes" reminder. |
| `.claude/skills/mockdata-copilot/SKILL.md` | Claude Code skill — YAML frontmatter `name: mockdata-copilot`, `invocation: /mockdata-copilot`; Prerequisites (ADC only, no ServiceNow/SMTP), ABSOLUTE TOOL RESTRICTION, 4-tool invocation table with exact `run_tool.py` commands, no-MCP workflow (Step 0 intent + Steps 1–6), Output/Analysis Rules. |
| `.github/agents/mockdata_copilot.agent.md` | GitHub Copilot agent — YAML frontmatter `name: Mock Data Copilot Agent` + `tools:` list, **no `invocation` key** (per phase-01); ABSOLUTE TOOL RESTRICTION, 4-tool CLI mapping, MANDATORY SEQUENCE (6 steps), Core Workflow, Output/Analysis Rules. |

Accurate tool inventory documented across all three (matches `mcp_server.py` `_dispatch` + `run_tool.py`):
`ensure_login`, `generate_mockdata`, `lookup_consumer`, `save_mockdata_report`.

## Tasks

- **Task 1 — Create the three companion docs:** DONE. Automated verify (`companions OK`) passed.
- **Task 2 — Final integration smoke + no-cross-import check:** DONE (offline). See Verification.
- **Checkpoint (human-verify):** Content produced below; NOT approved by the executor — surfaced
  for the user to action.

## Verification

| # | Check | Result |
|---|-------|--------|
| Task 1 | SKILL.md YAML + `invocation: /mockdata-copilot` + 4 tools; agent.md `name:` + `execute/runInTerminal` + `MANDATORY SEQUENCE` + NO `invocation:` key; AGENTS.md 4 tools + DV project + "never executes writes" | PASS (`companions OK`) |
| Check 1 | All 12 required files exist (8 package .py + dv_columns.json + AGENTS.md + SKILL.md + agent.md) | PASS |
| Check 2 | No cross-package **code** imports in `mockdata_copilot_agent/` | PASS — only one stale prose comment in `bigquery_tool.py:71` (Wave-2 verbatim copy); not a code import. See Deviations. |
| Check 3 | `run_tool.py --help` exits 0 and prints "mockdata_copilot_agent" | PASS (exit 0; epilog names the package) |
| Check 4 | Offline `generate_mockdata` (count=3, vary signature) → 3 rows, unique `extsystemidskey`, varied signature, GoogleSQL `TIMESTAMP '…'` literals, no `::` casts; `save_mockdata_report` writes `mockdata/<MMDDYYSS>.md` with `## Prompt` / `## external_system_ids` / `## consumer_pii` / `## Summary` + "does not execute writes" + A1 GoogleSQL note; second same-day save → different sequence suffix | PASS (`A1 GoogleSQL integration smoke PASS`; `ROUND-TRIP PASS`; saved `06242601.md` then `06242602.md`) |
| Check 5 | `git check-ignore` returns the report path; `git status --porcelain` lists nothing under `mockdata/` | PASS (check-ignore exit 0; no mockdata/ in status) |
| Check 6 | Live `lookup_consumer` smoke | SKIPPED / manual — no ADC; active account is `@accenture.com`; runtime forbids triggering `gcloud auth login`. To be run by the user after `@loreal.com` ADC login. |

### Smoke output (key lines)

```
companions OK
OK: (all 12 required files)
A1 GoogleSQL integration smoke PASS — 3 rows, unique keys, varied signature, TIMESTAMP literals, no :: casts
SAVE1: .../mockdata/06242601.md
SAVE2: .../mockdata/06242602.md
ROUND-TRIP PASS — MMDDYYSS pattern, distinct same-day suffix, all sections + reminder + A1 note present
git check-ignore mockdata_copilot_agent/mockdata/06242601.md -> exit 0 (ignored)
git status --porcelain -> (no mockdata/ files — GOOD)
```

## Deviations from Plan

### Adjusted verification (not an implementation change)

**1. [Plan/verify mismatch — corrected assertion] Task 2 `<automated>` expected `INSERT INTO external_system_ids (`**
- **Found during:** Task 2 automated verify.
- **Issue:** The plan's Task-2 automated check asserts the INSERT begins with the **unqualified**
  `INSERT INTO external_system_ids (`. The Wave-3 implementation correctly emits a
  **fully-qualified backtick GoogleSQL ref** —
  `` INSERT INTO `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.external_system_ids` ( `` —
  which is exactly what the [A1] confirmed decision and the human-verify checkpoint's own
  "Expected" text require ("a fully-qualified backtick `…external_system_ids` table ref").
- **Resolution:** The stale verify string predates the A1 fully-qualified-ref decision. Did NOT
  modify the implementation (it matches A1). Verified instead against the correct A1 contract:
  fully-qualified backtick ref + 3 rows + unique keys + varied signature + `TIMESTAMP '…'`
  literals + no `::` casts — all PASS. No code touched (Task 2 makes no file changes).

### Out-of-scope (logged, not fixed — belongs to Wave 2)

**2. [Rule 1 candidate — deferred, non-owned file] Stale comment in `bigquery_tool.py:71`**
- The verbatim-reused `mockdata_copilot_agent/tools/bigquery_tool.py` carries a comment:
  `# schema.json lives in the repo root (3 levels up from ticketasg_copilot_agent/tools/)` —
  a leftover reference to the source package it was copied from. This is a **comment, not a code
  import** (the plan explicitly allows comments; only code imports are bugs). CLAUDE.md mandates
  the reused tools stay verbatim, and this is a Wave-2 artifact, so it is left untouched and
  logged here for a future cosmetic cleanup. No functional impact.

## Known Stubs

**`.docs/dv_columns.json` is a `confirmed: false` fallback.** Column types were inferred from
`schema.json` + the `.docs` sample because ADC was unavailable and the active account is not
`@loreal.com`. The generator renders types correctly from this file today, but the DV column
types should be re-fetched via live `INFORMATION_SCHEMA.COLUMNS` (with `@loreal.com` ADC) before
production. Surfaced in the human-verify checklist (A2/A3) below. This is the only intentional
stub; it does not block offline generation.

---

## HUMAN-VERIFY CHECKPOINT — for the user to action (NOT approved by executor)

**Gate:** blocking (human-verify). The executor produced this content and ran the offline smoke;
the user must perform the steps below and reply `approved` (or describe issues) before the wave is
considered fully verified.

### What was built (full package, waves 1–5)

- Python: `__init__.py`, `config.py` (MockDataConfig, DV defaults), `mcp_server.py` (4 tools),
  `run_tool.py` (CLI), `tools/__init__.py`, `tools/gcloud_tool.py` (verbatim),
  `tools/bigquery_tool.py` (verbatim, blocklist intact), `tools/mockdata_tool.py` (pure)
- `.docs/dv_columns.json` (pinned DV column set — currently `confirmed: false`)
- `AGENTS.md`, `.claude/skills/mockdata-copilot/SKILL.md`,
  `.github/agents/mockdata_copilot.agent.md` (this wave)
- `.gitignore` updated with `mockdata/` (wave 1)

### Checklist to confirm

- [ ] **[A1 — GoogleSQL/BigQuery, CONFIRMED] Sanity-check the generated dialect.** Run the offline
      generate, then inspect:
      ```bash
      python3 mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {"extsystemidskey":"1b48bdbb-bdbb-7b6f-0003-000000000033","consumerkey":"6d74baaa-baaa-7a19-899c-000000000032","isocountry":"ID","signature":1,"lucid":"C2ID00000000010","sourceconsumerid":"ID011000000001C","createddatetime":"1900-01-01T00:00:00Z","createdsourcesystemid":"MOCK_DATA","lastupdatedsourcesystemid":"MANUAL"}, "vary": {"signature": ["45","01","24"]}, "count": 3}'
      ```
      Confirm: fully-qualified backtick table ref
      (`` `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.external_system_ids` ``),
      `TIMESTAMP '…'` literals, no `::` casts. Optionally dry-run one INSERT in BigQuery. The agent
      presents SQL only — run it manually.

- [ ] **[A2/A3 — RE-FETCH NEEDED] Re-acquire `dv_columns.json` after `@loreal.com` ADC login.**
      Open `mockdata_copilot_agent/.docs/dv_columns.json` — it is currently `confirmed: false`
      (types inferred). After `gcloud auth application-default login` with a `@loreal.com`
      account, re-run the `INFORMATION_SCHEMA.COLUMNS` fetch against
      `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public` for `external_system_ids`
      and `consumer_pii`, overwrite the file, and set `confirmed: true` so generated INSERTs use
      the real DV column types.

- [ ] **[A4 — lucid existence key, CONFIRMED] Confirm `lucid` disambiguation is sufficient.**
      The existence check keys on `lucid` (+ optional `consumerkey`/`signature`/`isocountry`).
      Confirm `lucid` (with the optional disambiguators) is the right uniqueness key for the DV
      `consumer_pii` table.

- [ ] **(Optional, needs ADC) Live read-only lookup smoke** — skipped by the executor (no ADC,
      account is `@accenture.com`):
      ```bash
      python3 mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "<a real DV lucid>"}'
      ```
      Expect JSON with an `exists` boolean; no write is performed.

**Resume signal:** Type `approved` when verification passes, or describe any issues (SQL style
mismatch, wrong `consumer_pii` columns, dialect/existence-key assumptions to change).

## Self-Check: PASSED

- `mockdata_copilot_agent/AGENTS.md` — FOUND
- `.claude/skills/mockdata-copilot/SKILL.md` — FOUND
- `.github/agents/mockdata_copilot.agent.md` — FOUND
- Commit `141d2100` — FOUND (`feat(phase-kayinleong-02): wave5 companions — AGENTS.md + SKILL.md + agent.md`)

## EXECUTION COMPLETE

Auto tasks done; offline integration smoke passed (live `lookup_consumer` skipped per ADC
constraints); three companion docs committed (`141d2100`); human-verify checklist surfaced above
for the user to action. The human-verify checkpoint is NOT approved by the executor.
