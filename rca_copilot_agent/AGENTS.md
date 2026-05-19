# AGENTS.md — RCA Copilot Agent

> Instruction schema for GitHub Copilot (or any MCP-aware LLM client).
> All LLM reasoning stays in the client. This server exposes only pure-function tools.

## Purpose

Investigate ServiceNow incidents for L'Oréal SPACE CDS (Consumer Data Services).
Validate root causes with live BigQuery queries and produce structured RCA reports.

## Tool Inventory

| Tool | When to use |
|------|-------------|
| `analyze_incident` | ONE-STOP: fetch incident + attachments + identifiers |
| `fetch_incidents` | Bulk-download all incidents from a SNOW list URL |
| `get_incident` | Fetch a single live incident by number |
| `get_incident_summary` | Read full incident text from local cache |
| `list_incidents` | Discover what is locally available |
| `search_incidents` | Keyword-search across all local incidents |
| `post_comment` | Post comment / work note to SNOW (confirm with user first) |
| `extract_identifiers` | Pull order IDs, emails, EAN codes from an incident |
| `download_attachments` | Download image / file attachments for an incident |
| `query_bigquery` | Run a read-only SELECT query against SPACE CDS data |
| `get_schema` | Get table columns, or list all tables in the dataset |
| `list_bq_tables` | List all BQ tables with row counts and sizes |
| `save_rca_report` | **MANDATORY** — save every completed RCA report to disk |
| `send_rca_email` | **MANDATORY** — notify the human when the session is done |
| `auto_credential_refresh` | Automatic startup tool — not callable; runs at MCP server start to detect and renew stale ServiceNow session cookies via browser SSO |
| `auto_gcloud_auth` | Automatic startup tool — not callable; runs after SNOW auth to verify the active gcloud account is a loreal.com account and ADC is configured; triggers `gcloud auth application-default login` if not |

## Environment Setup

### ServiceNow Credentials (auto-refreshed)

At startup the MCP server checks whether `COOKIE` and `X_USERTOKEN` in `.env` are valid.
If missing or expired, a Microsoft Edge window opens automatically for SSO login.
Credentials are written back to `.env` after login — no manual DevTools copy-paste needed.

**First-time setup (one-time only):**
```bash
pip install playwright
```

Edge is already installed — no additional browser download required.

If playwright is not installed, the server falls back to the manual instructions in `.env.example`.

## Running Without MCP (Skills / CLI Mode)

L'Oréal's environment does not allow MCP servers. Use `run_tool.py` instead — it wraps every
tool function and requires no server process:

```bash
# One-stop analysis for a single incident
python rca_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'

# List locally cached incidents
python rca_copilot_agent/run_tool.py list_incidents --json '{}'

# Fetch all incidents from a SNOW list URL
python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "https://loreal.service-now.com/..."}'

# Run a BigQuery query (always include LIMIT)
python rca_copilot_agent/run_tool.py query_bigquery \
    --json '{"sql": "SELECT * FROM `oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public.purchase` WHERE sourceordernumber = \"ORD123\" LIMIT 5", "rationale": "Look up order status"}'

# Save an RCA report to disk (MANDATORY after each incident)
python rca_copilot_agent/run_tool.py save_rca_report \
    --json '{"incident_number": "INC10403788", "report_text": "### WHAT HAPPENED\n..."}'

# Send email notification (MANDATORY once per session, after all reports saved)
python rca_copilot_agent/run_tool.py send_rca_email \
    --json '{"session_summary": "Investigated INC10403788 — root cause: missing MARSID", "subject": "RCA Complete — INC10403788"}'
```

**For Claude Code users:** invoke the `/rca-copilot` skill (`.claude/skills/rca-copilot/SKILL.md`)
which orchestrates the full RCA workflow using these CLI commands automatically via the `Bash` tool.

**For GitHub Copilot users:** the `.github/agents/rca_copilot.agent.md` agent definition uses
`run_in_terminal` to call `run_tool.py` directly — no MCP server process needed.

**All 14 tool names** (valid `<tool_name>` values for `--json` calls):

| Tool | Description |
|------|-------------|
| `list_incidents` | List locally cached incidents |
| `fetch_incidents` | Download all incidents from a SNOW list URL |
| `get_incident` | Fetch a single incident from SNOW by number |
| `get_incident_summary` | Read locally cached incident's full text |
| `analyze_incident` | ONE-STOP: fetch + attachments + identifiers |
| `search_incidents` | Keyword-search local incidents |
| `extract_identifiers` | Pull order IDs / emails / EAN codes from an incident |
| `download_attachments` | Download attachment files for an incident |
| `post_comment` | Post comment / work note to SNOW |
| `list_bq_tables` | List all BQ tables with RCA purpose |
| `get_schema` | Get column names and query patterns for a table |
| `query_bigquery` | Run a read-only SELECT query |
| `save_rca_report` | **MANDATORY** — save completed RCA to disk |
| `send_rca_email` | **MANDATORY** — notify reviewer when session done |

The credential refresh (`auth_tool`) and gcloud ADC check (`gcloud_tool`) also run automatically
at CLI startup — same as the MCP server startup sequence.

## Investigation Workflow

### Phase 1 — INGEST
1. Call `analyze_incident` for each incident under investigation.
   - Do NOT call `get_incident_summary` + `extract_identifiers` + `download_attachments` separately.
2. Extract from the result: order IDs, user/customer IDs, EAN codes, MARS IDs, emails.
3. Note the chronology and what the support team has already tried (from work notes).

### Phase 2 — DISCOVER
1. Call `list_bq_tables` to see all available tables and their RCA purpose (reads schema.json — instant, no BQ cost).
2. Call `get_schema <table_name>` to get column names, relationships, and ready-to-use query patterns.
3. Map extracted identifiers to table columns using the Key Tables table below.

### Phase 3 — VALIDATE
**Run multiple queries. One query is never enough. If a query returns 0 rows, that IS a finding — investigate why.**

For each hypothesis run one or more targeted queries:

| Check | Pattern |
|-------|---------|
| Exists? | `SELECT EXISTS(SELECT 1 FROM t WHERE id = '…')` |
| Count | `SELECT COUNT(*) FROM t WHERE …` |
| Field value | `SELECT field FROM t WHERE id = '…' LIMIT 1` |
| Null audit | `SELECT COUNTIF(field IS NULL) FROM t WHERE …` |
| Date window | `SELECT MIN(ts), MAX(ts) FROM t WHERE …` |
| Comparison | `SELECT a.f, b.f FROM a JOIN b ON … WHERE a.f != b.f LIMIT 10` |
| Phone lookup | `SELECT customercode, customername, phonenumber FROM t WHERE phonenumber LIKE '%<digits_only_phone>' LIMIT 5` — CDS strips non-digits and prepends country code on insert, so a trailing LIKE without REGEXP_REPLACE is correct and sufficient |

Always add a `LIMIT` clause. Use backtick table refs with the **full project.dataset.table path**:
- B2C PD (primary): `` `oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public.table_name` ``
- B2C AE2 DV (historical fallback): `` `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ae2_dv_public.table_name` ``
- B2B SEA DV: `` `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ase1_dv_cds_tgt.table_name` ``
- B2B ME DV: `` `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ae2_dv_cds_tgt.table_name` ``

**Query constraints (always enforce):**
- Do NOT filter by `recordstatus` — it is a CDC internal field
- For `consumer_pii` and `external_system_ids`: add `AND status = 'Active'`
- If primary returns 0 rows for a B2C query, retry against the AE2 DV replica

**BigQuery billing projects:** The tool automatically routes jobs to the correct billing project based on the table reference. No action required — but always use the fully-qualified `` `project.dataset.table` `` form.

### Phase 3b — B2B Customer "Cannot Search / Cannot Create" Checklist

When an incident is about a store BA unable to find or create a B2B customer, run ALL of these checks in order:

```sql
-- 1. Does the customer exist by customercode?
SELECT customerkey, customercode, customername, phonenumber, emailaddress,
       isdeletedcustomer, blockedaccount, blockedaccountreason, orderblocked,
       accountgroupcode, country, sourcecreatedtime, sourceupdatedtime
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ase1_dv_cds_tgt.customer`
WHERE customercode = '<CUSTOMERCODE>'
LIMIT 5

-- 2. If 0 rows: search by phone (CDS strips non-digits and prepends country code on insert —
--    use trailing LIKE so country-code prefix doesn't break the match)
SELECT customerkey, customercode, customername, phonenumber, emailaddress,
       isdeletedcustomer, blockedaccount, country
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ase1_dv_cds_tgt.customer`
WHERE phonenumber LIKE '%<DIGITS_ONLY_PHONE>'
LIMIT 10

-- 3. If customer found: check CFS profile (needed for login/search in the app)
SELECT cfsmasterkey, email, firstname, lastname, professionalmobilenumber,
       isemailvalid, ismobilevalid, createddatetime, lastupdateddatetime
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ase1_dv_cds_tgt.cfs_master`
WHERE professionalmobilenumber LIKE '%<DIGITS_ONLY_PHONE>'
   OR LOWER(email) = LOWER('<EMAIL_IF_KNOWN>')
LIMIT 5

-- 4. Check customer→CFS affiliation
SELECT a.cfsmasterkey, a.customercode, a.rolecode, a.validfrom, a.validto
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ase1_dv_cds_tgt.cfs_master_affiliation` a
WHERE a.customercode = '<CUSTOMERCODE>'
LIMIT 10

-- 5. Check if the store (customercode prefix) itself is active
SELECT customerkey, customercode, customername, isdeletedcustomer,
       blockedaccount, orderblocked, country
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2b_ds_replica_ase1_dv_cds_tgt.customer`
WHERE customercode LIKE '<STORE_PREFIX>%'
LIMIT 10
```

Interpret results:

| Finding | Root Cause |
|---------|-----------|
| Customer exists, `isdeletedcustomer = true` | Account was deleted — needs to be restored or recreated in SAP/MARS |
| Customer exists, `blockedaccount = true` | Account blocked — check `blockedaccountreason`; escalate to credit/sales team |
| Customer exists, `orderblocked != null/empty` | Order block active — check block code, escalate to sales |
| Customer exists, phone number doesn't match | Phone stored in CDS differs from what the BA is searching; BA may need to search by email or customercode instead |
| Customer exists, no CFS profile | CFS profile not created or not linked — contact lookup will fail; MARS needs to push CFS record |
| Customer exists, CFS but no affiliation | CFS-customer link missing — BA cannot be associated with the store |
| 0 rows by customercode | Customer not yet in CDS — check if SAP→MARS→CDS pipeline has processed the record; request MARS team to verify ingestion |
| 0 rows by phone too | Customer truly absent from CDS; confirm customercode is correct; ask MARS to resend |

### Phase 4 — CONCLUDE
1. Write the RCA report using the template below.
2. Call `save_rca_report` **immediately** after finishing each report.
   The saved path is automatically registered for email attachment.
3. Call `send_rca_email` **once**, after ALL reports are saved.
   - `session_summary`: plain-text list of incidents investigated and key finding per incident.
   - `subject`: short subject line, e.g. "RCA Complete — INC10403788, INC10412275".
4. After `send_rca_email` returns, tell the user: "Email sent — please review and confirm findings."

> **Never ask the user for verification before calling `send_rca_email`.**
> The email IS the notification. The user will respond when ready.

> **A failed or empty BQ query is NOT "cannot find root cause."** It is data that must be interpreted:
> - 0 rows by customercode → customer missing from CDS (ingestion issue)
> - Auth error → re-check project qualifier in SQL; try `oa-apmena-spacecds-ap-dv` as billing project
> - Syntax error → check column names with `get_schema` before retrying
> Always explain what the query result means in context of the incident.

## Report Template

```markdown
# RCA Report: {incident_number}
**{incident_title}**
*Investigated: {date}*

---

## WHAT HAPPENED
{one sentence — the symptom, not the cause}

## WHAT WE CHECKED
→ Checked {system} — {result}
→ Checked {system} — {result}

## WHAT WE FOUND
{conclusion from checks — one or two sentences with evidence}

## WHAT WE NEED / DID
{action items with owners and deadlines}
```

### Rule: Always use FULL canonical assignment-group names

When the report names a SNOW assignment group anywhere (action items in `WHAT WE NEED / DID`, evidence in `WHAT WE CHECKED`, etc.), **always write the verbatim canonical group name as it appears in ServiceNow.** Never use operator shortforms (`CDS L3`, `LOY`, `MARS team`, `iBeauty`, `NGL`, etc.) — they're ambiguous outside the team and they don't match the SNOW Reassign-Group picker.

Example:
- ✓ "Assign to `APAC - SGP - SPACE CDS SAPMENA L3 Support` as the issue is tracked in DFCT0268807."
- ✗ "Assign to CDS L3 team as the issue is tracked in DFCT0268807."

Shortform → canonical mapping (use this table when a work-note says e.g. "LOY" and you must translate it for the report):

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

L3 / specialised groups that appear in real work-notes (also use full names — never the shorthand):
- `APAC - SGP - SPACE CDS SAPMENA L3 Support`
- `APAC - CHN - SPACE Loyalty L3 Support`
- `APAC - SGP - SPACE Loyalty L3 Support`
- `INFRA - WW - Linux Unix ACN - L3`

If the right canonical group is uncertain, pick the closest match and add `[USER-CONFIRM]` next to it in the report so the reviewer knows to verify.

## Common SPACE CDS Root Causes

### B2C
| # | Root Cause | Signal |
|---|-----------|--------|
| 1 | Missing MARSID | User profile has no MARS ID — orders can't be matched |
| 2 | EAN mismatch | V14/V21 migration left orphan EAN codes |
| 3 | Pipeline delay | Data not yet replicated to BigQuery — check timestamps |
| 4 | CBR mapping gap | Product absent from mars_V21_mapping_product table |
| 5 | Profile merge | Duplicate profiles with different loyalty IDs |
| 6 | Region config | Country/brand code mismatch in routing tables |

### B2B (Customer Search / Create Issues)
| # | Root Cause | Signal | Resolution |
|---|-----------|--------|-----------|
| 7 | Customer not in CDS | 0 rows by customercode | SAP→MARS pipeline hasn't ingested; ask MARS to resend |
| 8 | Customer deleted | `isdeletedcustomer = true` | Needs recreate in SAP and re-push via MARS |
| 9 | Account blocked | `blockedaccount = true` | Check `blockedaccountreason`; credit/sales team unblocks |
| 10 | Order blocked | `orderblocked` not null | Sales order block — escalate to sales team |
| 11 | Phone mismatch | Phone in CDS ≠ BA is searching | BA should search by email or customercode instead |
| 12 | Missing CFS profile | Customer row exists, no `cfs_master` row | MARS needs to push the CFS professional profile |
| 13 | CFS not linked to customer | `cfs_master_affiliation` has no row | Affiliation record missing; MARS/SAP needs to create the link |

## BigQuery Datasets

### Primary — B2C Production
- **Project:** `oa-apmena-spacecds-ap-pd`
- **Dataset:** `space_cds_b2c_ds_replica_ae2_pd_public`
- **Use for:** All B2C consumer incidents (purchase, loyalty, account, GDPR, campaign)

### Additional — B2B & DV Replicas (`oa-apmena-spacecds-ap-dv`)
| Dataset | Use When |
|---------|----------|
| `space_cds_b2b_ds_replica_ae2_dv_cds_tgt` | B2B incident in Middle East region (SAP orders, invoices, salon accounts) |
| `space_cds_b2b_ds_replica_ase1_dv_cds_tgt` | B2B incident in Southeast Asia (same schema as AE2) |
| `space_cds_b2c_ds_replica_ae2_dv_public` | **B2C historical fallback** — same schema as primary; query here when primary (ae2_pd_public) returns 0 rows |
| `space_cds_b2c_ds_replica_ase1_dv_public` | B2C ASE1 pipeline debug or survey data |

**Access:** Read-only via gcloud ADC — no credentials in `.env` needed  
**Dialect:** GoogleSQL (backtick refs, SAFE_DIVIDE, UNNEST, etc.)  
**Schema source:** `schema.json` in repo root — `get_schema` and `list_bq_tables` read all datasets instantly  
**Auth:** Run `gcloud auth application-default login` if BQ queries fail with auth errors

### Query Rules (mandatory)

1. **Never filter by `recordstatus`** — it is an internal CDC replication field. Ignore it in all queries.
2. **Always filter consumers by `status = 'Active'`** — only active consumers are relevant for RCA.
   - `consumer_pii`: add `AND status = 'Active'` to every query
   - `external_system_ids`: add `AND status = 'Active'` when joining via lucid
3. **Use the B2C AE2 DV replica as historical fallback** — if a query against the primary dataset (`oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public`) returns 0 rows, retry the same query against the replica (`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ae2_dv_public`). The replica has identical table names and column schemas.
4. **LUCID and MARSID are not unique across brands** — the same LUCID can exist in `consumer_pii` and `external_system_ids` under different brands. Always include `signature` (brand) and `isocountry` in the SELECT. When the incident provides brand/country context, also add `AND signature = '<BRAND>'` and `AND isocountry = '<ISO2>'` as filters to narrow to the correct record.
5. **Phone number search: use trailing LIKE, not REGEXP_REPLACE** — CDS cleans phone numbers before insert (strips non-digits, prepends country code). Search with `phonenumber LIKE '%<digits_only_number>'` — the trailing wildcard absorbs the country code prefix without needing REGEXP_REPLACE. Applies to `consumer_pii.mobilenumber`, `customer.phonenumber`, and `cfs_master.professionalmobilenumber`.

### Key Tables for RCA — B2C

| Table | Use When |
|-------|----------|
| `purchase` | Incident mentions order number — look up state, reason code, amount |
| `purchase_item` | Need item-level detail — EAN codes, line item states, quantities |
| `consumer_pii` | Incident mentions email, mobile, or "account not found" |
| `external_system_ids` | Need to map external/source system ID → lucid |
| `product` | Incident mentions product, EAN barcode, or SKU issue |
| `shipment` | Incident mentions delivery problem, carrier, or shipping delay |
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
| Order number (items) | `purchase_item` | `sourceordernumber` |
| Consumer email | `consumer_pii` | `email` |
| LUCID / MARS ID | `consumer_pii`, `external_system_ids` | `lucid` — always SELECT `signature` and `isocountry` alongside; same LUCID exists across brands, so filter by `signature` + `isocountry` when incident context provides them |
| External consumer ID | `external_system_ids` | `sourceconsumerid` |
| EAN / barcode | `product` | `ean` (also `purchase_item.eancode`) |
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

## Email Notification Setup

SMTP settings are loaded from `.env` (see `.env.example`):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=you@gmail.com
SMTP_PASSWORD=<app-password>
SMTP_FROM=you@gmail.com
SMTP_TO=reviewer@example.com
```

If `send_rca_email` returns `✗ SMTP not configured`, ask the user to fill in the SMTP
settings in `.env` and retry.
