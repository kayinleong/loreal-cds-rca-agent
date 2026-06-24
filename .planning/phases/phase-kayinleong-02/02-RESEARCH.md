# Phase kayinleong-02: mockdata_copilot_agent — Research

**Researched:** 2026-06-24
**Domain:** Python Copilot-only agent — mock-data SQL generation for L'Oréal CDS B2C DV (SEA) replica
**Confidence:** HIGH (primary source: direct codebase analysis; every reuse decision and path/blocklist behavior verified by reading + running production code)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Copilot-only agent** — NO LLM calls in any tool / `mcp_server`. Copilot/Claude provides reasoning. Mirror `rca_copilot_agent` / `ticketasg_copilot_agent`.
- Package `mockdata_copilot_agent/` with: `__init__.py`, `config.py`, `run_tool.py` (CLI dispatch), `mcp_server.py` (tool registration), `AGENTS.md`, and `tools/`.
- Companion definitions: `.claude/skills/mockdata-copilot/SKILL.md` and `.github/agents/mockdata_copilot.agent.md` (same two companions phase-01 produced for ticketasg).
- **Reuse** `gcloud_tool.py` for GCP auth — `ensure_gcloud_auth("loreal.com")`. Default project must be the **DV** project `oa-apmena-spacecds-ap-dv` (differs from rca/ticketasg PD default).
- **Reuse** `bigquery_tool.py` for the read-only `consumer_pii` existence lookup. Keep its blocklist intact — the lookup is a SELECT; the agent never executes INSERT/MERGE.
- **DROP** all ServiceNow surface: no `auth_tool.py`, `snow_reader.py`, `incident_store.py`; no `COOKIE`/`X_USERTOKEN`; no SMTP/email tool.
- Pure-function `mockdata_tool.py` takes a seed row + variation spec (columns to vary, row count) → emits `INSERT INTO external_system_ids (...) VALUES (...)` matching the `.docs` `.sql` style (`::uuid` / `::timestamptz` casts, `MOCK_DATA`/`MANUAL` markers, synthetic UUID family `1b48bdbb-bdbb-7b6f-XXXX-…` / `6d74baaa-baaa-7a19-899c-…`, `NULL` for empty cells).
- Output file `mockdata/<MMDDYYSS>.md` containing the originating prompt, generated external_system_ids SQL, any generated consumer_pii SQL, and a short summary. (`SS` = 2-digit suffix to disambiguate same-day files; planner defines collision handling.)
- For each generated external_system_ids row, check existence in `consumer_pii` keyed by `lucid` (and/or `consumerkey`) via a read-only SELECT against the DV dataset. If absent, generate a **synthetic** `consumer_pii` INSERT (obviously-fake PII only — `MOCK_DATA` markers, fake names/emails like `mock+<id>@example.com`; never real PII).
- Agent presents SQL; it does **not** run writes. Only live BQ access is the read-only existence lookup.
- `mockdata/` output may contain synthetic PII only; ensure gitignored (mirror `my_reports/`) and never staged.
- No secrets, no credential files; gcloud ADC only.

### Claude's Discretion
- Exact tool names, function signatures, and `run_tool.py` dispatch wiring.
- Internal variation algorithm (how UUID suffixes / sourceconsumerid / signature increment).
- SKILL.md / agent.md wording.

### Deferred Ideas (OUT OF SCOPE)
- Executing the generated INSERTs against BigQuery.
- Email/SMTP notification of generated mock data.
- Mock-data generation for tables other than `external_system_ids` / `consumer_pii`.
</user_constraints>

---

## Summary

This phase clones the Copilot-agent skeleton established by `rca_copilot_agent` and `ticketasg_copilot_agent` into a third package, `mockdata_copilot_agent/`, with a sharply narrower surface. Where ticketasg has 19 tools spanning ServiceNow, BigQuery RCA, and assignment routing, the mockdata agent needs only **four tools**: an auth check, a read-only `consumer_pii` lookup, a pure-function mock-row generator, and a report writer. The two genuinely reused modules are `gcloud_tool.py` (verbatim) and `bigquery_tool.py` (verbatim — its `SafeBigQueryExecutor` blocklist is exactly what guarantees "SELECT only, never writes"). Everything ServiceNow (`snow_reader.py`, `incident_store.py`, `auth_tool.py`, `email_tool.py`, `retrieval_tool.py`, `assignment_tool.py`) is dropped.

The single net-new domain module is `mockdata_tool.py` — a pure function (no LLM, no I/O) that takes the 21-column seed row plus a variation spec and emits Postgres-style `INSERT` text byte-compatible with `mockdata_copilot_agent/.docs/external_system_ids mock up.sql`. The `.docs/.sql` sample uses `::uuid` / `::timestamptz` casts and a recognizable synthetic UUID family; the agent's only job is to clone the seed N times, vary the named attributes, keep `extsystemidskey` unique, and present the SQL — it never runs the INSERTs.

Two facts deserve early planner attention. **First, the SQL dialect is ambiguous**: `schema.json` declares the live BigQuery dialect as `GoogleSQL`, yet the `.docs` sample is unmistakably PostgreSQL (`::uuid` / `::timestamptz` casts do not exist in GoogleSQL). The generated INSERTs are evidently destined for a Postgres source/staging system, not BigQuery — the agent only *reads* BigQuery. Recommendation: match the `.docs` sample exactly (Postgres casts) and flag as an assumption. **Second, `schema.json` is partial** for these two tables: it lists 8 of 21 `external_system_ids` columns and 19 `consumer_pii` columns, and only under the **primary PD** dataset — the DV ASE1 public dataset entry lists only survey tables. The authoritative full column set for `consumer_pii` in the DV dataset must be obtained via a live `INFORMATION_SCHEMA.COLUMNS` SELECT (which passes the blocklist) or `bq show --schema`.

**Primary recommendation:** Copy `gcloud_tool.py` + `bigquery_tool.py` verbatim; change only the project default to `oa-apmena-spacecds-ap-dv`; write a new `mockdata_tool.py` pure function for seed→N-row generation; expose four tools through a stripped `mcp_server.py` + `run_tool.py`; generate Postgres-dialect SQL matching the `.docs` sample; gitignore `mockdata/`.

---

## Project Constraints (from CLAUDE.md)

- Python 3.11+ — `.venv` is Python 3.13.7 [VERIFIED: phase-01 research + openpyxl ran under 3.x this session]
- No LLM calls inside `mcp_server.py` or any `tools/*.py` — MCP layer is LLM-agnostic [CITED: project CLAUDE.md "What Not To Do"]
- BigQuery blocklist in `bigquery_tool.py` must not be weakened/bypassed [CITED: project CLAUDE.md "BigQuery Safety"]
- Synthetic data only; never commit `my_reports/`-style PII output dirs [CITED: project CLAUDE.md + global secrets rules]
- All config tunables in `config.py` with env-var overrides [CITED: project CLAUDE.md "Adding a new tool" step 3]
- Update `AGENTS.md` with every tool's name/description/inputs/outputs [CITED: project CLAUDE.md step 4]
- Never hardcode BQ project/dataset outside `config.py` [CITED: project CLAUDE.md "What Not To Do"] — **NOTE:** the reused `gcloud_tool.py`/`bigquery_tool.py` currently default the project via `os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")` and via `schema.json`. See Reuse Map for how to honor this rule for the DV default.
- Do not stage `schema.json` alongside code changes [CITED: project CLAUDE.md] — relevant because this agent reads schema.json but should not regenerate/commit it in the same commit as code.
- Claim-before-start + owner-scoped commits (`phase-kayinleong-02`) [CITED: global CLAUDE.md] — a `CLAIM.md` already exists for this phase.
- Never use `isolation: "worktree"` when spawning agents [CITED: global CLAUDE.md].

---

<phase_requirements>
## Phase Requirements

> No formal REQUIREMENTS.md / requirement IDs were supplied for this phase. The IDs below are derived from the CONTEXT.md locked decisions so the planner has a stable map; renumber if a REQUIREMENTS.md is later authored.

| ID | Description | Research Support |
|----|-------------|------------------|
| MD-01 | Package scaffold mirrors ticketasg shape (`__init__.py`, `config.py`, `run_tool.py`, `mcp_server.py`, `tools/`, `AGENTS.md`) | Reuse Map; "Recommended Project Structure" |
| MD-02 | GCP login enforced (NOT ServiceNow) via reused `ensure_gcloud_auth("loreal.com")`; default project = DV | Q2 "GCP login"; `gcloud_tool.py:183,138,166` |
| MD-03 | Read-only `consumer_pii` existence lookup against DV dataset; blocklist intact | Q3 "Read-only lookup"; blocklist verified passes |
| MD-04 | Pure-function `mockdata_tool` generates N external_system_ids rows by cloning seed + varying named attributes, keeping `extsystemidskey` unique | Q6 "Mock generation algorithm" |
| MD-05 | Conditional synthetic `consumer_pii` row when consumer absent (fake PII only) | Q3 + Q4; `consumer_pii` column set |
| MD-06 | Generated SQL matches `.docs` `.sql` style (Postgres casts, MOCK_DATA/MANUAL markers, synthetic UUID family, NULL for empties) | Q5 "SQL dialect"; `.docs/external_system_ids mock up.sql` |
| MD-07 | Output written to `mockdata/<MMDDYYSS>.md` with prompt echo + SQL sections + summary; collision-safe | Q7 "Output file" |
| MD-08 | `mockdata/` gitignored; agent never executes writes | Q7 + Safety; `.gitignore` |
| MD-09 | Companion `SKILL.md` + `agent.md` produced (same shape as phase-01) | Q8 + "Companion deliverables" |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| GCP login / ADC enforcement | `mockdata_copilot_agent/tools/gcloud_tool.py` (reused) | `run_tool.py` + `mcp_server.py` startup | ADC check identical to ticketasg; only project default changes |
| Read-only `consumer_pii` existence lookup | `mockdata_copilot_agent/tools/bigquery_tool.py` (reused) | — | Blocklist guarantees SELECT-only; this is the ONLY live BQ access |
| Seed→N-row mock generation (external_system_ids + consumer_pii SQL) | `mockdata_copilot_agent/tools/mockdata_tool.py` (NEW, pure function) | — | No LLM, no I/O; deterministic transformation |
| Decide which attributes to vary / how many rows | LLM client (GitHub Copilot / Claude) | — | Reasoning lives in the agent body, never in tools/ |
| Output report persistence | `mockdata_copilot_agent/mcp_server.py` (`save_mockdata_report`) | `run_tool.py` CLI | Same pattern as ticketasg `save_assignment_report` |
| Schema / column-set discovery | `bigquery_tool.py` (`get_schema`/live `INFORMATION_SCHEMA`) + committed reference | `schema.json` (partial) | schema.json is partial for these tables; see Q4 |

---

## Standard Stack

### Core (all already present — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-cloud-bigquery` | 3.41.0 | Read-only `consumer_pii` lookup via `SafeBigQueryExecutor` | Already used by all sibling agents [VERIFIED: phase-01 research §Dependencies] |
| `openpyxl` | 3.1.5 | Read the `.docs` xlsx seed layout (if seed supplied as file) | Installed; ran successfully this session [VERIFIED: `openpyxl.__version__` = 3.1.5] |
| `mcp` | 1.27.0 | Optional MCP server mode; `run_tool.py` works without it | Same optionality as ticketasg [VERIFIED: phase-01 research] |
| stdlib (`argparse`, `asyncio`, `json`, `datetime`, `uuid`, `re`, `pathlib`) | 3.13 | CLI dispatch, SQL string building, file naming | No third-party needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `subprocess` (stdlib, via reused tools) | — | gcloud / bq CLI invocation inside `gcloud_tool.py` + `bigquery_tool.py` | Reused verbatim; no change |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openpyxl` for seed input | Accept seed as pasted JSON/text in the tool args | Pasted text avoids file dependency entirely; recommend supporting BOTH — paste is primary (matches the worked example), xlsx is convenience. openpyxl already installed so no cost. |
| Live `INFORMATION_SCHEMA` for column set | Committed `mockdata_copilot_agent/.docs/consumer_pii.columns.json` generated once | Committed file is offline + deterministic; live query needs ADC. Recommend committed reference (see Q4). |

**Installation:** No `pip install` step required — all dependencies are already in `requirements.txt` per phase-01 research [VERIFIED: phase-01 §Dependencies]. The planner should NOT add new packages.

---

## Package Legitimacy Audit

> No external packages are introduced by this phase. All imports (`google-cloud-bigquery`, `openpyxl`, `mcp`, plus stdlib) are already installed and used by sibling agents.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none new) | — | — | — | — | — | No new installs |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Reuse Map (per-file)

Source = `ticketasg_copilot_agent/`. Target = `mockdata_copilot_agent/`. Verbatim file evidence cited inline.

| Source file | Disposition | What changes | Evidence |
|-------------|-------------|--------------|----------|
| `tools/gcloud_tool.py` | **COPY VERBATIM** | None to the file. Project default changes via env/config, see note below | `gcloud_tool.py:183` `ensure_gcloud_auth("loreal.com")`; `:138-146` `set_project()` reads `BQ_PROJECT` env (default PD); `:166-178` `set_quota_project()` same |
| `tools/bigquery_tool.py` | **COPY VERBATIM** | None. `_SCHEMA_JSON` path math (`parent.parent.parent`) resolves correctly from the new package at identical depth | `bigquery_tool.py:72` `_SCHEMA_JSON = Path(__file__)...parent.parent.parent / "schema.json"`; **VERIFIED** resolves to repo-root schema.json from `mockdata_copilot_agent/tools/` |
| `config.py` | **COPY WITH EDITS** | Strip `ServiceNowConfig` SNOW fields (`cookie`, `x_user_token`, `instance_url`) and SMTP; add a `MockDataConfig` with `output_dir` (default `<pkg>/mockdata`) + `bq_project` (default DV) | `config.py:52-86` ServiceNowConfig; `:26` `_PKG_DIR` pattern to reuse |
| `run_tool.py` | **COPY WITH EDITS** | Remove SNOW credential check (`ensure_credentials`) + incident-store preload; keep gcloud check + BQ init; dispatch to local `_dispatch`; change `reports_dir` → `output_dir` | `run_tool.py:69-105` startup sequence; `:104-105` `from mcp_server import _dispatch` |
| `mcp_server.py` | **COPY WITH EDITS** | Replace the 19-tool list + `_dispatch` chain with the 4 mockdata tools; remove `_build_reader`, `_auto_load_store`, `_resolve_sys_id`, all SNOW/assignment branches; keep gcloud + BQ init in `main()` | `mcp_server.py:570-954` `_dispatch`; `:63-77` `_build_reader` (DROP); `:1057-1075` startup (keep BQ+gcloud, drop SNOW) |
| `AGENTS.md` | **REWRITE** (new content, same shape) | New purpose + 4-tool inventory + mock-data workflow; drop all SNOW/RCA/guidebook content | `AGENTS.md` structure (Purpose / Tool Inventory / Mandatory Sequence / Running Without MCP / Environment Setup) |
| `tools/__init__.py` | **COPY VERBATIM** | Empty package marker | — |
| `__init__.py` | **COPY VERBATIM** | Empty package marker | — |
| `tools/auth_tool.py` | **DROP** | ServiceNow SSO refresh — not needed (no SNOW) | CONTEXT decision |
| `tools/snow_reader.py` | **DROP** | ServiceNow HTTP client | CONTEXT decision |
| `tools/incident_store.py` | **DROP** | Incident JSON store | CONTEXT decision |
| `tools/email_tool.py` | **DROP** | SMTP — not requested | CONTEXT decision |
| `tools/assignment_tool.py` | **DROP** | Routing logic — out of scope | CONTEXT decision |
| `tools/retrieval_tool.py` | **DROP** | kNN retrieval — out of scope | CONTEXT decision |
| `assignment_rules.json` | **DROP** | Routing matrix — out of scope | CONTEXT decision |
| `retrieval_index.npz` | **DROP** | kNN index artifact | CONTEXT decision |
| `test_config.py` | **OPTIONAL adapt** | If kept, retarget to MockDataConfig | — |
| — | **NEW: `tools/mockdata_tool.py`** | Pure-function seed→N-row generator (the only net-new domain code) | See Q6 |

**Cross-import safety [VERIFIED]:** grep for `snow_reader|incident_store|auth_tool|email_tool|retrieval_tool|assignment_tool` across `mockdata_copilot_agent` returns nothing (no mockdata `.py` files exist yet). Each sibling package is self-contained via `sys.path.insert(0, str(Path(__file__).resolve().parent))` (`run_tool.py:42`, `mcp_server.py:60`), so dropping these modules from the new package breaks nothing in `rca_`/`ticketasg_`. **Copy, do not symlink** — phase-01 made the same call to keep packages independent.

---

## Recommended Approach per Research Question

### Q1 — Reuse map
Covered in the Reuse Map table above. Net new code is one module (`mockdata_tool.py`) plus heavily-trimmed `config.py`/`mcp_server.py`/`run_tool.py`. `gcloud_tool.py` and `bigquery_tool.py` are byte-for-byte copies.

**DV-project default — honoring the CLAUDE.md "no hardcoded project outside config.py" rule.** Two mechanisms set the project today, both defaulting to PD:
- `gcloud_tool.py:138-146` `set_project()` and `:166-178` `set_quota_project()` read `os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")`.
- `bigquery_tool.py:434` `init_from_schema()` reads `schema["project"]` (PD) and adds extra executors for each project in `additional_datasets` — which already includes `oa-apmena-spacecds-ap-dv` [VERIFIED: schema.json `additional_datasets` keys all start `oa-apmena-spacecds-ap-dv.`]. `_pick_executor` (`:455-468`) routes a query to the executor whose project matches the first backtick-quoted ref in the SQL — so a query that references `` `oa-apmena-spacecds-ap-dv.…` `` is already billed to DV without any change.

**Minimal change (recommended):** keep both reused tool files verbatim and set the DV default in the new `config.py` + `run_tool.py`/`mcp_server.py` startup by exporting `BQ_PROJECT=oa-apmena-spacecds-ap-dv` into the environment **before** `ensure_gcloud_auth()` is called, and by ensuring the generated/looked-up SQL always uses the fully-qualified `` `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii` `` ref so `_pick_executor` selects the DV executor. Storing `bq_project = "oa-apmena-spacecds-ap-dv"` in `MockDataConfig` and doing `os.environ.setdefault("BQ_PROJECT", cfg.bq_project)` at startup satisfies the "config.py owns the project" rule without editing the shared tool files. `[CITED: gcloud_tool.py:141,169]`

### Q2 — GCP login
Call sites in ticketasg [VERIFIED]:
- `mcp_server.py:1071-1075` `main()` → `from tools.gcloud_tool import ensure_gcloud_auth; ensure_gcloud_auth()` (non-fatal try/except).
- `run_tool.py:97-101` same call in the CLI path (non-fatal try/except).

`ensure_gcloud_auth(required_domain="loreal.com")` (`gcloud_tool.py:183`) runs two checks: `_ensure_user_auth` (active account must end `@loreal.com` AND `gcloud auth print-access-token` works, else interactive `gcloud auth login` → `set_account` → `set_project`) and `_ensure_adc_auth` (`gcloud auth application-default print-access-token`, else interactive ADC login → `set_quota_project`). All gcloud stdout is forwarded to stderr (`:78-83`) so it never pollutes MCP stdio.

**Minimal change:** keep the call sites identical; make the project DV by `os.environ.setdefault("BQ_PROJECT", "oa-apmena-spacecds-ap-dv")` at the top of both startup paths (before the `ensure_gcloud_auth()` call) so `set_project()`/`set_quota_project()` pick up DV. No edit to `gcloud_tool.py` itself.

### Q3 — Read-only lookup
`bigquery_tool.py` executes a SELECT via `query_bigquery(sql, rationale="") -> str` (`:544-554`): it picks the executor by project (`_pick_executor`), runs `validate_query` (blocklist + must-start-SELECT/WITH), then `_bq_cli_execute` via the `bq` CLI (`--nouse_legacy_sql --format=json`), returning an LLM-friendly string (`QueryResult.to_llm_context`). The Python-client path `SafeBigQueryExecutor.execute` (`:181-224`) additionally dry-runs and enforces `maximum_bytes_billed`.

**Exact existence-check query (DV dataset, parameterizable):**
```sql
SELECT consumerkey, lucid, signature, isocountry, status
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`
WHERE lucid = 'C2ID00000000010'      -- or: AND consumerkey = '6d74baaa-…'
  AND status = 'Active'
LIMIT 5
```
0 rows → consumer absent → generate a synthetic `consumer_pii` INSERT. ≥1 row → consumer exists → external_system_ids FK is satisfiable, no consumer_pii row needed.

**Blocklist confirmation [VERIFIED this session]:** the existence-check query above passes `validate_query` → `(True, None)`. The blocklist (`DANGEROUS_KEYWORDS`, `:76-80`) blocks `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/MERGE/GRANT/REVOKE/EXECUTE/CALL/EXPORT/LOAD`. The generated mock-data INSERTs are **never** sent through `query_bigquery` — they are written to the report file and presented; if a generated INSERT were ever passed to the tool, the blocklist would reject it on `INSERT`. **Note (Q9 landmine):** `validate_query` strips single- and double-quoted literals before keyword scanning (`:154-157`), so a brand value like `'MARS_ID'` or a string containing `CREATE` inside a literal will NOT false-positive — but an **unquoted** identifier containing a bare blocklist word would. Keep the lookup query free of bare blocklist words (the existence query above is clean).

### Q4 — Full schema acquisition
`schema.json` is **partial** for both tables and lists them only under the **primary PD** dataset [VERIFIED: `tables.external_system_ids` has 8 columns; `tables.consumer_pii` has 19 columns; the DV ASE1 public `additional_datasets` entry lists only `survey`, `survey_qna`, `product_hierarchy_map`]. The authoritative 21-column `external_system_ids` set is the `.docs` sample + xlsx header [VERIFIED below]; the full `consumer_pii` column set in the DV dataset is NOT in schema.json.

Options:
- **(a) Live `INFORMATION_SCHEMA.COLUMNS` via the reused tool** — passes the blocklist [VERIFIED this session], returns column_name + data_type in ordinal order. Needs ADC.
  ```sql
  SELECT column_name, data_type, ordinal_position
  FROM `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.INFORMATION_SCHEMA.COLUMNS`
  WHERE table_name = 'consumer_pii'
  ORDER BY ordinal_position
  ```
- **(b) `bq show --schema`** — `bq show --schema --format=prettyjson oa-apmena-spacecds-ap-dv:space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`. Same auth requirement; CLI-only.
- **(c) Committed reference file** generated once, e.g. `mockdata_copilot_agent/.docs/consumer_pii.columns.json`.

**Recommendation: (c) committed reference, generated once via (a) or (b).** Rationale: the mock-data generator must emit a `consumer_pii` INSERT with a known, fixed column list; resolving columns live on every run is fragile (needs ADC) and non-deterministic. Generate the full DV `consumer_pii` schema once during execution (Wave that has ADC), commit it as a `.docs` reference, and have `mockdata_tool.py` read it offline — mirroring how `external_system_ids`'s 21 columns are pinned by the `.docs` sample. The 19 columns already in schema.json (`consumerkey, isocountry, signature, lucid, status, consumertype, gender, firstname, lastname, birthyear, birthmonth, birthday, mobile, phone, email, sourcecreationdatetime, registrationdatetime, withdrawaldatetime, recordstatus`) are a strong starting point but **must be confirmed against the live DV table** before being treated as complete `[ASSUMED]`.

### Q5 — SQL dialect
**Evidence is contradictory:**
- `schema.json` `dialect: "GoogleSQL"` and the reused BQ tool is GoogleSQL-only [VERIFIED: schema.json top-level `dialect`].
- The `.docs/external_system_ids mock up.sql` sample uses `'…'::uuid` and `'1900-01-01 00:00:00+00'::timestamptz` casts [VERIFIED: `.docs/.sql:25-40`]. `::type` cast syntax and the `uuid`/`timestamptz` types are **PostgreSQL**, not GoogleSQL (GoogleSQL has no `uuid` type and uses `CAST(x AS TIMESTAMP)` / `TIMESTAMP '…'`).

Interpretation: the generated INSERTs target a **Postgres source/staging database** (the upstream system whose data is replicated into the BigQuery DV), not BigQuery itself. The agent only *reads* BigQuery (the existence lookup); it *presents* Postgres INSERTs for a human to run against the Postgres source.

**Recommendation:** Generate SQL that **matches the `.docs` sample exactly** — Postgres `::uuid` / `::timestamptz` casts, `MOCK_DATA`/`MANUAL` markers, `NULL` for empty cells. Flag as assumption A1: confirm the generated INSERTs are run against the Postgres source DB (not BigQuery). Do NOT route generated INSERTs through `query_bigquery` (they'd be blocklist-rejected anyway, and they're not GoogleSQL).

### Q6 — Mock generation algorithm
Pure function in `mockdata_tool.py` — no LLM, no I/O. (The consumer_pii existence read lives in `bigquery_tool.py`, a separate tool.)

**Seed parsing.** Accept the seed two ways: (1) **pasted** as a dict/JSON keyed by the 21 column names (primary path — matches the worked example), or (2) read from the `.docs` xlsx via openpyxl (header row 0 = column names, row 1 = seed values) [VERIFIED layout below]. Normalize Excel quirks: integer cells come back as `int` (e.g. `signature` = `1`, `recordstatus` = `0`, `country_iso_3166_1` = `360`) — coerce to the string form the `.sql` uses (`'45'`, `'0'`, `'360'`); ISO datetimes `'2026-06-19T00:00:00Z'` map to `'2026-06-19 00:00:00+00'::timestamptz`; `None`/empty cells map to `NULL` (unquoted, no cast).

**The 21 columns (verified — xlsx header == .docs INSERT column list):**
`extsystemidskey, consumerkey, isocountry, signature, lucid, sourcesystemid, sourceconsumerid, creationlocationid, locationid, creationsalesrepid, salesrepid, createddatetime, status, lastlogindatetime, createdsourcesystemid, lastupdatedsourcesystemid, syscreateddatetime, sysupdatedatetime, recordstatus, country_iso_3166_1, consumersourcekey` [VERIFIED: xlsx Sheet1 row 0 + `.docs/.sql:1-22`].

**Synthetic UUID family (the recognizable pattern).** From the sample [VERIFIED: `.docs/.sql:25-40`]:
- `extsystemidskey` = `1b48bdbb-bdbb-7b6f-GGGG-NNNNNNNNNNNN` where `GGGG` is a 4-digit group block (`0001`..`0005`) and `NNNNNNNNNNNN` is a 12-digit per-row counter (`000000000011`…). Each emitted row gets a **unique** `extsystemidskey` — increment the trailing counter; this is what keeps the PK unique.
- `consumerkey` = `6d74baaa-baaa-7a19-899c-NNNNNNNNNNNN` — shared across rows belonging to the same consumer (multiple external_system_ids rows can map to one consumer).

**Variation rules (driven by the LLM-supplied `vary` spec — which columns + count):**
- For each of N rows: clone the seed dict, then for each column named in `vary`, apply an increment strategy. The worked example varies `signature` and `sourceconsumerid`. Recommended deterministic strategies (Claude's discretion per CONTEXT):
  - `signature` — cycle through a supplied list or increment within the seed's market (e.g. seed `'45'` → `'45','01','24',…`).
  - `sourceconsumerid` — increment the embedded sequence letter/suffix (seed `ID011000000001C` → `…001D`, `…001E`); preserve the country + structure prefix.
  - `extsystemidskey` — ALWAYS varied (trailing counter ++), regardless of `vary`, to keep the PK unique.
  - `consumerkey` — vary only if explicitly requested (varying it implies a different consumer → triggers a new consumer_pii lookup).
- Columns not in `vary` are copied verbatim from the seed.
- Empty/`None` seed cells stay `NULL` in every clone.
- `MOCK_DATA` / `MANUAL` markers (`createdsourcesystemid` / `lastupdatedsourcesystemid`) are preserved verbatim — they are the provenance markers and must remain.

**Output:** a list of value-tuples rendered as the `INSERT INTO external_system_ids (...) VALUES (row1),(row2),…;` block, byte-style-compatible with the `.docs` sample. Keep the function signature roughly:
```python
def generate_external_system_ids(seed: dict, vary: dict, count: int) -> dict:
    """Pure. Returns {"sql": "...", "rows": [...], "lucids": [...], "consumerkeys": [...]}.
    No LLM, no I/O. `vary` maps column_name -> strategy/value-list."""
```
The returned `lucids`/`consumerkeys` feed the consumer_pii lookup step.

### Q7 — Output file
`mockdata/<MMDDYYSS>.md`. Recommend `MMDDYYSS` = `MM` + `DD` + `YY` + `SS` where `SS` is a **2-digit sequence** (00–99) that disambiguates multiple files generated the same calendar day (not seconds — seconds collide less but a sequence is collision-proof and human-readable). Build it from `datetime.now()` for `MMDDYY`, then scan `mockdata/` for existing `MMDDYY*.md` and pick the next free 2-digit suffix; if 00–99 exhaust (unlikely), fall back to `MMDDYY_HHMMSS.md`.

**Collision handling (recommended):**
```python
base = datetime.now().strftime("%m%d%y")            # MMDDYY
existing = sorted(p.stem for p in out_dir.glob(f"{base}*.md"))
seq = next(f"{i:02d}" for i in range(100)
           if f"{base}{i:02d}" not in existing)
path = out_dir / f"{base}{seq}.md"
```

**Markdown sections (recommended):**
1. `# Mock Data — {MMDDYYSS}` + generated timestamp.
2. `## Prompt` — verbatim echo of the originating user prompt (seed + variation intent).
3. `## external_system_ids` — the generated INSERT block (Postgres dialect).
4. `## consumer_pii` — only present if ≥1 consumer was absent; the synthetic INSERT(s). State explicitly "No consumer_pii rows needed — all N consumers already exist" when none.
5. `## Summary` — N rows generated, which attributes varied, which lucids existed vs were synthesized, and the explicit reminder: **"Review and run these INSERTs manually against the Postgres source DB. This agent does not execute writes."**

**gitignore [VERIFIED]:** current `.gitignore` ends with a "ServiceNow incident data (may contain PII)" block listing `my_reports/`, `attachments/`, `rca_reports/`. Add `mockdata/` to this block. The output dir default should be `<pkg>/mockdata` (via `_PKG_DIR`) so it lands inside the package regardless of launch CWD — but the `.gitignore` rule `mockdata/` (no leading slash) matches at any depth, covering both `<pkg>/mockdata/` and a repo-root `mockdata/`. The planner must add this line; it is NOT currently present [VERIFIED: grep of `.gitignore`].

### Q8 — Tool inventory
Minimal four-tool set (each maps to a ticketasg analog):

| Tool | Signature (args) | Returns | ticketasg analog | Notes |
|------|------------------|---------|------------------|-------|
| `ensure_login` | `{}` | status string (account, ADC ok, project) | `ensure_gcloud_auth()` startup call | Thin wrapper so the agent can explicitly trigger/verify GCP login; reuses `gcloud_tool.ensure_gcloud_auth` |
| `lookup_consumer` | `{"lucid": str, "consumerkey": str?}` | existence + matched cols (JSON) | `query_bigquery` (`mcp_server.py:887-894`) | Builds the fixed existence SELECT against the DV `consumer_pii`; read-only; never INSERT |
| `generate_mockdata` | `{"seed": dict, "vary": dict, "count": int}` | `{external_system_ids_sql, rows, lucids, consumerkeys}` (JSON) | NEW — analogous to `recommend_assignment` being the net-new pure function | Pure function in `mockdata_tool.py` |
| `save_mockdata_report` | `{"prompt": str, "external_sql": str, "consumer_sql": str?, "summary": str}` | saved path string | `save_assignment_report` (`mcp_server.py:904-925`) | Writes `mockdata/<MMDDYYSS>.md`; no email registration (SMTP dropped) |

Optional 5th convenience tool `generate_consumer_pii(seed_or_lucid, ...)` → synthetic `consumer_pii` INSERT — or fold it into `generate_mockdata` so a single call returns both SQL blocks given lookup results passed back in. Recommend folding: the agent calls `generate_mockdata`, then `lookup_consumer` per distinct lucid, then a second `generate_mockdata`-style call (or a `generate_consumer_pii(absent_lucids)`) for the missing ones. Keep `mcp_server._dispatch` a flat `if/elif` chain exactly like ticketasg (`:570-954`).

### Q9 — Landmines & pitfalls
See "Common Pitfalls" section below.

---

## Architecture Patterns

### System Architecture Diagram
```
User prompt (seed row + variation intent)
        │
        ▼
[Copilot / Claude]  ── reasons: which columns to vary, how many rows ──┐
        │                                                               │
        │ calls run_tool.py / MCP tools (no LLM inside tools)           │
        ▼                                                               │
ensure_login ──► gcloud_tool.ensure_gcloud_auth("loreal.com")          │
        │         (user creds + ADC; project default = DV)             │
        ▼                                                               │
generate_mockdata(seed, vary, count) ──► mockdata_tool (PURE)          │
        │   emits N external_system_ids INSERT rows (Postgres dialect) │
        │   returns lucids/consumerkeys                                 │
        ▼                                                               │
lookup_consumer(lucid) ──► bigquery_tool.query_bigquery (SELECT only)  │
        │   reads DV consumer_pii ── blocklist guarantees no writes ───┤
        │   0 rows → consumer absent                                    │
        ▼                                                               │
generate_consumer_pii(absent lucids) ──► mockdata_tool (PURE)  ◄────────┘
        │   synthetic fake-PII INSERT (MOCK_DATA markers)
        ▼
save_mockdata_report(prompt, external_sql, consumer_sql, summary)
        │   writes mockdata/<MMDDYYSS>.md  (gitignored)
        ▼
Present SQL to user.  ── NEVER executes INSERT against any DB ──
```
Data-flow note: the **only** arrow that touches a live database is `lookup_consumer → BigQuery (read)`. All INSERT SQL flows to the report file and the user, never to a database.

### Recommended Project Structure
```
mockdata_copilot_agent/
├── __init__.py                     # empty marker (copy)
├── config.py                       # MockDataConfig (output_dir, bq_project=DV) — edited copy
├── run_tool.py                     # CLI dispatch; gcloud+BQ init, no SNOW — edited copy
├── mcp_server.py                   # 4-tool list + flat _dispatch — edited copy
├── AGENTS.md                       # new content, same shape
├── tools/
│   ├── __init__.py                 # empty marker (copy)
│   ├── gcloud_tool.py              # VERBATIM copy
│   ├── bigquery_tool.py            # VERBATIM copy
│   └── mockdata_tool.py            # NEW — pure-function generator
├── mockdata/                       # output dir (gitignored, may contain synthetic PII)
└── .docs/
    ├── external_system_ids mock up.sql   # existing — output contract
    ├── external_system_ids.xlsx          # existing — input layout
    └── consumer_pii.columns.json         # NEW (generated once via INFORMATION_SCHEMA)
.claude/skills/mockdata-copilot/SKILL.md  # NEW companion
.github/agents/mockdata_copilot.agent.md  # NEW companion
```

### Pattern 1: Flat `if/elif` dispatch shared by CLI + MCP
**What:** `run_tool.py` does `from mcp_server import _dispatch` and calls it; `mcp_server.create_mcp_server` wraps the same `_dispatch`. No duplicated routing.
**When to use:** every tool the agent exposes.
**Example:**
```python
# Source: ticketasg_copilot_agent/run_tool.py:104-105 + mcp_server.py:570
from mcp_server import _dispatch
result = asyncio.run(_dispatch(args.tool, arguments, output_dir))
```

### Pattern 2: Project-scoped BQ executor selection
**What:** `_pick_executor(sql)` routes a query to the executor whose project matches the first backtick ref; DV queries bill DV automatically.
**Example:**
```python
# Source: ticketasg_copilot_agent/tools/bigquery_tool.py:455-468
# Use fully-qualified `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`
# so the DV executor is selected.
```

### Anti-Patterns to Avoid
- **Routing generated INSERTs through `query_bigquery`:** they are Postgres dialect AND would be blocklist-rejected. Generated SQL goes to the report file only.
- **Symlinking `gcloud_tool.py`/`bigquery_tool.py`:** creates hidden coupling; copy instead (phase-01 precedent).
- **Hardcoding the DV project inside the copied tool files:** violates CLAUDE.md; set it via `config.py` + `BQ_PROJECT` env default.
- **Treating schema.json's 19 `consumer_pii` columns as complete:** they're a partial RCA-curated list under the PD dataset; confirm against live DV.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| gcloud/ADC auth + interactive login | Custom subprocess auth | reused `gcloud_tool.ensure_gcloud_auth` | Handles user-creds + ADC, domain check, stderr redirection, gcloud PATH fallbacks |
| Read-only BQ safety | Custom SELECT runner | reused `SafeBigQueryExecutor` / `query_bigquery` | Blocklist + dry-run + byte ceiling + row cap + timeout — the safety contract the whole repo depends on |
| xlsx parsing | Custom CSV/zip reader | `openpyxl` (installed) | Handles the `.xlsx` header + seed layout directly |
| CLI ⇆ MCP dual entry | Two routing tables | shared `_dispatch` | One source of truth; ticketasg/rca precedent |

**Key insight:** the entire BigQuery-safety guarantee for this agent comes for free by reusing `bigquery_tool.py` unchanged. Any reimplementation risks weakening the blocklist — explicitly forbidden by CLAUDE.md.

---

## Runtime State Inventory

> This is a greenfield package (new directory), but it reuses two shared modules and adds an output dir. Audited for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — agent stores no datastore keys. Output `mockdata/*.md` is generated artifacts only | none |
| Live service config | DV BigQuery dataset `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public` accessed read-only via ADC | none (read-only) |
| OS-registered state | None | none |
| Secrets/env vars | New optional env vars: `BQ_PROJECT` (default DV), `MOCKDATA_OUTPUT_DIR`. No COOKIE/X_USERTOKEN/SMTP. gcloud ADC unchanged | document in config.py + AGENTS.md |
| Build artifacts | `__pycache__` will appear under the new package (gitignored already via `__pycache__/`) | none |

**Nothing found** in Stored data / OS-registered state — verified by reading CONTEXT.md scope and the reused tools (no datastore writes).

---

## Common Pitfalls

### Pitfall 1: schema.json is partial and PD-scoped
**What goes wrong:** Generating a `consumer_pii` INSERT from schema.json's 19 columns produces an INSERT missing real columns, or with columns that don't exist in the DV table.
**Why it happens:** schema.json lists `consumer_pii` (19 cols) and `external_system_ids` (8 cols) under the **primary PD** dataset as an RCA-curated subset; the DV ASE1 public entry lists only survey tables [VERIFIED].
**How to avoid:** Pin the 21-col external_system_ids from the `.docs` sample; obtain the full DV `consumer_pii` column set via live `INFORMATION_SCHEMA.COLUMNS` once and commit it (Q4).
**Warning signs:** column count mismatch vs the `.docs` sample; BQ "no such field" if the schema were ever used to build a SELECT.

### Pitfall 2: Postgres vs GoogleSQL dialect confusion
**What goes wrong:** Generating GoogleSQL (`CAST(x AS TIMESTAMP)`) when the `.docs` contract is Postgres (`::timestamptz`), or trying to run the generated INSERT through the BigQuery tool.
**Why it happens:** schema.json says GoogleSQL (true for the read path) but the INSERT target is a Postgres source DB.
**How to avoid:** Match the `.docs` sample exactly; keep generated SQL out of `query_bigquery`. Flag A1 for user confirmation.

### Pitfall 3: blocklist false-positive on bare keywords
**What goes wrong:** A lookup query containing an unquoted blocklist word (e.g. a column or alias literally named `MERGE`/`LOAD`) gets rejected.
**Why it happens:** `validate_query` (`:149-167`) strips quoted literals then word-matches `DANGEROUS_KEYWORDS`.
**How to avoid:** Keep the existence query to the clean form in Q3 (verified to pass). Values like `'MOCK_DATA'`, `'MARS_ID'`, brand codes are all quoted literals → stripped → safe.
**Warning signs:** `"Blocked: 'X' statements are not allowed"` on a pure SELECT.

### Pitfall 4: `_PKG_DIR` / CWD-relative paths
**What goes wrong:** Output lands in the wrong directory, or schema.json isn't found, when launched from a different CWD (VS Code).
**Why it happens:** default dirs must resolve from `__file__`, not CWD.
**How to avoid:** Use the `_PKG_DIR = Path(__file__).resolve().parent` pattern (`config.py:26`) for `output_dir`; the reused `bigquery_tool.py:72` `_SCHEMA_JSON` math (`parent.parent.parent`) **was VERIFIED to resolve to the repo-root schema.json from the new package's depth** — do not change the directory nesting.
**Warning signs:** schema.json "not found"; reports written to CWD.

### Pitfall 5: stdout vs stderr for MCP stdio
**What goes wrong:** Any `print()` to stdout in a tool corrupts the MCP JSON-RPC stream.
**Why it happens:** stdio transport uses stdout for protocol.
**How to avoid:** Keep the reused tools' convention — all diagnostics go to stderr (`gcloud_tool.py:78-83`, `run_tool.py:44` logging to stderr). The new `mockdata_tool.py` must return strings, never print.

### Pitfall 6: openpyxl optionality / Excel type coercion
**What goes wrong:** Integer cells (`signature`=1, `recordstatus`=0, `country_iso_3166_1`=360) and ISO-Z datetimes from the xlsx don't match the `.sql` string forms; or openpyxl import fails in a minimal env.
**Why it happens:** Excel stores numbers as numerics and dates as ISO strings with trailing `Z` and microseconds (`2026-06-23T09:48:27.302993Z`).
**How to avoid:** Coerce numerics to the quoted string forms the `.sql` uses; normalize ISO-Z → `'YYYY-MM-DD HH:MM:SS+00'::timestamptz`. Make the xlsx path optional (primary input is pasted JSON) so a missing openpyxl never blocks the core flow. openpyxl 3.1.5 IS installed [VERIFIED].

---

## Code Examples

### Existence lookup (read-only, DV dataset)
```sql
-- Source: derived from bigquery_tool.query_bigquery contract; VERIFIED passes blocklist
SELECT consumerkey, lucid, signature, isocountry, status
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`
WHERE lucid = @lucid AND status = 'Active'
LIMIT 5
```

### Full DV column set (run once, then commit as .docs reference)
```bash
# Source: BigQuery INFORMATION_SCHEMA — VERIFIED query passes blocklist
bq show --schema --format=prettyjson \
  oa-apmena-spacecds-ap-dv:space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii
```

### Generated external_system_ids INSERT (must match this style)
```sql
-- Source: mockdata_copilot_agent/.docs/external_system_ids mock up.sql:25
('1b48bdbb-bdbb-7b6f-0001-000000000011'::uuid, '6d74baaa-baaa-7a19-899c-000000000011'::uuid,
 'VN', '45', 'C2VN00000000010', 'MARS_VN', 'VN011000000001A', 'VN0370', NULL, 'VNPGE450000',
 '1', '1900-01-01 00:00:00+00'::timestamptz, 'Inactive', NULL, 'MOCK_DATA', 'MANUAL',
 '2026-06-19 00:00:00+00'::timestamptz, '2026-06-19 00:00:00+00'::timestamptz, '0', '704', '525699')
```

### Startup project defaulting (config.py owns the project)
```python
# In run_tool.py / mcp_server.main(), BEFORE ensure_gcloud_auth():
import os
from config import load_config
cfg = load_config()
os.environ.setdefault("BQ_PROJECT", cfg.bq_project)  # cfg.bq_project = "oa-apmena-spacecds-ap-dv"
from tools.gcloud_tool import ensure_gcloud_auth
ensure_gcloud_auth("loreal.com")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| rca/ticketasg default project = PD (`oa-apmena-spacecds-ap-pd`) | mockdata defaults to DV (`oa-apmena-spacecds-ap-dv`) | This phase | Only the env/config default differs; tool files unchanged |
| ServiceNow-centric Copilot agents | GCP-only Copilot agent (no SNOW) | This phase | Drops 6 modules + SMTP; 4 tools instead of 19 |

**Deprecated/outdated for this agent:**
- `COOKIE` / `X_USERTOKEN` env vars — not used (no ServiceNow).
- SMTP env vars — not used (no email).

---

## Companion Deliverables (SKILL.md + agent.md)

Mirror the phase-01 companions [VERIFIED: `.claude/skills/ticketasg-copilot/SKILL.md` + `.github/agents/ticketasg_copilot.agent.md`]:
- **`.claude/skills/mockdata-copilot/SKILL.md`** — YAML frontmatter (`name`, `description`, `invocation: /mockdata-copilot`, the same `tools: [...]` execute list), then `## ABSOLUTE TOOL RESTRICTION` mandating `run_in_terminal` → `python mockdata_copilot_agent/run_tool.py <tool> --json '...'`, a tool→CLI mapping table for the 4 tools, and a mandatory sequence (ensure_login → generate_mockdata → lookup_consumer per lucid → generate_consumer_pii for absentees → save_mockdata_report → present SQL with the "review & run manually" reminder).
- **`.github/agents/mockdata_copilot.agent.md`** — identical YAML `name`/`description`/`tools` block (no `invocation` key — agent.md omits it per phase-01), same ABSOLUTE TOOL RESTRICTION + CLI mapping.

Both must state plainly: **the agent presents SQL and never executes writes.**

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Generated INSERTs target a Postgres source/staging DB (hence `::uuid`/`::timestamptz`), not BigQuery | Q5 / Pitfall 2 | If target is actually GoogleSQL, every generated INSERT has wrong cast syntax |
| A2 | schema.json's 19 `consumer_pii` columns are a partial subset; full DV column set differs | Q4 / Pitfall 1 | Synthetic consumer_pii INSERT has missing/extra columns |
| A3 | DV `consumer_pii` has the same schema as primary ("same schema as primary" note in schema.json) | Q3/Q4 | Lookup or INSERT column names wrong for DV |
| A4 | `lucid` (+ optional `consumerkey`) is the right existence key for consumer_pii | Q3 | False negatives/positives in existence check → unnecessary or missing consumer_pii rows |
| A5 | Synthetic UUID family pattern (`1b48bdbb-…` / `6d74baaa-…`) is a convention to keep, and the trailing 12-digit counter is the uniqueness mechanism for `extsystemidskey` | Q6 | PK collisions or unrecognizable mock data |
| A6 | `MMDDYYSS` = MMDDYY + 2-digit sequence (not literal seconds) | Q7 | File-naming mismatch vs user expectation |
| A7 | Primary seed input is pasted JSON; xlsx is a convenience path | Q6 | Over-engineering xlsx parsing if user always pastes |
| A8 | `MOCK_DATA`/`MANUAL` provenance markers must be preserved verbatim in every generated row | Q6 | Mock rows indistinguishable from real data |
| A9 | Synthetic consumer_pii must use obviously-fake PII (`mock+<id>@example.com`, fake names) per CONTEXT | Q8 | Accidental real-PII-shaped data |

**These need user confirmation before the planner locks them into tasks** — especially A1 (dialect), A2/A3 (DV schema), and A4 (existence key).

---

## Open Questions

1. **SQL dialect target (A1).**
   - What we know: `.docs` sample is Postgres; schema.json read-path is GoogleSQL.
   - What's unclear: which DB the user runs the generated INSERTs against.
   - Recommendation: match `.docs` exactly (Postgres); add a `[USER-CONFIRM]` note in the report header.

2. **Full DV `consumer_pii` column set (A2/A3).**
   - What we know: 19 columns in schema.json (PD, partial).
   - What's unclear: complete DV column list + types.
   - Recommendation: generate once via `INFORMATION_SCHEMA.COLUMNS`/`bq show --schema` during a wave that has ADC; commit as `.docs/consumer_pii.columns.json`.

3. **Existence key (A4).**
   - What we know: CONTEXT says "keyed by `lucid` (and/or `consumerkey`)".
   - What's unclear: whether lucid alone is unique enough in DV (lucid is NOT unique across brands per ticketasg AGENTS.md query rule 4).
   - Recommendation: key on `lucid` + (when seed provides them) `signature` + `isocountry`, mirroring the repo's documented BQ query rule.

4. **Variation strategy specifics (Claude's discretion).**
   - Recommendation: deterministic increment of trailing UUID counter for `extsystemidskey`; cycle/list for `signature`; suffix-increment for `sourceconsumerid`. Confirm with a sample output against the worked example before locking.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | ✓ | 3.13.7 (per phase-01) | — |
| `google-cloud-bigquery` | bigquery_tool.py | ✓ | 3.41.0 | — |
| `openpyxl` | xlsx seed parsing | ✓ | 3.1.5 (VERIFIED this session) | Accept pasted JSON seed instead |
| `mcp` | mcp_server.py (optional) | ✓ | 1.27.0 | run_tool.py works without MCP |
| gcloud CLI + ADC | gcloud_tool.py, live lookup | Requires `gcloud auth application-default login` | — | Generation works offline; only the consumer_pii lookup needs ADC — degrade by treating consumers as "unknown" and emitting consumer_pii rows for all, flagged for manual verification |
| `bq` CLI | bigquery_tool._bq_cli_execute + schema fetch | Bundled with gcloud SDK | — | Python client path (`SafeBigQueryExecutor.execute`) is the fallback |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** gcloud ADC (lookup degrades gracefully); openpyxl (paste seed instead).

---

## Validation Architecture

> No `.planning/config.json` in this repo — treat `nyquist_validation` as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected at repo root (phase-01 added `ticketasg_copilot_agent/test_config.py` as a standalone script, no pytest.ini) |
| Config file | none — Wave 0 may `pip install pytest` and add `mockdata_copilot_agent/tests/` |
| Quick run command | `python -m pytest mockdata_copilot_agent/ -x -q` (after framework install) |
| Full suite command | `python -m pytest mockdata_copilot_agent/ -v` |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| MD-04 | `generate_external_system_ids(seed, vary, count)` returns N rows; varied columns differ, others equal seed | unit | `pytest mockdata_copilot_agent/tests/test_mockdata_tool.py::test_row_count_and_variation -x` | ❌ Wave 0 |
| MD-04 | every generated `extsystemidskey` is unique | unit | `…::test_extsystemidskey_unique` | ❌ Wave 0 |
| MD-06 | generated SQL matches `.docs` style (Postgres casts, MOCK_DATA/MANUAL markers, NULL for empties) | unit (golden-string) | `…::test_sql_matches_docs_style` | ❌ Wave 0 |
| MD-06 | empty/None seed cells render as bare `NULL` (no cast, no quotes) | unit | `…::test_null_mapping` | ❌ Wave 0 |
| MD-05 | synthetic `consumer_pii` INSERT uses fake PII + MOCK_DATA markers; full column list | unit | `…::test_consumer_pii_synthetic` | ❌ Wave 0 |
| MD-03 | the consumer_pii lookup query passes the blocklist; an INSERT is rejected | unit | `pytest …/tests/test_blocklist.py::test_lookup_passes_insert_blocked` | ❌ Wave 0 (VERIFIED manually this session) |
| MD-02 | startup sets `BQ_PROJECT` default to DV before auth | unit | `…/tests/test_config.py::test_dv_project_default` | ❌ Wave 0 |
| MD-07 | output filename `MMDDYYSS`; collision picks next sequence | unit | `…/tests/test_report.py::test_filename_collision` | ❌ Wave 0 |
| MD-03 | live lookup returns existence (live) | smoke (needs ADC) | manual `run_tool.py lookup_consumer --json '{"lucid":"…"}'` | manual |

### Sampling Rate
- **Per task commit:** `python -m pytest mockdata_copilot_agent/ -x -q`
- **Per wave merge:** `python -m pytest mockdata_copilot_agent/ -v`
- **Phase gate:** full unit suite green; one manual smoke of `lookup_consumer` with ADC.

### Wave 0 Gaps
- [ ] `mockdata_copilot_agent/tests/__init__.py` + `test_mockdata_tool.py` — MD-04, MD-06
- [ ] `tests/test_blocklist.py` — MD-03 (lookup passes / INSERT blocked)
- [ ] `tests/test_config.py` — MD-02 (DV project default)
- [ ] `tests/test_report.py` — MD-07 (filename collision)
- [ ] Framework install: `pip install pytest` (not in requirements.txt per phase-01)
- [ ] Commit `.docs/consumer_pii.columns.json` (one-time INFORMATION_SCHEMA fetch) — needed before MD-05 golden tests are meaningful

---

## Security Domain

> No formal `security_enforcement` flag (no config.json). Included because the phase touches PII-shaped data + a live datastore.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | gcloud ADC via reused `gcloud_tool.ensure_gcloud_auth` — no credentials in code/.env |
| V3 Session Management | no | No sessions; ADC tokens managed by gcloud |
| V4 Access Control | yes | BigQuery IAM (dataViewer + jobUser only, per bigquery_tool docstring) — read-only |
| V5 Input Validation | yes | `validate_query` blocklist + must-start-SELECT/WITH on every BQ call |
| V6 Cryptography | no | No crypto introduced; never hand-roll |
| V7 Data Protection (PII) | yes | Synthetic PII only (`mock+<id>@example.com`, fake names, MOCK_DATA markers); `mockdata/` gitignored; never stage |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental write to BigQuery | Tampering | Blocklist rejects INSERT/MERGE; generated SQL never routed through the tool |
| Real PII leakage into committed mock data | Information Disclosure | Fake-PII generator + `mockdata/` gitignore + "never stage" rule |
| SQL injection via seed values | Tampering | Generated SQL is presented (not executed); lookup SELECT uses fixed structure / parameterizable lucid |
| Credential leakage | Information Disclosure | gcloud ADC only; no COOKIE/SMTP; no credential files |

---

## Sources

### Primary (HIGH confidence)
- `ticketasg_copilot_agent/config.py` — config dataclass + `_PKG_DIR` pattern [VERIFIED: file read]
- `ticketasg_copilot_agent/run_tool.py` — CLI startup sequence + shared `_dispatch` [VERIFIED: file read]
- `ticketasg_copilot_agent/mcp_server.py` — 19-tool list + flat `_dispatch` + startup [VERIFIED: file read]
- `ticketasg_copilot_agent/tools/gcloud_tool.py` — `ensure_gcloud_auth`, `set_project`/`set_quota_project` BQ_PROJECT defaults [VERIFIED: file read]
- `ticketasg_copilot_agent/tools/bigquery_tool.py` — `SafeBigQueryExecutor`, blocklist, `_pick_executor`, `_SCHEMA_JSON` path [VERIFIED: file read + path math run]
- `ticketasg_copilot_agent/AGENTS.md` — companion doc shape + DV dataset table + query rules [VERIFIED: file read]
- `mockdata_copilot_agent/.docs/external_system_ids mock up.sql` — 21-col Postgres INSERT contract [VERIFIED: file read]
- `mockdata_copilot_agent/.docs/external_system_ids.xlsx` — 21-col header + seed row [VERIFIED: openpyxl read this session]
- `schema.json` — dialect=GoogleSQL, partial consumer_pii (19)/external_system_ids (8) cols, DV additional_datasets [VERIFIED: python inspection this session]
- `.gitignore` — PII output-dir block; `mockdata/` NOT yet present [VERIFIED: file read]
- `.claude/skills/ticketasg-copilot/SKILL.md` + `.github/agents/ticketasg_copilot.agent.md` — companion format [VERIFIED: file read]
- `.planning/phases/phase-kayinleong-01/01-RESEARCH.md` + `01-PLAN-wave1.md` — repo wave/plan format precedent [VERIFIED: file read]
- Blocklist + schema-path behavior — [VERIFIED: re-implemented `validate_query` and ran the existence + INFORMATION_SCHEMA queries through it this session; both pass; path resolves to repo-root schema.json]

### Secondary (MEDIUM confidence)
- DV `consumer_pii` having "same schema as primary" — [CITED: schema.json additional_datasets note] — not confirmed against live table.

### Tertiary (LOW confidence / ASSUMED)
- SQL dialect target being Postgres source DB [ASSUMED from `.docs` cast syntax].
- Variation-increment specifics [ASSUMED — Claude's discretion per CONTEXT].

---

## Metadata

**Confidence breakdown:**
- Reuse map: HIGH — every source file read; cross-import absence verified.
- GCP login + project defaulting: HIGH — call sites + env-default logic read directly.
- Read-only lookup + blocklist: HIGH — blocklist re-run this session; existence query verified to pass.
- Full consumer_pii schema: MEDIUM — schema.json partial; full DV set needs one live fetch.
- SQL dialect: MEDIUM-LOW — contract is clear (`.docs`), but target DB is an assumption.
- Generation algorithm: HIGH on structure (sample + xlsx verified), MEDIUM on increment specifics (discretion).
- Output naming / gitignore: HIGH — `.gitignore` read; `mockdata/` confirmed absent.

**Research date:** 2026-06-24
**Valid until:** 2026-07-24 (stable codebase; A1/A2/A3/A4 need user confirmation regardless of date)

---

## RESEARCH COMPLETE
