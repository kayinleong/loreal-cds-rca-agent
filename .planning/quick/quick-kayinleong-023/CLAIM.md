# Claim: quick-kayinleong-023
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: done
- summary: Caught up the two GitHub Copilot agent definitions under `.github/agents/` with the doc changes from quick-020 (v2 hybrid recommender), quick-021 (RCA report template), and quick-022 (canonical-names rule + shortform mapping). After this claim: all 6 agent docs files (3 entry-points × 2 packages) are mutually consistent — zero stale OLD-format strings in the repo, 12/12 canonical group names appear verbatim in every doc.

## Trigger

The user's INC10449165 assignment report (timestamp 2026-05-19 21:46:52) shipped with the OLD format:

```
### Routing Signals
### Reassignment Decision
### Alternative Groups
```

A `grep -rEn "### Routing Signals|### Reassignment Decision|### Alternative Groups"` search across the repo found those strings only in `.github/agents/ticketasg_copilot.agent.md`. That file also still tells the agent to call `recommend_assignment` (v1) instead of `recommend_assignment_v2`, and has no canonical-names rule.

## What Will Change

### `.github/agents/ticketasg_copilot.agent.md`
Bring it in line with `.claude/skills/ticketasg-copilot/SKILL.md` (which is already current). Specifically:

1. **Tool inventory** — add `recommend_assignment_v2`, `find_similar_incidents`, `build_retrieval_index`; mark the legacy `recommend_assignment` as v1-fallback
2. **Mandatory sequence** — replace step 3 (call `recommend_assignment`) with: build retrieval index if not yet built → call `recommend_assignment_v2` → reason about the three signals
3. **Step 4 CLI example** — change the command from `recommend_assignment` to `recommend_assignment_v2` and add `build_retrieval_index` + `find_similar_incidents` examples
4. **Step 5 report-format block** — replace `### Routing Signals / ### Reassignment Decision / ### Alternative Groups` with the RCA template (`### WHAT HAPPENED / ### WHAT WE CHECKED / ### WHAT WE FOUND / ### WHAT WE NEED / DID`)
5. **Canonical-names rule** — add the same "FULL canonical assignment-group names — never shortforms" rule + 13-row mapping table that lives in the SKILL.md
6. **LLM-as-judge signal-weighting matrix** — mirror the same table from SKILL.md so Copilot operators see the same instructions Claude Code does

### `.github/agents/rca_copilot.agent.md`
Already on the RCA report template (it was the canonical reference for quick-021). Only missing the quick-022 canonical-names rule:

1. **Canonical-names rule + mapping table** — same content as in `rca_copilot_agent/AGENTS.md` and `.claude/skills/rca-copilot/SKILL.md`. Inserted right after the RCA report-format block.

## What Will NOT Change

- No code changes in `tools/*`, `mcp_server.py`, `run_tool.py`, `assignment_rules.json`, `retrieval_index.npz`
- No new tools, no MCP changes
- Match rate against the 64-incident sample (38/64 = 59.4 %) unchanged — the LLM client just learns the same template the SKILL.md already documents
- The v1 `recommend_assignment` CLI command still exists for back-compat — only the Copilot agent's *default sequence* changes to use v2

## What Has Changed

### `.github/agents/ticketasg_copilot.agent.md` (+167 / -34)

Three doc updates folded into one file:

1. **Tool table updated** — added rows for `recommend_assignment_v2`, `find_similar_incidents`, `build_retrieval_index`. Marked the legacy `recommend_assignment` as v1-fallback.
2. **Mandatory sequence rewritten** — was 6 steps (`analyze → get_rules → recommend → write → save → email`); now 8 steps with explicit "build retrieval index one-time", "call v2", "reason about three signals" between.
3. **Step 4 — Recommend assignment** — replaced the `recommend_assignment` CLI example with `build_retrieval_index` + `recommend_assignment_v2` + optional `find_similar_incidents` flow. Added the full LLM-as-judge signal-weighting matrix and the 5-rule conflict-resolution recipe.
4. **Step 5 — Write the report** — replaced the OLD `Routing Signals / Reassignment Decision / Alternative Groups` template with the L'Oréal RCA template (`### WHAT HAPPENED / ### WHAT WE CHECKED / ### WHAT WE FOUND / ### WHAT WE NEED / DID`). Recommendation lives in `### WHAT WE NEED / DID` with `**REASSIGN to:** \`{group}\``, `**Confidence:**`, `**Justification:**`, `**Action:**`. Optional `Similar past tickets:` list inside the same section.
5. **Canonical-names rule** — added the same "FULL canonical assignment-group names — never shortforms" rule + 13-row shortform→canonical mapping + 4-entry L3/specialised list + `[USER-CONFIRM]` fallback guidance that lives in the SKILL.md and AGENTS.md.

### `.github/agents/rca_copilot.agent.md` (+34 / -0)

Smaller update — this file was already on the RCA template (it was the canonical reference for quick-021); it only lacked the canonical-names rule. Inserted right after the `## RCA Report Format (MANDATORY)` block, before the `## Tool Use Rules` block. Content identical to the rule added in quick-022 to `rca_copilot_agent/AGENTS.md` and `.claude/skills/rca-copilot/SKILL.md`.

## Verification

### What was tested

1. **Stale OLD-format string search** across the whole repo:
   ```
   grep -rEn "^### Routing Signals\$|^### Reassignment Decision\$|^### Alternative Groups\$" --include="*.md"
   → (no matches outside .planning/)
   ```
   Zero stale strings anywhere. ✓

2. **Canonical-names rule presence** in all 6 docs files (3 entry-points × 2 packages):
   ```
   rca_copilot_agent/AGENTS.md                       2 hits
   .claude/skills/rca-copilot/SKILL.md               2 hits
   ticketasg_copilot_agent/AGENTS.md                 2 hits
   .claude/skills/ticketasg-copilot/SKILL.md         2 hits
   .github/agents/rca_copilot.agent.md               2 hits  ← new this claim
   .github/agents/ticketasg_copilot.agent.md         2 hits  ← new this claim
   ```
   Each file has the "FULL canonical" header and the "Shorthand seen" table header. ✓

3. **Canonical-name fidelity check** — loaded all 12 canonical group names from `ticketasg_copilot_agent/assignment_rules.json` (10 L2 + 2 L3 from `l3_escalation.l2_to_l3`) and `grep`ed each one against all 6 docs files. **12/12 found verbatim in every file.** Zero typos. ✓

### Regression Report

- **No code touched.** `git diff -- ticketasg_copilot_agent/tools/ rca_copilot_agent/tools/ ticketasg_copilot_agent/mcp_server.py rca_copilot_agent/mcp_server.py ticketasg_copilot_agent/assignment_rules.json ticketasg_copilot_agent/retrieval_index.npz` is empty.
- **No rule data changed.** `assignment_rules.json` still v2.0.
- **No new dependencies.** `requirements.txt` unchanged.
- **Match rate unchanged.** v2.0's 38/64 = 59.4 % still applies — only the human-facing report template the Copilot agent uses changed.
- **Backward compatibility for `save_assignment_report` and `save_rca_report` tools** — unchanged. They store report text verbatim regardless of section headers, so callers that don't yet know about the RCA template still work.
- **Past saved reports** — `my_reports/assignment_reports/*` and `my_reports/rca_reports/*` keep their original wording. The template change applies to reports generated from this commit forward.
- **The legacy `recommend_assignment` (v1) CLI command** still exists and works. The Copilot agent's *default sequence* now uses v2, but a manual call to v1 still functions for back-compat.
- **The two updated files mirror their SKILL.md counterparts in content** — any operator reading the GitHub Copilot agent definition now sees the same instructions Claude Code users see via the skill.

### What was ruled out

- **Updating past `assignment_reports/*` files to the new format** — past reports keep their wording.
- **Adding a runtime validator** that rejects reports containing shortforms — additive; deferred. For now we trust the LLM to follow the docs (the canonical-names list is now in every doc the LLM might load).
- **Touching `rca_copilot_agent/run_tool.py`, `tools/*`, `mcp_server.py`, `assignment_rules.json`** — all explicitly out of scope; this claim is purely docs catch-up.
