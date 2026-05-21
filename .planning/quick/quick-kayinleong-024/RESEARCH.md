---
title: RCA-parity for ticketasg_copilot_agent + CDS Incident Handling Guidebook integration
claim: quick-kayinleong-024
owner: kayinleong
date: 2026-05-21
status: complete
---

# RESEARCH — quick-kayinleong-024

Investigation into bringing `ticketasg_copilot_agent` to RCA-parity with `rca_copilot_agent` (appending a Reassignment Decision section), and folding the new CDS Incident Handling Guidebook into the prompt.

Source guidebook: `.planning/quick/quick-kayinleong-024/research_inputs/CDS_Incident_Handling_Guidebook.txt` (converted from `CDS_Incident_Handling_Guidebook 2.docx` via `textutil`).

---

## PART 1 — RCA report shape (`rca_copilot_agent`)

### 1.1 Exact section headings (verbatim)

Canonical RCA report uses exactly four `###` headers. Identical across `rca_copilot_agent/AGENTS.md` (lines 222–241), `.github/agents/rca_copilot.agent.md` (lines 195–223), and `.claude/skills/rca-copilot/SKILL.md` (lines 125–141):

```
### WHAT HAPPENED
### WHAT WE CHECKED
### WHAT WE FOUND
### WHAT WE NEED / DID
```

Header preamble:

```markdown
# RCA Report: {incident_number}
**{incident_title}**
*Investigated: {date}*

---
```

### 1.2 Intent and required content of each section

| Section | Intent / required content |
|---|---|
| `### WHAT HAPPENED` | One sentence — the symptom, not the cause. |
| `### WHAT WE CHECKED` | Arrow-prefixed evidence lines (`→ Checked [source] — [what you found]`). Sources include comments, work notes, attachments, and BigQuery results. Quote dates, authors, error messages, data points. |
| `### WHAT WE FOUND` | Conclusion from checks — one or two sentences with evidence. If root cause unclear, state known vs unknown. |
| `### WHAT WE NEED / DID` | Bulleted action items with owner if named. Include team/group to escalate (full canonical names). |

### 1.3 MCP tools and canonical order

From `rca_copilot_agent/AGENTS.md:105-219` (Investigation Workflow):

**Phase 1 — INGEST**
1. `analyze_incident` (one-stop: fetch + attachments + identifier extraction). Explicitly: do NOT call `get_incident_summary` + `extract_identifiers` + `download_attachments` separately.

**Phase 2 — DISCOVER**
2. `list_bq_tables` → table catalog from `schema.json`
3. `get_schema <table_name>` → columns + ready-to-use query patterns

**Phase 3 — VALIDATE**
4. `query_bigquery` — run multiple targeted queries. AGENTS.md mandates: "Run multiple queries. One query is never enough. If a query returns 0 rows, that IS a finding."

**Phase 3b — B2B Customer Search/Create Checklist** (lines 146–200): a 5-query script against `customer`, `cfs_master`, `cfs_master_affiliation`.

**Phase 4 — CONCLUDE**
5. Write the RCA using the template
6. `save_rca_report` **immediately** after each report
7. `send_rca_email` **once** at end of session — never ask the user for verification first

Auxiliary: `fetch_incidents`, `get_incident`, `get_incident_summary`, `list_incidents`, `search_incidents`, `extract_identifiers`, `download_attachments`, `post_comment`. Auto-startup: `auto_credential_refresh`, `auto_gcloud_auth`.

### 1.4 Findings accumulation pattern

`rca_copilot_agent` is the no-LLM MCP variant — **no wiki accumulator**. Findings accumulate in the LLM client's context across tool calls, then commit via `save_rca_report` (Markdown file) and `register_report(filepath)` for email attachment (`mcp_server.py:696-717`).

### 1.5 Delivery channels

1. **Disk** — `save_rca_report` writes `<reports_dir>/rca_reports/<INC>_rca_<timestamp>.md`.
2. **Email** — `send_rca_email` (once at end of session) sends HTML email to `SMTP_TO`, attaching every registered file. Subject default `"RCA Analysis Complete — Please Review"`.
3. **Optional ServiceNow comment** — `post_comment` posts back as customer-visible or work-note, ONLY when user explicitly says "post comment".

### 1.6 Existing reassignment treatment in rca_copilot

No dedicated reassignment section. Group reassignment lives as an action item inside `### WHAT WE NEED / DID`. The "FULL canonical assignment-group names — never shortforms" rule (`rca_copilot_agent/AGENTS.md:243-275`) is enforced with the same shortform→canonical mapping table that lives in ticketasg's prompt.

---

## PART 2 — Current report shape (`ticketasg_copilot_agent`)

### 2.1 Current sections (verbatim)

From `ticketasg_copilot_agent/AGENTS.md:79-112`, mirrored in `.github/agents/ticketasg_copilot.agent.md:150-180` and `.claude/skills/ticketasg-copilot/SKILL.md:175-205`:

```
## Assignment Analysis — {INCIDENT_NUMBER}

### WHAT HAPPENED
### WHAT WE CHECKED
### WHAT WE FOUND
### WHAT WE NEED / DID
```

Ticketasg already uses the same four headers. Two functional differences inside the sections:

- `### WHAT WE CHECKED` carries **routing signals** (Hard rules / Keyword scorer / kNN top-1 / kNN weighted vote / L3 escalation), not data evidence.
- `### WHAT WE NEED / DID` carries the structured reassignment block (`**REASSIGN to:** ...` / `**NO REASSIGNMENT NEEDED.** ...`) plus optional similar past tickets.

### 2.2 Tools available + canonical order

From `AGENTS.md:14-44`:

| # | Tool | Notes |
|---|---|---|
| 1 | `analyze_incident` | ONE-STOP fetch + identifiers (does NOT download attachments — see 2.5) |
| 2 | `get_assignment_rules` | Read before recommending — shows routing matrix, hard rules, L3 escalation map |
| 3 | `build_retrieval_index` | One-time after each `fetch_incidents` |
| 4 | `recommend_assignment_v2` | Hybrid: hard rules + keyword + retrieval + L3 escalation |
| 5 | (LLM reasoning — "LLM-as-judge") | Weigh four signals |
| 6 | `find_similar_incidents` | Optional second-opinion / past-ticket citations |
| 7 | Write the report |
| 8 | `save_assignment_report` | MANDATORY before output |
| 9 | `send_assignment_email` | MANDATORY once per session |

Auxiliary: `fetch_incidents`, `get_incident`, `get_incident_summary`, `list_incidents`, `search_incidents`, `post_comment`, `recommend_assignment` (legacy v1).

**Notable absence:** `query_bigquery`, `get_schema`, `list_bq_tables` are NOT exposed in ticketasg's MCP server or run_tool dispatch. The package contains `tools/bigquery_tool.py` on disk and runs `init_from_schema()` at startup (`mcp_server.py:874`, `run_tool.py:78`), but no dispatch arm routes to BQ tools — they're effectively dead code for the agent.

### 2.3 How `recommend_assignment_v2` works

Implementation: `ticketasg_copilot_agent/tools/assignment_tool.py:361-622`. Pure function, no LLM calls.

**Four signals (in order):**
1. **Hard rules** — regex shortcuts from `assignment_rules.json["hard_rules"]`. First match wins. Currently 4 patterns (MARS-region, CAPLINERR/Linux/disk usage, Cloudflare/outage, Aesop hypercare).
2. **Keyword scoring** — v1 logic; substring + word-boundary keywords per group; confidence = `top_score / total_score`. Fallback group `APAC - ZN - O+O.OPERATIONS - L2`.
3. **kNN retrieval** — sentence-transformers index over `_all_incidents.json` (`retrieval_index.npz`). Returns top-k, top-1, and weighted vote.
4. **L3 escalation** — regex signals from `assignment_rules.json["l3_escalation"]["escalation_signals"]`.

**Combined source field:**
- `hard_rule` → conf 0.95
- `l3_escalation` → conf 0.85
- `retrieval+keyword` (agree, ret≥0.6) → `0.5 + score/2`
- `retrieval_top1` (kw<0.4, ret≥0.7, ≥2 of top-5 share group) → `0.5 + score/2`
- `keyword` → kw confidence

**Outputs:** `recommended_group`, `confidence`, `reason`, `source`, `reassignment_needed`, `reassignment_reason`, and a `signals` sub-object with raw blocks.

### 2.4 Current reassignment communication

Inside `### WHAT WE NEED / DID`:

When `final_choice != current_group`:
```
**REASSIGN to:** `{full canonical group name}`
**Confidence:** {0-100 %}
**Justification:** {Why this group is correct — name the signals ...}
**Action:** Please reassign this ticket to `{group}` and add the justification above as a public comment.
```

When `final_choice == current_group`:
```
**NO REASSIGNMENT NEEDED.** The current assignment group `{current_group}` matches what the routing signals indicate. {One-sentence supporting evidence.}
```

Plus optional `**Similar past tickets:**` bullets.

### 2.5 Gaps vs `rca_copilot_agent`

**Missing investigative tools (code-level):**
- `query_bigquery` — not exposed.
- `get_schema` — not exposed.
- `list_bq_tables` — not exposed.
- `extract_identifiers` — runs inside `analyze_incident` but not exposed standalone.
- `download_attachments` — not exposed; `analyze_incident` does NOT download attachments (`mcp_server.py:583-592` returns only summary + identifiers).

**Missing report content (prompt-level):**
- `### WHAT WE CHECKED` enumerates routing signals, not data evidence (no `→ Checked [system] — [what you found]` with timestamps, errors, BQ results).
- `### WHAT WE FOUND` summarises signal agreement, not root cause.
- No coverage of common SPACE CDS root causes (MARSID missing, EAN mismatch, pipeline delay, CBR mapping, profile merge, region config).
- No B2B customer-search/create checklist.
- No identifier→table mapping.
- No instruction to download/read attachments.
- No instruction to query CDS for consumer/order/customercode.
- No "migrated vs ongoing" distinction.
- No "3-question framework".

---

## PART 3 — Guidebook intelligence

Source: `.planning/quick/quick-kayinleong-024/research_inputs/CDS_Incident_Handling_Guidebook.txt` — 474 lines, KT owner Dipti Patil, scope ANZ + SEA: SG/MY/ID/TH/VN/PH.

### 3.1 The 3-question framework (verbatim, Section 14, lines 383-395)

> If you cannot solve an incident, it is almost always because one of these three questions has not been answered correctly. Answer them in order.
>
> 1. **What data is impacted?** Consumer or purchase? Be specific.
> 2. **Is it migrated or ongoing?** Use source creation datetime vs market go-live. Use LUCID prefix (C2 vs C5) to confirm.
> 3. **Which system owns that responsibility?** Migrated → LS owns historical sends. Ongoing → CDS owns API + CE batch. Mars owns Mars ID.
>
> If these are clear, the correct action becomes obvious.

### 3.2 Section 9 — Standard incident analysis (verbatim)

> Follow these five steps in order. Do not skip ahead.

- **Step 1 — Understand the ask.** What exactly is missing or wrong? Consumer? Order? Loyalty points? Brand / civility / location? Which market / country? Which system raised the issue (CDS, Mars, Loyalty, SFMC, SA)? What does the requester expect to see?
- **Step 2 — Identify data type.** Consumer issues: Cannot find / Duplicate / Wrong details / Inactive Mars ID. Purchase issues: Missing orders / Incorrect amount / Loyalty points not awarded.
- **Step 3 — Check creation timing.** Always pull Source creation datetime + Order datetime; compare against market go-live (Section 4).
- **Step 4 — Migration check (C2 LUCID).** Confirm Source Consumer Key populated and LS Customer ID exists. **Do NOT ask CDS to resend.** LS owns historical sends. Route/escalate to LS.
- **Step 5 — Ongoing data check (C5 LUCID).** Confirm API ingestion success in CDS; consumer in `CONSUMER_PII_TBL`; Mars ID linkage in `EXTERNAL_SYSTEM_IDS_TBL`. If Mars missing, confirm whether CE nightly batch (incremental extract) ran and the consumer was picked up. Ask CE team for file name + run confirmation, then ask Mars to ingest.

### 3.3 Section 10 — Common incident patterns

| Pattern | Correct handling |
|---|---|
| **10.1 Loyalty points missing** | Migrated or ongoing? Migrated → LS owns historical sends to Loyalty; CDS does NOT push historical purchases. Ongoing → check downstream event/extract flow from CDS; confirm order exists in CDS first. Common mistake: raising a CDS defect without first confirming the purchase is in CDS. |
| **10.2 "Consumer not found in Mars"** | Confirm consumer in CDS (`CONSUMER_PII_TBL`); check `EXTERNAL_SYSTEM_IDS_TBL` for Mars ID + status; ask CE team when extract last ran and whether this consumer was included; ask Mars to ingest. |
| **10.3 Brand / civility / code mismatch** | CDS rejects unknown codes — it's a source-data compliance issue, not a CDS bug. Action: ask source system (e.g. Mars) to fix mapping. Do NOT patch CDS to accept bad codes without approval. |
| **10.4 Missing orders** | Migrated → LS owns the historical send. Ongoing → check inbound MARS OrderHeader / OrderItem feeds for the date (file arrival, processing status). Always confirm source order number, order datetime, country signature. |
| **10.5 Incorrect order amount** | Compare source order vs CDS `PURCHASE_TBL`. If CDS matches source → downstream issue (Loyalty/reporting); do NOT patch CDS. If CDS does not match source → check OrderHeader / OrderItem ingestion. |
| **10.6 Brand / location data wrong** | Brand/location often does not originate from CDS. Identify upstream system (typically Counter / BA feeds from MARS or CEGID). Avoid defaulting every metadata issue to CDS. |

### 3.4 Section 11 — Status mismatch (PI vs External System ID)

> Observed: PI status = inactive, External System ID = active (or vice versa).
>
> **Expected behaviour:** Only one active Mars ID per consumer. Older Mars IDs are inactivated when a new one is created.
>
> Action: verify scenario before raising RCA. A status mismatch is not automatically a defect — it may be the expected lifecycle behaviour. Only escalate if genuinely inconsistent with the rule above.

### 3.5 Section 12 — Common mistakes (verbatim)

> ✗ Checking the wrong country / market.
> ✗ Jumping straight to merge requests or data patches without root cause.
> ✗ Asking CDS to resend migrated data — that is LS's responsibility.
> ✗ Providing RCA without verifying source creation dates.
> ✗ Responding without screenshots or model checks.
> ✗ Defaulting every metadata issue to CDS without identifying the upstream owner.
> ✗ Treating standardised-code rejections as CDS bugs.

### 3.6 Section 13 — Expectations from L2 / L3 (verbatim)

> - Perform first-level analysis independently.
> - Use the CDS data model and B2C Mapping Doc V3 to validate fields and routing.
> - Bring specific, evidenced doubts to KT calls — not open-ended questions.
> - Provide on every ticket: clear analysis, screenshots with all mandatory fields, and a logical conclusion.
> - Escalate only when needed, with evidence.

### 3.7 Section 5 — Key identifiers

| Identifier | Description |
|---|---|
| **LUCID** | L'Oréal Unique Consumer ID. Generated only by CDS. Global, unique. Same email or mobile within a country → same LUCID across brands. |
| **LUCID prefix C2** | Migrated consumer (sourced from LS). |
| **LUCID prefix C5** | Ongoing consumer (created after go-live via real-time API). |
| **Mars ID** | Generated by Mars after CDS sends consumer data. Multiple may exist but only ONE active at a time. When Mars creates a new ID, CDS inactivates older ones. |
| **Source Consumer Key (LS Customer ID)** | LS-side customer identifier. If populated, strong signal the consumer is migrated. Used to prevent duplicates. |

### 3.8 Section 8 — Mandatory fields for incident screenshots

> Screenshots are evidence. If a screenshot is missing any of the fields below, your analysis is incomplete and the ticket will bounce back.

**Consumer incidents (required):** ISO Country / Country Signature; LUCID; Secondary key — Email (ANZ) / Mobile (others); Source creation datetime; System created / updated datetime; External System IDs + Status (Mars ID and Active/Inactive flag); Source Consumer Key (LS Cust ID).

**Purchase incidents (required):** ISO Country / Country Signature; LUCID; Source order number; Order datetime; System created / updated datetime.

> Rule: source creation datetime ≠ system created datetime. Use the source datetime to decide migrated vs ongoing.

### 3.9 Section 4 — Go-live timeline

| Region | Markets | Go-live |
|---|---|---|
| ANZ | AU, NZ | Mid-July |
| SEA rollout | SG, MY, ID, TH, VN, PH | Mid-December 2025 |

Rule: creation date before market go-live → migrated (LS-sourced). After → ongoing (API-sourced).

> ⚠ ANZ go-live year is not stated in the guidebook source; assume mid-July 2025 unless confirmed otherwise.

### 3.10 Section 6 — Brand & country reference (ANZ inbound)

`01` Lancôme (MARS, AU/NZ), `16` Giorgio Armani (MARS, AU), `24` La Roche-Posay (SFMC, AU), `25` Brand 25 (SFMC, AU), `42` SkinCeuticals (MARS, AU), `45` Kiehl's (MARS, AU/NZ), `51` YSL Beauty (MARS, AU), `75` IT Cosmetics (SFMC, AU), `85` AESOP (**CEGID, not MARS**, AU/NZ), `C4` Kérastase (SFMC, AU).

Critical: AESOP (signature 85) is sourced via CEGID, not MARS. If signature 85 appears on an incident, inbound flow is CEGID.

### 3.11 Section 7 — Inbound source data flows (PROD times UTC+8)

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

### 3.12 Appendix A — CDS table relationships

`CONSUMER_PII_TBL` is master. Tables that hang off via `consumerKey`: `CONSUMER_EXTRA_TBL`, `ADDRESSES_TBL`, `SOCIAL_CONTACTS_TBL`, `EXTERNAL_SYSTEM_IDS_TBL`, `AGREEMENT_LOGS_TBL`, `BEHAVIOUR_TBL`, `CONSUMER_PROSPECT_TBL`, `MARKETING_PREFERENCES_TBL`, `BEAUTY_EXPERIENCE_TBL`. `PURCHASE_TBL → PURCHASEITEM_TBL` via `purchaseKey`; `PURCHASEITEM_TBL → PRODUCT_TBL` via `productKey`. `SHIPMENT_ADDRESSES_TBL → SHIPMENT_TBL` via `shippingKey`.

### 3.13 Routing/assignment implications

The guidebook does NOT contain an explicit group-to-rule matrix. It contains **ownership statements** the routing prompt should respect:

- Migrated data, downstream missing → route/escalate to LS. LS is NOT in ticketasg's 10-group list; closest match is `APAC - ZN - SPACE B2C Hypercare` (which carries `LS team`, `LS Hypercare` keywords).
- Ongoing data, Mars missing → CE team for file/run confirmation, then Mars Ops.
- Brand / civility / code mismatch → source system (e.g. Mars), not CDS.
- Brand / location metadata → upstream Counter/BA feeds (MARS or CEGID), not CDS.
- AESOP brand (signature 85) → inbound flow is CEGID, not MARS.

### 3.14 Evidence requirements & expectations

- Section 8: screenshots ARE evidence; missing mandatory fields → analysis incomplete.
- Section 13: independent first-level analysis; CDS data model + B2C Mapping Doc V3; specific evidenced doubts; clear analysis + screenshots + logical conclusion; escalate only with evidence.
- No explicit SLAs / response-time KPIs / escalation matrix in this guidebook.

---

## PART 4 — Gap analysis & recommendations

### 4.1 Target report structure

Recommendation: **bipartite report** — four canonical RCA headers focused on root cause, then `### REASSIGNMENT DECISION` appended as the LAST section. Matches the user's verbatim ask ("in rca last session"). Keeps the rca_copilot template literally identical for the first four sections, puts ALL routing-signal noise in its own section so L3 reviewer can read root cause without wading through routing metadata.

```markdown
# RCA Report: {INC}
**{title}**
*Investigated: {date}*

---

### WHAT HAPPENED
One sentence — symptom only.

### WHAT WE CHECKED
→ Checked work notes — {what found, who, when}
→ Checked attachments — {OCR / screenshot findings, mandatory-fields check}
→ Checked BigQuery {table} — {result; "0 rows" is a finding}
→ Checked LUCID prefix — {C2 → migrated / C5 → ongoing}
→ Checked source creation datetime vs market go-live — {migrated / ongoing decision}
→ Checked External System IDs status — {Mars ID active/inactive}

### WHAT WE FOUND
One or two sentences — actual root cause with evidence.

### WHAT WE NEED / DID
- {Bulleted action items, with owner from work notes}

### REASSIGNMENT DECISION
**REASSIGN to:** `{full canonical group name}`
**Confidence:** {0-100 %}
**Source:** {hard_rule / l3_escalation / retrieval+keyword / retrieval_top1 / keyword}
**Signals checked:**
→ Hard rules — {matched: rule + target / no match}
→ Keyword scorer — {group} (conf {x.xx}, matched: {kw1, kw2, ...})
→ kNN retrieval (top-1) — INC{nnnnnn} → {group} (similarity {x.xx})
→ kNN retrieval (weighted vote) — {group: sum, ...}
→ L3 escalation signals — {triggered: ... / not triggered}
**Justification:** {Which signals led here.}
**Similar past tickets:**
- INC{nnnnnn} (similarity 0.XX) — currently in `{full canonical group name}`

{When reassignment is NOT needed:}
**NO REASSIGNMENT NEEDED.** The current group `{current_group}` matches what the routing signals indicate. {one-sentence supporting evidence.}
```

The section is ALWAYS included (its body differs based on `reassignment_needed`) — this gives the reader a single grep target.

### 4.2 Prompt additions

Apply the following to all three prompt files (`ticketasg_copilot_agent/AGENTS.md`, `.github/agents/ticketasg_copilot.agent.md`, `.claude/skills/ticketasg-copilot/SKILL.md`):

- 3-question framework (Section 14) — at top of workflow
- Section 9 five-step analysis — new "Phase 1 — Understand & Triage" before tool calls
- Common patterns table (Section 10) — reference table; agent should pattern-match before recommending
- Status mismatch rule (Section 11) — verbatim
- Common mistakes (Section 12) — "Never do this" guardrails
- Mandatory screenshot fields (Section 8) — agent flags missing fields and downgrades confidence
- Key identifiers (Section 5) — LUCID C2/C5, Mars ID lifecycle, Source Consumer Key
- Go-live dates (Section 4) — required for migrated-vs-ongoing call
- Inbound feeds + PROD times (Section 7) — agent suggests "check whether IN MARS OrderHeader processed on {date}"
- Brand/country reference (Section 6) — critical for AESOP-via-CEGID routing
- Expectations from L2/L3 (Section 13) — bar for analysis depth
- Reassignment Decision block spec — as defined in 4.1

Update Mandatory Sequence: insert "Apply the 3-question framework to the incident before scoring any group" between `analyze_incident` and `get_assignment_rules`.

### 4.3 Code changes

This is ~85% prompt-engineering. The routing engine (`recommend_assignment_v2`) does not need changes. But to bring report depth to rca_copilot's level, two gaps close:

1. **Expose BigQuery tools through ticketasg.** Add `query_bigquery`, `get_schema`, `list_bq_tables` to `ticketasg_copilot_agent/mcp_server.py`:
   - Tool descriptors in `list_tools()` (copy from `rca_copilot_agent/mcp_server.py:289-346`)
   - Dispatch arms in `_dispatch()` (copy from `mcp_server.py:641-656`)
   - JSON-RPC fallback `tools/list` array (line 825-832)
   Without BQ access the LLM cannot answer "Is consumer X in CONSUMER_PII_TBL?" — which guidebook Steps 4 & 5 explicitly require.

2. **Add attachment download.** Mirror rca_copilot's `analyze_incident` (which calls `download_all_attachments` — `mcp_server.py:575-585`). Also expose `download_attachments` as a standalone tool for retry-on-failure. Guidebook Section 8 is explicit: screenshots ARE evidence.

**Optional (cosmetic):**

3. Align saved-report filename to `<INC>_rca_<ts>.md` (currently `<INC>_assignment_<ts>.md`).
4. Align email subject default to `"RCA Analysis Complete — Please Review"`.

**No changes to** `assignment_rules.json`, `tools/assignment_tool.py`, `tools/retrieval_tool.py`, or `tools/bigquery_tool.py`. Deterministic routing stays exactly as-is.

### 4.4 Open questions / risks

1. **Scope creep — ticketasg becoming a duplicate of rca_copilot.** With BQ + attachment download + same prompt depth, the two agents are ~90% the same code. Decision: keep both distinct; ticketasg ADDS root-cause investigation on top of routing, doesn't replace it.

2. **BQ access in L'Oréal environment.** rca_copilot uses gcloud ADC. If ticketasg is invoked without ADC, BQ tools fail. Prompt must surface this as a known-fail mode and degrade gracefully to routing-only.

3. **"LS team" routing destination.** Guidebook references LS team but `assignment_rules.json` has no LS group; closest is `APAC - ZN - SPACE B2C Hypercare`. Question: is LS team a separate canonical SNOW group? If yes, `ASSIGNMENT_GROUPS` needs an 11th entry.

4. **Geographic scope.** Guidebook is ANZ + SEA. Does the new content apply globally or geo-gated? Recommendation: apply globally (the principles — migrated-vs-ongoing, LUCID prefix, Mars lifecycle — are not market-specific), with country-specific tables (Section 4 go-lives, Section 6 brands, Section 7 feeds) called out as ANZ-only.

5. **ANZ go-live year.** Guidebook line 117 says "Mid-July" with no year. Assumption: 2025.

6. **No SLA/KPI table in guidebook.** Won't add SLA-flagging behaviour without source data.

7. **OCR of screenshots.** Per CLAUDE.md, MCP layer stays pure-function. Attachments are downloaded; OCR/inspection is the LLM client's responsibility.

8. **`retrieval_index.npz` modification in git status** is unrelated to this work — regenerated kNN index file. Should not be staged here.

### 4.5 Implementation summary

| Change | Type | Files |
|---|---|---|
| Add 3-question framework, Sections 4–13 guidebook content | Prompt | `ticketasg_copilot_agent/AGENTS.md`, `.github/agents/ticketasg_copilot.agent.md`, `.claude/skills/ticketasg-copilot/SKILL.md` |
| Reshape report → four RCA sections + appended `### REASSIGNMENT DECISION` | Prompt | Same three files |
| Insert "Apply 3-question framework" step in Mandatory Sequence | Prompt | Same three files |
| Expose `query_bigquery`, `get_schema`, `list_bq_tables` | Code | `ticketasg_copilot_agent/mcp_server.py` |
| Add attachment download to `analyze_incident` (mirror rca_copilot) | Code | `ticketasg_copilot_agent/mcp_server.py` |
| Expose `download_attachments` as standalone tool | Code | `ticketasg_copilot_agent/mcp_server.py` |
| (Optional) align save-report filename to `<INC>_rca_<ts>.md` | Code | `ticketasg_copilot_agent/mcp_server.py` |
| (Optional) align email subject default | Code | `ticketasg_copilot_agent/mcp_server.py` |

---

## Key files referenced

- `rca_copilot_agent/AGENTS.md`
- `rca_copilot_agent/mcp_server.py`
- `rca_copilot_agent/run_tool.py`
- `.github/agents/rca_copilot.agent.md`
- `.claude/skills/rca-copilot/SKILL.md`
- `ticketasg_copilot_agent/AGENTS.md`
- `ticketasg_copilot_agent/mcp_server.py`
- `ticketasg_copilot_agent/run_tool.py`
- `ticketasg_copilot_agent/assignment_rules.json`
- `ticketasg_copilot_agent/tools/assignment_tool.py`
- `.github/agents/ticketasg_copilot.agent.md`
- `.claude/skills/ticketasg-copilot/SKILL.md`
- `.planning/quick/quick-kayinleong-024/research_inputs/CDS_Incident_Handling_Guidebook.txt`
