# FINDINGS — Improving ticketasg_copilot_agent assignment logic

**Claim:** quick-kayinleong-018
**Date:** 2026-05-19
**Source:** 64 active ServiceNow incidents (`active=true ^ assignment_group DYNAMIC d6435e965f510100a9ad2572f2b47744 ^ state!=6`), fetched into `./my_reports/`
**Method:** Pure-Python analysis of `_all_incidents.json` against `ticketasg_copilot_agent/assignment_rules.json` (see `scripts/analyze.py`, `scripts/handoffs.py`)
**Scope:** Research-only. No code or rules changes in this claim — follow-up claims will implement.

---

## TL;DR — Headline numbers

| Metric | Value |
|---|---:|
| Incidents fetched | **64** (0 errors) |
| Distinct *current* assignment groups in sample | **4** |
| Match rate (current group = rule-predicted group) | **11/64 = 17.2 %** |
| Match rate restricted to incidents in **canonical 10 groups** | **11/35 = 31.4 %** |
| Canonical groups with **zero** tickets in sample | **8 of 10** |
| Distinct handoff/reassignment phrases extracted from work-notes | **215** across 64 tickets |

**The current `assignment_rules.json` cannot be trusted in production:** of every 10 active incidents in your queue, only **1.7** would currently be routed correctly by the keyword scorer. Even within the subset already sitting in one of the supported L2 groups, less than a third would be confirmed by the rules.

---

## 1. Sample composition — important caveats first

The list-view URL filters on `assignment_group DYNAMIC d6435e965f510100a9ad2572f2b47744`. That is the **"my groups"** dynamic filter, scoped to the groups the *fetching user* (Kayin) is a member of — **not** the 10 canonical L2 groups defined in `assignment_rules.json`.

### 1.1 Current-group distribution in the fetched sample

| # | Current Group | Tickets | % | In canonical 10? |
|---|---|---:|---:|:---:|
| 1 | `APAC - SGP - SPACE CDS SAPMENA L3 Support` | 22 | 34.4 % | ✗ (L3, not L2) |
| 2 | `APAC - ZN - SPACE B2C Hypercare` | 19 | 29.7 % | ✓ |
| 3 | `APAC - SGP - SPACE CDS SAPMENA L2 Support` | 16 | 25.0 % | ✓ |
| 4 | `APAC - CHN - SPACE Loyalty L3 Support` | 7 | 10.9 % | ✗ (L3, not L2) |

### 1.2 Canonical groups with **no** tickets in this sample

```
APAC - THN - Retail IT
APAC - ZN - iBeauty 2.0 - Retail - L2
APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2
APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2
APAC - ZN - O+O.CRM - L2
APAC - ZN - O+O.NGLORA - L2
APAC - ZN - O+O.OPERATIONS - L2
TECH FNDN - WW - HIP INCIDENT L2
```

**Implication:** these 8 groups' keyword sets cannot be validated against real evidence from this fetch. A wider fetch (queue-wide URL, not "my groups") would be needed to validate them. See the **Recommendations** section for the proposed wider sweep.

### 1.3 Real groups not in the canonical 10

Two **L3** support groups handle a large share of the queue but are not modelled in the rules:

- `APAC - SGP - SPACE CDS SAPMENA L3 Support` (22 tickets — 34 % of the queue!)
- `APAC - CHN - SPACE Loyalty L3 Support` (7 tickets — 11 %)

The rule schema does not model **L2 ↔ L3 escalation** at all, so the recommender silently maps L3 tickets onto whichever L2 group's keywords happen to match — producing a spurious "reassign to L2" verdict in many cases.

---

## 2. Per-incident routing trace (current rules)

The full table is in [`ANALYSIS-RAW.md`](./ANALYSIS-RAW.md) §2 (64 rows). The summary below highlights the failure modes.

### 2.1 The 11 incidents where current rules are correct

| # | Incident | Current = Predicted Group | Matched Keywords |
|---|---|---|---|
| 2 | INC10419095 | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP, SAPMENA, Singapore |
| 3 | INC10487330 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP |
| 4 | INC10387135 | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP, SAPMENA |
| 6 | INC10482324 | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP |
| 7 | INC10453163 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA |
| 8 | INC10462256 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA |
| 9 | INC10462212 | SGP - SPACE CDS SAPMENA L2 Support | CDS |
| 19 | INC10483228 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP |
| 30 | INC10475182 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP |
| 32 | INC10377206 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP |
| 45 | INC10462250 | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA |

**Every correct prediction was for `SAPMENA L2`** and the matched keywords were almost always `CDS` + `SAP` (± `SAPMENA`, `ERP`, `Singapore`). No other canonical group was ever correctly predicted by the rules — because no other canonical group had tickets in the sample.

### 2.2 Categorised failure modes for the 53 mispredictions

| Failure mode | Count | Example | Root cause |
|---|---:|---|---|
| **L3 ticket → wrong L2 group** | 29 | INC10312845 (SAPMENA L3) → `O+O.CRM - L2` | Rules don't model L2/L3 distinction |
| **B2C Hypercare → wrong L2 group** | 19 | INC10430912 (B2C Hypercare) → `O+O.CRM - L2` | `hypercare`/`B2C` keywords too narrow; routine MARS/Loyalty/Lucid tickets in Hypercare miss |
| **Generic keyword wins (false positive)** | 17 | INC10293500 → `OMNISALES` because of `MARS` and `Capgemini` keywords | `MARS`, `Capgemini`, `API`, `lucid`, `loyalty` are universal; not group-discriminating |
| **Substring collisions on short keys** | 5+ | iBeauty 2.0's `BA` keyword matches `based`, `ba`, etc. — 56 hits, 0 correct | Sub-3-char or substring matches without word boundaries |
| **Real signal absent from rules** | many | `Aesop`, `SFCC`, `SFMC`, `EBTQ`, `LS team`, `LOY team`, `Outbound Gap`, `MARSID`, `C360` | Vocabulary mismatch with operators' actual reassignment language |

---

## 3. Per-keyword diagnostic — which existing keywords actually work

Full per-keyword table in [`ANALYSIS-RAW.md`](./ANALYSIS-RAW.md) §4. Below are the verdicts.

### 3.1 Keywords that pull their weight (low drift, real hits in the right group)

| Group | Keyword | Total hits | Hits in own group | Drift | Verdict |
|---|---|---:|---:|---:|---|
| SAPMENA L2 | `SAPMENA` | 10 | 5 | 0.50 | KEEP — discriminating |
| SAPMENA L2 | `ERP` | 10 | 4 | 0.60 | KEEP — discriminating |
| B2C Hypercare | `hypercare` | 12 | 8 | 0.33 | KEEP — best-performing keyword in the dataset |
| B2C Hypercare | `B2C` | 13 | 5 | 0.62 | KEEP |
| B2C Hypercare | `launch` | 3 | 1 | 0.67 | KEEP (low volume but on-topic) |

### 3.2 Keywords that *appear* but always in the *wrong* group (high-drift; remove or relocate)

| Owning group | Keyword | Total hits | Hits in own group | Drift | Verdict |
|---|---|---:|---:|---:|---|
| OMNISALES | `MARS` | 47 | 0 | 1.00 | **REMOVE from OMNISALES** — MARS is a backend system that *all* groups discuss; not OMNISALES-exclusive |
| OMNISALES | `Capgemini` | 30 | 0 | 1.00 | **REMOVE** — Capgemini is one of several vendors (Accenture, Sapient, TCS, LTIMINDTREE, NAGARRO, VISEO are all present); not OMNISALES-exclusive |
| OMNISALES | `omni` | 2 | 0 | 1.00 | **REMOVE** — never indicates OMNISALES |
| OMNISALES | `GDC` | 1 | 0 | 1.00 | **REMOVE** — 1 hit, not in own group |
| OMNISALES | `OMNISALES` | 1 | 0 | 1.00 | KEEP, but accept it's rare in real text |
| OPERATIONS | `API` | 47 | 0 | 1.00 | **REMOVE from OPERATIONS** — `API` is universal in this domain |
| OPERATIONS | `batch` | 13 | 0 | 1.00 | **REMOVE** — describes work, not ownership |
| OPERATIONS | `ETL` | 3 | 0 | 1.00 | **REMOVE** — describes work, not ownership |
| CRM | `lucid` | 37 | 0 | 1.00 | **MOVE** — `LUCID` is the consumer identifier used by every team. It does NOT predict CRM |
| CRM | `CRM` | 28 | 0 | 1.00 | **REMOVE** — used as concept everywhere, including SAPMENA L2/L3 |
| CRM | `loyalty` | 24 | 0 | 1.00 | **REMOVE/MOVE** — loyalty is *the* topic of CHN-Loyalty L3, not OMNISALES-CRM-L2 |
| CRM | `account` | 17 | 0 | 1.00 | **REMOVE** — universal noun |
| iBeauty 2.0 | `BA` | 56 | 0 | 1.00 | **REMOVE** — 2-char substring; matches "based", "above", etc. inside larger words. Catastrophic false-positive driver |
| iBeauty 2.0 | `iBeauty` | 15 | 0 | 1.00 | **MOVE** — iBeauty issues in this sample sit in SAPMENA L2/L3 or B2C Hypercare, not in the iBeauty 2.0 Retail L2 group |
| iBeauty 2.0 | `skin` | 2 | 0 | 1.00 | REMOVE |
| iBeauty 2.0 | `retail app` | 1 | 0 | 1.00 | KEEP (low volume but plausibly discriminating) |
| NGLORA | `points` | 18 | 0 | 1.00 | **MOVE** — points = loyalty topic, currently routed via NGLORA but those issues actually sit in CHN Loyalty L3 / B2C Hypercare |
| NGLORA | `ORA` | 8 | 0 | 1.00 | **REVIEW** — 8 hits, may be matching as substring of other words |
| NGLORA | `redemption` | 1 | 0 | 1.00 | KEEP (low volume; on-topic) |
| HIP | `server` | 18 | 0 | 1.00 | **REMOVE** — common noun |
| HIP | `HIP` | 15 | 0 | 1.00 | KEEP (HIP group has no tickets in sample — drift is unverified, not necessarily a bug) |
| HIP | `database` | 12 | 0 | 1.00 | **REMOVE** — common noun |
| HIP | `SSO` | 8 | 0 | 1.00 | KEEP (specific) |
| HIP | `cloud` | 3 | 0 | 1.00 | KEEP if HIP is real owner — low volume |
| THN Retail IT | `POS` | 25 | 0 | 1.00 | **REVIEW** — POS appears widely but no Retail-IT tickets in sample |
| THN Retail IT | `Thailand` | 2 | 0 | 1.00 | KEEP (but tickets currently route to SAPMENA/B2C) |

### 3.3 Dead keywords — 0 total hits across all 64 incidents (no evidence either way)

```
APAC - THN - Retail IT:           cashier, terminal, store network, in-store, point of sale
APAC - ZN - iBeauty 2.0 - L2:     beauty advisor, clienteling, advisor app, consultation, shade, in-store app
APAC - ZN - OMNISALES:            click and collect, ship from store, inventory, retail order, MARS integration
APAC - ZN - O+O ONLINE.CED:       e-commerce, web order, cart, checkout, SPACE GDS, online store, SPACE-GDS
APAC - ZN - O+O.CRM:              consent, GDPR, Salesforce, email campaign
APAC - ZN - O+O.NGLORA:           NGLORA, LORA, loyalty rewards, rewards programme
APAC - ZN - O+O.OPERATIONS:       data sync, webhook, data ingestion
APAC - ZN - SPACE B2C Hypercare:  cutover, P1, escalation, new market, regression
TECH FNDN - WW - HIP INCIDENT L2: network, certificate, DNS
APAC - SGP - SAPMENA L2:          SGP, SAP order, product sync
```

These could be:
1. Genuinely high-precision keywords that simply don't fire on this sample (e.g. `cutover`, `P1`, `MARS integration`)
2. **Aspirational** keywords copied from group names without verifying real ticket language (most likely — the `assignment_rules.json` header literally says `[USER-CONFIRM] keywords are inferred from group names`).

Either way: they contribute zero to the current 17 % match rate and should be reviewed before they accidentally fire on something irrelevant.

---

## 4. Real-text signals discovered in incident comments / work-notes

Two complementary views: **top tokens by group** (frequency-based) and **explicit handoff phrases** (operator-written reassignment language).

### 4.1 Top discriminating tokens — by current group

From `ANALYSIS-RAW.md §3`, after stripping author names and SNOW boilerplate (`comment`, `additional`, `accenture`, `sapient`, `private`, `notes`, `wang`, `sherlyn`, `hanizam` etc.):

| Group | Content tokens that recur (with frequency from 64-ticket sample) |
|---|---|
| **SAPMENA L2 Support** | `cds` (123), `mars` (111), `customer` (59), `consumer` (50), `sales` (41), `code` (41), `update` (38), `outbound` (5+), `sapmena` (10+) |
| **SAPMENA L3 Support** | `cds` (high), `mars` (high), `lucid` (very high), `patch`, `prb`, `parent ticket`, `l3 team` |
| **B2C Hypercare** | `lucid` (234), `mars` (222), `cds` (218), `customer` (165), `orders` (125), `loy` (110), `LS` (high) |
| **CHN Loyalty L3** | `loyalty`, `loy`, `points`, `redemption`, `tier`, `rule`, `subscription` |

Cross-group recurring tokens (universal — useless for routing): `lucid`, `mars`, `cds`, `customer`, `consumer`, `account`, `points`, `order`, `code`, `merge`, `duplicate`.

### 4.2 Explicit reassignment phrases — what operators actually say (215 phrases)

Full list: [`HANDOFFS-RAW.md`](./HANDOFFS-RAW.md). The real routing destinations operators reference, with example counts in the sample:

| Real handoff destination | Example phrase | Group code(s) it likely maps to |
|---|---|---|
| `CDS L2` | "Reassigning back to L2 for verification and closure" | SAPMENA L2 |
| `CDS L3` | "Reassigning to CDS L3, any update on the fix will be tracked under PRB0082698" | SAPMENA L3 (NOT canonical) |
| `MARS` / `MARS team` / `MARS Ops team` | "Reassigning to MARS", "Reassigning to retail Ops team" | A *MARS support team* — likely OMNISALES or a separate one |
| `LS` / `LS team` / `LS Hypercare team` | "Assigning to LS team" | Unmapped — possibly OMNISALES.RETAIL or B2C Hypercare-adjacent |
| `LOY` / `Loyalty` / `LOY L3` | "Reassigning to Loyalty, please refer to the comment below" | CHN-Loyalty L3 (NOT canonical) / NGLORA? |
| `Aesop hypercare` | "Reassigning to Aesop hypercare" | Brand-specific hypercare — not in rules |
| `SFCC` | "Reassigning to SFCC please refer to the comment below" | O+O ONLINE.CED (Salesforce Commerce Cloud) |
| `NGL L2` | "Assigning to NGL L2" | NGLORA (correct mapping) |
| `iBeauty L2` / `IBeauty team` | "Assigning to IBeauty team for further analysis" | iBeauty 2.0 Retail L2 (correct mapping) |
| `HIP team` | "We checked with the SFCC L2 team... HI HIP team" | HIP INCIDENT L2 (correct mapping) |
| `C360 team` | "Assigning to C360 team to fetch the Birthday call list for YSL SG" | Reporting/BI — unmapped |
| `Azure team` | "assign to Azure team" | Likely HIP cloud |
| `INFRA - WW - Linux Unix ACN - L3` | (verbatim group name in a work-note) | HIP-adjacent |
| `CE team` / `CE Ops team` | "for the CE team to trigger the CRM001 file outbound file to MARS" | Possibly O+O.CRM |

**Key insight:** operators route by *system name being touched* (`CDS`, `LS`, `LOY`, `MARS`, `SFCC`, `iBeauty`) plus *tier* (`L2` vs `L3`) — NOT by the business-architecture group names in `assignment_rules.json`. The current rules sit at a different level of abstraction than the actual routing decisions.

### 4.3 New high-signal tokens NOT in current rules

| Token | Likely target group | Evidence in sample |
|---|---|---|
| `Aesop` (brand) | New group: *APAC - Aesop hypercare* | Mentioned verbatim in INC10421600 work-note; brand-specific |
| `SFCC` (Salesforce Commerce Cloud) | `O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2` | "Reassigning to SFCC" (INC10442394) |
| `SFMC` (Salesforce Marketing Cloud) | `O+O.CRM - L2` | INC10475182, INC10483228 |
| `SFDC` (Salesforce) | `O+O.CRM - L2` or CHN-Loyalty | INC10466783 |
| `iBeauty 2.0` (specific app version) | `iBeauty 2.0 - Retail - L2` (more specific than current `iBeauty`) | INC10482324 |
| `Outbound Gap Data` | `SAPMENA L2 Support` | INC10453163, INC10462256, INC10462212, INC10377206, INC10462250 (5 tickets!) |
| `MARSID` / `Mars ID` | NOT routing-specific (universal customer ID) | High frequency, low discrimination |
| `LUCID` (consumer profile ID) | NOT routing-specific (universal identifier) | 234 mentions in B2C Hypercare alone — too generic to discriminate |
| `MARS team` / `retail Ops team` | OMNISALES or a separate MARS L2 — needs business validation | "Reassigning to MARS team" (INC10328738) |
| `CDS L3` (the L3 tier) | `SAPMENA L3 Support` (NEW canonical group?) | 30+ mentions |
| `LS team` (Lucid Server?) | Unmapped — needs business validation | High frequency, recurring routing destination |
| `LOY L3` (loyalty L3 tier) | `CHN-Loyalty L3 Support` (NEW canonical group?) | Multiple mentions |
| `NGL` | NGLORA | "Assigning to NGL L2" (INC10442394) |
| `Tourist` / `Tourist Others` | Specific profile type — needs subcategory | INC10081673, INC10310154, INC10431241 |
| `Birthday Call List` / `C360` | Reporting/BI team — needs new mapping | INC10395005 |
| `EBTQ` (E-Boutique registration channel) | Likely SFCC/O+O ONLINE.CED | INC10199563 |
| `CloudSQL` / `Replica` | HIP infrastructure (already correctly routed by `cloud` keyword) | INC10450026 |
| `Linux Host` / `FS /mnt` / `usage above` | HIP — Linux Unix L3 | INC10396182 |
| `Cloudfare` (sic — likely Cloudflare) | HIP infrastructure | INC10466356 |
| `FindConsumerProfile`, `GetCustomerById`, `GetPurchaseV2`, `GetCalculatedAttributes`, `POST Customer/*` | API failures → `SAPMENA L2` (CDS API team) | Frequent in SAPMENA L2/L3 tickets |
| `E2E Monitoring` (automated alerts) | SAPMENA L2 (alert routing) | INC10442394, INC10367251, INC10190032 |

---

## 5. Recommendations (deferred to follow-up claim — DO NOT IMPLEMENT YET)

A separate quick claim should propose:

### 5.1 Schema changes to `assignment_rules.json`

1. **Add an `l3_groups` mapping** alongside `groups` — model L2 ↔ L3 explicitly. When a ticket's text contains "L3" or "PRB" or "data patch", recommend the L3 counterpart rather than the L2.
2. **Add per-keyword `boundary` flag** — for short keywords like `BA`, `NGL`, `ORA`, `LS`, force word-boundary regex match (`\bBA\b`) instead of substring. The current `kw.lower() in full_text.lower()` substring match is causing massive false positives.
3. **Add `negative_keywords`** — words that *exclude* a group. Example: "MARS" appearing with "CDS" should NOT route to OMNISALES (OMNISALES tickets specifically reference MARS-but-not-CDS).
4. **Add per-group `min_hits` and `weight`** — require ≥ 2 distinct keyword hits before predicting a group, to suppress single-token false positives like `BA` → iBeauty.

### 5.2 Per-group keyword rewrites (concrete proposals)

| Group | Remove | Add | Notes |
|---|---|---|---|
| `SAPMENA L2 Support` | `SGP`, `pipeline`, `SPACE CDS`, `SAP order`, `product sync` | `Outbound Gap`, `E2E Monitoring`, `FindConsumerProfile`, `GetCustomerById`, `GetPurchaseV2`, `GetCalculatedAttributes`, `SFMC`, `SFCC -> CDS`, `stg_sap_*` (table prefix) | Keep `SAP`, `SAPMENA`, `ERP`, `Singapore`, `CDS` |
| `iBeauty 2.0 - Retail - L2` | `BA` (catastrophic), `skin`, `shade`, `consultation`, `clienteling`, `advisor app`, `in-store app`, `iBeauty` (move to broader rule) | `iBeauty 2.0`, `\bBA\b` (boundary), `Beauty Advisor` (full phrase), `BA name` | Word-boundary regex mandatory |
| `OMNISALES.RETAIL - MARS` | `MARS` (move out), `Capgemini`, `omni`, `GDC`, `MARS integration` | `retail Ops team`, `OMNISALES`, `MARS Ops`, `sales rep`, `salesrep`, `location code`, `store code`, `MARS-{country}` patterns | The current rules are wildly mis-anchored |
| `O+O ONLINE.CED` | `SPACE GDS`, `SPACE-GDS`, `online store`, `cart`, `checkout`, `web order`, `e-commerce` (kept only if validated) | `SFCC`, `EBTQ`, `Arvato` (3PL), `online order`, `web cart` | Validate with wider fetch first |
| `O+O.CRM` | `lucid` (universal, MOVE), `account` (universal), `loyalty` (universal), `marketing`, `consent`, `GDPR`, `email campaign`, `Salesforce` (too generic; use SFMC/SFDC) | `SFMC`, `SFDC`, `Campaign`, `CRM001 file`, `CE team`, `prospect ingestion`, `consumer registration` | The CRM rule is currently the worst false-positive driver |
| `O+O.NGLORA` | `LORA`, `ORA` (substring trap), `loyalty rewards`, `rewards programme`, `NGLORA` (rare in real text) | `NGL`, `NGL L2`, `points credit`, `points redemption`, `rule-500` | `ORA` matches inside e.g. "respective", "operations" |
| `O+O.OPERATIONS` | `API` (universal), `batch`, `ETL`, `webhook`, `data sync`, `data ingestion`, `pipeline`, `integration` | (rely on negative-keywords from other groups + fallback flag) | This group should likely **be the silent fallback only**, not match keywords. Almost everything is "operations" |
| `SPACE B2C Hypercare` | `P1`, `escalation`, `new market`, `regression`, `cutover` (all 0 hits) | `LS team`, `LS Hypercare team`, `Hypercare group` | Keep `hypercare`, `B2C`, `go live`, `go-live`, `launch` — these actually work |
| `THN - Retail IT` | `cashier`, `terminal`, `store network`, `point of sale`, `in-store`, `printer` | (unable to validate — no Thailand-Retail-IT tickets in sample) | Re-fetch a queue scoped to this group before changing |
| `HIP INCIDENT L2` | `network`, `DNS`, `certificate` (0 hits, unverified) | `Linux Host`, `Cloudflare` (note spelling — also `Cloudfare`), `Azure`, `FS usage`, `disk usage`, `CloudSQL`, `Replica`, `auth failure` | Keep `HIP`, `SSO`, `SSL`, `infrastructure`, `database`, `server`, `cloud`, `platform` — but require ≥ 2 hits |

### 5.3 New canonical groups to consider adding

If the agent is meant to route across L'Oréal's actual operational reality (not just the "supported 10"):

| Proposed new group | Real-text signals |
|---|---|
| `APAC - SGP - SPACE CDS SAPMENA L3 Support` | "CDS L3", "PRB", "data patch", "patch script", "tracked under PRB" |
| `APAC - CHN - SPACE Loyalty L3 Support` | "LOY L3", "LOY team", "Loyalty L3", "rule-500", "subscription points" |
| `Aesop Hypercare` | "Aesop hypercare", "Aesop brand" |
| `INFRA - WW - Linux Unix ACN - L3` | "Linux Host", "FS /mnt", "Capline" hostnames |

### 5.4 Process recommendation

Before changing `assignment_rules.json`, fetch a **broader queue** that's not scoped to "my groups" — for example:

```
active=true^state!=6  (all active across all APAC support groups)
```

This would let us validate the 8 canonical groups that had 0 tickets in this sample. Without that data, edits to those groups are still guesses.

---

## 6. Files produced by this claim

```
.planning/quick/quick-kayinleong-018/
├── CLAIM.md
├── FINDINGS.md           ← this file
├── ANALYSIS-RAW.md       ← per-incident table, per-group token counts, per-keyword drift
├── HANDOFFS-RAW.md       ← 215 explicit handoff phrases from work-notes
└── scripts/
    ├── analyze.py        ← regenerates ANALYSIS-RAW.md from _all_incidents.json + assignment_rules.json
    └── handoffs.py       ← regenerates HANDOFFS-RAW.md
```

**Data on disk (gitignored — DO NOT COMMIT):**
- `./my_reports/INC*.json` — 64 incident JSON files
- `./my_reports/_all_incidents.json` — combined 295MB
- `./my_reports/attachments/INC*/` — downloaded screenshots & files (may contain PII)

**To regenerate:**

```bash
.venv/bin/python .planning/quick/quick-kayinleong-018/scripts/analyze.py \
    ./my_reports/_all_incidents.json \
    ./ticketasg_copilot_agent/assignment_rules.json \
  > .planning/quick/quick-kayinleong-018/ANALYSIS-RAW.md

.venv/bin/python .planning/quick/quick-kayinleong-018/scripts/handoffs.py \
    ./my_reports/_all_incidents.json \
  > .planning/quick/quick-kayinleong-018/HANDOFFS-RAW.md
```
