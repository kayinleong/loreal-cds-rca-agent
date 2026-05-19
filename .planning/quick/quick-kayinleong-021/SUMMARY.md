---
slug: quick-kayinleong-021
status: complete
claim: ticketasg report format → L'Oréal RCA template
date: 2026-05-19
---

# Summary — quick-kayinleong-021

Converted the ticketasg_copilot_agent report format to the canonical L'Oréal RCA template used by `rca_copilot_agent` and L2/L3 operators in real SNOW work-notes. The reassignment group + justification land in `### WHAT WE NEED / DID`.

## Before → After

| Aspect | Before (quick-020) | After (this claim) |
|---|---|---|
| Section headers | `### How the three signals lined up`, `### My reasoning`, `### Reassignment Decision`, `### Similar past tickets` | `### WHAT HAPPENED`, `### WHAT WE CHECKED`, `### WHAT WE FOUND`, `### WHAT WE NEED / DID` (with optional `Similar past tickets:` list inside it) |
| Recommendation placement | Top-level `**Recommended Group:**` field + duplicated in `### Reassignment Decision` | **Only** inside `### WHAT WE NEED / DID` as `**REASSIGN to:**` |
| Signal enumeration | Free-form prose under "How the three signals lined up" | Four `→ Checked` bullets under `### WHAT WE CHECKED` — one per signal from `recommend_assignment_v2` |
| Match with rca_copilot_agent template | partial | exact |

## Files changed

| File | Lines |
|---|---|
| `ticketasg_copilot_agent/AGENTS.md` | +21 / −27 |
| `.claude/skills/ticketasg-copilot/SKILL.md` | +25 / −18 |
| `.planning/quick/quick-kayinleong-021/CLAIM.md` | claim lifecycle |
| `.planning/quick/quick-kayinleong-021/SUMMARY.md` | this file |

**Nothing else changed** — verified with `git diff`.

## What did NOT change

- `assignment_rules.json` — same v2.0
- `tools/assignment_tool.py` — same `recommend_assignment_v2` logic
- `tools/retrieval_tool.py` — unchanged
- `mcp_server.py` — same Tool registrations
- `requirements.txt` — unchanged
- Match rate against the 64-incident sample — still **38/64 = 59.4 %** (no re-score needed because no tool input/output changed)
- `rca_copilot_agent/`, `rca_agent/`, `schema.json`, `CLAUDE.md` — none touched

## Verification

- `grep` confirms the four RCA headers exist in both files (6 + 7 total references)
- `grep` confirms the six removed section names are absent from both files
- `git status -s` shows only the two intended files modified (plus claim/summary planning files)
- Mirror check: ticketasg AGENTS.md headers now match `rca_copilot_agent/AGENTS.md` and `.claude/skills/rca-copilot/SKILL.md` exactly

## Sample output (what the agent will now write)

```markdown
## Assignment Analysis — INC10293500

### WHAT HAPPENED
[MARS-ANZ] Sales representative does not exist; ticket currently sits in APAC - SGP - SPACE CDS SAPMENA L2 Support.

### WHAT WE CHECKED
→ Hard rules — matched `MARS-{COUNTRY}` (uppercase) → OMNISALES.RETAIL
→ Keyword scorer — APAC - SGP - SPACE CDS SAPMENA L2 Support (confidence 0.4, matched: MARS Ops, retail Ops team)
→ kNN retrieval (top-1) — INC10204372 → ZN - SPACE B2C Hypercare (similarity 0.71)
→ kNN retrieval (weighted vote) — OMNISALES.RETAIL 1.21, B2C Hypercare 0.71
→ L3 escalation signals — not triggered

### WHAT WE FOUND
The `[MARS-ANZ]` hard rule is the strongest signal, and the weighted-vote retrieval also points to OMNISALES.RETAIL. Both signals agree this is a MARS/OMNISALES ticket misrouted into SAPMENA L2.

### WHAT WE NEED / DID
**REASSIGN to:** `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2`
**Confidence:** 95 %
**Justification:** Hard-rule match on `[MARS-ANZ]` country-tagged prefix indicates explicit MARS/OMNISALES ownership. Two of the top-5 neighbours also sit in OMNISALES.RETAIL.
**Action:** Please reassign this ticket to `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2` and post the justification above as a public comment.

**Similar past tickets:**
- INC10204372 (similarity 0.71) — currently in ZN - SPACE B2C Hypercare
- INC10324255 (similarity 0.58) — currently in SGP - SPACE CDS SAPMENA L3 Support
```
