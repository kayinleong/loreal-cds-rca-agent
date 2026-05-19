# Claim: quick-kayinleong-021
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: done
- summary: Converted ticketasg_copilot_agent report format to the L'Oréal RCA template (WHAT HAPPENED / WHAT WE CHECKED / WHAT WE FOUND / WHAT WE NEED / DID). The reassignment group + justification land in `### WHAT WE NEED / DID`. Docs-only change — no code, no rules, no behaviour change. Diff: AGENTS.md +21/−27, SKILL.md +25/−18.

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

1. **`ticketasg_copilot_agent/AGENTS.md`** — replaced the "Report Format" block. New template:
   - `### WHAT HAPPENED` — one-sentence symptom + current group
   - `### WHAT WE CHECKED` — four bullets, one per signal (hard rules, keyword scorer, kNN top-1, kNN weighted vote, L3 escalation) with the actual values from `recommend_assignment_v2`
   - `### WHAT WE FOUND` — one or two sentences citing which signals agreed and where they pointed
   - `### WHAT WE NEED / DID` — the recommended group + confidence + justification + reassignment action (or "no reassignment needed" with one-sentence evidence)
   - Optional `Similar past tickets:` list under `### WHAT WE NEED / DID`
   - Added an explanatory "Why this format" note: matches the wording L'Oréal L2/L3 operators already use in real SNOW work-notes; reassignment-as-action-item is the semantic right place for the recommendation

2. **`.claude/skills/ticketasg-copilot/SKILL.md`** — mirrored the same template into Step 5 of the workflow. Added an "Important — what goes WHERE" subsection clarifying that the recommendation is in `### WHAT WE NEED / DID` only, not duplicated in top-level fields.

## Verification

### What was tested

1. **`grep` check — RCA headers present in both files** ✓
   - AGENTS.md: 6 mentions of the four RCA header strings (4 in template + 2 in surrounding prose)
   - SKILL.md: 7 mentions (4 in template + 3 in prose)
2. **`grep` check — old section names removed** ✓
   - `### Reassignment Decision`, `### Routing Signals`, `### Alternative Groups`, `### How the three signals lined up`, `### My reasoning`, `### Similar past tickets` — zero matches in either file
3. **`git diff` scope** ✓
   - Exactly two files changed: `ticketasg_copilot_agent/AGENTS.md` (+21/-27 lines), `.claude/skills/ticketasg-copilot/SKILL.md` (+25/-18 lines)
   - Zero changes to: `assignment_rules.json`, any file under `tools/`, `mcp_server.py`, `run_tool.py`, `requirements.txt`, `retrieval_index.npz`, any file in `rca_copilot_agent/`, `rca_agent/`, or `schema.json`

### Regression Report

- **Behaviour unchanged.** Only the *report wording template* changed — the LLM agent is told to use different section headings when writing the analysis. The deterministic recommendation logic in `recommend_assignment_v2` is untouched: same hard rules, same keyword scorer, same kNN retrieval, same L3 escalation, same combining rules.
- **No need to re-score the 64 incidents** — match rate from quick-020 (38/64 = 59.4 %) still applies because no tool input or output changed.
- **The four RCA section headers match the canonical template** used by `rca_copilot_agent/AGENTS.md` and `.claude/skills/rca-copilot/SKILL.md` exactly (`WHAT HAPPENED` / `WHAT WE CHECKED` / `WHAT WE FOUND` / `WHAT WE NEED / DID`). This means an operator reading both rca_copilot and ticketasg_copilot reports sees consistent structure.
- **Recommendation placement** matches the user instruction: the reassignment group + justification land in `### WHAT WE NEED / DID` and nowhere else. This is the canonical "action items" semantics for the RCA template.
- **Backward compatibility for the `save_assignment_report` tool** — unchanged. The tool stores whatever report text the agent submits; it does not parse section headers, so changing the template names is transparent to the tool layer.
- **Downstream consumers** — `email_tool.send_assignment_email` reads saved report files verbatim. Subject lines and attachment behaviour unchanged. The HTML rendering treats `###` headings as `<h3>`; no broken markup expected.

### What was ruled out

- **Auto-posting RCA reports to SNOW work-notes** — out of scope. `post_comment` semantics unchanged. If an operator wants to post the new-format RCA as a work note, the existing `post_comment` workflow handles it (the agent already shows the report to the user before calling `post_comment`).
- **Updating prior saved reports** — past `assignment_reports/` files keep their original format. The template change applies only to reports generated from this commit forward.
- **Modifying the deterministic combined recommendation** — the tool still returns the same `recommended_group` / `confidence` / `source` / `signals`. The agent now wraps them in different section headers when writing the human-facing report.
