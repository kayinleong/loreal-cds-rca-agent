# Claim: quick-kayinleong-016
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-06
- status: done
- summary: Update rca_copilot_agent AGENTS.md with two business feedback items — phone LIKE trailing search and LUCID/MARSID brand+isocountry disambiguation

## What Changed

File: `rca_copilot_agent/AGENTS.md`

1. **Phone number search** — replaced `REGEXP_REPLACE(phonenumber, r'[^0-9]', '') LIKE '%…%'` with `phonenumber LIKE '%<digits>'` (trailing/suffix match) in:
   - Phase 3 VALIDATE pattern table (generic phone lookup row)
   - B2B checklist query #2 (`customer.phonenumber`)
   - B2B checklist query #3 (`cfs_master.professionalmobilenumber`)
   - Added new Query Rule #5 explaining the rationale (CDS strips non-digits and prepends country code on insert)

2. **LUCID / MARSID multi-brand disambiguation** — same LUCID can exist across brands in `consumer_pii` and `external_system_ids`:
   - Added Query Rule #4 mandating `signature` (brand) and `isocountry` in SELECT, and as WHERE filters when incident context provides them
   - Updated Key Identifier → Table Mappings LUCID row with brand/isocountry note

## Verification

- Confirmed no residual `REGEXP_REPLACE` patterns remain in SQL examples (only in explanatory prose)
- All three phone lookup sites updated consistently
- LUCID guidance added to both the rule block and the identifier mapping table
- Regression surface: AGENTS.md is instruction-only (no executable code) — no runtime regressions possible
