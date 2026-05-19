---
slug: quick-kayinleong-023
status: complete
claim: GitHub Copilot agent.md files — catch-up to quick-020 / 021 / 022 (v2 + RCA + canonical names)
date: 2026-05-19
---

# Summary — quick-kayinleong-023

The two GitHub Copilot agent definitions under `.github/agents/` had been silently bypassed by quicks 020, 021, and 022 — only the SKILL.md and package-level AGENTS.md were updated. The Copilot operator path (which is what L'Oréal users actually invoke) was still running the v1 keyword-only flow and the OLD `Routing Signals / Reassignment Decision / Alternative Groups` report format. That's what produced the user's INC10449165 report in the old format.

This claim closes the gap. All 6 agent docs files are now mutually consistent.

## Trigger

User showed an INC10449165 assignment report generated at 2026-05-19 21:46:52 with the OLD format. A grep for `### Routing Signals` returned only one hit — `.github/agents/ticketasg_copilot.agent.md`.

## Files changed

| File | Diff |
|---|---:|
| `.github/agents/ticketasg_copilot.agent.md` | +167 / -34 |
| `.github/agents/rca_copilot.agent.md` | +34 / -0 |
| `.planning/quick/quick-kayinleong-023/CLAIM.md` | claim lifecycle |
| `.planning/quick/quick-kayinleong-023/SUMMARY.md` | this file |

**Nothing else changed.** No code, no rules, no requirements, no retrieval index.

## What each Copilot agent file looks like NOW

### `.github/agents/ticketasg_copilot.agent.md` (full catch-up)
- Tool table lists `recommend_assignment_v2`, `find_similar_incidents`, `build_retrieval_index` (in addition to the legacy v1 `recommend_assignment` for back-compat)
- Mandatory sequence is 8 steps including the explicit "build retrieval index one-time", "call v2", "reason about three signals"
- Step 4 CLI example uses `recommend_assignment_v2`
- Step 5 report template is the L'Oréal RCA (`### WHAT HAPPENED / ### WHAT WE CHECKED / ### WHAT WE FOUND / ### WHAT WE NEED / DID`)
- Recommendation lives only in `### WHAT WE NEED / DID` with `**REASSIGN to:** \`{full canonical group name}\``, justification, action
- Has the LLM-as-judge signal-weighting matrix + 5-rule conflict-resolution recipe
- Has the FULL canonical assignment-group-names rule + 13-row shortform→canonical mapping + 4-entry L3 list + `[USER-CONFIRM]` fallback

### `.github/agents/rca_copilot.agent.md` (canonical-names rule only)
- Already on the RCA template (it was the canonical reference)
- Now also has the FULL canonical assignment-group-names rule + 13-row mapping + L3 list + `[USER-CONFIRM]` fallback

## State of the 6 agent docs after this claim

| Entry point | Package | File | v2 / hybrid? | RCA template? | Canonical names? |
|---|---|---|:---:|:---:|:---:|
| Package docs | ticketasg | `ticketasg_copilot_agent/AGENTS.md` | ✓ (quick-020) | ✓ (quick-021) | ✓ (quick-022) |
| Claude Code skill | ticketasg | `.claude/skills/ticketasg-copilot/SKILL.md` | ✓ (quick-020) | ✓ (quick-021) | ✓ (quick-022) |
| **GitHub Copilot agent** | ticketasg | `.github/agents/ticketasg_copilot.agent.md` | **✓ (this claim)** | **✓ (this claim)** | **✓ (this claim)** |
| Package docs | rca | `rca_copilot_agent/AGENTS.md` | n/a (no v2 for rca) | ✓ (was the source) | ✓ (quick-022) |
| Claude Code skill | rca | `.claude/skills/rca-copilot/SKILL.md` | n/a | ✓ (was the source) | ✓ (quick-022) |
| **GitHub Copilot agent** | rca | `.github/agents/rca_copilot.agent.md` | n/a | ✓ (was already) | **✓ (this claim)** |

All 6 are now in sync.

## Verification

- Repo-wide `grep` for OLD-format strings (`### Routing Signals`, `### Reassignment Decision`, `### Alternative Groups`) returns **zero hits outside `.planning/`** — all stale references purged.
- Repo-wide `grep` for the canonical-names rule (`FULL canonical` + `Shorthand seen`) returns **2 hits in every one of the 6 agent docs**.
- All 12 canonical group names from `assignment_rules.json` appear **verbatim in all 6 docs (12/12 each)** — zero typos.
- `git status` shows exactly the 2 intended `.github/agents/*.md` files modified (+ claim/summary planning files).

## What the user will see next time

Re-running the Copilot agent on INC10449165 (or any other ticket) will now produce a report shaped like this — RCA template with the full canonical group name in `### WHAT WE NEED / DID`:

```markdown
## Assignment Analysis — INC10449165

### WHAT HAPPENED
Customer profile for TH0L00000001563 (TH Lancome) closed in MARS; loyalty points
for the 2026-03-30 transaction not credited. Ticket currently in
`APAC - SGP - SPACE CDS SAPMENA L3 Support`.

### WHAT WE CHECKED
→ Hard rules — no match
→ Keyword scorer — APAC - SGP - SPACE CDS SAPMENA L2 Support (confidence 0.5, matched: CDS)
→ kNN retrieval (top-1) — INCxxxxxxxx → APAC - SGP - SPACE CDS SAPMENA L3 Support (similarity 0.7x)
→ kNN retrieval (weighted vote) — APAC - SGP - SPACE CDS SAPMENA L3 Support 0.92
→ L3 escalation signals — triggered: PRB0082698, DFCT0268807, tracked under PRB, data patching

### WHAT WE FOUND
Multiple escalation signals fired (PRB, DFCT, data patching) and the L2 keyword winner
(SAPMENA L2) has an L3 counterpart. Three of the top-5 retrieval neighbours also sit in
SAPMENA L3, confirming this is L3 work.

### WHAT WE NEED / DID
**NO REASSIGNMENT NEEDED.** The current group `APAC - SGP - SPACE CDS SAPMENA L3 Support` matches what the routing signals indicate — the L3 escalation triggers (DFCT0268807, PRB linkage, data patching) and retrieval consensus both confirm this is L3 work.

Action items going forward (within this group):
- `APAC - SGP - SPACE CDS SAPMENA L3 Support` to extract the full outbound file and share it with `APAC - ZN - O+O.NGLORA - L2` to sync the lucid.
- `APAC - ZN - O+O.NGLORA - L2` to confirm the customer profile state in MARS after the sync completes.
```
