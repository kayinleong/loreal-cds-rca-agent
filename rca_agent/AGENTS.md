# AGENTS.md — RCA Investigation Schema

> This is the "schema file" in Karpathy's LLM Wiki pattern.
> It tells the agent how to structure its investigation, what workflows
> to follow, and how to compile findings into the wiki.

## Purpose

This agent investigates ServiceNow incidents for L'Oréal's SPACE CDS
(Consumer Data Services) platform. It validates root causes by querying
BigQuery production data replicas and produces structured RCA reports.

## Wiki Structure

```
wiki/
├── wiki_state.json    ← Persisted investigation state (auto-managed)
│
├── Pages (in-memory, keyed by category):
│   ├── timeline       ← Chronological events from incident
│   ├── evidence       ← Validated data points from BQ/SNOW
│   ├── hypothesis     ← Theories being tested
│   ├── conclusion     ← Confirmed findings
│   └── action_item    ← Remediation steps needed
│
└── log                ← Append-only operation log
```

## Investigation Workflow

### Phase 1: INGEST
- Load incident data (description, comments, work notes, attachments)
- Extract identifiers: order IDs, user IDs, EAN codes, MARS IDs, emails
- Record timeline entries from incident chronology
- Note what the team has already tried (from work notes)

### Phase 2: DISCOVER
- List available BigQuery tables in the dataset
- Get schemas for relevant tables (orders, users, products, etc.)
- Map incident identifiers to table columns

### Phase 3: VALIDATE
For each hypothesis, run targeted BQ queries. Enforce these constraints on every query:
- Do NOT use `recordstatus` in WHERE clauses
- Add `AND status = 'Active'` to all `consumer_pii` queries
- If a B2C query returns 0 rows from primary, retry against the AE2 DV replica

| Check Type | Query Pattern |
|-----------|---------------|
| Existence | `SELECT EXISTS(SELECT 1 FROM t WHERE id = @id)` |
| Count | `SELECT COUNT(*) FROM t WHERE condition` |
| Field check | `SELECT field FROM t WHERE id = @id LIMIT 1` |
| Null audit | `SELECT COUNTIF(field IS NULL) FROM t WHERE ...` |
| Date range | `SELECT MIN(ts), MAX(ts) FROM t WHERE ...` |
| Comparison | `SELECT a.f, b.f FROM a JOIN b ON ... WHERE a.f != b.f LIMIT 10` |

### Phase 4: CONCLUDE
- Review all wiki findings (read_wiki → "all")
- Produce the four-section RCA report
- Record action items with owners and deadlines

## Common CDS Root Causes

1. **Missing MARSID** → User profile has no MARS ID, orders can't be matched
2. **EAN mismatch** → V14/V21 migration left orphan EAN codes  
3. **Pipeline delay** → Data not yet replicated to BigQuery (check timestamps)
4. **CBR mapping gap** → Product not in mars_V21_mapping_product table
5. **Profile merge issue** → Duplicate profiles with different loyalty IDs
6. **Region config** → Country/brand code mismatch in routing tables

## BigQuery Datasets

### Primary — B2C Production
- **Project:** `oa-apmena-spacecds-ap-pd`
- **Dataset:** `space_cds_b2c_ds_replica_ae2_pd_public`
- **Access:** Read-only via gcloud ADC
- **Dialect:** GoogleSQL (backtick table refs, SAFE_DIVIDE, UNNEST, etc.)

### Additional — DV Replicas & B2B (`oa-apmena-spacecds-ap-dv`)
| Dataset | Use When |
|---------|----------|
| `space_cds_b2c_ds_replica_ae2_dv_public` | **Historical fallback for B2C** — same schema as primary; query when primary returns 0 rows |
| `space_cds_b2c_ds_replica_ase1_dv_public` | B2C ASE1 / SEA pipeline debug |
| `space_cds_b2b_ds_replica_ae2_dv_cds_tgt` | B2B incidents in Middle East |
| `space_cds_b2b_ds_replica_ase1_dv_cds_tgt` | B2B incidents in Southeast Asia |

### Query Rules (mandatory)
1. **Never filter by `recordstatus`** — it is an internal CDC replication field; ignore in all queries.
2. **Always filter consumers by `status = 'Active'`** — add `AND status = 'Active'` to all `consumer_pii` queries.
3. **Use replica as historical fallback** — if primary B2C query returns 0 rows, retry with `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ae2_dv_public` (same table/column names).

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
{conclusion from checks, one or two sentences with evidence}

## WHAT WE NEED / DID
{action items with owners and deadlines}
```
