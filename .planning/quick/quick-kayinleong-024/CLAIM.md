# Claim: quick-kayinleong-024
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-21
- status: done
- summary: Brought ticketasg_copilot_agent to RCA-parity with rca_copilot_agent. Exposed query_bigquery / get_schema / list_bq_tables / download_attachments / extract_identifiers in ticketasg's MCP server + run_tool dispatch; updated analyze_incident to auto-download attachments; reshaped the report contract to 4 RCA sections + appended ### REASSIGNMENT DECISION (always present); folded the CDS Incident Handling Guidebook into the prompt across AGENTS.md, .claude/skills/ticketasg-copilot/SKILL.md, and .github/agents/ticketasg_copilot.agent.md. Produced RESEARCH.md as the source-of-truth synthesis document.

## Trigger

User invoked `/gsd-quick --research` with the following request:

> I want you to research rca_copilot_agent and ticketasg_copilot_agent.
> Now the ticketasg_copilot_agent will generate rca but not the rca that is generated in rca_copilot_agent.
> I want the ticketasg_copilot_agent to generate a rca just like in rca_copilot_agent, then add in reassignment grouping (if needed) in rca last session.
> Also improve the ticketasg_copilot_agent by reading the CDS_Incident_Handling_Guidebook 2.docx:
> 1. generate a research md
> 2. improve the ticketasg_copilot_agent

## What Will Change

1. **research.md** — Synthesis document in `.planning/quick/quick-kayinleong-024/RESEARCH.md` covering:
   - rca_copilot_agent's RCA report shape (template, sections, MCP tool wiring)
   - ticketasg_copilot_agent's current report shape (recommend_assignment_v2 + RCA template variant)
   - Gap analysis — what's missing in ticketasg that rca has
   - Guidebook findings — process rules, escalation matrix, evidence requirements, KPIs
   - Recommended improvements to ticketasg_copilot_agent (tools, prompts, report sections)

2. **ticketasg_copilot_agent updates** — code/doc changes to make the agent:
   - Generate the same RCA report structure as rca_copilot_agent
   - Append a `### Reassignment Decision` section at the end (only when reassignment is recommended)
   - Apply additional improvements surfaced in the guidebook research

3. **AGENTS.md / SKILL.md / .github/agents/ticketasg_copilot.agent.md** — kept in sync with the new report contract

## What Has Changed

### Code (`ticketasg_copilot_agent/mcp_server.py`)
- Added MCP `Tool(...)` descriptors for: `extract_identifiers`, `download_attachments`, `query_bigquery`, `get_schema`, `list_bq_tables`.
- Added dispatch arms for the same five tools — implementations mirror `rca_copilot_agent/mcp_server.py` exactly (same `is_enabled` / `_BQ_UNAVAILABLE` fallback for BQ; same `download_all_attachments` for attachments).
- `analyze_incident` now auto-downloads attachments (matches rca_copilot behaviour). Output is now `summary + identifiers + attachments`, not just `summary + identifiers`.
- Updated `analyze_incident`'s tool description to call out attachment download and reference the guidebook's Section 8 screenshot rule.
- Updated JSON-RPC fallback `tools/list` to include the new tools.
- Updated the top-of-file docstring to group the new tools by purpose (ServiceNow / BigQuery / Assignment).

### Prompts (three files, kept mutually consistent)

All three files now teach the agent to:
1. Produce a bipartite report — four `###` headers identical to `rca_copilot_agent`'s RCA template, followed by `### REASSIGNMENT DECISION` as the LAST section.
2. **Always include** the REASSIGNMENT DECISION section. When current_group is correct, body is `**NO REASSIGNMENT NEEDED.** + Confidence + Source + Signals checked + Evidence`. When reassignment is recommended, body is `**REASSIGN to:** + Confidence + Source + Signals checked + Justification + Action + Similar past tickets`.
3. Apply the **3-question framework** (what data / migrated-vs-ongoing / which system owns) BEFORE recommending an assignment.
4. Pattern-match against the **Section 10 common incident patterns** (loyalty points missing, consumer not found in Mars, brand/civility/code mismatch, missing orders, incorrect order amount, brand/location data wrong).
5. Apply the **Section 11 status-mismatch rule** (mismatched PI/External-System-ID status is not automatically a defect).
6. Avoid **Section 12 mistakes** (don't ask CDS to resend migrated data, don't default metadata issues to CDS, etc.).
7. Verify the **Section 8 mandatory screenshot fields** when reading attachments; flag missing fields and downgrade confidence.
8. Use the **Section 5 key identifiers** (LUCID C2/C5, Mars ID lifecycle, Source Consumer Key).
9. Use the **Section 4 go-live timeline** to decide migrated-vs-ongoing.
10. Apply the **Section 6 brand reference** (especially: AESOP signature 85 → CEGID, not MARS).
11. Reference the **Section 7 inbound feeds + PROD times** when investigating missing orders/consumers.

`AGENTS.md` carries the full reference (guidebook content + Common SPACE CDS Root Causes table + BigQuery datasets + Query Rules + Key Tables + Identifier→Table mappings, mirroring rca_copilot's AGENTS.md). `SKILL.md` and `.github/agents/ticketasg_copilot.agent.md` carry the workflow-essential subset.

### Research artefact
- `.planning/quick/quick-kayinleong-024/RESEARCH.md` — 4-part synthesis (rca_copilot RCA shape; ticketasg current shape + gaps; guidebook intelligence with verbatim section references; gap analysis + recommendations) including the implementation summary table the build followed.
- `.planning/quick/quick-kayinleong-024/research_inputs/CDS_Incident_Handling_Guidebook.txt` — guidebook converted from `CDS_Incident_Handling_Guidebook 2.docx` via `textutil`, kept committed so RESEARCH.md's verbatim quotes are reproducible.

### Files intentionally NOT committed
- `ticketasg_copilot_agent/retrieval_index.npz` — unrelated kNN index regeneration, left in working tree.
- `CDS_Incident_Handling_Guidebook 2.docx` — source DOCX at repo root; left untracked for the user to decide whether the binary belongs in git.

## Verification

### Static checks
- `python3 -c 'import ast; ast.parse(open("ticketasg_copilot_agent/mcp_server.py").read())'` → OK.
- `py_compile.compile('ticketasg_copilot_agent/mcp_server.py', doraise=True)` → OK.
- All 19 tool `Tool(name=...)` descriptors have matching `elif name == ...` dispatch arms; no orphaned descriptors and no dispatch arms without descriptors.
- All four imports from `tools.bigquery_tool` (`is_enabled`, `query_bigquery`, `_BQ_UNAVAILABLE`, `get_schema_from_file`) exist in the module.
- Both methods used in the new dispatch arms (`snow_reader.download_all_attachments`, `incident_store.extract_identifiers`) exist.

### Live dispatch smoke tests (no creds required)
- `_dispatch('get_assignment_rules', {}, './my_reports')` → returned routing matrix containing `APAC` group names ✓
- `_dispatch('list_bq_tables', {}, './my_reports')` → returned `PRIMARY DATASET: oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public ...` from `schema.json` ✓

### Existing tests
- `python3 ticketasg_copilot_agent/test_config.py` → 3/3 PASS (assignment_rules_file defaults, env override, SMTP gating).

### Prompt-file consistency checks
- `grep -c "REASSIGNMENT DECISION"` finds the new section in all three prompt files (6 / 5 / 4 occurrences).
- `grep -E "^### (Routing Signals|Reassignment Decision|Alternative Groups)$"` finds zero matches (no old-template section headers remain).
- Guidebook-derived content present in all three files (3-question framework + migrated/C2/C5 references): AGENTS.md 20 hits, SKILL.md 13 hits, `.github/agents/ticketasg_copilot.agent.md` 16 hits.

### Regression surface considered
- **`recommend_assignment_v2` deterministic engine** — untouched. No changes to `tools/assignment_tool.py`, `tools/retrieval_tool.py`, `tools/bigquery_tool.py`, or `assignment_rules.json`. Routing math is unchanged.
- **MCP server tool registry** — adding new tools is additive. Existing clients that only call the legacy 13 tools see no change in behaviour. The mcp SDK's `list_tools()` simply exposes more tools to discovery; clients ignore unknown ones.
- **JSON-RPC fallback** — the fallback `tools/list` array grew from 11 names to 19 names. Pre-existing names are still present in the same order. Old clients that send `tools/call` with a legacy tool name continue to route correctly via the unchanged dispatcher.
- **`analyze_incident` output shape change** — the function now returns `summary + identifiers + attachments` (three sections joined by `\n\n`). Old clients that parsed the output as two sections will now see an extra trailing section. This is the same behaviour rca_copilot's `analyze_incident` already produces, so the contract is now aligned, not divergent. No `IDENTIFIERS:` regex callers exist in the codebase.
- **Report template change** — the prompt now teaches the agent to emit five `###` headers instead of four. Any downstream parser that splits SNOW comments on `### WHAT WE NEED / DID` will now see a follow-up `### REASSIGNMENT DECISION` block. Downstream tooling that searched for the legacy structured `**REASSIGN to:**` block will find it inside `### REASSIGNMENT DECISION` instead of `### WHAT WE NEED / DID` — a grep for `\*\*REASSIGN to:\*\*` continues to match.
- **Email subject default** — unchanged (`"Ticket Assignment Analysis Complete — Please Review"`); agent prompts can override via subject arg.
- **Save-report filename pattern** — unchanged (`<INC>_assignment_<ts>.md` under `assignment_reports/`). Cosmetic rename to `<INC>_rca_<ts>.md` was flagged as optional in RESEARCH.md and deferred per scope.

### Backstop assumption flagged for reviewer
- ANZ go-live year (used in the prompt for migrated-vs-ongoing decisions) is **assumed mid-July 2025** because the guidebook lists only "Mid-July" with no year. Mark `[USER-CONFIRM]` if this is wrong.
