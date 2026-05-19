# Claim: quick-kayinleong-023
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: in-progress
- summary: Catch up the two GitHub Copilot agent definitions under `.github/agents/` with the doc changes from quick-020 (v2 hybrid recommender), quick-021 (RCA report template), and quick-022 (canonical-names rule + shortform mapping). These two files were missed by all three earlier claims, so users invoking the agents via GitHub Copilot are still seeing the v1 keyword-only flow and the OLD `Routing Signals / Reassignment Decision / Alternative Groups` report format.

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

(To be filled when complete.)

## Verification

(To be filled when complete.)
