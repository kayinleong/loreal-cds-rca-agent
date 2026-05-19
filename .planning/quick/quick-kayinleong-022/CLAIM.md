# Claim: quick-kayinleong-022
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: done
- summary: Enforced full canonical assignment-group names in agent-generated RCA / assignment reports. Forbid shortforms like `CDS L3 team` / `LOY` / `MARS team` — the agent must always write the verbatim ServiceNow group name (e.g. `APAC - SGP - SPACE CDS SAPMENA L3 Support`). Docs-only — added a "FULL canonical names" rule and a 13-row shortform→canonical mapping table to all 4 agent docs files. Verified all 12 canonical strings appear verbatim in every doc.

## Trigger

Example from `my_reports/rca_reports/INC10449165_rca_20260519_213556.md`:

> `### WHAT WE NEED / DID`
> - Assign to **CDS L3 team** as the issue is tracked in DFCT0268807.
> - **CDS** to extract the full outbound file and share it with **LOY**...
> - **LOY** to sync the lucid according to the shared outbound file.

The strings `CDS L3 team`, `CDS`, `LOY`, `MARS team` etc. are operator shorthand from work-notes. They're ambiguous to anyone outside the team and they don't match the SNOW Reassign-Group picker exactly. The agent should ALWAYS expand to the full canonical group name.

## What Will Change

1. **`rca_copilot_agent/AGENTS.md`** — add a "Group names: always canonical, never shortforms" rule + a shortform→canonical mapping table; apply to the RCA report-format block (especially `### WHAT WE NEED / DID`).
2. **`.claude/skills/rca-copilot/SKILL.md`** — same rule + table.
3. **`ticketasg_copilot_agent/AGENTS.md`** — same rule + table (the ticketasg report template already uses full names in examples, but no explicit "never shortform" guardrail).
4. **`.claude/skills/ticketasg-copilot/SKILL.md`** — same rule + table.

## What Will NOT Change

- No code changes in `tools/*` or `mcp_server.py`
- No `assignment_rules.json` change
- The 64-incident match rate (38/64 = 59.4 %) is unaffected — this only changes how the LLM writes its report
- `schema.json`, `requirements.txt`, `CLAUDE.md` — untouched

## Shortform → canonical mapping (to embed in both agents' docs)

| Operator shorthand | Canonical ServiceNow group |
|---|---|
| `CDS L2` / `CDS L2 team` / `SAPMENA CDS group` | `APAC - SGP - SPACE CDS SAPMENA L2 Support` |
| `CDS L3` / `CDS L3 team` | `APAC - SGP - SPACE CDS SAPMENA L3 Support` |
| `LOY` / `LOY team` / `Loyalty` / `Loyalty team` (Loyalty backend issue) | `APAC - ZN - O+O.NGLORA - L2` |
| `LOY L3` / `Loyalty L3` (Loyalty L3 issue, often China/loyalty rules) | `APAC - CHN - SPACE Loyalty L3 Support` |
| `MARS` / `MARS team` / `MARS Ops` / `MARS Operations` / `retail Ops team` | `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2` |
| `iBeauty` / `iBeauty team` / `IBeauty team` / `iBeauty L2` | `APAC - ZN - iBeauty 2.0 - Retail - L2` |
| `SFCC` / `SFCC L2` | `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2` |
| `CRM` / `SFMC team` / `SFDC team` / `CE team` / `CE Ops team` | `APAC - ZN - O+O.CRM - L2` |
| `NGL` / `NGL L2` / `NGLORA` | `APAC - ZN - O+O.NGLORA - L2` |
| `Operations` / `Ops` / `OPS team` (only when nothing more specific fits) | `APAC - ZN - O+O.OPERATIONS - L2` |
| `Hypercare` / `Hypercare team` / `Hypercare group` / `LS team` / `LS Hypercare` / `Aesop hypercare` | `APAC - ZN - SPACE B2C Hypercare` |
| `HIP` / `HIP team` / `Infrastructure team` / `Azure team` (HIP-adjacent) | `TECH FNDN - WW - HIP INCIDENT L2` |
| `THN Retail` / `Thailand Retail` | `APAC - THN - Retail IT` |

L3 groups outside the canonical 10 (also full names, never shortforms):
- `APAC - SGP - SPACE CDS SAPMENA L3 Support`
- `APAC - CHN - SPACE Loyalty L3 Support`
- `APAC - SGP - SPACE Loyalty L3 Support`
- `INFRA - WW - Linux Unix ACN - L3` (per real work-notes)

When uncertain, the agent should ALWAYS pick the closest canonical full name and add a `[USER-CONFIRM]` flag in the justification.

## What Has Changed

Same content (rule + 13-row mapping table + L3 list + `[USER-CONFIRM]` fallback guidance) added to all 4 files:

1. **`rca_copilot_agent/AGENTS.md`** — inserted after the `## Report Template` block, before `## Common SPACE CDS Root Causes`
2. **`.claude/skills/rca-copilot/SKILL.md`** — inserted after the `## RCA Report Format (MANDATORY)` block, before `## Output Rules`
3. **`ticketasg_copilot_agent/AGENTS.md`** — inserted after the `### Why this format` block, before `## Assignment Groups Supported`. Adds an additional line about citing similar past tickets with full group names.
4. **`.claude/skills/ticketasg-copilot/SKILL.md`** — inserted after the `**Important — what goes WHERE:**` block, before `### Step 6 — Save report`

## Verification

### What was tested

1. **Scope check** — `git status` confirms only the 4 intended docs files changed. Zero changes to `tools/`, `mcp_server.py`, `assignment_rules.json`, `requirements.txt`, `retrieval_index.npz`, or anything else.
2. **Rule presence** — `grep` shows 2 hits per file ("FULL canonical" header + "Shorthand seen" table header) in each of the 4 files. ✓
3. **Canonical-name fidelity** — wrote a Python check that loads all 12 canonical group names from `ticketasg_copilot_agent/assignment_rules.json` (10 L2 + 2 L3 from `l3_escalation.l2_to_l3`) and `grep`s each one against all 4 docs files:

   ```
   rca_copilot_agent/AGENTS.md:                 12/12 canonical names found
   .claude/skills/rca-copilot/SKILL.md:         12/12 canonical names found
   ticketasg_copilot_agent/AGENTS.md:           12/12 canonical names found
   .claude/skills/ticketasg-copilot/SKILL.md:   12/12 canonical names found
   ```

   Zero typos — every canonical name in the docs matches the JSON exactly. This is important because the LLM agent will copy these strings verbatim into reports, and SNOW's Reassign-Group picker requires exact matches.

### Regression Report

- **No code touched.** `git diff -- ticketasg_copilot_agent/tools/ ticketasg_copilot_agent/mcp_server.py ticketasg_copilot_agent/run_tool.py ticketasg_copilot_agent/assignment_rules.json ticketasg_copilot_agent/retrieval_index.npz` and similar globs under `rca_copilot_agent/` are empty.
- **No rules touched.** `assignment_rules.json` unchanged — still v2.0.
- **Match rate unchanged.** v2.0's 38/64 = 59.4 % still applies because the agent's recommender output is unchanged; only the *human report wording* changes.
- **Backward-compatible.** Past reports in `my_reports/rca_reports/` and `my_reports/assignment_reports/` keep their original shortform wording. Only reports generated from this commit forward use full canonical names.
- **Downstream consumers unaffected.** `save_rca_report` / `save_assignment_report` store report text verbatim; `send_*_email` reads it back unchanged. No header-parsing anywhere depends on the canonical-name guidance.
- **SNOW Reassign-Group picker compatibility improved.** Because the agent now uses the same string as the SNOW dropdown, copy-pasting from the agent's `WHAT WE NEED / DID` section into the SNOW UI will match exactly. Previously the operator had to mentally translate `CDS L3` → `APAC - SGP - SPACE CDS SAPMENA L3 Support`.

### What was ruled out

- **Rewriting past reports** — past saved reports keep their wording. The rule applies going forward only.
- **Adding a runtime validator** in `save_assignment_report` / `save_rca_report` that rejects reports containing shortforms — additive, could be a future claim. For now we trust the LLM to follow the docs (the canonical-names list is now embedded in the prompt).
- **Touching `assignment_tool.py`** — the `recommend_assignment_v2` already returns canonical full names. The bug was in the LLM's rephrasing into the report, which is a docs/prompt fix.
