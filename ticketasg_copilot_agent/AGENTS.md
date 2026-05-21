# AGENTS.md — Ticket Assignment Copilot Agent

> Instruction schema for GitHub Copilot (or any MCP-aware LLM client).
> All LLM reasoning stays in the client. This server exposes only pure-function tools.

## Purpose

Investigate L'Oréal SPACE CDS ServiceNow incidents and produce **the same RCA report that `rca_copilot_agent` produces, with an additional `### REASSIGNMENT DECISION` section appended as the last section**. The agent:

1. Investigates the incident's root cause using ticket text, attachments, identifiers, and BigQuery data — the canonical `### WHAT HAPPENED / WHAT WE CHECKED / WHAT WE FOUND / WHAT WE NEED / DID` template.
2. Always appends a `### REASSIGNMENT DECISION` section at the end stating whether reassignment is needed, the target group (full canonical SNOW name), confidence, signals checked, and justification.

**The reassignment section is ALWAYS present**. When the current group is already correct, the body is `**NO REASSIGNMENT NEEDED.**` plus a one-line evidence statement; when reassignment is recommended, the body is the structured REASSIGN block.

## CDS Incident Handling Guidebook — apply these rules to every analysis

These rules come from the L'Oréal KT session (Dipti Patil) captured in the CDS Incident Handling Guidebook. They drive the root-cause investigation in `### WHAT WE CHECKED` and `### WHAT WE FOUND`.

### The 3-question framework (apply BEFORE scoring any assignment group)

If you cannot solve an incident, it is almost always because one of these three questions has not been answered correctly. Answer them in order:

1. **What data is impacted?** Consumer or purchase? Be specific.
2. **Is it migrated or ongoing?** Use source creation datetime vs market go-live. Use LUCID prefix (C2 → migrated, C5 → ongoing) to confirm.
3. **Which system owns that responsibility?** Migrated → LS owns historical sends. Ongoing → CDS owns API + CE batch. Mars owns Mars ID.

If these are clear, the correct action — and the correct routing — usually becomes obvious.

### Five-step standard analysis (Section 9)

Follow these in order. Do not skip ahead.

- **Step 1 — Understand the ask.** What exactly is missing or wrong? Consumer? Order? Loyalty points? Brand / civility / location? Which market / country? Which system raised the issue (CDS, Mars, Loyalty, SFMC, SA)? What does the requester expect to see?
- **Step 2 — Identify data type.** Consumer issues: cannot find consumer / duplicate / wrong details (civility, brand, status) / inactive Mars ID. Purchase issues: missing orders / incorrect order amount / loyalty points not awarded.
- **Step 3 — Check creation timing.** Always pull both `Source creation datetime` and `Order datetime` (for purchases). Compare against market go-live to decide migrated vs ongoing.
- **Step 4 — Migration check (C2 LUCID).** Confirm `Source Consumer Key` populated and `LS Customer ID` exists. If a downstream system is missing the record, **do NOT ask CDS to resend** — LS owns historical sends to CDS and Loyalty. Route or escalate to the LS team.
- **Step 5 — Ongoing data check (C5 LUCID).** Confirm API ingestion in CDS; consumer in `CONSUMER_PII_TBL`; Mars ID linkage in `EXTERNAL_SYSTEM_IDS_TBL`. If Mars does not have the consumer, confirm whether the CE nightly batch ran and the consumer was picked up. Ask CE team for file name and run confirmation, then ask Mars to ingest the file. Do not assume CDS is broken until you have evidence.

### Common SPACE CDS patterns (Section 10) — pattern-match before recommending

| Pattern | Correct handling |
|---|---|
| **Loyalty points missing** | Migrated → LS owns historical sends to Loyalty; CDS does NOT push historical purchases. Ongoing → check downstream event/extract flow from CDS; confirm order exists in CDS first. Common mistake: raising a CDS defect without first confirming the purchase is in CDS. |
| **"Consumer not found in Mars"** | Confirm consumer in CDS (`CONSUMER_PII_TBL`); check `EXTERNAL_SYSTEM_IDS_TBL` for Mars ID + status; ask CE team when extract last ran and whether this consumer was included; ask Mars to ingest the file. |
| **Brand / civility / code mismatch** | CDS rejects unknown codes — it's a source-data compliance issue, not a CDS bug. Action: ask source system (e.g. Mars) to fix the mapping. Do NOT patch CDS to accept bad codes without approval. |
| **Missing orders** | Migrated → LS owns the historical send. Ongoing → check inbound MARS OrderHeader / OrderItem feeds for the date in question. Always confirm source order number, order datetime, country signature. |
| **Incorrect order amount** | Compare source order vs CDS `PURCHASE_TBL`. If CDS matches source → downstream issue (Loyalty / reporting); do NOT patch CDS. If CDS does not match source → check OrderHeader / OrderItem ingestion. |
| **Brand / location data wrong** | Brand and location often do NOT originate from CDS. Identify upstream system (typically Counter / BA feeds from MARS or CEGID). Avoid defaulting every metadata issue to CDS. |

### Status mismatch (PI vs External System ID) (Section 11)

> Observed scenario: PI status = inactive, External System ID = active (or vice versa).
>
> Expected behaviour: only ONE active Mars ID per consumer. Older Mars IDs are inactivated when a new one is created.

**Action: verify the scenario before raising RCA.** A status mismatch is NOT automatically a defect — it may be expected lifecycle behaviour. Only escalate if it is genuinely inconsistent with the rule above.

### Common mistakes — never do this (Section 12)

- ✗ Checking the wrong country / market.
- ✗ Jumping to merge requests or data patches without root cause.
- ✗ Asking CDS to resend migrated data — that is LS's responsibility.
- ✗ Providing RCA without verifying source creation dates.
- ✗ Responding without screenshots or model checks.
- ✗ Defaulting every metadata issue to CDS without identifying the upstream owner.
- ✗ Treating standardised-code rejections as CDS bugs.

### Key identifiers (Section 5)

| Identifier | Description |
|---|---|
| **LUCID** | L'Oréal Unique Consumer ID. Generated only by CDS. Same email or mobile within a country → same LUCID across brands. |
| **LUCID prefix C2** | Migrated consumer (LS-sourced). |
| **LUCID prefix C5** | Ongoing consumer (created via real-time API after go-live). |
| **Mars ID** | Generated by Mars after CDS sends consumer data. Multiple may exist but only ONE is active at a time; CDS inactivates older ones when a new one is created. |
| **Source Consumer Key (LS Customer ID)** | LS-side customer identifier. If populated, strong signal the consumer is migrated. |

### Mandatory screenshot fields (Section 8) — verify when reading attachments

Screenshots ARE evidence. If a screenshot is missing any of the fields below, flag the analysis as incomplete and downgrade confidence.

- **Consumer incidents:** ISO Country / Country Signature; LUCID; Secondary key (Email for ANZ, Mobile elsewhere); Source creation datetime; System created / updated datetime; External System IDs + Status (Mars ID + Active/Inactive); Source Consumer Key (LS Cust ID).
- **Purchase incidents:** ISO Country / Country Signature; LUCID; Source order number; Order datetime; System created / updated datetime.

Rule: `source creation datetime` ≠ `system created datetime`. Use the **source** datetime to decide migrated vs ongoing.

### Go-live timeline (Section 4)

| Region | Markets | Go-live |
|---|---|---|
| ANZ | AU, NZ | Mid-July 2025 (year assumed; confirm with reviewer) |
| SEA rollout | SG, MY, ID, TH, VN, PH | Mid-December 2025 |

Creation date BEFORE market go-live → migrated (LS). AFTER → ongoing (API).

### Brand & country reference (Section 6) — ANZ inbound

`01` Lancôme (MARS, AU/NZ), `16` Giorgio Armani (MARS, AU), `24` La Roche-Posay (SFMC, AU), `25` Brand 25 (SFMC, AU), `42` SkinCeuticals (MARS, AU), `45` Kiehl's (MARS, AU/NZ), `51` YSL Beauty (MARS, AU), `75` IT Cosmetics (SFMC, AU), `85` AESOP (**CEGID, NOT MARS**, AU/NZ), `C4` Kérastase (SFMC, AU).

**Critical:** AESOP (signature `85`) is sourced via CEGID. If you see signature `85` on an incident, the inbound flow is CEGID — do not look for it in MARS feeds.

### Inbound feeds + PROD times (UTC+8, Section 7)

| Data object | Source | CDS interface | PROD time |
|---|---|---|---|
| Consumer (Cust_Basic) | MARS | IN MARS Cust_Basic | 01:45 (AU) / 03:45 (NZ) |
| Order Header | MARS | IN MARS OrderHeader | 01:46 (AU) / 03:46 (NZ) |
| Order Item | MARS | IN MARS OrderItem | 01:46 (AU) / 03:46 (NZ) |
| BA (Master) | MARS | IN MARS BA | 01:47 |
| Counter (Master) | MARS | IN MARS COUNTER | 01:48 |
| CBR Items | MARS | IN MARS CBR | 01:49 |
| BA / Counter (AESOP) | CEGID | IN CEGID BA / COUNTER | 01:47 |
| Product / Hierarchy | SAP | IN SAP Product / Hierarchy | 00:30 |
| Campaign / Target / Response | SFMC | IN SFMC Campaign / Targ / Resp | 05:30 |
| Opt-In | SFMC | IN SFMC OptIn | 05:30 |
| Prospect | SFMC | IN SFMC Prospect | 06:00 |
| Calculated Attributes | CE | IN CE CalculatedAttributes | 05:30 |
| Inactive Consumer Delete | CE | IN CE Delete Inactive Consumer | 05:30 |

When an object is missing, first check whether the relevant inbound file arrived on schedule and processed cleanly. A missing file is a different problem from a rejected record.

### Expectations from L2 / L3 (Section 13)

- Perform first-level analysis independently.
- Use the CDS data model and B2C Mapping Doc V3 to validate fields and routing.
- Bring specific, evidenced doubts to KT calls — not open-ended questions.
- Provide on every ticket: clear analysis, screenshots with all mandatory fields, and a logical conclusion.
- Escalate only when needed, with evidence.

## Tool Inventory

| Tool | When to use |
|------|-------------|
| `analyze_incident` | **START HERE** — ONE-STOP: fetch incident + identifiers + attachments |
| `fetch_incidents` | Bulk-download all incidents from a SNOW list URL |
| `get_incident` | Fetch a single live incident by number |
| `get_incident_summary` | Read full incident text from local cache |
| `list_incidents` | Discover what is locally available |
| `search_incidents` | Keyword-search across all local incidents |
| `extract_identifiers` | Pull structured identifiers (LUCID, Mars ID, orders, EAN) from a cached incident |
| `download_attachments` | Download screenshots / files for an incident (use when `analyze_incident`'s auto-download failed) |
| `post_comment` | Post comment / work note to SNOW (confirm with user first) |
| `list_bq_tables` | List BigQuery tables in the SPACE CDS dataset (instant; reads `schema.json`) |
| `get_schema` | Get columns + ready-to-use query patterns for a BQ table |
| `query_bigquery` | Run a read-only SELECT / WITH against SPACE CDS data — **use to confirm migrated-vs-ongoing**, presence of consumer / order / Mars ID linkage |
| `get_assignment_rules` | **READ BEFORE RECOMMENDING** — routing matrix (10 groups + keywords + hard rules + L3 escalation) |
| `recommend_assignment_v2` | **USE THIS** — hybrid recommender: hard rules + keyword + retrieval + L3 escalation. Returns all signals separately. |
| `find_similar_incidents` | kNN retrieval — top-5 semantically-similar tickets in the local corpus. Use as a second-opinion signal. |
| `build_retrieval_index` | Run once after `fetch_incidents` to refresh the kNN corpus. |
| `recommend_assignment` | Legacy v1 keyword-only path. Prefer `recommend_assignment_v2`. Kept for backward-compat. |
| `save_assignment_report` | **MANDATORY** — save every completed RCA + reassignment report to disk |
| `send_assignment_email` | **MANDATORY** — notify the human when the session is done |

## Mandatory Sequence (no exceptions)

1. `analyze_incident` — gather incident data, identifiers, and attachments
2. **Apply the 3-question framework** to the incident text and identifiers BEFORE scoring any group. The answer to "migrated vs ongoing" + "which system owns it" often makes the routing decision obvious.
3. `get_assignment_rules` — read the routing matrix, hard rules, and L3 escalation map
4. If the retrieval index does not yet exist (first analysis after `fetch_incidents`), call `build_retrieval_index` — one-time per fetch
5. **Investigate root cause with BigQuery** when identifiers are present:
   - `list_bq_tables` → `get_schema <table>` → `query_bigquery <SELECT>`
   - Typical checks: consumer in `CONSUMER_PII_TBL`, Mars ID + status in `EXTERNAL_SYSTEM_IDS_TBL`, order in `PURCHASE_TBL` / `PURCHASE_ITEM_TBL`, source vs CDS amount comparison, recent inbound feed status
   - **Run multiple queries. One is never enough.** "0 rows" IS a finding.
   - If BigQuery is unavailable (no gcloud ADC, etc.), degrade gracefully: state the unverified hypotheses explicitly in `### WHAT WE CHECKED` and downgrade confidence.
6. `recommend_assignment_v2` — get the combined recommendation plus all four signals
7. **REASON about the four signals** (see "LLM-as-judge" below) — weigh hard-rule vs keyword vs retrieval vs L3 escalation and explain your final choice in `### REASSIGNMENT DECISION`
8. Write the RCA + reassignment report (see Report Format below)
9. `save_assignment_report` — **MANDATORY**: save before outputting the report
10. After ALL incidents in the session: `send_assignment_email` — **MANDATORY** notification

**Never skip steps 2, 5, 7, 9, or 10.**

## LLM-as-judge — how to read the three signals from `recommend_assignment_v2`

`recommend_assignment_v2` returns a JSON object whose top-level fields are the **deterministic combined answer** (`recommended_group`, `confidence`, `reason`, `source`). The `signals` sub-object gives you the raw inputs.

| Signal | Strong evidence | Weak evidence |
|---|---|---|
| `signals.hard_rule` | Non-null (a regex matched) → **trust it** — these are tested high-precision shortcuts (MARS-{country}, Linux Host, etc). | `null` — no shortcut fired; nothing learned. |
| `signals.keyword.confidence` | ≥ 0.5 with 3+ matched keywords → keyword scorer is confident | ≤ 0.2 with 1 keyword → likely a single substring coincidence |
| `signals.retrieval.top1.score` | ≥ 0.7 → semantically very similar ticket exists in corpus → very strong | < 0.5 → corpus has no close match → ignore retrieval |
| `signals.retrieval.weighted_vote.tally` | One group has > 1.5 summed score AND ≥ 2 neighbours → consensus | scores split roughly equally → no consensus |
| `signals.l3_escalation.signals_matched` | Non-empty AND keyword winner has an `escalated_from_to` → recommend the **L3** group | Empty → stay at L2 |

### Conflict-resolution rules (write your reasoning in the report)

1. **Hard rule** wins everything else. If `signals.hard_rule` is non-null, recommend its target.
2. If **escalation signals fired** and a `escalated_from_to.to` is given, recommend the L3 target unless the hard rule disagrees.
3. If **keyword and retrieval top-1 agree** AND retrieval top-1 score ≥ 0.6, recommend that group with high confidence.
4. If **keyword and retrieval top-1 disagree** — explain both in the report and prefer:
   - Retrieval when retrieval top-1 score ≥ 0.7 and ≥ 2 of top-5 are the same group
   - Keyword otherwise (the rules are validated; retrieval may be noisy on under-represented groups)
5. If **all signals are weak** (no hard rule, keyword conf < 0.2, retrieval top-1 < 0.5) — explicitly flag the recommendation as low-confidence and recommend human review.

### When to consult `find_similar_incidents` separately

Call it when:
- `recommend_assignment_v2.source` was `keyword` AND the recommendation goes to `OPERATIONS - L2` (the fallback) — retrieval may surface a better neighbour
- You want to cite specific historical tickets in your reasoning ("similar to INC10293500 which resolved in OMNISALES")
- The user asks "what other tickets look like this one"

## Report Format — RCA + Reassignment Decision (MANDATORY)

The report is **bipartite**: the canonical RCA template used by `rca_copilot_agent` (four `###` headers focused on root cause), then a `### REASSIGNMENT DECISION` section appended as the LAST section. The reassignment section is **always present** — its body differs based on whether reassignment is needed.

```markdown
# RCA Report: {INCIDENT_NUMBER}
**{incident_title}**
*Investigated: {YYYY-MM-DD}*

---

### WHAT HAPPENED
{One sentence — the symptom as reported, not the cause.}
Example: "Order YSL001234 placed 2025-11-01 is not visible in the CDS portal for AU/YSL Beauty consumer (LUCID C5xxxxxxxx)."

### WHAT WE CHECKED
{Arrow-prefixed evidence lines, sourced from the incident's comments, work notes, attachments, AND BigQuery query results. Quote dates, authors, error messages, and data points.}
→ Checked work notes — {what found, who, when}
→ Checked attachments — {OCR / screenshot findings; flag any missing mandatory fields from Section 8}
→ Checked LUCID prefix — {C2 → migrated / C5 → ongoing}
→ Checked source creation datetime vs market go-live — {migrated / ongoing decision}
→ Checked BigQuery `CONSUMER_PII_TBL` — {consumer found / not found; signature + isocountry}
→ Checked BigQuery `EXTERNAL_SYSTEM_IDS_TBL` — {Mars ID + status (active/inactive)}
→ Checked BigQuery `PURCHASE_TBL` — {order found / not found; amount; status}
→ Checked inbound feed timing — {`IN MARS OrderHeader` processed at HH:MM UTC+8 / not processed}

### WHAT WE FOUND
{One or two sentences — the actual root cause with evidence. Reference the 3-question framework: what data, migrated or ongoing, which system owns it. If root cause is unclear, state what is known vs unknown.}
Example: "Order is ongoing (C5 LUCID, source datetime 2025-11-01 11:24 SGT is after AU go-live). PURCHASE_TBL contains the row but EXTERNAL_SYSTEM_IDS_TBL shows Mars ID inactive — this is expected lifecycle (Section 11) because a newer Mars ID was created on 2025-11-15. Not a defect."

### WHAT WE NEED / DID
{Bulleted action items, with owner from work notes. Use FULL canonical assignment-group names (see rule below).}
- {Owner / Team}: {specific action — e.g. "CE team: confirm whether IN MARS OrderHeader extract on 2025-11-02 included LUCID C5xxxxxxxx"}
- {Owner / Team}: {action}
- Closing note: {one-line summary of what was done in this session — e.g. "Root cause confirmed as expected Mars-ID lifecycle; closing as Not a Defect."}

### REASSIGNMENT DECISION

{ALWAYS include this section. Two body variants:}

{Variant A — when recommended group ≠ current_group:}

**REASSIGN to:** `{full canonical SNOW group name}`
**Confidence:** {0-100 %}
**Source:** {hard_rule | l3_escalation | retrieval+keyword | retrieval_top1 | keyword}
**Signals checked:**
→ Hard rules — {matched: rule + target group / no match}
→ Keyword scorer — {group} (conf {0.00-1.00}, matched: {kw1, kw2, ...})
→ kNN retrieval (top-1) — INC{nnnnnn} → `{group}` (similarity {0.00-1.00})
→ kNN retrieval (weighted vote) — {`{group}`: sum, `{group}`: sum, ...}
→ L3 escalation signals — {triggered: signal1, signal2, ... / not triggered}
**Justification:** {Which signals led here. Cite specific keywords / similar tickets / hard rules. If you overrode the combined recommendation, explain why. Cross-reference the root-cause finding above — e.g. "Root cause is LS-owned migrated data → route to LS team via Hypercare group, NOT to CDS L2 (guidebook Section 12: 'Asking CDS to resend migrated data — that is LS's responsibility')."}
**Action:** Please reassign this ticket to `{group}` and post the justification above as a public comment.
**Similar past tickets:**
- INC{nnnnnn} (similarity 0.XX) — currently in `{full canonical SNOW group name}`
- INC{nnnnnn} (similarity 0.XX) — currently in `{full canonical SNOW group name}`

{Variant B — when recommended group == current_group:}

**NO REASSIGNMENT NEEDED.** The current group `{current_group}` matches what the routing signals indicate.
**Confidence:** {0-100 %}
**Source:** {hard_rule | l3_escalation | retrieval+keyword | retrieval_top1 | keyword}
**Signals checked:**
→ Hard rules — {matched: rule + target group / no match}
→ Keyword scorer — {group} (conf {0.00-1.00}, matched: {kw1, kw2, ...})
→ kNN retrieval (top-1) — INC{nnnnnn} → `{group}` (similarity {0.00-1.00})
→ kNN retrieval (weighted vote) — {`{group}`: sum, ...}
→ L3 escalation signals — {triggered / not triggered}
**Evidence:** {One-sentence supporting evidence — e.g. "Hard rule `[MARS-ANZ]` matched and top-3 kNN neighbours also sit in OMNISALES.RETAIL — current group is correct."}
```

### Why this shape

- The first four `###` headers are **byte-identical** to `rca_copilot_agent`'s template — anyone reading both agents' output sees the same RCA contract.
- All routing-signal metadata is contained in `### REASSIGNMENT DECISION` so the L3 reviewer can read the root cause without wading through kNN scores and weighted votes.
- The section is ALWAYS present (variant A or B), so reviewers and downstream tooling have a single grep target.
- Cross-referencing the root cause inside the reassignment Justification (e.g. "migrated data → LS owns it → route to Hypercare") turns the guidebook rules into routing decisions automatically.

### Rule: FULL canonical assignment-group names — never shortforms

When the report references a SNOW assignment group (the recommendation in `### WHAT WE NEED / DID`, evidence in `### WHAT WE CHECKED`, similar tickets, etc.), **always write the verbatim canonical group name as it appears in ServiceNow.** Never use operator shortforms (`CDS L3`, `LOY`, `MARS team`, `iBeauty`, `NGL`, etc.) — they're ambiguous outside the team and they don't match the SNOW Reassign-Group picker.

Example:
- ✓ "**REASSIGN to:** `APAC - SGP - SPACE CDS SAPMENA L3 Support`"
- ✗ "**REASSIGN to:** CDS L3 team"

Use this shortform → canonical mapping to translate work-note shorthand to the full SNOW group name:

| Shorthand seen in work-notes | Full canonical SNOW group |
|---|---|
| `CDS L2`, `CDS L2 team`, `SAPMENA CDS group` | `APAC - SGP - SPACE CDS SAPMENA L2 Support` |
| `CDS L3`, `CDS L3 team` | `APAC - SGP - SPACE CDS SAPMENA L3 Support` |
| `LOY`, `LOY team`, `Loyalty`, `Loyalty team` (loyalty backend) | `APAC - ZN - O+O.NGLORA - L2` |
| `LOY L3`, `Loyalty L3` | `APAC - CHN - SPACE Loyalty L3 Support` |
| `MARS`, `MARS team`, `MARS Ops`, `MARS Operations`, `retail Ops team` | `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2` |
| `iBeauty`, `iBeauty team`, `IBeauty team`, `iBeauty L2` | `APAC - ZN - iBeauty 2.0 - Retail - L2` |
| `SFCC`, `SFCC L2` | `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2` |
| `CRM`, `SFMC team`, `SFDC team`, `CE team`, `CE Ops team` | `APAC - ZN - O+O.CRM - L2` |
| `NGL`, `NGL L2`, `NGLORA` | `APAC - ZN - O+O.NGLORA - L2` |
| `Operations`, `Ops`, `OPS team` (only when no more specific match) | `APAC - ZN - O+O.OPERATIONS - L2` |
| `Hypercare`, `Hypercare team`, `Hypercare group`, `LS team`, `LS Hypercare`, `Aesop hypercare` | `APAC - ZN - SPACE B2C Hypercare` |
| `HIP`, `HIP team`, `Infrastructure team`, `Azure team` (HIP-adjacent) | `TECH FNDN - WW - HIP INCIDENT L2` |
| `THN Retail`, `Thailand Retail` | `APAC - THN - Retail IT` |

L3 / specialised groups that appear in real work-notes (also use full names):
- `APAC - SGP - SPACE CDS SAPMENA L3 Support`
- `APAC - CHN - SPACE Loyalty L3 Support`
- `APAC - SGP - SPACE Loyalty L3 Support`
- `INFRA - WW - Linux Unix ACN - L3`

If the right canonical group is uncertain, pick the closest match and add `[USER-CONFIRM]` after it in the report so the reviewer knows to verify.

When citing **Similar past tickets** in `### WHAT WE NEED / DID`, also use the full canonical group name (`currently in APAC - SGP - SPACE CDS SAPMENA L3 Support`, not `currently in SGP - SPACE CDS SAPMENA L3 Support`).

## Assignment Groups Supported

[USER-CONFIRM] Routing keywords are inferred — verify against SharePoint matrix before production use.

| Group | Routing Signals |
|-------|----------------|
| APAC - SGP - SPACE CDS SAPMENA L2 Support | SAP, SAPMENA, ERP, Singapore, product sync |
| APAC - THN - Retail IT | Thailand, POS, retail store, printer, cashier |
| APAC - ZN - iBeauty 2.0 - Retail - L2 | iBeauty, beauty advisor, in-store app, clienteling |
| APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | OMNISALES, MARS, Capgemini, click and collect |
| APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2 | CED, e-commerce, online, web order, SPACE GDS |
| APAC - ZN - O+O.CRM - L2 | CRM, loyalty, consumer profile, lucid, consent |
| APAC - ZN - O+O.NGLORA - L2 | NGLORA, NGL, loyalty, ORA, rewards, redemption |
| APAC - ZN - O+O.OPERATIONS - L2 | operations, ETL, pipeline, data sync, API (default fallback) |
| APAC - ZN - SPACE B2C Hypercare | hypercare, go live, launch, cutover, P1 escalation |
| TECH FNDN - WW - HIP INCIDENT L2 | infrastructure, HIP, cloud, server, network, SSL, DNS |

## Common SPACE CDS Root Causes

When investigating the root cause in `### WHAT WE CHECKED` and `### WHAT WE FOUND`, pattern-match against the table below in addition to the guidebook Section 10 patterns above.

### B2C
| # | Root Cause | Signal |
|---|-----------|--------|
| 1 | Missing MARSID | User profile has no Mars ID — orders can't be matched |
| 2 | EAN mismatch | V14/V21 migration left orphan EAN codes |
| 3 | Pipeline delay | Data not yet replicated to BigQuery — check timestamps |
| 4 | CBR mapping gap | Product absent from `mars_V21_mapping_product` table |
| 5 | Profile merge | Duplicate profiles with different loyalty IDs |
| 6 | Region config | Country/brand code mismatch in routing tables |
| 7 | Mars ID lifecycle | Older Mars ID inactivated when newer one created (Section 11 — NOT a defect) |

### B2B (Customer Search / Create Issues)
| # | Root Cause | Signal | Resolution |
|---|-----------|--------|-----------|
| 8 | Customer not in CDS | 0 rows by customercode | SAP→MARS pipeline hasn't ingested; ask MARS to resend |
| 9 | Customer deleted | `isdeletedcustomer = true` | Needs recreate in SAP and re-push via MARS |
| 10 | Account blocked | `blockedaccount = true` | Check `blockedaccountreason`; credit/sales team unblocks |
| 11 | Order blocked | `orderblocked` not null | Sales order block — escalate to sales team |
| 12 | Phone mismatch | Phone in CDS ≠ BA is searching | BA should search by email or customercode instead |
| 13 | Missing CFS profile | Customer row exists, no `cfs_master` row | MARS needs to push the CFS professional profile |
| 14 | CFS not linked to customer | `cfs_master_affiliation` has no row | Affiliation record missing; MARS/SAP needs to create the link |

## BigQuery Datasets

### Primary — B2C Production
- **Project:** `oa-apmena-spacecds-ap-pd`
- **Dataset:** `space_cds_b2c_ds_replica_ae2_pd_public`
- **Use for:** All B2C consumer incidents (purchase, loyalty, account, GDPR, campaign)

### Additional — B2B & DV Replicas (`oa-apmena-spacecds-ap-dv`)
| Dataset | Use When |
|---------|----------|
| `space_cds_b2b_ds_replica_ae2_dv_cds_tgt` | B2B incident in Middle East (SAP orders, invoices, salon accounts) |
| `space_cds_b2b_ds_replica_ase1_dv_cds_tgt` | B2B incident in Southeast Asia |
| `space_cds_b2c_ds_replica_ae2_dv_public` | **B2C historical fallback** — query here when primary returns 0 rows |
| `space_cds_b2c_ds_replica_ase1_dv_public` | B2C ASE1 pipeline debug or survey data |

**Access:** Read-only via gcloud ADC — no credentials in `.env` needed.
**Dialect:** GoogleSQL (backtick refs, SAFE_DIVIDE, UNNEST, etc.).
**Schema source:** `schema.json` in repo root — `get_schema` and `list_bq_tables` read it instantly.
**Auth:** Run `gcloud auth application-default login` if BQ queries fail with auth errors. If unavailable, degrade gracefully — state the unverified hypotheses in `### WHAT WE CHECKED` and downgrade confidence.

### Query Rules (mandatory)

1. **Never filter by `recordstatus`** — it is an internal CDC replication field. Ignore it in all queries.
2. **Always filter consumers by `status = 'Active'`** — only active consumers are relevant.
   - `consumer_pii`: add `AND status = 'Active'`
   - `external_system_ids`: add `AND status = 'Active'` when joining via lucid
3. **B2C AE2 DV replica = historical fallback.** If a query against the primary dataset returns 0 rows, retry against `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ae2_dv_public` (identical schema).
4. **LUCID and Mars ID are not unique across brands.** Same LUCID can exist under different brands. Always include `signature` (brand) and `isocountry` in the SELECT. Filter by `AND signature = '<BRAND>' AND isocountry = '<ISO2>'` when incident context provides them.
5. **Phone-number search: use trailing LIKE, not REGEXP_REPLACE.** CDS cleans phone numbers before insert. Use `phonenumber LIKE '%<digits_only_number>'` — the trailing wildcard absorbs the country code prefix.

### Key Tables for RCA — B2C

| Table | Use When |
|-------|----------|
| `purchase` | Incident mentions order number — look up state, reason code, amount |
| `purchase_item` | Need item-level detail — EAN codes, line item states, quantities |
| `consumer_pii` | Incident mentions email, mobile, or "account not found" |
| `external_system_ids` | Need to map external/source system ID → lucid; check Mars ID status |
| `product` | Incident mentions product, EAN barcode, or SKU issue |
| `shipment` | Delivery / carrier / shipping delay |
| `care_case` | Check if incident is already logged as a CRM care case |
| `consumer_behaviour` | Loyalty points earn/burn discrepancy |
| `consumer_marketing_preferences` | Consumer not receiving emails/SMS despite opt-in |
| `consumer_merge` | Duplicate account or profile merge issue |
| `auto_replenishment` | Unexpected repeat charge or subscription issue |
| `delete_consumer_request` | GDPR erasure request status |

### Key Tables for RCA — B2B

| Table | Use When |
|-------|----------|
| `customer` | B2B salon/distributor account lookup by `customercode` |
| `cfs_master` | B2B professional contact lookup by email or `cfsmasterkey` |
| `sales_order` | Incident mentions SAP order number or B2B order issue |
| `sales_order_line` | Need EAN/product detail within a B2B order |
| `invoice` | Invoice payment status, clearing date, amount disputes |
| `delivery` | B2B delivery/shipping status by SAP delivery or order number |
| `cfs_master_consents` | B2B contact marketing opt-in/out issues |
| `customer_open_brands` | B2B customer not authorised to order a brand/product |

### Key Identifier → Table Mappings

**B2C identifiers:**

| Identifier | Table | Column |
|-----------|-------|--------|
| Order number | `purchase` | `sourceordernumber` |
| Order items | `purchase_item` | `sourceordernumber` |
| Consumer email | `consumer_pii` | `email` |
| LUCID / Mars ID | `consumer_pii`, `external_system_ids` | `lucid` — always SELECT `signature` + `isocountry` alongside |
| External consumer ID | `external_system_ids` | `sourceconsumerid` |
| EAN / barcode | `product` (or `purchase_item.eancode`) | `ean` |
| Shipping / delivery | `shipment` | `sourceordernumber` |
| Loyalty points | `consumer_behaviour` | `lucid` |

**B2B identifiers:**

| Identifier | Table | Column |
|-----------|-------|--------|
| SAP order number | `sales_order` | `saporderid` |
| SAP invoice number | `invoice` | `sapinvoiceid` |
| SAP delivery number | `delivery` | `sapdeliveryid` |
| B2B customer/salon code | `customer` | `customercode` |
| B2B contact email | `cfs_master` | `email` |
| CFS profile key | `cfs_master` | `cfsmasterkey` |

## Running Without MCP (Skills / CLI Mode)

L'Oréal's environment does not allow MCP servers. Use `run_tool.py` instead:

```bash
# ONE-STOP analysis (now includes attachment downloads)
python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'

# Show routing rules (hard_rules + l3_escalation)
python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'

# Build the kNN retrieval index — run ONCE after each fetch_incidents
python ticketasg_copilot_agent/run_tool.py build_retrieval_index --json '{}'

# BigQuery — discover, inspect, query
python ticketasg_copilot_agent/run_tool.py list_bq_tables --json '{}'
python ticketasg_copilot_agent/run_tool.py get_schema --json '{"table_name": "consumer_pii"}'
python ticketasg_copilot_agent/run_tool.py query_bigquery --json '{"sql": "SELECT lucid, signature, isocountry, status FROM `oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public.consumer_pii` WHERE lucid = '\''C5xxxxxxxx'\'' AND status = '\''Active'\'' LIMIT 5", "rationale": "Confirm consumer is in CDS for migrated-vs-ongoing check"}'

# Re-download attachments if analyze_incident auto-download failed
python ticketasg_copilot_agent/run_tool.py download_attachments --json '{"incident_number": "INC10403788"}'

# v2 recommender — hard rule + keyword + retrieval + L3 escalation
python ticketasg_copilot_agent/run_tool.py recommend_assignment_v2 \
    --json '{"incident_number": "INC123", "short_description": "SFCC -> CDS Missing Order PRB0083209", "description": "Reassigning to CDS L3 — data patch required", "current_group": "APAC - SGP - SPACE CDS SAPMENA L2 Support"}'

# kNN similarity search — second-opinion signal
python ticketasg_copilot_agent/run_tool.py find_similar_incidents \
    --json '{"query_text": "SAPMENA FindConsumerProfile failure", "top_k": 5}'

# Legacy v1 (kept for back-compat — prefer v2)
python ticketasg_copilot_agent/run_tool.py recommend_assignment \
    --json '{"incident_number": "INC123", "short_description": "SAP sync error", "description": "SAPMENA pipeline failure", "current_group": "APAC - ZN - O+O.OPERATIONS - L2"}'

# Save report (MANDATORY)
python ticketasg_copilot_agent/run_tool.py save_assignment_report \
    --json '{"incident_number": "INC123", "report_text": "# RCA Report: INC123\n..."}'

# Send email (MANDATORY, once per session)
python ticketasg_copilot_agent/run_tool.py send_assignment_email \
    --json '{"session_summary": "Analysed INC123 — root cause LS-owned migrated order, reassign to Hypercare"}'
```

**For Claude Code users:** invoke the `/ticketasg-copilot` skill (`.claude/skills/ticketasg-copilot/SKILL.md`).

**For GitHub Copilot users:** the `.github/agents/ticketasg_copilot.agent.md` agent definition
uses `run_in_terminal` to call `run_tool.py` — no MCP server required.

## Environment Setup

### ServiceNow Credentials (auto-refreshed)

At startup the server checks `COOKIE` and `X_USERTOKEN` in `.env`.
If missing or expired, a browser window opens for SSO login.

### Required .env Keys

| Variable | Source |
|----------|--------|
| `COOKIE` | Chrome DevTools → Network → SNOW request → Cookie header |
| `X_USERTOKEN` | Same request → X-UserToken header |
| `SMTP_HOST` | Your SMTP server (for email notifications) |
| `SMTP_FROM` | From address |
| `SMTP_TO` | Recipient(s), comma-separated |
| `ASSIGNMENT_RULES_FILE` | Optional — path to assignment_rules.json override |
