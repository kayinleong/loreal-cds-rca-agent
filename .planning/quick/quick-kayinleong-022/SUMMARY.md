---
slug: quick-kayinleong-022
status: complete
claim: enforce full canonical assignment-group names in agent reports — no shortforms
date: 2026-05-19
---

# Summary — quick-kayinleong-022

Forbid operator shortforms (`CDS L3`, `LOY`, `MARS team`, `iBeauty`, `NGL`, etc.) in agent-generated reports. The agent must always write the verbatim canonical ServiceNow group name — so the recommendation can be copy-pasted straight into the SNOW Reassign-Group picker without operator translation.

## Trigger

`my_reports/rca_reports/INC10449165_rca_20260519_213556.md`:
> "Assign to **CDS L3 team** as the issue is tracked in DFCT0268807."

Now expected:
> "Assign to `APAC - SGP - SPACE CDS SAPMENA L3 Support` as the issue is tracked in DFCT0268807."

## Files changed (4 docs files, lines added)

| File | Change |
|---|---|
| `rca_copilot_agent/AGENTS.md` | +44 / -0 |
| `.claude/skills/rca-copilot/SKILL.md` | +28 / -0 |
| `ticketasg_copilot_agent/AGENTS.md` | +30 / -0 |
| `.claude/skills/ticketasg-copilot/SKILL.md` | +32 / -0 |

Each file gained the same canonical "Rule + 13-row mapping table + L3 list + `[USER-CONFIRM]` fallback" block, positioned right after that file's report-format definition.

## What did NOT change

- `tools/assignment_tool.py` — `recommend_assignment_v2` already returns canonical names; the bug was in the LLM's rephrasing
- `tools/retrieval_tool.py` — unchanged
- `assignment_rules.json` — still v2.0
- `mcp_server.py`, `run_tool.py` — unchanged
- `requirements.txt`, `retrieval_index.npz` — unchanged
- Match rate against 64-incident sample — still 38/64 = 59.4 %
- `rca_agent/`, `schema.json`, `CLAUDE.md` — none touched

## Verification

- Scope: only 4 docs files touched (plus claim/summary)
- All 12 canonical group names from `assignment_rules.json` appear verbatim in all 4 docs files (12/12 each)
- Both rule statements (`FULL canonical` header + `Shorthand seen` table) present in every doc

## What the agent will write from now on

Before:
```
- Assign to CDS L3 team as the issue is tracked in DFCT0268807.
- CDS to extract the full outbound file and share it with LOY.
- LOY to sync the lucid according to the shared outbound file.
```

After:
```
- Assign to `APAC - SGP - SPACE CDS SAPMENA L3 Support` as the issue is tracked in DFCT0268807.
- `APAC - SGP - SPACE CDS SAPMENA L3 Support` to extract the full outbound file and share it with `APAC - ZN - O+O.NGLORA - L2` (or `APAC - CHN - SPACE Loyalty L3 Support` if the case requires L3 loyalty work).
- `APAC - ZN - O+O.NGLORA - L2` to sync the lucid according to the shared outbound file.
```

(The agent uses the closest-canonical match for each shortform; for ambiguous cases like generic "LOY" it can add `[USER-CONFIRM]` to flag.)
