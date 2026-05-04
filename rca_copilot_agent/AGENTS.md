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
For each hypothesis run one or more targeted queries:

| Check | Pattern |
|-------|---------|
| Exists? | `SELECT EXISTS(SELECT 1 FROM t WHERE id = '…')` |
| Count | `SELECT COUNT(*) FROM t WHERE …` |
| Field value | `SELECT field FROM t WHERE id = '…' LIMIT 1` |
| Null audit | `SELECT COUNTIF(field IS NULL) FROM t WHERE …` |
| Date window | `SELECT MIN(ts), MAX(ts) FROM t WHERE …` |
| Comparison | `SELECT a.f, b.f FROM a JOIN b ON … WHERE a.f != b.f LIMIT 10` |

Always add a `LIMIT` clause. Use backtick table refs:
`` `oa-apmena-spacecds-ap-pd`.`space_cds_b2c_ds_replica_ae2_pd_public`.table_name ``

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

## Common SPACE CDS Root Causes

| # | Root Cause | Signal |
|---|-----------|--------|
| 1 | Missing MARSID | User profile has no MARS ID — orders can't be matched |
| 2 | EAN mismatch | V14/V21 migration left orphan EAN codes |
| 3 | Pipeline delay | Data not yet replicated to BigQuery — check timestamps |
| 4 | CBR mapping gap | Product absent from mars_V21_mapping_product table |
| 5 | Profile merge | Duplicate profiles with different loyalty IDs |
| 6 | Region config | Country/brand code mismatch in routing tables |

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
| `space_cds_b2c_ds_replica_ase1_dv_public` | B2C ASE1 pipeline debug or survey data |

**Access:** Read-only via gcloud ADC — no credentials in `.env` needed  
**Dialect:** GoogleSQL (backtick refs, SAFE_DIVIDE, UNNEST, etc.)  
**Schema source:** `schema.json` in repo root — `get_schema` and `list_bq_tables` read all datasets instantly  
**Auth:** Run `gcloud auth application-default login` if BQ queries fail with auth errors

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
| LUCID / MARS ID | `consumer_pii`, `external_system_ids` | `lucid` |
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
