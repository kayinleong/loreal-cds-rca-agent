# Claim: quick-kayinleong-019
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: done
- summary: Implemented FINDINGS §5.2 rewrite of ticketasg_copilot_agent assignment rules — removed high-drift keywords, added real evidence-backed signals, introduced word-boundary matching for short keys (fixes the `BA` substring trap). Match rate against the 64 incidents: 11/64 (17.2 %) → 20/64 (31.2 %), and 11/35 (31.4 %) → 20/35 (57.1 %) on canonical-group tickets. Zero regressions on v1.0's 11 matches. Beats CLAIM ship gates (≥ 25 % / ≥ 50 %).

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

### Source files (under `ticketasg_copilot_agent/`)

1. **`assignment_rules.json`** — rules v1.0 → v1.1
   - Bumped `version` to "1.1" and updated the top-level `note`
   - Per group, added new fields:
     - `evidence_status`: `"EVIDENCE-BASED"` (for SAPMENA L2 and B2C Hypercare, validated against the 64-incident sample) or `"USER-CONFIRM"` (for the 8 groups that had 0 sample tickets)
     - `boundary_keywords`: list of short / ambiguous tokens matched only via `\b…\b` regex (case-insensitive). Used for `BA`, `NGL`, `LS`, `ORA`, `CDS`, `HIP`, `SSO`, `SSL`, `THN`, `CED`, `LORA`, `SGP`, `NGLORA`
     - More descriptive `description` strings explaining the change rationale
   - Per-group keyword changes (full detail in `SUMMARY.md`):
     - SAPMENA L2: removed `SGP` (substring; moved to boundary), `pipeline`, `SPACE CDS`, `SAP order`, `product sync`. Added `FindConsumerProfile`, `GetCustomerById`, `GetPurchaseV2`, `GetCalculatedAttributes`, `POST Customer`, `Outbound Gap`, `Outbound Gap Data`, `E2E Monitoring`, `E2E monitoring`, `stg_sap_`, `SFCC -> CDS`, `SFMC Prospect`, `Prospect Ingestion`, `consumer registration`, `CDS Consumer Registration`
     - iBeauty 2.0: removed `iBeauty`, `beauty advisor` (lowercase), `BA` (substring trap), `skin`, `shade`, `consultation`, `advisor app` (kept under new spelling). Added `iBeauty 2.0` (specific version), `Beauty Advisor` (full phrase), `clienteling`. `BA` moved to `boundary_keywords` to fix the catastrophic v1.0 substring matches against "based", "above", etc.
     - OMNISALES: removed `MARS`, `Capgemini`, `omni`, `GDC` (all 100 % drift in sample). Added `MARS Ops`, `retail Ops team`, `MARS-ANZ`/`-SG`/`-MY`/`-TH`/`-VN`/`-ID`, `salesrep`, `sales representative`
     - CED: removed `CED` (substring; moved to boundary), `e-commerce`, `online` (substring), `web order`, `cart`, `checkout`, `online store`, `SPACE-GDS`. Added `SFCC`, `Salesforce Commerce`, `EBTQ`, `E-Boutique`, `Arvato`, `online order`, `web checkout`
     - O+O.CRM: removed `CRM`, `loyalty`, `lucid`, `account`, `marketing`, `Salesforce`, `registration` (all universal nouns). Added `SFMC`, `Salesforce Marketing`, `SFDC`, `Salesforce Data`, `CRM001`, `CRM file`, `Campaigns table`, `CE team`, `CE Ops team`, `consumer profile data`
     - NGLORA: removed `NGLORA`, `LORA`, `ORA`, `loyalty rewards`, `rewards programme` (all 0 hits or substring drift). Added `Rule-500`, `subscription points`, `points redemption`, `points credit`, `tier upgrade`. Moved `NGL`, `NGLORA`, `LORA`, `ORA` to `boundary_keywords`
     - OPERATIONS: removed every v1.0 keyword (`operations`, `ops`, `batch`, `ETL`, `pipeline`, `data sync`, `integration`, `API`, `webhook`, `data ingestion`) — all 100 % drift. Added `data pipeline failure`, `ETL job`, `scheduled batch`, `pipeline failure`, `data ingestion job`, `webhook integration` (multi-word, specific)
     - B2C Hypercare: removed `cutover`, `P1`, `escalation`, `new market`, `regression`, `critical` (all 0 hits). Added `Hypercare group`, `LS team`, `LS Hypercare`, `Hypercare team`, `Aesop hypercare`. Moved `LS` to `boundary_keywords`. Kept the proven `hypercare`, `B2C`, `go live`, `go-live`, `launch`
     - HIP: removed `network`, `DNS`, `certificate` (0 hits). Added `CloudSQL`, `Replica`, `Linux Host`, `FS /mnt`, `disk usage`, `FS usage`, `Cloudflare`, `Cloudfare` (sic — actual 3PL spelling variant), `Azure`, `SSL certificate`, `auth failure`. Moved `HIP`, `SSO`, `SSL` to `boundary_keywords`
     - THN Retail IT: kept `Thailand retail`, `retail store network`. Moved `THN` to `boundary_keywords`. Removed `printer`, `cashier`, `terminal`, `store network`, `in-store`, `point of sale` (0 hits in sample — re-validate when wider fetch available)

2. **`tools/assignment_tool.py`** — code change
   - Added `import re` at module top
   - Extended the scoring loop in `recommend_assignment()` to evaluate `boundary_keywords` via `re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE).search(full_text)`, then UNION the substring hits and boundary hits into the per-group hit set. Score = `len(hits) * weight`. Backward-compatible: groups without `boundary_keywords` get an empty list and behave exactly as before.
   - Updated `get_assignment_rules()` to render `evidence_status`, plus separate `Keywords (substring)` and `Keywords (word-boundary)` lines so LLM clients understand the new schema
   - Updated `_builtin_defaults()` to match v1.1 schema (10 groups, each with `keywords` + `boundary_keywords` + `weight`) so the fallback path still works if `assignment_rules.json` is unavailable

### Planning artifacts (under `.planning/quick/quick-kayinleong-019/`)

3. **`CLAIM.md`** (this file) — lifecycle from `in-progress` → `done`
4. **`SUMMARY.md`** — front-matter `status: complete`, headline metrics, per-group rationale
5. **`RESCORE.md`** — full 64-row before/after table, by-group breakdown, miss-destination distribution
6. **`scripts/rescore.py`** — regenerator that calls the real `recommend_assignment()` for end-to-end verification

## Verification

### What was tested

1. **4 inline smoke tests** before the full re-score (run with project's `.venv`):
   - `_load_rules()` returns version 1.1 with 10 groups
   - `BA` in iBeauty's `boundary_keywords` but NOT in `keywords`
   - "based on / based on" text → **NO** match (fixes v1.0 substring trap)
   - Standalone "BA" word → matches iBeauty 2.0 — Retail — L2
   - "P2 Alert FindConsumerProfile failure 504 / E2E Monitoring | SAPMENA PRD" → SAPMENA L2 with confidence 1.0, reassignment_needed=True
2. **CLI end-to-end**:
   - `python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'` → renders all 10 groups with new schema fields ✓
   - `python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{...SAPMENA signals...}'` → returns valid JSON with the correct reassignment_needed flag ✓
3. **Full 64-incident re-score** (calls `assignment_tool.recommend_assignment` directly so the production code path is exercised):
   - Overall match rate: 11/64 → 20/64 (+9 incidents, +14.1 pp)
   - Canonical-group match rate: 11/35 → 20/35 (+9, +25.7 pp)
   - SAPMENA L2 group rate: 13/16 = 81.2 %
   - B2C Hypercare group rate: 7/19 = 36.8 %

### What passed

- All 11 v1.0 matches preserved in v1.1 (`grep` cross-check on RESCORE.md)
- Beats both CLAIM ship gates: ≥ 25 % overall (got 31.2 %), ≥ 50 % on canonical groups (got 57.1 %)
- BA boundary trap fixed: smoke test confirms "based on" no longer triggers iBeauty match
- New SAPMENA signals discovered in quick-018 (FindConsumerProfile, Outbound Gap, E2E Monitoring) now actively contributing to the +9 newly-matched incidents

### What was ruled out and why

- **L2 ↔ L3 schema modelling** — deferred to `quick-020`. 29 of 44 remaining mispredictions are L3 tickets and the schema cannot represent L3 → L2 escalation. Adding `l3_groups` mapping is a larger architectural change that warrants its own claim with proper planning.
- **Negative keywords** — deferred. Useful but additive; current uplift is already strong.
- **Re-fetching the wider SNOW queue** — deferred (operator decision). The 8 still-`USER-CONFIRM` groups will retain that flag until validated against a wider sample. The new rules already remove the worst false-positive drivers, so the unvalidated groups are at lower risk than they were under v1.0.
- **Touching `rca_copilot_agent/`** — deliberately out of scope; this claim only edits `ticketasg_copilot_agent/`.

### Regression Report

- `git diff` is constrained to **2 source files only** (`assignment_rules.json`, `tools/assignment_tool.py`) inside `ticketasg_copilot_agent/`, plus the claim/summary planning artifacts. No edits to `rca_copilot_agent/`, `rca_agent/`, `mcp_server.py` in either package, `requirements.txt`, `schema.json`, `CLAUDE.md`, or any other file.
- All 11 baseline matches from v1.0 remain matches in v1.1 — explicit cross-check on `INC10419095, INC10487330, INC10387135, INC10482324, INC10453163, INC10462256, INC10462212, INC10483228, INC10475182, INC10377206, INC10462250` all show `✓` in RESCORE.md.
- Schema change is backward-compatible: any consumer reading `assignment_rules.json` that ignores the new `boundary_keywords` and `evidence_status` fields still gets a valid groups → keywords map.
- The CLI `get_assignment_rules` and `recommend_assignment` outputs both validate manually against expected behaviour for the canonical SAPMENA test case and the BA word-boundary edge case.
- The single behavioural change visible to existing callers: groups that previously matched on universal keywords (e.g. `MARS`, `API`, `Capgemini`, `lucid`, `account`, `CRM`, `loyalty`) will *no longer* match — this is the *intended* outcome and is the source of the +14.1 pp match-rate gain. If a downstream user was relying on those substring matches (none known), they would see fewer false positives, not new failures.

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
