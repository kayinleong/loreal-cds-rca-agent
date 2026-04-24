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
For each hypothesis, run targeted BQ queries:

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

## BigQuery Dataset

- Project: `oa-apmena-spacecds-ap-pd`
- Dataset: `space_cds_b2c_ds_replica_ae2_pd_public`
- Access: Read-only via service account
- Dialect: GoogleSQL (backtick table refs, SAFE_DIVIDE, UNNEST, etc.)

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
