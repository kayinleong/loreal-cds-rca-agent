# Phase Plan: BigQuery gcloud MCP Tool

**Goal:** Replace env-var-based BigQuery access with a gcloud ADC (Application Default Credentials) MCP tool that reads from a local `schema.json`, enabling richer, schema-aware RCA queries without requiring BQ credentials in `.env`.

**Project:** `oa-apmena-spacecds-ap-pd` · Dataset: `space_cds_b2c_ds_replica_ae2_pd_public`  
**Auth:** `kayin.leong@loreal.com` via gcloud ADC (already configured)  
**Tables discovered:** 45 tables including purchase, consumer_pii, product, shipment, care_case

---

## Why this matters

Currently the agent can only summarise ticket comments and attachments. With a schema-aware BQ tool, it can cross-reference actual pipeline data (purchase records, consumer profiles, shipments) against incident identifiers — finding root causes instead of just restating symptoms.

The old approach required `BQ_PROJECT` + `BQ_DATASET` in `.env` and in `rca_copilot.agent.md`, making setup fragile. The new approach uses gcloud ADC already on the machine — no credentials to configure.

---

## Wave 1 — Schema Discovery (Sequential, must run first)

### Task 1.1 — Run full schema discovery and write `schema.json`

**What to do:**

Run the following `bq` commands and write output to `/schema.json` in the repo root:

```bash
# List all tables with row counts
bq ls --format=json --project_id=oa-apmena-spacecds-ap-pd space_cds_b2c_ds_replica_ae2_pd_public

# For each core table, get schema
bq show --schema --format=prettyjson oa-apmena-spacecds-ap-pd:space_cds_b2c_ds_replica_ae2_pd_public.<TABLE>
```

Tables to document (core set — skip `_bkp_*` and `_01_07` backup tables):

| Table | RCA Purpose |
|-------|-------------|
| `consumer_pii` | Consumer identity — email, mobile, lucid, MARS ID lookup |
| `external_system_ids` | Cross-system ID mapping (sourceconsumerid ↔ lucid) |
| `purchase` | Order header — order number, state, amount, country |
| `purchase_item` | Order line items — EAN codes, product IDs, quantities |
| `purchase_commercial_ids` | Commercial order identifiers |
| `purchase_item_commercial_ids` | Commercial line item identifiers |
| `product` | Product catalogue — EAN, SAP material number, hierarchy |
| `product_hierarchy` | Product category tree |
| `shipment` | Shipping records — carrier, delivery dates |
| `shipment_addresses` | Shipping address details |
| `consumer_addresses` | Consumer address book |
| `consumer_extra` | Extended consumer profile (age, occupation, locale) |
| `consumer_marketing_preferences` | Opt-in/opt-out status per channel |
| `consumer_calculated_attributes` | Computed attributes (loyalty tier, etc.) |
| `consumer_behaviour` | Points earn/burn events |
| `consumer_behaviour_items` | Behaviour event line items |
| `consumer_agreement_logs` | Consent audit trail |
| `consumer_merge` | Consumer merge/dedup history |
| `care_case` | CRM care cases — maps to ServiceNow incidents |
| `campaign` | Marketing campaigns |
| `campaign_target` | Campaign audience segments |
| `campaign_response_inbound` | Campaign response events |
| `auto_replenishment` | Auto-replenishment subscriptions |
| `location` | Store/location master data |
| `sales_rep` | Sales representative master |
| `consumer_beauty_experience` | Beauty experience events |
| `consumer_beauty_profile` | Beauty profile attributes |
| `survey` / `survey_responses` / `survey_targets` | Survey data |
| `delete_consumer_request` | GDPR deletion audit trail |
| `iso_country_iso_3166_1_map` | Country code reference |
| `consumer_social_contacts` | Social profile links |

**Output format for `schema.json`:**

```json
{
  "project": "oa-apmena-spacecds-ap-pd",
  "dataset": "space_cds_b2c_ds_replica_ae2_pd_public",
  "dialect": "GoogleSQL",
  "auth": "gcloud ADC (Application Default Credentials)",
  "tables": {
    "purchase": {
      "purpose": "Order header records — look up order by sourceordernumber or lucid",
      "description": "One row per order. Links to purchase_item via purchasekey.",
      "clustered_by": ["isocountry", "signature", "purchasekey"],
      "partitioned_by": "sysupdatedatetime (DAY)",
      "columns": [
        {"name": "purchasekey", "type": "STRING", "mode": "NULLABLE", "description": "Primary key"},
        {"name": "isocountry", "type": "STRING", "mode": "NULLABLE", "description": "ISO country code"},
        {"name": "signature", "type": "STRING", "mode": "NULLABLE", "description": "Brand/division signature"},
        {"name": "sourceordernumber", "type": "STRING", "mode": "NULLABLE", "description": "Order number from source system — matches incident order IDs"},
        {"name": "lucid", "type": "STRING", "mode": "NULLABLE", "description": "L'Oréal Universal Consumer ID"},
        {"name": "currentstate", "type": "STRING", "mode": "NULLABLE", "description": "Order lifecycle state"},
        {"name": "orderdatetime", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When order was placed"},
        {"name": "amountwithtax", "type": "NUMERIC", "mode": "NULLABLE", "description": "Order total with tax"},
        {"name": "reasoncode", "type": "STRING", "mode": "NULLABLE", "description": "Cancellation/error reason code"},
        {"name": "reasonmessage", "type": "STRING", "mode": "NULLABLE", "description": "Cancellation/error reason message"},
        {"name": "sysupdatedatetime", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Last BQ sync timestamp"}
      ],
      "relationships": [
        "purchase.purchasekey → purchase_item.purchasekey (one-to-many)",
        "purchase.lucid → consumer_pii.lucid",
        "purchase.sourceordernumber → shipment.sourceordernumber",
        "purchase.purchasekey → purchase_commercial_ids.purchasekey"
      ],
      "common_queries": [
        "Find order by number: SELECT * FROM purchase WHERE sourceordernumber = '...' LIMIT 1",
        "Find orders by consumer: SELECT * FROM purchase WHERE lucid = '...' ORDER BY orderdatetime DESC LIMIT 10"
      ]
    }
  },
  "key_identifiers": {
    "lucid": "L'Oréal Universal Consumer ID — links consumer_pii, purchase, external_system_ids, behaviour",
    "consumerkey": "Internal BQ consumer key — used in consumer_* tables",
    "purchasekey": "Internal BQ order key — links purchase to purchase_item, shipment",
    "sourceordernumber": "External order number from source system — appears in incident text",
    "ean": "European Article Number — product identifier, appears in incidents about product issues",
    "sourceconsumerid": "External system consumer ID — use external_system_ids to resolve to lucid"
  },
  "common_rca_patterns": {
    "order_not_found": "SELECT EXISTS(SELECT 1 FROM purchase WHERE sourceordernumber = '...')",
    "order_state_check": "SELECT currentstate, reasoncode, reasonmessage FROM purchase WHERE sourceordernumber = '...' LIMIT 1",
    "consumer_lookup_by_email": "SELECT lucid, status FROM consumer_pii WHERE email = '...' AND isocountry = '...' LIMIT 1",
    "product_by_ean": "SELECT name, type, productcategory FROM product WHERE ean = '...' LIMIT 1",
    "shipment_status": "SELECT shippingmethod, carrier, expecteddeliverydatetime FROM shipment WHERE sourceordernumber = '...' LIMIT 1"
  }
}
```

**Acceptance criteria:**
- `schema.json` exists in repo root
- Contains `project`, `dataset`, `tables` keys
- Each core table has `purpose`, `columns` (with `name`, `type`), `relationships`, `common_queries`
- `key_identifiers` section maps identifier names to their join paths
- `common_rca_patterns` provides ready-to-use query templates

---

## Wave 2 — New BQ Tool Implementation (depends on Wave 1)

### Task 2.1 — Rewrite `rca_copilot_agent/tools/bigquery_tool.py`

**Read first:** `rca_copilot_agent/tools/bigquery_tool.py` (current implementation)

**What to change:**

Replace the env-var-based initialization with schema.json-driven initialization. Keep `SafeBigQueryExecutor` and all safety guardrails unchanged.

**Remove:**
- `init_executor(project, dataset, **kwargs)` function signature that takes env var values
- `_BQ_UNAVAILABLE` message referencing BQ_PROJECT/BQ_DATASET

**Add:**
```python
import json
from pathlib import Path

# schema.json lives in the repo root (3 levels up from this tools/ file)
_SCHEMA_JSON = Path(__file__).resolve().parent.parent.parent / "schema.json"

def _load_schema_json() -> dict:
    """Load schema.json from repo root. Raises RuntimeError if missing."""
    if not _SCHEMA_JSON.exists():
        raise RuntimeError(
            f"schema.json not found at {_SCHEMA_JSON}. "
            "Run schema discovery (Task 1.1) to generate it."
        )
    return json.loads(_SCHEMA_JSON.read_text(encoding="utf-8"))


def init_from_schema() -> None:
    """Initialize BQ executor from schema.json. No env vars required."""
    global _executor, _dataset
    schema = _load_schema_json()
    project = schema["project"]
    _dataset = schema["dataset"]
    _executor = SafeBigQueryExecutor(
        project=project,
        max_bytes=500_000_000,
        timeout=30.0,
        max_rows=100,
    )


def get_schema_from_file(table_name: str = "") -> str:
    """Return schema info from schema.json. Empty name = list all tables."""
    schema = _load_schema_json()
    tables = schema.get("tables", {})
    project = schema.get("project", "")
    dataset = schema.get("dataset", "")

    if not table_name:
        lines = [
            f"PROJECT: `{project}`",
            f"DATASET: `{dataset}`",
            f"DIALECT: {schema.get('dialect', 'GoogleSQL')}",
            "",
            f"TABLES ({len(tables)}):",
        ]
        for name in sorted(tables.keys()):
            t = tables[name]
            purpose = t.get("purpose", t.get("description", ""))
            lines.append(f"  `{project}.{dataset}.{name}` — {purpose}")
        return "\n".join(lines)

    # Exact match first, then substring
    matched = table_name if table_name in tables else next(
        (k for k in tables if table_name.lower() in k.lower()), None
    )
    if not matched:
        return f"Table '{table_name}' not found in schema.json. Call list_bq_tables to see available tables."

    t = tables[matched]
    lines = [
        f"TABLE: `{project}.{dataset}.{matched}`",
        f"Purpose: {t.get('purpose', '')}",
        f"Description: {t.get('description', '')}",
        "",
        "COLUMNS:",
    ]
    for col in t.get("columns", []):
        desc = f"  -- {col['description']}" if col.get("description") else ""
        lines.append(f"  {col['name']:<42} {col['type']:<12}{desc}")

    if t.get("relationships"):
        lines.append("\nRELATIONSHIPS:")
        for rel in t["relationships"]:
            lines.append(f"  {rel}")

    if t.get("common_queries"):
        lines.append("\nCOMMON QUERIES:")
        for q in t["common_queries"]:
            lines.append(f"  {q}")

    return "\n".join(lines)


_BQ_UNAVAILABLE = (
    "BigQuery is not available. schema.json may be missing from the repo root. "
    "Ensure schema.json exists and gcloud ADC is configured (run: gcloud auth application-default login)."
)
```

**Keep unchanged:**
- `SafeBigQueryExecutor` class (all validation, dry-run, execute, list_tables, get_schema methods)
- `DANGEROUS_KEYWORDS` set
- `QueryResult` dataclass
- `query_bigquery()` function
- `is_enabled()` function
- `_executor`, `_dataset` module-level variables

**Acceptance criteria:**
- `bigquery_tool.py` contains `init_from_schema()` function
- `bigquery_tool.py` contains `get_schema_from_file(table_name="")` function
- `bigquery_tool.py` contains `_SCHEMA_JSON` path pointing to repo root `schema.json`
- `init_executor(project, dataset, **kwargs)` is removed
- `is_enabled()` still works (returns True when `_executor` is not None)
- `query_bigquery(sql, rationale)` still works unchanged

---

### Task 2.2 — Update `rca_copilot_agent/mcp_server.py`

**Read first:** `rca_copilot_agent/mcp_server.py` (lines 840–912, the `main()` function)

**Remove from `main()`:**
```python
# DELETE these lines:
from config import load_config, load_bq_config
bq_cfg = load_bq_config()
if bq_cfg.enabled:
    from tools.bigquery_tool import init_executor as init_bq
    init_bq(
        project=bq_cfg.project,
        dataset=bq_cfg.dataset,
        max_bytes=bq_cfg.max_bytes,
        timeout=bq_cfg.timeout,
        max_rows=bq_cfg.max_rows,
    )
    logger.info(f"[BQ] Initialized: {bq_cfg.project}.{bq_cfg.dataset}")
else:
    logger.info("[BQ] BQ_PROJECT not set — BigQuery tools disabled.")
```

**Replace with:**
```python
from config import load_config
# Initialize BigQuery from schema.json (gcloud ADC — no env vars needed)
try:
    from tools.bigquery_tool import init_from_schema
    init_from_schema()
    logger.info("[BQ] Initialized from schema.json via gcloud ADC")
except Exception as bq_err:
    logger.warning(f"[BQ] Not available: {bq_err}")
```

**Update `_dispatch()` for `get_schema`** (line ~644):
```python
elif name == "get_schema":
    from tools.bigquery_tool import get_schema_from_file
    return get_schema_from_file(arguments.get("table_name", ""))
```

**Update `_dispatch()` for `list_bq_tables`** (line ~651):
```python
elif name == "list_bq_tables":
    from tools.bigquery_tool import get_schema_from_file
    return get_schema_from_file("")  # empty = list all tables
```

**Update `query_bigquery` tool description in `list_tools()`** — remove the `f"{'{BQ_PROJECT}'}.{'{BQ_DATASET}'}` format string reference; replace with:
```python
description=(
    "Execute a read-only SELECT or WITH query against the SPACE CDS BigQuery dataset. "
    "Use to look up order data, pipeline events, or any structured data that may explain "
    "a ServiceNow incident. Blocked from INSERT/UPDATE/DELETE/DROP. "
    "Always add a LIMIT clause. Use backticks for table refs: "
    "`oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public.table_name`."
),
```

**Update `get_schema` tool description:**
```python
description=(
    "Get schema info for a BigQuery table from the local schema.json, or list all tables "
    "when no table name is given. Faster than a live BQ call — use this before writing queries "
    "to confirm column names and types."
),
```

**Update `list_bq_tables` tool description:**
```python
description=(
    "List all tables in the SPACE CDS BigQuery dataset with their purpose and column count. "
    "Reads from local schema.json — instant, no BQ cost."
),
```

**Acceptance criteria:**
- `main()` does not import or call `load_bq_config()`
- `main()` calls `init_from_schema()` inside a try/except
- `get_schema` handler calls `get_schema_from_file()`
- `list_bq_tables` handler calls `get_schema_from_file("")`
- No `f"` string with `'{BQ_PROJECT}'` or `'{BQ_DATASET}'` format vars in tool descriptions
- Server starts without BQ env vars set (verify: unset BQ_PROJECT and run `python mcp_server.py --help`)

---

## Wave 3 — Config & Env Cleanup (parallel with Wave 2)

### Task 3.1 — Update `rca_copilot_agent/config.py`

**Read first:** `rca_copilot_agent/config.py` (full file)

**Remove entirely:**
- `BigQueryConfig` dataclass (lines 64–74)
- `load_bq_config()` function (lines 100–116)

**Acceptance criteria:**
- `grep -n "BigQueryConfig\|load_bq_config\|BQ_PROJECT\|BQ_DATASET" rca_copilot_agent/config.py` returns nothing
- `ServiceNowConfig` and `SmtpConfig` and their `load_*` functions are still present

---

### Task 3.2 — Update `.env.example`

**Read first:** `.env.example` (full file)

**Remove the BigQuery section** (first 6 lines):
```
# ── BigQuery ─────────────────────────────────────────────────────
BQ_PROJECT=oa-apmena-spacecds-ap-pd
BQ_DATASET=space_cds_b2c_ds_replica_ae2_pd_public
BQ_MAX_BYTES=500000000
BQ_TIMEOUT=30
BQ_MAX_ROWS=100
```

**Add a note at the top** (after the ServiceNow section header):
```
# BigQuery access is provided via gcloud Application Default Credentials.
# No BQ_ env vars needed — run: gcloud auth application-default login
```

**Acceptance criteria:**
- `grep -n "BQ_PROJECT\|BQ_DATASET\|BQ_MAX\|BQ_TIMEOUT\|BQ_MAX_ROWS" .env.example` returns nothing
- `.env.example` still contains COOKIE, X_USERTOKEN, REPORTS_DIR, SMTP_* entries

---

### Task 3.3 — Update `.env` (remove BQ_ lines)

**Read first:** `.env` (full file)

**Remove:**
```
BQ_PROJECT=oa-apmena-spacecds-ap-pd
BQ_DATASET=space_cds_b2c_ds_replica_ae2_pd_public
BQ_MAX_BYTES=500000000
BQ_TIMEOUT=30
BQ_MAX_ROWS=100
```

**Acceptance criteria:**
- `grep "BQ_" .env` returns nothing

---

## Wave 4 — Agent Documentation Update (depends on Waves 2 & 3)

### Task 4.1 — Update `.github/agents/rca_copilot.agent.md`

**Read first:** `.github/agents/rca_copilot.agent.md` (full file)

**Changes:**

1. **Remove from `mcp-servers.snow-mcp.env` section:**
```yaml
      BQ_PROJECT: oa-apmena-spacecds-ap-pd
      BQ_DATASET: space_cds_b2c_ds_replica_ae2_pd_public
      BQ_MAX_BYTES: "500000000"
      BQ_TIMEOUT: "30"
      BQ_MAX_ROWS: "100"
```

2. **Update BigQuery usage guidelines** (Step 4 in the workflow, after "If order IDs…"):
Replace:
```
- Always call `get_schema` or `list_bq_tables` before writing a query to confirm table and column names.
```
With:
```
- Call `get_schema` or `list_bq_tables` to look up table structure from schema.json (instant, no BQ cost).
- `get_schema` returns full column list, relationships, and ready-to-use query patterns.
- `list_bq_tables` returns all 30+ tables with their RCA purpose — use when you don't know which table to query.
```

3. **Add a Phase 2 — DISCOVER section** to the workflow (between Step 1 and Step 2 in the current agent.md), documenting the schema-first approach:
```markdown
### Step 1.5 — Understand what BigQuery data is available

Before querying, understand the schema:

1. If identifiers were found in the incident, call `list_bq_tables` to see which table is relevant.
2. Call `get_schema <table_name>` to confirm column names and see common query patterns.
3. Use `common_rca_patterns` from the schema as query templates — fill in the identifier values.

Key identifier → table mappings:
| Identifier | Table | Column |
|-----------|-------|--------|
| Order number | `purchase` | `sourceordernumber` |
| Consumer email | `consumer_pii` | `email` |
| EAN code | `product` | `ean` (also `purchase_item.eancode`) |
| lucid / MARS ID | `consumer_pii`, `external_system_ids` | `lucid` |
```

**Acceptance criteria:**
- `grep "BQ_PROJECT\|BQ_DATASET\|BQ_MAX_BYTES\|BQ_TIMEOUT\|BQ_MAX_ROWS" .github/agents/rca_copilot.agent.md` returns nothing
- Agent.md contains `get_schema` and `list_bq_tables` usage instructions
- Identifier → table mapping table is present

---

### Task 4.2 — Update `rca_copilot_agent/AGENTS.md`

**Read first:** `rca_copilot_agent/AGENTS.md` (full file)

**Changes:**

1. **Update BigQuery Dataset section:**
Replace:
```markdown
## BigQuery Dataset

- **Project:** `oa-apmena-spacecds-ap-pd`
- **Dataset:** `space_cds_b2c_ds_replica_ae2_pd_public`
- **Access:** Read-only (SELECT / WITH only)
- **Dialect:** GoogleSQL (backtick refs, SAFE_DIVIDE, UNNEST, etc.)
```
With:
```markdown
## BigQuery Dataset

- **Project:** `oa-apmena-spacecds-ap-pd`
- **Dataset:** `space_cds_b2c_ds_replica_ae2_pd_public`
- **Access:** Read-only via gcloud ADC — no credentials in `.env` needed
- **Dialect:** GoogleSQL (backtick refs, SAFE_DIVIDE, UNNEST, etc.)
- **Schema source:** `schema.json` in repo root — call `get_schema` or `list_bq_tables` to read it
- **Auth:** Run `gcloud auth application-default login` if BQ queries fail with auth errors

### Key Tables for RCA

| Table | Use When |
|-------|----------|
| `purchase` | Incident mentions order number — look up state, reason code |
| `purchase_item` | Need item-level detail — EAN codes, line item states |
| `consumer_pii` | Incident mentions email or "account not found" |
| `external_system_ids` | Need to map external ID → lucid |
| `product` | Incident mentions product/EAN issue |
| `shipment` | Incident mentions delivery/shipping problem |
| `care_case` | Check if incident is already recorded as a care case |
| `consumer_behaviour` | Loyalty points issue — check earn/burn history |
| `consumer_marketing_preferences` | Marketing opt-in/opt-out issue |
```

2. **Update Phase 2 — DISCOVER** to reference schema.json:
```markdown
### Phase 2 — DISCOVER
1. Call `list_bq_tables` to see all available tables and their RCA purpose (reads schema.json — instant).
2. Call `get_schema <table_name>` to get column list and query patterns for the relevant table.
3. Map extracted identifiers to columns using the key_identifiers section of schema.json.
```

**Acceptance criteria:**
- AGENTS.md contains "gcloud ADC" and "schema.json" in BigQuery section
- Key Tables for RCA table is present with at least 8 entries
- `grep "BQ_PROJECT\|BQ_DATASET" rca_copilot_agent/AGENTS.md` returns nothing (except in the project/dataset literal values which are fine)

---

## Testing Checklist

After all waves complete, verify:

```bash
# 1. schema.json exists and is valid JSON
python3 -c "import json; s=json.load(open('schema.json')); print(f'Tables: {len(s[\"tables\"])}')"

# 2. BQ tool initializes without env vars
unset BQ_PROJECT BQ_DATASET
cd rca_copilot_agent && python3 -c "from tools.bigquery_tool import init_from_schema; init_from_schema(); print('OK')"

# 3. get_schema_from_file works offline
python3 -c "from tools.bigquery_tool import init_from_schema, get_schema_from_file; init_from_schema(); print(get_schema_from_file('purchase'))"

# 4. config.py has no BQ symbols
grep -c "BigQueryConfig\|load_bq_config" rca_copilot_agent/config.py  # must return 0

# 5. .env.example has no BQ_ vars
grep -c "^BQ_" .env.example  # must return 0

# 6. agent.md has no BQ_ env vars in frontmatter
grep -c "BQ_PROJECT\|BQ_DATASET\|BQ_MAX" .github/agents/rca_copilot.agent.md  # must return 0
```

---

## Files Changed Summary

| File | Action | What Changes |
|------|--------|-------------|
| `schema.json` (new) | Create | Full BQ schema with relationships, purpose, query patterns |
| `rca_copilot_agent/tools/bigquery_tool.py` | Rewrite | Replace env-init with schema.json-driven init; add `get_schema_from_file()` |
| `rca_copilot_agent/mcp_server.py` | Update | `main()` uses `init_from_schema()`; `get_schema`/`list_bq_tables` handlers use schema.json |
| `rca_copilot_agent/config.py` | Update | Remove `BigQueryConfig` and `load_bq_config()` |
| `.env.example` | Update | Remove BQ_ section, add gcloud ADC note |
| `.env` | Update | Remove BQ_ lines |
| `.github/agents/rca_copilot.agent.md` | Update | Remove BQ env vars from frontmatter; update BQ usage guidelines |
| `rca_copilot_agent/AGENTS.md` | Update | Add key tables table, update schema source to schema.json |
