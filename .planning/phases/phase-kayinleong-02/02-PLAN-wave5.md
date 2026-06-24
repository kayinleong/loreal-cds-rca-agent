---
wave: 5
depends_on: [wave4]
files_modified:
  - mockdata_copilot_agent/AGENTS.md
  - .claude/skills/mockdata-copilot/SKILL.md
  - .github/agents/mockdata_copilot.agent.md
autonomous: true
requirements:
  - phase-kayinleong-02
must_haves:
  - AGENTS.md documents all 4 tool names with when-to-use guidance, the DV project/dataset, and the "presents SQL, never executes writes" rule
  - SKILL.md has valid YAML frontmatter with name, description, invocation: /mockdata-copilot
  - mockdata_copilot.agent.md has valid YAML frontmatter with name and tools list (no invocation key)
  - Both companion files include the MANDATORY SEQUENCE (ensure_login → generate_mockdata → lookup_consumer per lucid → generate consumer_pii for absentees → save_mockdata_report → present SQL with the review-&-run-manually reminder)
  - SKILL.md tool table lists all 4 tools with exact run_tool.py commands
  - Final integration smoke passes: run_tool.py --help exits 0; generate_mockdata + save_mockdata_report produce a mockdata/<MMDDYYSS>.md; no cross-package imports
---

<objective>
Create the two companion definitions (`SKILL.md` for Claude Code, `agent.md` for GitHub Copilot)
plus the package `AGENTS.md`, mirroring the phase-01 ticketasg companions, and run the final
end-to-end integration smoke (offline where possible, with a single optional live
`lookup_consumer` smoke if ADC is present). All companions state plainly: the agent presents SQL
and never executes writes.

Purpose: Without these files the tooling exists but no AI client can drive it. This wave is the
interface between the Wave 3-4 tool layer and Copilot/Claude, and the final gate before the user
invokes the agent.

Output: 3 files — `mockdata_copilot_agent/AGENTS.md`,
`.claude/skills/mockdata-copilot/SKILL.md`, `.github/agents/mockdata_copilot.agent.md`.

## Artifacts this wave produces
- New files: `mockdata_copilot_agent/AGENTS.md`,
  `.claude/skills/mockdata-copilot/SKILL.md`, `.github/agents/mockdata_copilot.agent.md`
- Companion invocation: `/mockdata-copilot` (SKILL) and the GitHub agent definition
- No new code, no new config — verification + docs only

## Assumptions restated for the user checkpoint (do NOT drop)
- [A1] dialect = Postgres (`::uuid`/`::timestamptz`) matching the `.docs` sample — confirm the
  generated INSERTs run against the Postgres source/staging DB, not BigQuery.
- [A2/A3] full DV `consumer_pii` columns — confirm `.docs/consumer_pii.columns.json` is
  live-acquired (`confirmed: true`); if `false`, re-run with ADC before production.
- [A4] existence key = `lucid` (+ optional `consumerkey`/`signature`/`isocountry`) — confirm
  lucid disambiguation is sufficient for the DV table.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/CLAUDE.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-CONTEXT.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-RESEARCH.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/ticketasg_copilot_agent/AGENTS.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.claude/skills/ticketasg-copilot/SKILL.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.github/agents/ticketasg_copilot.agent.md

<interfaces>
<!-- 4 tool names for the doc tables -->
ensure_login, lookup_consumer, generate_mockdata, save_mockdata_report

<!-- Mandatory sequence (per-prompt flow from CONTEXT.md) -->
1. ensure_login                          (GCP login: gcloud user creds + ADC; project = DV)
2. generate_mockdata                     (N external_system_ids rows; returns lucids/consumerkeys)
3. lookup_consumer per distinct lucid     (read-only existence check; collect absent lucids)
4. generate_mockdata with absent_lucids   (adds consumer_pii INSERTs for absent consumers)
5. save_mockdata_report                   (writes mockdata/<MMDDYYSS>.md)
6. Present the SQL with the reminder: review & run manually; agent never executes writes
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create AGENTS.md, SKILL.md, and mockdata_copilot.agent.md</name>
  <files>
    mockdata_copilot_agent/AGENTS.md
    .claude/skills/mockdata-copilot/SKILL.md
    .github/agents/mockdata_copilot.agent.md
  </files>
  <read_first>
    ticketasg_copilot_agent/AGENTS.md — structural template (Purpose / Tool Inventory / Mandatory Sequence / Running Without MCP / Environment Setup)
    .claude/skills/ticketasg-copilot/SKILL.md — SKILL.md structure + YAML frontmatter + tool-invocation table
    .github/agents/ticketasg_copilot.agent.md — agent.md structure + YAML frontmatter (no invocation key) + ABSOLUTE TOOL RESTRICTION + CLI mapping
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 494-501 — companion deliverables shape (SKILL.md + agent.md)
  </read_first>
  <action>
**Create `mockdata_copilot_agent/AGENTS.md`** — follow the ticketasg structure; replace all
ServiceNow/assignment content with mock-data content. Sections:
  - `# AGENTS.md — Mock Data Copilot Agent` + the "instruction schema; all LLM reasoning stays
    in the client; this server exposes only pure-function tools" header.
  - `## Purpose` — Generate mock `external_system_ids` (and conditional `consumer_pii`) SQL for
    the L'Oreal CDS B2C DV (SEA) replica and PRESENT it. State plainly: the agent NEVER executes
    writes; the only live BigQuery access is the read-only `consumer_pii` existence lookup. GCP
    target: project `oa-apmena-spacecds-ap-dv`, dataset `space_cds_b2c_ds_replica_ase1_dv_public`.
  - `## Tool Inventory` table (4 rows):
    | Tool | When to use |
    | `ensure_login` | Ensure L'Oreal GCP login (gcloud user creds + ADC); default project = DV |
    | `generate_mockdata` | CORE — clone the seed into N external_system_ids rows; optionally add consumer_pii rows for absent lucids |
    | `lookup_consumer` | Read-only consumer_pii existence check against the DV dataset |
    | `save_mockdata_report` | MANDATORY — write mockdata/<MMDDYYSS>.md and present the SQL |
  - `## GCP Target` — project/dataset; gcloud ADC only (`gcloud auth application-default login`);
    NO COOKIE/X_USERTOKEN, NO SMTP.
  - `## Mock-Data Workflow` — the 6-step Mandatory Sequence from the interfaces block.
  - `## Running Without MCP (Skills / CLI Mode)` — the 4 `run_tool.py` example commands.
  - `## Assumptions to confirm` — A1 (Postgres dialect), A2/A3 (DV consumer_pii columns), A4
    (existence key = lucid). Each flagged `[USER-CONFIRM]`.
  - A closing reminder block: "This agent presents SQL only. Review and run the generated
    INSERTs manually against the Postgres source DB. mockdata/ is gitignored — never stage it."

**Create `.claude/skills/mockdata-copilot/SKILL.md`** — YAML frontmatter EXACTLY:
```yaml
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
```
Body sections (mirror ticketasg SKILL.md):
  - `## Mock Data Copilot Skill — No-MCP Mode` brief intro.
  - `## Prerequisites` — `.venv` activated; `gcloud auth application-default login` (for the
    read-only lookup); `schema.json` present in repo root; NO `.env` COOKIE/X_USERTOKEN needed.
  - `## ABSOLUTE TOOL RESTRICTION` — you MUST use the Bash/`run_in_terminal` tool to call
    `python mockdata_copilot_agent/run_tool.py <tool> --json '<JSON>'` for all data operations.
  - `## Tool Invocation Reference` table (all 4 tools) with exact commands:
    | Ensure GCP login | `python mockdata_copilot_agent/run_tool.py ensure_login --json '{}'` |
    | Generate mock rows (CORE) | `python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {...}, "vary": {"signature": ["45","01"]}, "count": 2}'` |
    | Check consumer (read-only) | `python mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "C2ID00000000010"}'` |
    | Save report (MANDATORY) | `python mockdata_copilot_agent/run_tool.py save_mockdata_report --json '{"prompt": "...", "external_sql": "...", "consumer_sql": "...", "summary": "..."}'` |
  - `## Mock-Data Workflow (No-MCP)` — Step 0 intent detection (seed pasted as JSON vs xlsx
    path; how many rows; which columns to vary), then Steps 1-6 = the Mandatory Sequence.
  - `## Output Rules` — present the generated SQL; ALWAYS append `Report saved: <path>`; never
    claim the SQL was executed; show the "review & run manually" reminder.
  - `## Analysis Rules` — only use data from Bash tool outputs; synthetic fake PII only; the
    generated INSERTs are Postgres-dialect [A1 USER-CONFIRM]; the agent never runs writes.

**Create `.github/agents/mockdata_copilot.agent.md`** — YAML frontmatter EXACTLY (NO
`invocation` key — agent.md omits it per phase-01):
```yaml
---
name: Mock Data Copilot Agent
description: >
  Mock-data SQL generator for the L'Oreal CDS B2C DV (SEA) replica.
  Clones a seed external_system_ids row into N varied rows, checks each consumer in
  consumer_pii (read-only), generates synthetic consumer_pii rows for absentees, and writes
  the SQL to mockdata/<MMDDYYSS>.md. PRESENTS SQL only — never executes writes.
  Uses run_tool.py CLI — no MCP server required.
tools:
  [
    execute/runNotebookCell,
    execute/executionSubagent,
    execute/getTerminalOutput,
    execute/killTerminal,
    execute/sendToTerminal,
    execute/createAndRunTask,
    execute/runInTerminal,
    execute/runTests,
  ]
---
```
Body: `## ABSOLUTE TOOL RESTRICTION (READ THIS FIRST)` — use `run_in_terminal` to call
`mockdata_copilot_agent/run_tool.py` for all data operations; the same 4-tool CLI mapping table
as SKILL.md; then `**MANDATORY SEQUENCE — no exceptions:**` listing the 6 steps; and a
`## Output Rules` / `## Analysis Rules` section. State plainly the agent presents SQL and never
executes writes; mockdata/ is gitignored and must never be staged.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import re, pathlib
skill = pathlib.Path('.claude/skills/mockdata-copilot/SKILL.md').read_text()
assert re.match(r'^---\n.*?\n---', skill, re.DOTALL), 'SKILL.md no YAML frontmatter'
assert 'name: mockdata-copilot' in skill
assert 'invocation: /mockdata-copilot' in skill
for t in ('ensure_login','lookup_consumer','generate_mockdata','save_mockdata_report'):
    assert t in skill, f'SKILL.md missing {t}'
agent = pathlib.Path('.github/agents/mockdata_copilot.agent.md').read_text()
assert 'name: Mock Data Copilot Agent' in agent
assert 'execute/runInTerminal' in agent
assert 'MANDATORY SEQUENCE' in agent
assert 'invocation:' not in agent.split('---')[1], 'agent.md must NOT have invocation key in frontmatter'
ag = pathlib.Path('mockdata_copilot_agent/AGENTS.md').read_text()
for t in ('ensure_login','lookup_consumer','generate_mockdata','save_mockdata_report'):
    assert t in ag, f'AGENTS.md missing {t}'
assert 'oa-apmena-spacecds-ap-dv' in ag
assert 'never executes writes' in ag.lower() or 'never execute writes' in ag.lower()
print('companions OK')
"</automated>
  </verify>
  <done>
    All 3 files exist. `SKILL.md` has valid YAML with `name: mockdata-copilot` and
    `invocation: /mockdata-copilot` and lists all 4 tools. `mockdata_copilot.agent.md` has
    `name: Mock Data Copilot Agent`, `execute/runInTerminal`, `MANDATORY SEQUENCE`, and NO
    `invocation:` key in its frontmatter. `AGENTS.md` documents all 4 tools, names the DV
    project `oa-apmena-spacecds-ap-dv`, and states the agent never executes writes.
  </done>
</task>

<task type="auto">
  <name>Task 2: Final integration smoke (offline + optional live lookup) and no-cross-import check</name>
  <files></files>
  <read_first>
    mockdata_copilot_agent/run_tool.py — confirm sys.path.insert + _dispatch import
    mockdata_copilot_agent/mcp_server.py — confirm 4-tool _dispatch
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 583-588 — sampling rate / phase gate (full unit suite + one manual lookup smoke)
  </read_first>
  <action>
This task makes NO file changes. Run the full end-to-end smoke. Fix any failure in the OWNING
wave's file (not here), then re-run.

**Check 1 — All required files exist** (10 files):
```
mockdata_copilot_agent/__init__.py
mockdata_copilot_agent/config.py
mockdata_copilot_agent/mcp_server.py
mockdata_copilot_agent/run_tool.py
mockdata_copilot_agent/tools/__init__.py
mockdata_copilot_agent/tools/gcloud_tool.py
mockdata_copilot_agent/tools/bigquery_tool.py
mockdata_copilot_agent/tools/mockdata_tool.py
mockdata_copilot_agent/.docs/consumer_pii.columns.json
mockdata_copilot_agent/AGENTS.md
```
plus `.claude/skills/mockdata-copilot/SKILL.md` and `.github/agents/mockdata_copilot.agent.md`.

**Check 2 — No cross-package imports:** `grep -rn "rca_copilot_agent\|ticketasg_copilot_agent"
mockdata_copilot_agent/` returns empty (comments allowed, code imports are bugs).

**Check 3 — `run_tool.py --help` exits 0** and prints "mockdata_copilot_agent".

**Check 4 — offline generate → save round-trip via the CLI:** run `generate_mockdata` for 3
rows varying `signature`, pipe the `external_system_ids_sql` into `save_mockdata_report`, and
confirm a `mockdata/<8 digits>.md` file is created containing the prompt, the INSERT block, the
Summary, and the "does not execute writes" reminder. Confirm the file path matches the
`MMDDYYSS` pattern and a second save in the same day produces a DIFFERENT sequence suffix
(collision handling).

**Check 5 — gitignore honored:** `git check-ignore mockdata_copilot_agent/mockdata/<the file>`
returns the path (i.e. it IS ignored). Confirm `git status --porcelain` does NOT list any file
under a `mockdata/` directory.

**Check 6 (optional, needs ADC) — live lookup smoke:** `python
mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "<a real DV lucid>"}'`
returns JSON with an `exists` boolean and does NOT error on the blocklist. Skip if no ADC;
record as "manual/skipped" in the SUMMARY.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && \
for f in mockdata_copilot_agent/__init__.py mockdata_copilot_agent/config.py mockdata_copilot_agent/mcp_server.py mockdata_copilot_agent/run_tool.py mockdata_copilot_agent/tools/__init__.py mockdata_copilot_agent/tools/gcloud_tool.py mockdata_copilot_agent/tools/bigquery_tool.py mockdata_copilot_agent/tools/mockdata_tool.py "mockdata_copilot_agent/.docs/consumer_pii.columns.json" mockdata_copilot_agent/AGENTS.md .claude/skills/mockdata-copilot/SKILL.md .github/agents/mockdata_copilot.agent.md; do test -f "$f" || { echo "MISSING: $f"; exit 1; }; done && \
test -z "$(grep -rn 'rca_copilot_agent\|ticketasg_copilot_agent' mockdata_copilot_agent/)" && echo "no cross-import OK" && \
python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {"extsystemidskey":"1b48bdbb-bdbb-7b6f-0003-000000000033","consumerkey":"6d74baaa-baaa-7a19-899c-000000000032","isocountry":"ID","signature":1,"lucid":"C2ID00000000010","sourceconsumerid":"ID011000000001C","createddatetime":"1900-01-01T00:00:00Z","createdsourcesystemid":"MOCK_DATA","lastupdatedsourcesystemid":"MANUAL"}, "vary": {"signature": ["45","01","24"]}, "count": 3}' 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); assert d['external_system_ids_sql'].startswith('INSERT INTO external_system_ids ('); assert len(d['rows'])==3; print('integration smoke PASS')"</automated>
  </verify>
  <done>
    All 12 files exist. `grep -rn "rca_copilot_agent|ticketasg_copilot_agent"
    mockdata_copilot_agent/` is empty. `run_tool.py --help` exits 0. The offline
    `generate_mockdata` → `save_mockdata_report` round-trip writes a `mockdata/<8 digits>.md`
    with prompt + INSERT block + Summary + "does not execute writes" reminder; a second same-day
    save uses a different sequence suffix. `git check-ignore` confirms the report file is
    gitignored and `git status --porcelain` lists nothing under `mockdata/`. The live
    `lookup_consumer` smoke either passes (ADC present) or is recorded as manual/skipped.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Complete `mockdata_copilot_agent` package:
    - Python files: `__init__.py`, `config.py` (MockDataConfig, DV defaults), `mcp_server.py`
      (4 tools), `run_tool.py` (CLI), `tools/__init__.py`, `tools/gcloud_tool.py` (verbatim),
      `tools/bigquery_tool.py` (verbatim, blocklist intact), `tools/mockdata_tool.py` (pure)
    - `.docs/consumer_pii.columns.json` (pinned DV column set)
    - `AGENTS.md`, `.claude/skills/mockdata-copilot/SKILL.md`,
      `.github/agents/mockdata_copilot.agent.md`
    - `.gitignore` updated with `mockdata/`
  </what-built>
  <how-to-verify>
    1. Generate mock rows (offline — no ADC needed):
       ```bash
       python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {"extsystemidskey":"1b48bdbb-bdbb-7b6f-0003-000000000033","consumerkey":"6d74baaa-baaa-7a19-899c-000000000032","isocountry":"ID","signature":1,"lucid":"C2ID00000000010","sourceconsumerid":"ID011000000001C","creationlocationid":"ID0160","locationid":null,"creationsalesrepid":"IDPGE450000","salesrepid":0,"createddatetime":"1900-01-01T00:00:00Z","status":"Close","lastlogindatetime":null,"createdsourcesystemid":"MOCK_DATA","lastupdatedsourcesystemid":"MANUAL","syscreateddatetime":"2026-06-19T00:00:00Z","sysupdatedatetime":"2026-06-23T09:48:27.302993Z","recordstatus":0,"country_iso_3166_1":360,"consumersourcekey":526979}, "vary": {"signature": ["45","01","24"], "sourceconsumerid": "increment"}, "count": 3}'
       ```
       Expected: JSON with an `external_system_ids_sql` INSERT block of 3 rows, each with a
       unique `extsystemidskey`, varied `signature`, and Postgres `::uuid`/`::timestamptz` casts.
       Compare against `mockdata_copilot_agent/.docs/external_system_ids mock up.sql` style.

    2. Save the report and inspect it:
       ```bash
       python mockdata_copilot_agent/run_tool.py save_mockdata_report --json '{"prompt": "create mock data with different signature and sourceconsumerid, 3 rows", "external_sql": "<paste external_system_ids_sql>", "summary": "3 rows; varied signature + sourceconsumerid"}'
       cat mockdata_copilot_agent/mockdata/*.md
       ```
       Expected: a `mockdata/<MMDDYYSS>.md` with `## Prompt`, `## external_system_ids`,
       `## consumer_pii`, `## Summary`, the "review & run manually / does not execute writes"
       reminder, and the `[A1 USER-CONFIRM]` Postgres-dialect note.

    3. [A2/A3 USER-CONFIRM] Open `mockdata_copilot_agent/.docs/consumer_pii.columns.json`:
       - Is `confirmed: true` (live-acquired)? If `false`, re-run the INFORMATION_SCHEMA fetch
         with ADC before production so synthetic `consumer_pii` INSERTs use the real DV columns.

    4. [A1 / A4 USER-CONFIRM] Confirm:
       - Generated INSERTs are run against the Postgres source/staging DB (the `::uuid`/
         `::timestamptz` dialect), NOT BigQuery. (A1)
       - `lucid` (+ optional `consumerkey`/`signature`/`isocountry`) is the right existence key
         for the DV `consumer_pii` table. (A4)

    5. (Optional, needs ADC) Live read-only lookup:
       ```bash
       python mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "<a real DV lucid>"}'
       ```
       Expected: JSON with an `exists` boolean; no write is performed.
  </how-to-verify>
  <resume-signal>
    Type "approved" when verification passes, or describe any issues found (SQL style mismatch,
    wrong consumer_pii columns, dialect/existence-key assumptions to change).
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| agent instruction → LLM | SKILL.md / agent.md / AGENTS.md instruct the LLM; no code execution risk |
| SKILL.md Bash calls → run_tool.py | CLI invocations; arguments passed as JSON strings |
| generated report → git | `mockdata/<MMDDYYSS>.md` may contain synthetic PII; gitignore + "never stage" rule prevent commits |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave5-01 | Repudiation | A1/A2/A3/A4 assumptions in companions | accept | Assumptions are flagged `[USER-CONFIRM]` in AGENTS.md + SKILL.md; the human-verify checkpoint is mandatory before production use |
| T-wave5-02 | Information Disclosure | mockdata/ report in git | mitigate | Wave-1 `.gitignore` line `mockdata/`; Check 5 verifies `git check-ignore`; companions repeat the "never stage" rule |
| T-wave5-03 | Elevation of Privilege | agent instructions implying execution | mitigate | All 3 companions state the agent presents SQL only and never executes writes; the only live access is the read-only lookup |
| T-wave5-SC | Tampering | npm/pip installs | accept | No new packages introduced this phase (02-RESEARCH Package Legitimacy Audit: none); all imports already installed; no install task exists |
</threat_model>

<verification>
From repo root (all must pass before the wave is complete):
1. `python mockdata_copilot_agent/run_tool.py --help` — exit 0, prints "mockdata_copilot_agent"
2. `cat .claude/skills/mockdata-copilot/SKILL.md | grep "invocation"` — returns `invocation: /mockdata-copilot`
3. `cat .github/agents/mockdata_copilot.agent.md | grep "name:"` — returns `name: Mock Data Copilot Agent`
4. `grep -rn "rca_copilot_agent\|ticketasg_copilot_agent" mockdata_copilot_agent/` — empty
5. offline `generate_mockdata` (count=3) → 3 rows, unique `extsystemidskey`, INSERT block starts with `INSERT INTO external_system_ids (`
6. `git check-ignore mockdata_copilot_agent/mockdata/<generated file>` — returns the path (ignored)
</verification>

<success_criteria>
- SKILL.md is discoverable by Claude Code at `/mockdata-copilot`
- All companion files reference `mockdata_copilot_agent/run_tool.py` (not rca/ticketasg)
- AGENTS.md documents all 4 tool names, the DV project/dataset, and the "presents SQL, never executes writes" rule
- MANDATORY SEQUENCE present in both the GitHub agent and the Claude skill
- Full integration smoke passes offline; `mockdata/<MMDDYYSS>.md` is produced and gitignored
- Assumptions A1/A2/A3/A4 are surfaced for the user at the human-verify checkpoint
- Human checkpoint approved (dialect, consumer_pii columns, existence key confirmed or updated)
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-02/phase-kayinleong-02-wave5-SUMMARY.md`

Also update `.planning/phases/phase-kayinleong-02/CLAIM.md` (if present):
- status: done
- "## What Has Changed" — list all new files across waves 1-5
- "## Verification" — paste the integration smoke output confirming all checks pass
</output>