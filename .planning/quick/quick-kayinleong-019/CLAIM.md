# Claim: quick-kayinleong-019
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: in-progress
- summary: Implement FINDINGS §5.2 rewrite of ticketasg_copilot_agent assignment rules — remove high-drift keywords, add real evidence-backed signals, introduce word-boundary matching for short keys (fixes the `BA` substring trap). Verify by re-scoring the 64 incidents fetched in quick-018 and reporting before/after match rate.

## What Will Change

1. **`ticketasg_copilot_agent/assignment_rules.json`** — rules rewrite per group
   - Remove keywords that scored 100 % drift in quick-018 (e.g. `MARS` from OMNISALES, `Capgemini` from OMNISALES, `API`/`batch`/`ETL` from OPERATIONS, `lucid`/`CRM`/`loyalty`/`account` from O+O.CRM, `BA` substring from iBeauty 2.0)
   - Remove 0-hit aspirational keywords (e.g. `printer`, `cashier`, `consent`, `GDPR`, `NGLORA`, `LORA`, `webhook`, `data sync`, `cutover`, `email campaign`)
   - Add new field `boundary_keywords` — short tokens matched only on word boundaries (e.g. `BA`, `NGL`, `LS`, `ORA`, `LAN`, `KIE`, `YSL`, `KER`, `SHU`, `GA`)
   - Add evidence-backed real signals discovered in the 215 handoff phrases:
     - SAPMENA L2: `Outbound Gap`, `FindConsumerProfile`, `GetCustomerById`, `GetPurchaseV2`, `GetCalculatedAttributes`, `E2E Monitoring`, `stg_sap_`, `SFCC -> CDS`, `SFMC Prospect`
     - O+O ONLINE.CED: `SFCC`, `Arvato`, `EBTQ`
     - O+O.CRM: `SFMC`, `SFDC`, `CRM001`, `Prospect Ingestion`, `consumer registration`
     - O+O.NGLORA: `NGL` (boundary), `points credit`, `points redemption`, `Rule-500`
     - HIP: `CloudSQL`, `Replica`, `Linux Host`, `Cloudflare`, `Cloudfare` (sic), `Azure`, `FS usage`, `disk usage`
     - SPACE B2C Hypercare: `LS team`, `Hypercare group`, `LS Hypercare`
     - Note bump: `[USER-CONFIRM]` becomes `[EVIDENCE-BASED v1.1]` for groups validated against the 64-incident sample (SAPMENA L2 + B2C Hypercare); flag stays `[USER-CONFIRM]` for the 8 groups that had 0 tickets in the sample

2. **`ticketasg_copilot_agent/tools/assignment_tool.py`** — code change to support `boundary_keywords`
   - Add `boundary_keywords` to the per-group scoring loop
   - Use compiled `re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)` for boundary matches
   - Existing `keywords` (substring) behaviour unchanged — backward compatible
   - Update built-in defaults to include the new field (default: empty list)

3. **Verification scripts under `.planning/quick/quick-kayinleong-019/scripts/`**
   - `rescore.py` — loads `_all_incidents.json`, calls the actual `recommend_assignment()` function (so we test the real code path), produces a before/after match-rate table

4. **`SUMMARY.md`** — front-matter `status: complete`, before/after match rates, per-group rationale, no surprises

## What Has Changed

(To be filled when complete.)

## Verification

(To be filled when complete.)

## Scope discipline (what is NOT in this claim)

- L2 ↔ L3 schema modelling — deferred to quick-020. The current sample shows
  31 % (20/64) of mispredictions are L3 tickets, but adding an `l3_groups` mapping
  and the corresponding code branch is a larger architectural change that deserves
  its own claim and proper planning.
- Negative keywords — deferred. Useful but additive, can ship after.
- Re-fetch wider queue to validate the 8 zero-sample canonical groups — deferred,
  optional (the FINDINGS recommend this; if the user proceeds, those 8 groups'
  keywords are still flagged `[USER-CONFIRM]` not `[EVIDENCE-BASED]`).
- Touching `rca_copilot_agent/` — out of scope; this claim only touches
  `ticketasg_copilot_agent/`.

## Expected outcome

Before quick-019: match rate 11/64 = 17.2 % overall; 11/35 = 31.4 % on canonical-group tickets.
After quick-019: target match rate **≥ 25 %** overall; **≥ 50 %** on canonical-group tickets.
If the new rules score worse than that, this claim status becomes `abandoned` and
nothing ships.
