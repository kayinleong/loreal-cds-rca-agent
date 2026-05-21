---
slug: quick-kayinleong-024
status: complete
claim: ticketasg_copilot_agent — RCA-parity with rca_copilot_agent + CDS Incident Handling Guidebook integration
date: 2026-05-21
---

# Summary — quick-kayinleong-024

`ticketasg_copilot_agent` was a routing agent that mimicked the rca_copilot RCA template but did not actually investigate root cause — it had no BigQuery access, no attachment downloads, and its prompt knew nothing about the migrated-vs-ongoing distinction that drives almost every SPACE CDS incident. This claim closes that gap.

After this claim, ticketasg produces the **same** RCA report `rca_copilot_agent` produces (`### WHAT HAPPENED / ### WHAT WE CHECKED / ### WHAT WE FOUND / ### WHAT WE NEED / DID`) with an additional `### REASSIGNMENT DECISION` section appended as the LAST section. The reassignment section is always present — body varies based on whether reassignment is needed.

## Trigger

User asked:

> the ticketasg_copilot_agent will generate rca but not the rca that is generated in rca_copilot_agent. I want the ticketasg_copilot_agent to generate a rca just like in rca_copilot_agent, then add in reassignment grouping (if needed) in rca last session. Also improve the ticketasg_copilot_agent by read the CDS_Incident_Handling_Guidebook 2.docx: (1) generate a research md, (2) improve the ticketasg_copilot_agent.

## Files changed

| File | Diff |
|---|---|
| `ticketasg_copilot_agent/mcp_server.py` | +132 / -10 (5 new tools, attachment auto-download in analyze_incident, JSON-RPC fallback, docstring) |
| `ticketasg_copilot_agent/AGENTS.md` | +280 / -55 (guidebook content + new report template + BigQuery reference + common root causes + identifier mappings) |
| `.claude/skills/ticketasg-copilot/SKILL.md` | +145 / -45 (guidebook quick-ref + 3-question framework step + BQ step + new report template + description) |
| `.github/agents/ticketasg_copilot.agent.md` | +130 / -45 (same shape as SKILL.md, terminal-first) |
| `.planning/quick/quick-kayinleong-024/RESEARCH.md` | new — 4-part synthesis (rca_copilot RCA shape; ticketasg gaps; guidebook intelligence; recommendations) |
| `.planning/quick/quick-kayinleong-024/research_inputs/CDS_Incident_Handling_Guidebook.txt` | new — guidebook converted via `textutil` so RESEARCH.md verbatim quotes are reproducible |
| `.planning/quick/quick-kayinleong-024/CLAIM.md` | claim lifecycle + regression report |
| `.planning/quick/quick-kayinleong-024/SUMMARY.md` | this file |

**Not changed:** `assignment_rules.json`, `tools/assignment_tool.py`, `tools/retrieval_tool.py`, `tools/bigquery_tool.py`. The deterministic routing engine and BQ executor stay exactly as-is — this is a tools-exposed-to-agent + prompt-engineering change.

## Code changes — `ticketasg_copilot_agent/mcp_server.py`

Five new tools are now exposed via both `list_tools()` (MCP path), `_dispatch()`, and the JSON-RPC fallback's `tools/list`:

| Tool | Implementation mirrors |
|---|---|
| `query_bigquery` | rca_copilot's `query_bigquery` — same `is_enabled()` + `_BQ_UNAVAILABLE` graceful-degrade path |
| `get_schema` | rca_copilot's `get_schema_from_file(table_name)` |
| `list_bq_tables` | rca_copilot's `get_schema_from_file("")` |
| `download_attachments` | rca_copilot's full implementation — detects RITM/TASK/INC table prefix, calls `reader.download_all_attachments` |
| `extract_identifiers` | rca_copilot's wrapper around `incident_store.extract_identifiers` |

`analyze_incident` now auto-downloads attachments (mirroring rca_copilot's `analyze_incident` line-for-line). Output went from `summary + identifiers` to `summary + identifiers + attachments`.

## Prompt changes — three files, mutually consistent

All three files now teach the agent:

1. **Five-section report template** — four canonical RCA headers, then `### REASSIGNMENT DECISION` appended as the LAST section. The section is ALWAYS present (Variant A `**REASSIGN to:**` or Variant B `**NO REASSIGNMENT NEEDED.**`).
2. **3-question framework** (Section 14 of the guidebook) — applied BEFORE scoring any assignment group: what data is impacted / migrated or ongoing / which system owns it.
3. **Five-step Standard Analysis** (Section 9) — Understand the ask → Identify data type → Check creation timing → Migration check (C2) → Ongoing check (C5).
4. **Common SPACE CDS patterns** (Section 10) — loyalty points missing, "consumer not found in Mars", brand/civility/code mismatch, missing orders, incorrect order amount, brand/location wrong.
5. **Status mismatch rule** (Section 11) — PI vs External System ID mismatch is not automatically a defect; only ONE active Mars ID is expected.
6. **Never-do guardrails** (Section 12) — don't ask CDS to resend migrated data, don't default metadata to CDS, etc.
7. **Mandatory screenshot fields** (Section 8) — flag missing fields and downgrade confidence.
8. **Key identifiers** (Section 5) — LUCID C2 / C5, Mars ID lifecycle, Source Consumer Key.
9. **Go-live timeline** (Section 4) — ANZ AU/NZ mid-July 2025, SEA mid-December 2025.
10. **Brand reference** (Section 6) — especially: AESOP signature `85` → CEGID, not MARS.
11. **Inbound feeds + PROD times** (Section 7) — agent suggests "check whether `IN MARS OrderHeader` processed on {date}" when an order is missing.
12. **BigQuery investigation step** — `list_bq_tables` → `get_schema <table>` → `query_bigquery <SELECT>`. Run multiple queries. "0 rows" IS a finding. Always include `signature` + `isocountry` in SELECTs (LUCID is not unique across brands). Always filter consumers by `status = 'Active'`.

`AGENTS.md` carries the full reference (guidebook + Common SPACE CDS Root Causes table + BQ datasets + query rules + key tables + identifier→table mappings, exactly mirroring `rca_copilot_agent/AGENTS.md`'s reference sections). `SKILL.md` and `.github/agents/ticketasg_copilot.agent.md` carry the workflow-essential subset.

## State of the 6 agent docs after this claim

| Entry point | Package | File | RCA-parity? | Guidebook? | Reassignment-as-last-section? |
|---|---|---|:---:|:---:|:---:|
| Package docs | ticketasg | `ticketasg_copilot_agent/AGENTS.md` | **✓ (this claim)** | **✓ (this claim)** | **✓ (this claim)** |
| Claude Code skill | ticketasg | `.claude/skills/ticketasg-copilot/SKILL.md` | **✓ (this claim)** | **✓ (this claim)** | **✓ (this claim)** |
| GitHub Copilot agent | ticketasg | `.github/agents/ticketasg_copilot.agent.md` | **✓ (this claim)** | **✓ (this claim)** | **✓ (this claim)** |
| Package docs | rca | `rca_copilot_agent/AGENTS.md` | source of truth | not in scope (was the reference) | n/a — RCA only |
| Claude Code skill | rca | `.claude/skills/rca-copilot/SKILL.md` | source of truth | not in scope | n/a |
| GitHub Copilot agent | rca | `.github/agents/rca_copilot.agent.md` | source of truth | not in scope | n/a |

All 3 ticketasg entry points are now mutually consistent.

## Verification

- `python3 -c 'import ast; ast.parse(...)'` and `py_compile` on `mcp_server.py` → both clean.
- All 19 `Tool(name=...)` descriptors have matching `elif name == ...` dispatch arms.
- All BQ imports (`is_enabled`, `query_bigquery`, `_BQ_UNAVAILABLE`, `get_schema_from_file`) exist in `tools/bigquery_tool.py`. `snow_reader.download_all_attachments` and `incident_store.extract_identifiers` exist.
- `_dispatch('get_assignment_rules', {}, ...)` → returned full routing matrix with `APAC` group names.
- `_dispatch('list_bq_tables', {}, ...)` → returned `PRIMARY DATASET: oa-apmena-spacecds-ap-pd...` from `schema.json` (proves the new BQ wiring works end-to-end, no creds needed).
- `python3 ticketasg_copilot_agent/test_config.py` → 3/3 PASS.
- `grep -c "REASSIGNMENT DECISION"` → 6 / 5 / 4 hits across the three prompt files.
- `grep -E "^### (Routing Signals|Reassignment Decision|Alternative Groups)$"` → zero hits (no old-template headers leaked).
- Guidebook-derived content (`3-question framework`, `migrated`, `C2 LUCID`, `C5 LUCID`) present in all three prompt files (20 / 13 / 16 hits).

## Regression surface considered

- **`recommend_assignment_v2` deterministic engine** untouched — no changes to `assignment_tool.py`, `retrieval_tool.py`, `bigquery_tool.py`, or `assignment_rules.json`. Routing math is unchanged.
- **MCP server tool registry** — adding tools is additive. Existing clients that only call the legacy 13 tools see no change.
- **JSON-RPC fallback `tools/list`** — grew from 11 names to 19. Pre-existing names retained.
- **`analyze_incident` output shape** — now returns `summary + identifiers + attachments`. This matches rca_copilot's existing behaviour, so the two agents are now aligned, not divergent. No callers in the codebase parse `analyze_incident` output by regex.
- **Report template change** — five `###` headers instead of four. Downstream tooling searching for `\*\*REASSIGN to:\*\*` continues to match (now inside `### REASSIGNMENT DECISION` instead of `### WHAT WE NEED / DID`).
- **Email subject + save-report filename** — unchanged. Cosmetic alignment to `<INC>_rca_<ts>.md` was flagged optional in RESEARCH.md and deferred.

## Open questions flagged for reviewer

1. ANZ go-live year is **assumed 2025** in the prompt — guidebook source only says "Mid-July" with no year. Confirm before production use.
2. `LS team` (referenced in guidebook Step 4 for migrated-data routing) is NOT a separate canonical SNOW group in `assignment_rules.json`. Closest match is `APAC - ZN - SPACE B2C Hypercare` (which lists `LS team`, `LS Hypercare` as keywords). Is LS a separate group that should be added as the 11th canonical entry?
3. `CDS_Incident_Handling_Guidebook 2.docx` left untracked at repo root. Decision pending: commit to git, move into `.planning/quick/quick-kayinleong-024/research_inputs/`, or leave external.
4. `ticketasg_copilot_agent/retrieval_index.npz` shows as modified in working tree — unrelated to this claim, deliberately not staged.

## What the user will see next time

Running the ticketasg agent on a SPACE CDS incident will now produce a five-section report like:

```markdown
# RCA Report: INC10449165
**Loyalty points missing for TH Lancome consumer**
*Investigated: 2026-05-21*

---

### WHAT HAPPENED
Loyalty points for the 2026-03-30 transaction not credited to customer TH0L00000001563. Ticket currently in `APAC - SGP - SPACE CDS SAPMENA L3 Support`.

### WHAT WE CHECKED
→ Checked work notes — Reassignment from CDS L2 with note "PRB0082698 raised, data patching required" (2026-04-15, M. Tan).
→ Checked attachments — Screenshot present; LUCID + ISO Country + source datetime + External System ID status all visible (Section 8 mandatory fields complete).
→ Checked LUCID prefix — C2 → migrated consumer.
→ Checked source creation datetime — 2025-03-12 (before TH go-live mid-Dec 2025); confirms migrated.
→ Checked BigQuery `CONSUMER_PII_TBL` — consumer present, status Active, signature LANC, isocountry TH.
→ Checked BigQuery `EXTERNAL_SYSTEM_IDS_TBL` — older Mars ID inactive (expected lifecycle); newer Mars ID active.

### WHAT WE FOUND
Migrated consumer with active Mars ID. Missing loyalty points are an LS-owned historical-send issue (guidebook Step 4: "Do NOT ask CDS to resend; LS owns historical sends to Loyalty"). Not a CDS defect; need LS team to confirm the original historical send to Loyalty included this transaction.

### WHAT WE NEED / DID
- `APAC - ZN - SPACE B2C Hypercare` (covers `LS team` per shortform mapping): confirm whether the 2026-03-30 transaction was part of the LS historical send to Loyalty.
- `APAC - ZN - O+O.NGLORA - L2`: hold on data patch until LS confirms; do not raise CDS resend.
- Closing note: routing to Hypercare for LS coordination.

### REASSIGNMENT DECISION
**REASSIGN to:** `APAC - ZN - SPACE B2C Hypercare`
**Confidence:** 75 %
**Source:** keyword + retrieval
**Signals checked:**
→ Hard rules — no match
→ Keyword scorer — `APAC - ZN - O+O.NGLORA - L2` (conf 0.42, matched: Loyalty, points)
→ kNN retrieval (top-1) — INC10204372 → `APAC - ZN - SPACE B2C Hypercare` (similarity 0.71)
→ kNN retrieval (weighted vote) — `APAC - ZN - SPACE B2C Hypercare`: 1.4, `APAC - ZN - O+O.NGLORA - L2`: 0.7
→ L3 escalation signals — triggered: PRB0082698, data patching
**Justification:** Root cause is LS-owned migrated data (C2 LUCID + source date pre-go-live). Per guidebook Section 12, "Asking CDS to resend migrated data — that is LS's responsibility." LS coordination flows through `APAC - ZN - SPACE B2C Hypercare` (which lists `LS team`, `LS Hypercare` as keywords). Overriding the keyword winner (NGLORA) because the root-cause finding outranks the loyalty-keyword score.
**Action:** Please reassign this ticket to `APAC - ZN - SPACE B2C Hypercare` and post the justification above as a public comment.
**Similar past tickets:**
- INC10204372 (similarity 0.71) — currently in `APAC - ZN - SPACE B2C Hypercare`
- INC10293500 (similarity 0.58) — currently in `APAC - ZN - SPACE B2C Hypercare`
```
