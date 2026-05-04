# Claim: quick-kayinleong-006
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: in-progress
- summary: Fix rca_copilot_agent to detect customer codes and phone numbers in extract_identifiers, and update agent instructions to never skip BQ when consumer identifiers are present

## What will change
- `rca_copilot_agent/tools/incident_store.py`: add regex patterns for customer/store codes (e.g. VN0210468003452) and phone numbers to `extract_identifiers`
- `.github/agents/rca_copilot.agent.md`: add customer code and phone number to identifier→table mappings; add explicit rule to always attempt BQ lookup when any consumer identifier is found

## What has changed
(to be filled)

## Verification
(to be filled)
