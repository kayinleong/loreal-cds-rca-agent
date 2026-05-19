# Claim: quick-kayinleong-021
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: in-progress
- summary: Convert ticketasg_copilot_agent report format to the L'Oréal RCA template (WHAT HAPPENED / WHAT WE CHECKED / WHAT WE FOUND / WHAT WE NEED / DID). The reassignment group + justification land in `### WHAT WE NEED / DID`. Docs-only change — no code, no rules, no behaviour change.

## What Will Change

1. **`ticketasg_copilot_agent/AGENTS.md`** — replace the "Report Format" block with the canonical RCA template used by `rca_copilot_agent` and adapted for assignment-routing context:
   - `### WHAT HAPPENED` — one-sentence incident summary (current group, short description)
   - `### WHAT WE CHECKED` — bullet list of the four routing signals consulted (hard rules, keyword scorer, kNN retrieval, L3 escalation), each with the matched/unmatched outcome
   - `### WHAT WE FOUND` — one-or-two-sentence conclusion citing which signals agreed and where they pointed
   - `### WHAT WE NEED / DID` — **the recommended assignment group + the justification + the reassignment action** (or "no reassignment needed" with reason)

2. **`.claude/skills/ticketasg-copilot/SKILL.md`** — same template change, kept in sync with AGENTS.md.

## What Will NOT Change

- No code in `ticketasg_copilot_agent/tools/*`
- No edits to `assignment_rules.json`
- No new tools, no MCP changes
- The deterministic recommendation logic in `recommend_assignment_v2` is unchanged — only the *report wording* the LLM writes after the tool call changes
- No re-score needed — match-rate metrics from quick-020 still apply
- `rca_copilot_agent/` not touched

## What Has Changed

(To be filled when complete.)

## Verification

(To be filled when complete.)
