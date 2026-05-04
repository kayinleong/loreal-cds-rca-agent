# Claim: quick-kayinleong-006
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-04
- status: done
- summary: Fix rca_copilot_agent to detect customer codes and phone numbers in extract_identifiers, and update agent instructions to never skip BQ when consumer identifiers are present

## What will change
- `rca_copilot_agent/tools/incident_store.py`: add regex patterns for customer/store codes (e.g. VN0210468003452) and phone numbers to `extract_identifiers`
- `.github/agents/rca_copilot.agent.md`: add customer code and phone number to identifier→table mappings; add explicit rule to always attempt BQ lookup when any consumer identifier is found

## What has changed
- `rca_copilot_agent/tools/incident_store.py`: added `customer_codes` extraction (2-letter country + digits pattern, e.g. `VN0210468003452`) and `phone_numbers` extraction (9-15 digit sequences) to `extract_identifiers`
- `rca_copilot_agent/mcp_server.py`: updated `analyze_incident` tool description to explicitly list new identifier types and enforce BQ follow-up
- `.github/agents/rca_copilot.agent.md`:
  - Step 2 BQ trigger broadened from "order IDs or pipeline identifiers" to "ANY identifiers"
  - Added hard rule: never skip BQ when customer code, phone, email, EAN, or any consumer identifier is present
  - Added `customer code` and `phone number` rows to B2C identifier→table mapping

## Verification
- Tested regex against INC10425353 text: `VN0210468003452` correctly detected as customer code; `0984093452` correctly detected as phone number
- Deduplication logic preserved (set conversion)
- No existing patterns modified — only additive changes
- Regression surface: `extract_identifiers` is additive; new keys (`customer_codes`, `phone_numbers`) don't affect existing callers that only read `order_ids`, `user_ids`, `ean_codes`, `emails`
