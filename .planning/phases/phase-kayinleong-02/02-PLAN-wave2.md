---
wave: 2
depends_on: [wave1]
files_modified:
  - mockdata_copilot_agent/tools/gcloud_tool.py
  - mockdata_copilot_agent/tools/bigquery_tool.py
autonomous: true
requirements:
  - phase-kayinleong-02
must_haves:
  - tools/gcloud_tool.py is a verbatim copy of ticketasg_copilot_agent/tools/gcloud_tool.py (exports ensure_gcloud_auth, set_project, set_quota_project)
  - tools/bigquery_tool.py is a verbatim copy of ticketasg_copilot_agent/tools/bigquery_tool.py (exports query_bigquery, init_from_schema, validate_query via SafeBigQueryExecutor; DANGEROUS_KEYWORDS blocklist intact)
  - bigquery_tool _SCHEMA_JSON resolves to the repo-root schema.json from the new package depth (parent.parent.parent)
  - DV routing works WITHOUT editing either file — BQ_PROJECT env default + _pick_executor select the DV executor when SQL references the fully-qualified DV table
  - both files import cleanly with sys.path including mockdata_copilot_agent/
---

<objective>
Copy the two genuinely-reused tool modules — `gcloud_tool.py` (GCP auth) and `bigquery_tool.py`
(read-only SELECT executor + safety blocklist) — into the new package VERBATIM. Encode and
verify that the DV project becomes the default purely via the `BQ_PROJECT` env default
(set from config at Wave 4 startup) and `_pick_executor`'s project routing — NO edits to either
shared file.

Purpose: Wave 3's `mockdata_tool.py` and Wave 4's `mcp_server.py` depend on these. The entire
BigQuery safety guarantee (SELECT-only, blocklist, dry-run, byte ceiling) comes for free by
copying `bigquery_tool.py` unchanged. The blocklist must not be weakened (CLAUDE.md).

Output: 2 files in `mockdata_copilot_agent/tools/`.

## Artifacts this wave produces
- New files: `mockdata_copilot_agent/tools/gcloud_tool.py` (verbatim),
  `mockdata_copilot_agent/tools/bigquery_tool.py` (verbatim)
- Reused functions made available: `ensure_gcloud_auth`, `set_project`, `set_quota_project`
  (gcloud), `init_from_schema`, `query_bigquery`, `validate_query`/`SafeBigQueryExecutor`,
  `_pick_executor`, `DANGEROUS_KEYWORDS` (bigquery)
- No new CLI flags, no config fields (DV default lives in Wave 1 config)

## Assumptions surfaced this wave
- [ASSUMPTION A3 — confirm with user]: DV `consumer_pii` "same schema as primary". This wave
  does not depend on column lists; it only proves the executor routes to DV. Full DV column
  acquisition is Wave 3.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/CLAUDE.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-RESEARCH.md

<interfaces>
<!-- Both files are COPY-VERBATIM. Public surface relied on by later waves: -->

From tools/gcloud_tool.py [VERIFIED ticketasg_copilot_agent/tools/gcloud_tool.py]:
```python
def ensure_gcloud_auth(required_domain: str = "loreal.com") -> None: ...
def set_project(project_id: str | None = None) -> None:
    # reads os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")
def set_quota_project(project_id: str | None = None) -> None:
    # reads os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")
```

From tools/bigquery_tool.py [VERIFIED ticketasg_copilot_agent/tools/bigquery_tool.py]:
```python
_SCHEMA_JSON = Path(__file__).resolve().parent.parent.parent / "schema.json"  # resolves to repo-root schema.json
DANGEROUS_KEYWORDS = {"INSERT","UPDATE","DELETE","DROP","CREATE","ALTER",
                      "TRUNCATE","MERGE","GRANT","REVOKE","EXECUTE","CALL","EXPORT","LOAD"}
def init_from_schema() -> None: ...          # adds one executor per project in additional_datasets (DV is among them)
def _pick_executor(sql: str) -> SafeBigQueryExecutor: ...  # routes by first backtick-quoted project ref
def query_bigquery(sql: str, rationale: str = "") -> str: ...  # validate_query then bq CLI; SELECT-only
class SafeBigQueryExecutor:
    def validate_query(self, sql: str) -> tuple[bool, Optional[str]]: ...
```

DV-routing contract [from 02-RESEARCH Q1 lines 171-176]: do NOT hardcode the DV project in
either file. Wave 4 startup runs `os.environ.setdefault("BQ_PROJECT", cfg.bq_project)` before
auth, so `set_project()`/`set_quota_project()` pick up DV. `init_from_schema()` already creates
an executor for every project in schema.json `additional_datasets` (all of which begin
`oa-apmena-spacecds-ap-dv.`), and `_pick_executor` selects it whenever the SQL references the
fully-qualified `` `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.<table>` ``.
The Wave-3 lookup SQL MUST use that fully-qualified ref so DV billing is selected.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Copy gcloud_tool.py and bigquery_tool.py verbatim</name>
  <files>
    mockdata_copilot_agent/tools/gcloud_tool.py
    mockdata_copilot_agent/tools/bigquery_tool.py
  </files>
  <read_first>
    ticketasg_copilot_agent/tools/gcloud_tool.py — copy truly verbatim (no string references to RCA/SNOW)
    ticketasg_copilot_agent/tools/bigquery_tool.py — copy truly verbatim; _SCHEMA_JSON path depth is identical (3 parents from package/tools/)
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 142-144 — verbatim-copy disposition + _SCHEMA_JSON path math
  </read_first>
  <action>
Copy both files byte-for-byte from the ticketasg analog into `mockdata_copilot_agent/tools/`:

1. `gcloud_tool.py` — copy truly verbatim. No strings reference RCA or ServiceNow — no changes
   at all. `set_project()`/`set_quota_project()` keep reading
   `os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")`; do NOT change the PD literal here
   — the DV default is supplied at startup via the env var set from config (Wave 4). Hardcoding
   DV in this file would violate the CLAUDE.md "no project outside config.py" rule.

2. `bigquery_tool.py` — copy truly verbatim. The `_SCHEMA_JSON` line is:
   ```python
   _SCHEMA_JSON = Path(__file__).resolve().parent.parent.parent / "schema.json"
   ```
   From `mockdata_copilot_agent/tools/bigquery_tool.py` this resolves to the repo-root
   `schema.json` (same 3-level depth as the analog). Do NOT change this line. Do NOT touch
   `DANGEROUS_KEYWORDS`, `validate_query`, `init_from_schema`, `_pick_executor`, or
   `query_bigquery` — the blocklist must stay intact (CLAUDE.md "BigQuery Safety").

For both files: `from config import load_config` or any config import (if present in the
analog) will resolve against `sys.path` — Wave 4 startup inserts `mockdata_copilot_agent/` at
the front of `sys.path`, so they bind to the local package. Do not rewrite imports.

Copy, do NOT symlink (phase-01 precedent — keep packages independent).
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import sys; sys.path.insert(0,'mockdata_copilot_agent')
from tools.gcloud_tool import ensure_gcloud_auth, set_project, set_quota_project
from tools.bigquery_tool import DANGEROUS_KEYWORDS, _pick_executor, init_from_schema, query_bigquery, SafeBigQueryExecutor, _SCHEMA_JSON
req = {'INSERT','UPDATE','DELETE','DROP','CREATE','ALTER','TRUNCATE','MERGE','GRANT','REVOKE','EXECUTE','CALL','EXPORT','LOAD'}
assert req.issubset(set(DANGEROUS_KEYWORDS)), 'blocklist weakened'
assert _SCHEMA_JSON.name == 'schema.json'
print('imports OK; blocklist intact; schema path:', _SCHEMA_JSON)
"</automated>
  </verify>
  <done>
    Both files exist in `mockdata_copilot_agent/tools/`. Imports of `ensure_gcloud_auth`,
    `query_bigquery`, `init_from_schema`, `SafeBigQueryExecutor`, `_pick_executor`, and
    `DANGEROUS_KEYWORDS` succeed. The blocklist contains all 14 dangerous keywords (not
    weakened). `_SCHEMA_JSON` resolves to a path whose filename is `schema.json`. `diff
    mockdata_copilot_agent/tools/bigquery_tool.py ticketasg_copilot_agent/tools/bigquery_tool.py`
    returns no differences.
  </done>
</task>

<task type="auto">
  <name>Task 2: Verify blocklist + DV routing without editing the shared files</name>
  <files></files>
  <read_first>
    mockdata_copilot_agent/tools/bigquery_tool.py — confirm validate_query strips quoted literals before keyword scan
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 186-199 — exact existence-check query + blocklist confirmation (Q3)
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 358-365 — _pick_executor DV routing (Pattern 2)
  </read_first>
  <action>
This task makes NO file changes. It proves two safety properties that later waves depend on,
without weakening or bypassing anything:

1. The read-only existence-check SELECT passes the blocklist:
   ```sql
   SELECT consumerkey, lucid, signature, isocountry, status
   FROM `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`
   WHERE lucid = 'C2ID00000000010' AND status = 'Active'
   LIMIT 5
   ```
   `SafeBigQueryExecutor.validate_query(sql)` must return `(True, None)`.

2. An INSERT against the same table is REJECTED by `validate_query` (returns `(False, <msg>)`)
   — proving generated INSERTs would be blocked if ever (incorrectly) routed through the tool.
   Generated INSERTs are NEVER sent through `query_bigquery`; they go to the report file only
   (Wave 4).

Run the verification command below. If `validate_query` is unavailable because
`init_from_schema()` has not populated executors (no ADC), construct a `SafeBigQueryExecutor`
directly with a dummy project to exercise `validate_query` in isolation — the blocklist logic
is independent of ADC. Do NOT modify `bigquery_tool.py` to make this pass.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import sys; sys.path.insert(0,'mockdata_copilot_agent')
from tools.bigquery_tool import SafeBigQueryExecutor
ex = SafeBigQueryExecutor(project='oa-apmena-spacecds-ap-dv')
sel = '''SELECT consumerkey, lucid, signature, isocountry, status
FROM \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii\`
WHERE lucid = 'C2ID00000000010' AND status = 'Active' LIMIT 5'''
ok, err = ex.validate_query(sel)
assert ok is True and err is None, f'SELECT should pass: {err}'
ins = \"INSERT INTO \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii\` (lucid) VALUES ('x')\"
bad_ok, bad_err = ex.validate_query(ins)
assert bad_ok is False, 'INSERT must be blocked'
print('SELECT passes, INSERT blocked:', bad_err)
"</automated>
  </verify>
  <done>
    `validate_query` returns `(True, None)` for the DV `consumer_pii` existence SELECT and
    `(False, <message>)` for an INSERT against the same table. No edits were made to
    `bigquery_tool.py` or `gcloud_tool.py`. The verify command prints the blocked-INSERT
    message.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| generated SQL → query_bigquery | Generated INSERTs are Postgres-dialect AND blocklist-rejected; they must never be routed through the BQ tool — only the read-only existence SELECT goes through it |
| DV BigQuery dataset → bigquery_tool | Live read-only SELECT via ADC; IAM grants dataViewer + jobUser only |
| BQ_PROJECT env → set_project/set_quota_project | Project id sourced from config at startup; non-secret value |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave2-01 | Tampering | bigquery_tool.py blocklist | mitigate | Copied verbatim — DANGEROUS_KEYWORDS rejects INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/MERGE/GRANT/REVOKE/EXECUTE/CALL/EXPORT/LOAD before any execution; verified in Task 2 |
| T-wave2-02 | Denial of Service | bigquery_tool.py | mitigate | Copied verbatim — maximum_bytes_billed ceiling + row cap + dry-run already enforced |
| T-wave2-03 | Information Disclosure | gcloud_tool.py auth | mitigate | Copied verbatim — all gcloud stdout forwarded to stderr; gcloud ADC only, no credential files, no COOKIE/token logging |
| T-wave2-04 | Tampering | accidental write to BigQuery | mitigate | Generated INSERTs never routed through query_bigquery (Wave 4 writes them to the report file only); blocklist is the backstop |
</threat_model>

<verification>
From repo root:
1. `python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.gcloud_tool import ensure_gcloud_auth, set_project; from tools.bigquery_tool import query_bigquery, DANGEROUS_KEYWORDS, _pick_executor; print('OK')"` — exits 0
2. `diff mockdata_copilot_agent/tools/gcloud_tool.py ticketasg_copilot_agent/tools/gcloud_tool.py` — no output (identical)
3. `diff mockdata_copilot_agent/tools/bigquery_tool.py ticketasg_copilot_agent/tools/bigquery_tool.py` — no output (identical)
4. `python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.bigquery_tool import SafeBigQueryExecutor; ex=SafeBigQueryExecutor(project='oa-apmena-spacecds-ap-dv'); ok,_=ex.validate_query('SELECT 1 FROM \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii\` LIMIT 1'); assert ok; print('SELECT passes')"` — prints `SELECT passes`
</verification>

<success_criteria>
- `gcloud_tool.py` and `bigquery_tool.py` exist in `mockdata_copilot_agent/tools/` and are byte-identical to the ticketasg analogs
- The blocklist (`DANGEROUS_KEYWORDS`) is unchanged — all 14 keywords present
- The DV `consumer_pii` existence SELECT passes `validate_query`; an INSERT is rejected
- `_SCHEMA_JSON` resolves to the repo-root `schema.json` from the new package depth
- DV routing requires NO edits to either file — it is achieved via the `BQ_PROJECT` env default (config) + `_pick_executor`
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-02/phase-kayinleong-02-wave2-SUMMARY.md`
</output>
