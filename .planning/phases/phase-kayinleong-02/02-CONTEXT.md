# Phase kayinleong-02: mockdata_copilot_agent — Context

**Gathered:** 2026-06-24
**Status:** Ready for planning
**Source:** Direct user spec via /gsd-plan-phase --research --auto (no discuss-phase; decisions captured here by orchestrator)

<domain>
## Phase Boundary

Build a new **Copilot-only agent** `mockdata_copilot_agent/` whose single job is to **generate mock data SQL** for the L'Oréal CDS B2C DV (SEA) replica and present it to the user. It does **not** execute writes against BigQuery — it produces `INSERT` statements for the user to run.

Per-prompt user flow:
1. **Ensure the user is logged into L'Oréal GCP** (NOT ServiceNow — no SNOW anywhere in this agent).
2. **Ingest the user's prompt** — a seed row (21-column `external_system_ids` record, supplied via the `.docs` xlsx layout or pasted) plus natural-language variation intent (which attributes to vary, how many rows).
3. **Generate N mock `external_system_ids` rows** by cloning the seed and varying the requested attributes.
4. For each generated row, **look up the consumer in `consumer_pii`** (live read). If the consumer is absent, **also generate a mock `consumer_pii` row** so the external_system_ids FK is satisfiable.
5. **Write the generated SQL** to `mockdata/<MMDDYYSS>.md` and **present it to the user**.

GCP target (DIFFERENT from the RCA agent's PD project):
- **Project:** `oa-apmena-spacecds-ap-dv`
- **Dataset:** `space_cds_b2c_ds_replica_ase1_dv_public` ("B2C DV ASE1 — same schema as primary")
- **Tables:** `external_system_ids` (mock-data target) and `consumer_pii` (lookup + conditional mock target)

This agent mirrors the established Copilot-agent shape of `rca_copilot_agent/` and `ticketasg_copilot_agent/`.
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Agent type & layout
- Copilot-only agent (NO LLM calls in any tool / mcp_server — Copilot/Claude provides reasoning), mirroring `rca_copilot_agent` / `ticketasg_copilot_agent`.
- Package `mockdata_copilot_agent/` with: `__init__.py`, `config.py`, `run_tool.py` (CLI dispatch), `mcp_server.py` (tool registration), `AGENTS.md`, and `tools/`.
- Companion definitions: `.claude/skills/mockdata-copilot/SKILL.md` and `.github/agents/mockdata_copilot.agent.md` (same two companions phase-01 produced for ticketasg).

### Reuse vs. drop
- **Reuse** `gcloud_tool.py` for GCP auth — `ensure_gcloud_auth("loreal.com")` already checks user creds + ADC and triggers interactive login. Default project must be the **DV** project (`oa-apmena-spacecds-ap-dv`), so `BQ_PROJECT` default differs from rca/ticketasg.
- **Reuse** `bigquery_tool.py` for the read-only `consumer_pii` existence lookup (keep its blocklist intact — the lookup is a SELECT; the agent never executes INSERT/MERGE).
- **DROP** all ServiceNow surface: no `auth_tool.py`, `snow_reader.py`, `incident_store.py`; no `COOKIE`/`X_USERTOKEN`; no SMTP/email tool (not requested).

### Mock-data generation
- A pure-function tool (e.g. `mockdata_tool.py`) takes a **seed row** + a **variation spec** (columns to vary, row count) and emits `INSERT INTO external_system_ids (...) VALUES (...)` statements that match the `.docs` `.sql` sample style: `::uuid` / `::timestamptz` casts, `MOCK_DATA` / `MANUAL` markers, the recognizable synthetic UUID family (`1b48bdbb-bdbb-7b6f-XXXX-XXXXXXXXXXXX`, `6d74baaa-baaa-7a19-899c-XXXXXXXXXXXX`), `NULL` for empty cells.
- Output file: `mockdata/<MMDDYYSS>.md` containing the originating prompt, the generated external_system_ids SQL, any generated consumer_pii SQL, and a short summary. (`SS` = a 2-digit suffix to disambiguate multiple files in the same day; planner to define collision handling.)

### consumer_pii dependency
- For each generated external_system_ids row, check existence in `consumer_pii` keyed by `lucid` (and/or `consumerkey`) via a read-only SELECT against the DV dataset.
- If absent, generate a **synthetic** `consumer_pii` INSERT (obviously-fake PII only — `MOCK_DATA` markers, fake names/emails like `mock+<id>@example.com`; never real PII).

### Safety / hygiene
- Agent presents SQL; it does **not** run writes. The only live BQ access is the read-only existence lookup.
- `mockdata/` output may contain synthetic PII only; ensure it is gitignored (mirror `my_reports/` handling) and never staged.
- No secrets, no credential files; gcloud ADC only.

### Claude's Discretion
- Exact tool names, function signatures, and `run_tool.py` dispatch wiring.
- Internal variation algorithm (how UUID suffixes / sourceconsumerid / signature increment).
- SKILL.md / agent.md wording.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Sample data (the contract for generated output)
- `mockdata_copilot_agent/.docs/external_system_ids mock up.sql` — full 21-column INSERT style + synthetic value conventions to replicate.
- `mockdata_copilot_agent/.docs/external_system_ids.xlsx` — header row (21 columns) + seed-row layout the user supplies.

### Pattern to mirror
- `ticketasg_copilot_agent/` (most recent Copilot agent — `config.py`, `mcp_server.py`, `run_tool.py`, `AGENTS.md`, `tools/`).
- `rca_copilot_agent/` (original Copilot agent of this shape).
- `.planning/phases/phase-kayinleong-01/` — CLAIM.md + 01-PLAN-wave*.md show the wave/plan format and the SKILL.md + agent.md companion deliverables.

### Reusable tools
- `ticketasg_copilot_agent/tools/gcloud_tool.py` — GCP login (`ensure_gcloud_auth`, project defaulting via `BQ_PROJECT`).
- `ticketasg_copilot_agent/tools/bigquery_tool.py` — read-only BQ executor + safety blocklist (read before reusing).

### Schema
- `schema.json` (repo root) — declares the DV ASE1 dataset as "same schema as primary"; provides column **descriptions** for `consumer_pii` (19 listed) and `external_system_ids` (8 listed). **CAUTION:** these are CURATED/PARTIAL lists for RCA, NOT full DDL. The full `external_system_ids` column list (21) is in the `.docs` sample; `consumer_pii`'s full column set must be confirmed against the live table.

### Project rules
- `CLAUDE.md` (root) + `~/.claude/CLAUDE.md` — Copilot agents are LLM-agnostic (no LLM in tools); BQ safety blocklist must not be weakened; synthetic data only; never commit `mockdata/`-style PII dirs.
</canonical_refs>

<specifics>
## Specific Ideas

- Worked example from the user: prompt = "create mock data for me with different signature and sourceconsumerid"; seed = the single xlsx row (`1b48bdbb-…-0003-000000000033`, `6d74baaa-…-899c-000000000032`, ISO `ID`, …); expected output = several external_system_ids rows cloned from the seed with `signature` and `sourceconsumerid` varied, row count taken from the prompt.
- Generated SQL must stay valid GoogleSQL/Postgres-style consistent with the `.docs` `.sql` (the sample uses `::uuid` / `::timestamptz` Postgres casts — planner to confirm the target dialect for the DV replica and match it).
</specifics>

<deferred>
## Deferred Ideas

- Executing the generated INSERTs against BigQuery (explicitly out of scope — present SQL only).
- Email/SMTP notification of generated mock data (not requested).
- Mock-data generation for tables other than `external_system_ids` / `consumer_pii`.
</deferred>

---

*Phase: phase-kayinleong-02 — mockdata_copilot_agent*
*Context captured 2026-06-24 by /gsd-plan-phase orchestrator (no discuss-phase). Decisions above are the orchestrator's reasoned choices from the user's spec; user should confirm before execution.*
