---
status: complete
quick_id: quick-kayinleong-012
date: 2026-05-06
---

# Summary: quick-kayinleong-012

## What Changed

### schema.json
- Added `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ae2_dv_public` to `additional_datasets` as a B2C historical fallback with `fallback_for` field pointing to the primary dataset
- Updated top-level `note` to explicitly prohibit `recordstatus` filtering and require `status = 'Active'` for consumer queries
- Updated all 7 `recordstatus` column descriptions to "Internal CDC replication field — do not use in queries"
- Added `AND status = 'Active'` to `consumer_by_email` and `consumer_by_lucid` common RCA patterns

### rca_copilot_agent/AGENTS.md
- Added B2C AE2 DV replica row to Additional Datasets table
- Added "Query Rules (mandatory)" section with three rules: no recordstatus, status=Active for consumers, replica fallback when primary returns 0 rows
- Updated Phase 3 VALIDATE dataset reference list to include AE2 DV replica

### rca_agent/AGENTS.md
- Expanded "BigQuery Dataset" section to list all four non-primary datasets
- Added "Query Rules (mandatory)" section with same three rules
- Updated Phase 3 VALIDATE intro to state the query constraints

## Verification

- `python3 -c "import json; json.load(open('schema.json')); print('JSON valid')"` → JSON valid
- consumer_by_email pattern confirmed: includes `AND status = 'Active'`
- consumer_by_lucid pattern confirmed: includes `AND status = 'Active'`
- `additional_datasets` now has 4 entries including B2C AE2 DV replica
- All 7 recordstatus descriptions updated (consumer_pii, purchase, purchase_item, consumer_behaviour, shipment, + 2 in ase1_dv_public dataset)
- No existing query patterns used recordstatus — regression surface is nil

## Regression Report

**Tested:** JSON validity, schema structure inspection via Python  
**Passed:** All three schema mutation points verified programmatically  
**Ruled out:** No Python tool code was changed — bigquery_tool.py reads schema.json generically; the new additional_datasets entry is picked up automatically by `get_schema_from_file()` and `init_from_schema()`. No risk of breaking BQ executor routing.
