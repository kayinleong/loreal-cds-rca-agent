---
phase: phase-kayinleong-01
plan: wave2
subsystem: api
tags: [servicenow, assignment, python, bigquery]

requires:
  - phase: phase-kayinleong-01-wave1
    provides: config.py with assignment_rules_file, assignment_rules.json
provides:
  - assignment_tool.py with recommend_assignment() and get_assignment_rules()
  - 5 verbatim tool copies (snow_reader, incident_store, auth_tool, gcloud_tool, bigquery_tool)
  - email_tool.py adapted with Ticket Assignment branding
affects: [wave3]

tech-stack:
  added: []
  patterns: [pure-function-tools, singleton-cache, keyword-scoring]

key-files:
  created:
    - ticketasg_copilot_agent/tools/assignment_tool.py
    - ticketasg_copilot_agent/tools/snow_reader.py
    - ticketasg_copilot_agent/tools/incident_store.py
    - ticketasg_copilot_agent/tools/auth_tool.py
    - ticketasg_copilot_agent/tools/gcloud_tool.py
    - ticketasg_copilot_agent/tools/bigquery_tool.py
    - ticketasg_copilot_agent/tools/email_tool.py

key-decisions:
  - "recommend_assignment returns confidence as float 0.0-1.0 (proportion of total hits)"
  - "FALLBACK_GROUP = APAC - ZN - O+O.OPERATIONS - L2 when no keywords match"
  - "send_rca_email function name preserved in email_tool.py (aliased in mcp_server)"
  - "assignment_tool._load_rules() singleton cache mirrors bigquery_tool pattern"

patterns-established:
  - "Keyword scoring: count unique keyword hits × weight, rank descending"
  - "reassignment_needed: True iff current_group is non-empty AND differs from recommended"

requirements-completed:
  - phase-kayinleong-01

duration: 12min
completed: 2026-05-13
---

# Phase phase-kayinleong-01 Wave 2 Summary

**assignment_tool.py with keyword-scoring engine for 10 L2 groups + 6 adapted tool copies**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-05-13
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- `assignment_tool.py` implements deterministic keyword-scoring routing (no LLM calls)
- All 4 inline unit tests pass: SAP→SGP routing, THN no-reassignment, fallback, rules text
- 5 verbatim tool copies created (snow_reader, incident_store, auth_tool, gcloud_tool, bigquery_tool)
- `email_tool.py` adapted with 4 "Ticket Assignment" string replacements; `send_rca_email` name preserved

## Task Commits

1. **Tasks 1-3 (tools)** - `cfb868b4`

## Verification

- All 4 assignment_tool tests: PASS
- `grep -c 'Ticket Assignment' email_tool.py` → 4 ✓
- `grep 'def send_rca_email' email_tool.py` → present ✓
- `grep -r 'rca_copilot_agent' ticketasg_copilot_agent/tools/` → empty ✓

## Decisions Made
- `_FALLBACK_GROUP = "APAC - ZN - O+O.OPERATIONS - L2"` — catches unclassifiable ops tickets
- Confidence is proportional (top_score/total_score) not absolute — prevents overconfidence when few signals exist

## Deviations from Plan
None

## Issues Encountered
None

## Next Phase Readiness
- All tools importable from `ticketasg_copilot_agent/tools/`
- Wave 3 can now import `assignment_tool`, `snow_reader`, etc. in `mcp_server.py`

---
*Phase: phase-kayinleong-01*
*Completed: 2026-05-13*
