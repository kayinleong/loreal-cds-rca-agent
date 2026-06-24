---
wave: 3
depends_on: [wave2]
files_modified:
  - mockdata_copilot_agent/.docs/dv_columns.json
  - mockdata_copilot_agent/tools/mockdata_tool.py
autonomous: true
requirements:
  - phase-kayinleong-02
must_haves:
  - .docs/dv_columns.json exists — the pinned full DV column metadata (name, data_type, ordinal_position) for BOTH external_system_ids and consumer_pii, used to render type-correct GoogleSQL
  - mockdata_tool.py is a pure-function module (no LLM calls, no I/O except reading the committed columns reference) — exports generate_external_system_ids, generate_consumer_pii, build_lookup_sql
  - generate_external_system_ids(seed, vary, count) returns N rows; every extsystemidskey is unique; varied columns differ across rows; non-varied columns equal the seed
  - generated external_system_ids SQL is valid BigQuery GoogleSQL — fully-qualified backtick table ref, STRING literals single-quoted, TIMESTAMP columns rendered as TIMESTAMP 'YYYY-MM-DD HH:MM:SS+00', numeric columns unquoted, bare NULL for empty cells, NO Postgres ::uuid/::timestamptz casts, MOCK_DATA/MANUAL markers preserved
  - generate_consumer_pii produces synthetic obviously-fake PII (mock+<id>@example.com, fake names) with MOCK_DATA markers across the full DV column list
  - build_lookup_sql(lucid, ...) returns the fully-qualified DV consumer_pii existence SELECT (GoogleSQL) that passes the blocklist
---

<objective>
Build the single net-new domain module — `mockdata_tool.py`, a pure-function seed→N-row
generator — and pin the full DV column metadata (`.docs/dv_columns.json`) for BOTH
`external_system_ids` and `consumer_pii`, acquired once via a live `INFORMATION_SCHEMA.COLUMNS`
query. The module emits **BigQuery GoogleSQL** INSERT text (the confirmed A1 dialect) and builds
the read-only existence-lookup SELECT (executed later in Wave 4).

Purpose: This is where the worked example ("vary signature and sourceconsumerid, N rows")
becomes deterministic SQL. The module has NO LLM and NO side effects beyond reading the
committed columns reference — the LLM (Copilot/Claude) decides WHICH columns to vary and HOW
MANY rows; the tool only transforms. Generated SQL targets the BigQuery DV dataset directly, so
value rendering MUST be driven by each column's real BigQuery type (STRING vs INT64 vs TIMESTAMP),
not by name heuristics — hence the column-metadata fetch for both tables.

Output: 2 files — `mockdata_copilot_agent/.docs/dv_columns.json` (committed reference) and
`mockdata_copilot_agent/tools/mockdata_tool.py` (pure functions).

## Artifacts this wave produces
- New files: `mockdata_copilot_agent/.docs/dv_columns.json`,
  `mockdata_copilot_agent/tools/mockdata_tool.py`
- New functions:
  - `generate_external_system_ids(seed: dict, vary: dict, count: int) -> dict`
  - `generate_consumer_pii(consumers: list, ...) -> dict`
  - `build_lookup_sql(lucid: str, consumerkey: str | None = None, signature: str | None = None, isocountry: str | None = None) -> str`
  - `load_column_types(table: str) -> dict` (reads `.docs/dv_columns.json`; returns {column_name: data_type})
  - `parse_seed_xlsx(path: str) -> dict` (optional convenience — paste-JSON is primary)
- Pinned constants: `EXTERNAL_SYSTEM_IDS_COLUMNS` (the 21 columns, ordinal order), `_DV_PROJECT`,
  `_DV_DATASET`

## Confirmed decisions this wave (locked by user 2026-06-24)
- [A1 — SQL dialect: GoogleSQL — CONFIRMED]: Generated SQL is **BigQuery GoogleSQL** targeting the
  DV dataset `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public`. Fully-qualified
  backtick table refs; STRING literals single-quoted; TIMESTAMP columns as `TIMESTAMP '…+00'`;
  INT64/NUMERIC/FLOAT64 columns unquoted; BOOL as `true`/`false`; bare `NULL` for empty cells.
  NO Postgres `::uuid`/`::timestamptz` casts (the `.docs` sample is Postgres and is the column/
  value reference ONLY, not the dialect). The agent still NEVER executes these INSERTs — it
  presents them for the user to run against BigQuery.
- [A2 / A3 — full DV column metadata: live fetch — CONFIRMED]: The full column set + types for
  BOTH tables is acquired live once via `INFORMATION_SCHEMA.COLUMNS` (Task 1) and committed.
  schema.json's curated columns are a fallback STARTING POINT only.
- [A4 — existence key: lucid — CONFIRMED]: existence lookup keys on `lucid` (+ optional
  `consumerkey`/`signature`/`isocountry` disambiguators, since lucid is not unique across brands).
- [A5 — UUID family]: keep the synthetic UUID family (`1b48bdbb-bdbb-7b6f-GGGG-NNNNNNNNNNNN` /
  `6d74baaa-baaa-7a19-899c-NNNNNNNNNNNN`); the trailing 12-digit counter is the uniqueness
  mechanism for `extsystemidskey`.
- [A8]: `MOCK_DATA` / `MANUAL` provenance markers are preserved verbatim in every generated row.
- [A9]: synthetic `consumer_pii` PII is obviously fake (`mock+<id>@example.com`, fake names).
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/CLAUDE.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-RESEARCH.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/mockdata_copilot_agent/.docs/external_system_ids mock up.sql

<interfaces>
<!-- mockdata_tool.py — pure functions. NO LLM, NO I/O except reading the committed columns ref. -->

The 21 external_system_ids columns (ordinal order; xlsx header == .docs INSERT column list)
[VERIFIED in 02-RESEARCH lines 231-232]:
  extsystemidskey, consumerkey, isocountry, signature, lucid, sourcesystemid, sourceconsumerid,
  creationlocationid, locationid, creationsalesrepid, salesrepid, createddatetime, status,
  lastlogindatetime, createdsourcesystemid, lastupdatedsourcesystemid, syscreateddatetime,
  sysupdatedatetime, recordstatus, country_iso_3166_1, consumersourcekey

Worked-example seed (xlsx Sheet1 row 1) [VERIFIED]:
  extsystemidskey='1b48bdbb-bdbb-7b6f-0003-000000000033', consumerkey='6d74baaa-baaa-7a19-899c-000000000032',
  isocountry='ID', signature=1(int), lucid='C2ID00000000010', sourcesystemid='MARS_ID',
  sourceconsumerid='ID011000000001C', creationlocationid='ID0160', locationid=None->NULL,
  creationsalesrepid='IDPGE450000', salesrepid=0(int), createddatetime='1900-01-01T00:00:00Z',
  status='Close', lastlogindatetime=None->NULL, createdsourcesystemid='MOCK_DATA',
  lastupdatedsourcesystemid='MANUAL', syscreateddatetime='2026-06-19T00:00:00Z',
  sysupdatedatetime='2026-06-23T09:48:27.302993Z', recordstatus=0(int),
  country_iso_3166_1=360(int), consumersourcekey=526979(int)

GoogleSQL rendering rules (type-driven — type comes from .docs/dv_columns.json per column):
  - Table ref: `` INSERT INTO `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.<table>` ``
  - STRING / BYTES column: single-quoted literal `'value'` (escape embedded single quotes by
    doubling: `''`). UUID-looking values (extsystemidskey, consumerkey) are STRING in BigQuery —
    NO `::uuid` cast.
  - TIMESTAMP column: normalize ISO-Z input (`2026-06-19T00:00:00Z`, drop sub-second beyond micros
    is OK to keep) to `YYYY-MM-DD HH:MM:SS[.ffffff]+00`, render as `TIMESTAMP '<norm>'`.
  - DATE column: `DATE 'YYYY-MM-DD'`. DATETIME column: `DATETIME '<norm-no-offset>'`.
  - INT64 / INTEGER / NUMERIC / BIGNUMERIC / FLOAT64 column: unquoted numeric form (e.g. `0`,
    `360`, `526979`). If the type says numeric but the seed value is a string of digits, emit the
    bare number.
  - BOOL column: `true` / `false`.
  - None / empty string: bare `NULL` (no quotes, no cast) regardless of type.
  - Unknown/missing type metadata for a column: default to single-quoted STRING and emit a
    `-- [A2/A3] unknown type for <col>` comment once (degraded mode only).

Function signatures:
```python
def load_column_types(table: str) -> dict:
    """Pure read of .docs/dv_columns.json. Returns {column_name: DATA_TYPE_UPPER}. Empty dict if
    the file/table entry is missing (callers degrade to STRING). NO live query."""

def generate_external_system_ids(seed: dict, vary: dict, count: int,
                                 column_types: dict | None = None) -> dict:
    """Pure. Returns {"sql": str, "rows": list[dict], "lucids": list[str], "consumerkeys": list[str]}.
    `vary` maps column_name -> value-list or strategy. extsystemidskey is ALWAYS varied (trailing
    12-digit counter ++) regardless of `vary`, to keep the PK unique. `column_types` defaults to
    load_column_types('external_system_ids'); tests may inject an explicit map. NO LLM, NO I/O
    beyond the columns ref."""

def generate_consumer_pii(consumers: list[dict], column_types: dict | None = None) -> dict:
    """Pure. `consumers` = list of {"lucid","consumerkey","signature","isocountry", ...} found
    ABSENT. Returns {"sql": str, "rows": list[dict]}. Synthetic fake PII only
    (mock+<id>@example.com, fake names, MOCK_DATA markers) across the committed DV column list.
    `column_types` defaults to load_column_types('consumer_pii')."""

def build_lookup_sql(lucid: str, consumerkey: str | None = None,
                     signature: str | None = None, isocountry: str | None = None) -> str:
    """Pure. Returns the fully-qualified DV consumer_pii existence SELECT (GoogleSQL, passes the
    blocklist). Uses `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`
    so _pick_executor selects the DV executor. Single-quotes all literal values."""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Acquire and commit full DV column metadata for both tables</name>
  <files>
    mockdata_copilot_agent/.docs/dv_columns.json
  </files>
  <read_first>
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 201-215 — full schema acquisition options (Q4)
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 452-457 — bq show --schema command
    mockdata_copilot_agent/tools/bigquery_tool.py — query_bigquery / init_from_schema available for the INFORMATION_SCHEMA fetch
  </read_first>
  <action>
Acquire the authoritative full DV column metadata for BOTH `external_system_ids` and
`consumer_pii` ONCE and commit it as a `.docs` reference. This is the only column/type source the
generators read — GoogleSQL rendering depends on real BigQuery types (STRING vs INT64 vs
TIMESTAMP), so the curated 8/19-column schema.json subsets are NOT sufficient on their own.

Preferred (needs ADC — the agent ensures L'Oréal GCP login): run the INFORMATION_SCHEMA query
through the reused read-only tool (it passes the blocklist):
```sql
SELECT table_name, column_name, data_type, ordinal_position
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('external_system_ids','consumer_pii')
ORDER BY table_name, ordinal_position
```
Run it directly (run_tool.py does not exist until Wave 4):
```bash
BQ_PROJECT=oa-apmena-spacecds-ap-dv python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.bigquery_tool import init_from_schema, query_bigquery; init_from_schema(); print(query_bigquery('SELECT table_name, column_name, data_type, ordinal_position FROM \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.INFORMATION_SCHEMA.COLUMNS\` WHERE table_name IN (\"external_system_ids\",\"consumer_pii\") ORDER BY table_name, ordinal_position'))"
```
or, equivalently, `bq show --schema --format=prettyjson oa-apmena-spacecds-ap-dv:space_cds_b2c_ds_replica_ase1_dv_public.external_system_ids` (and consumer_pii).

Write `mockdata_copilot_agent/.docs/dv_columns.json` as:
```json
{
  "source": "INFORMATION_SCHEMA.COLUMNS (oa-apmena-spacecds-ap-dv / space_cds_b2c_ds_replica_ase1_dv_public)",
  "acquired": "<YYYY-MM-DD>",
  "confirmed": true,
  "tables": {
    "external_system_ids": [
      {"name": "extsystemidskey", "data_type": "STRING", "ordinal_position": 1}
    ],
    "consumer_pii": [
      {"name": "consumerkey", "data_type": "STRING", "ordinal_position": 1}
    ]
  }
}
```
preserving ordinal order per table.

ADC-UNAVAILABLE FALLBACK (degrade, do NOT block): if neither ADC nor `bq show` works, write the
file with `"confirmed": false` and a `"note": "[A2/A3] Live DV fetch unavailable; types inferred
from schema.json + .docs sample. Re-run INFORMATION_SCHEMA with ADC before production."`, using:
  - external_system_ids (21 cols, inferred types): STRING for all *key/*id/code/marker/status
    columns (extsystemidskey, consumerkey, isocountry, signature, lucid, sourcesystemid,
    sourceconsumerid, creationlocationid, locationid, creationsalesrepid, salesrepid, status,
    createdsourcesystemid, lastupdatedsourcesystemid, country_iso_3166_1, consumersourcekey);
    TIMESTAMP for createddatetime, lastlogindatetime, syscreateddatetime, sysupdatedatetime;
    INT64 for recordstatus. (These are best-guess; the `confirmed:false` flag makes the wave5
    checkpoint surface them.)
  - consumer_pii (19 PD cols per 02-RESEARCH line 215): consumerkey, isocountry, signature, lucid,
    status, consumertype, gender, firstname, lastname, birthyear, birthmonth, birthday, mobile,
    phone, email = STRING; sourcecreationdatetime, registrationdatetime, withdrawaldatetime =
    TIMESTAMP; recordstatus = INT64.

Do NOT regenerate or stage the repo-root `schema.json` in this commit (CLAUDE.md: schema
regeneration is a separate deliberate action). Commit ONLY `dv_columns.json` alongside the Wave 3
code.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import json, pathlib
d = json.loads(pathlib.Path('mockdata_copilot_agent/.docs/dv_columns.json').read_text())
t = d['tables']
esi = t['external_system_ids']; cpi = t['consumer_pii']
assert len(esi) == 21, f'external_system_ids expected 21 cols, got {len(esi)}'
assert len(cpi) >= 19, f'consumer_pii expected >=19 cols, got {len(cpi)}'
esi_names = [c['name'] for c in esi]
for req in ('extsystemidskey','consumerkey','lucid','signature','sourceconsumerid','recordstatus'):
    assert req in esi_names, f'missing external_system_ids.{req}'
cpi_names = [c['name'] for c in cpi]
for req in ('consumerkey','lucid','email','firstname','lastname','signature','isocountry'):
    assert req in cpi_names, f'missing consumer_pii.{req}'
assert all('data_type' in c for c in esi+cpi), 'every column needs data_type'
print('confirmed:', d.get('confirmed'), '| esi cols:', len(esi), '| cpi cols:', len(cpi))
"</automated>
  </verify>
  <done>
    `.docs/dv_columns.json` exists with `tables.external_system_ids` (21 entries, ordinal order)
    and `tables.consumer_pii` (>=19 entries), each column having `name` + `data_type`. A
    `confirmed` flag records whether acquired live (`true`) or via fallback (`false`, with the
    `[A2/A3]` note). The repo-root `schema.json` is NOT staged in this commit.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create mockdata_tool.py (pure-function GoogleSQL generator + lookup builder)</name>
  <files>
    mockdata_copilot_agent/tools/mockdata_tool.py
  </files>
  <read_first>
    mockdata_copilot_agent/.docs/external_system_ids mock up.sql — column list + value conventions (MOCK_DATA/MANUAL, NULL, the synthetic UUID family). NOTE: this sample is Postgres dialect — use it for COLUMNS and VALUES, NOT for the cast syntax. The dialect is GoogleSQL (A1 confirmed).
    mockdata_copilot_agent/.docs/dv_columns.json — column order + BigQuery types for both tables
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 226-254 — mock-generation algorithm (Q6): seed parsing, UUID family, variation rules
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 186-199 — existence-lookup SELECT shape (Q3)
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 434-437 — Excel type coercion pitfall (Pitfall 6)
  </read_first>
  <behavior>
    - generate_external_system_ids(SEED, {}, 3) returns 3 rows; len(result["rows"]) == 3
    - every row's extsystemidskey is unique across the 3 rows (trailing 12-digit counter increments)
    - with vary={"signature": ["45","01","24"]}, the 3 rows have signature values "45","01","24" and all OTHER columns equal the seed
    - result["sql"] starts with "INSERT INTO `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.external_system_ids` ("
    - result["sql"] contains "MOCK_DATA" and "MANUAL" and contains NO "::uuid" and NO "::timestamptz" (GoogleSQL, not Postgres)
    - a TIMESTAMP-typed seed cell "2026-06-19T00:00:00Z" renders as "TIMESTAMP '2026-06-19 00:00:00+00'"
    - a seed cell that is None renders as bare "NULL" (no quotes, no cast) — e.g. locationid and lastlogindatetime
    - a STRING-typed UUID value renders single-quoted with NO cast: "'1b48bdbb-bdbb-7b6f-0003-000000000033'"
    - an INT64-typed column (recordstatus) renders unquoted: the SQL contains a bare integer for it, not "'0'"
    - generate_consumer_pii([{"lucid":"C2ID00000000099","consumerkey":"6d74baaa-baaa-7a19-899c-000000000099","signature":"45","isocountry":"ID"}]) returns sql containing "INSERT INTO `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`", a mock+...@example.com email, a "MOCK_DATA" marker, and NO real-looking PII
    - build_lookup_sql("C2ID00000000010") returns a string starting with "SELECT" containing the fully-qualified `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii` and "lucid = 'C2ID00000000010'"
    - build_lookup_sql output passes SafeBigQueryExecutor.validate_query (read-only, blocklist-clean)
  </behavior>
  <action>
Create `mockdata_copilot_agent/tools/mockdata_tool.py` — a PURE-function module. NO LLM calls.
NO I/O except reading the committed `.docs/dv_columns.json`. All diagnostics (if any) go to
stderr; functions RETURN strings, never `print()` to stdout (MCP-stdio safety, Pitfall 5).

Module docstring must state plainly: this module generates BigQuery GoogleSQL only; the agent
never executes writes; and record the confirmed decisions A1 (GoogleSQL / BigQuery DV — confirmed
2026-06-24), A2/A3 (column types from committed dv_columns.json, live-fetched), A4 (existence key
= lucid + optional disambiguators), A5 (UUID family), A8 (MOCK_DATA/MANUAL preserved), A9
(synthetic fake PII).

Define `EXTERNAL_SYSTEM_IDS_COLUMNS` as the 21-column tuple in ordinal order (from the interfaces
block). Define `_DV_PROJECT = "oa-apmena-spacecds-ap-dv"` and
`_DV_DATASET = "space_cds_b2c_ds_replica_ase1_dv_public"` and a helper
`_table_ref(table) -> f"`{_DV_PROJECT}.{_DV_DATASET}.{table}`"`. These project/dataset literals are
SQL identifiers in the generated/lookup text, not a Python config of the BQ client, so this does
not violate the "no hardcoded project outside config.py" rule for the executor; the executor's
billing project still comes from Wave 1 config via BQ_PROJECT. (Optional: accept project/dataset
as kwargs defaulting to these constants.)

Implement `load_column_types(table)`:
  - Read `.docs/dv_columns.json` (path resolved relative to this module's package, robust to CWD).
  - Return `{column_name: DATA_TYPE.upper()}` for the requested table; `{}` if missing.

Implement type-driven `_render_value(value, data_type)`:
  - None or "" -> bare `NULL`
  - data_type in {STRING, BYTES, "" (unknown)} -> single-quoted, doubling embedded `'`
  - data_type in {TIMESTAMP} -> normalize ISO-Z (`...T...Z`) to `YYYY-MM-DD HH:MM:SS[.ffffff]+00`,
    render `TIMESTAMP '<norm>'`
  - data_type in {DATE} -> `DATE '<YYYY-MM-DD>'`; {DATETIME} -> `DATETIME '<norm without +00>'`
  - data_type in {INT64, INTEGER, NUMERIC, BIGNUMERIC, FLOAT64, FLOAT} -> str(value) unquoted
    (strip surrounding quotes if the seed gave a numeric string)
  - data_type in {BOOL, BOOLEAN} -> `true`/`false`

Implement `generate_external_system_ids(seed, vary, count, column_types=None)`:
  - `column_types = column_types or load_column_types("external_system_ids")`.
  - For each of `count` rows: deep-copy the seed dict.
  - ALWAYS vary `extsystemidskey`: parse its `GGGG-NNNNNNNNNNNN` tail and increment the trailing
    12-digit counter per row so each PK is unique (A5).
  - For each column in `vary`: list -> cycle by row index; scalar/strategy string -> deterministic
    increment (e.g. `sourceconsumerid` suffix `...001C`->`...001D`; `signature` cycle). Document
    each strategy inline.
  - Columns not in `vary` (and not extsystemidskey) are copied verbatim from the seed.
  - Render each row via `_render_value(value, column_types.get(col, ""))` in
    EXTERNAL_SYSTEM_IDS_COLUMNS order; build
    `INSERT INTO `<ref>` (\n  col,\n  ...\n) VALUES\n  (row1),\n  (row2);` matching the .docs
    layout but with the GoogleSQL backtick table ref and GoogleSQL literals.
  - Return `{"sql": ..., "rows": [<dict per row>], "lucids": [...distinct lucid...],
    "consumerkeys": [...distinct consumerkey...]}`.

Implement `generate_consumer_pii(consumers, column_types=None)`:
  - `column_types = column_types or load_column_types("consumer_pii")`; column order from the same
    dv_columns.json entry.
  - For each absent consumer, build a row: copy known keys (lucid, consumerkey, signature,
    isocountry); set provenance/marker columns to `MOCK_DATA`/`MANUAL` where such columns exist;
    fill name/email with OBVIOUSLY FAKE values: `firstname='Mock'`, `lastname='Tester'`,
    `email='mock+' + <lucid-or-counter> + '@example.com'`, fake phone/mobile constants. NEVER emit
    real-looking PII (A9).
  - Render via `_render_value` by type; build `INSERT INTO `<consumer_pii ref>` (...) VALUES (...);`.
  - Return `{"sql": ..., "rows": [...]}`.

Implement `build_lookup_sql(lucid, consumerkey=None, signature=None, isocountry=None)`:
  - Return the read-only SELECT keyed on `lucid` with optional AND clauses for provided
    disambiguators (A4), against the fully-qualified consumer_pii ref, `LIMIT 5`. Single-quote all
    literals. Must pass `SafeBigQueryExecutor.validate_query`.

(Optional) Implement `parse_seed_xlsx(path)` using openpyxl: header row 0 = column names, row 1 =
seed values. Guard the openpyxl import; paste-JSON is the primary input (A7).
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import sys; sys.path.insert(0,'mockdata_copilot_agent')
from tools.mockdata_tool import generate_external_system_ids, generate_consumer_pii, build_lookup_sql, EXTERNAL_SYSTEM_IDS_COLUMNS
from tools.bigquery_tool import SafeBigQueryExecutor
assert len(EXTERNAL_SYSTEM_IDS_COLUMNS) == 21

# Inject an explicit type map so the unit test is deterministic regardless of live fetch.
ESI_TYPES = {c:'STRING' for c in EXTERNAL_SYSTEM_IDS_COLUMNS}
ESI_TYPES.update({'createddatetime':'TIMESTAMP','lastlogindatetime':'TIMESTAMP','syscreateddatetime':'TIMESTAMP','sysupdatedatetime':'TIMESTAMP','recordstatus':'INT64'})

SEED = {
 'extsystemidskey':'1b48bdbb-bdbb-7b6f-0003-000000000033','consumerkey':'6d74baaa-baaa-7a19-899c-000000000032',
 'isocountry':'ID','signature':1,'lucid':'C2ID00000000010','sourcesystemid':'MARS_ID',
 'sourceconsumerid':'ID011000000001C','creationlocationid':'ID0160','locationid':None,
 'creationsalesrepid':'IDPGE450000','salesrepid':0,'createddatetime':'1900-01-01T00:00:00Z',
 'status':'Close','lastlogindatetime':None,'createdsourcesystemid':'MOCK_DATA',
 'lastupdatedsourcesystemid':'MANUAL','syscreateddatetime':'2026-06-19T00:00:00Z',
 'sysupdatedatetime':'2026-06-23T09:48:27.302993Z','recordstatus':0,'country_iso_3166_1':360,
 'consumersourcekey':526979}

r = generate_external_system_ids(SEED, {'signature':['45','01','24']}, 3, column_types=ESI_TYPES)
assert len(r['rows']) == 3
keys = [row['extsystemidskey'] for row in r['rows']]
assert len(set(keys)) == 3, f'extsystemidskey not unique: {keys}'
assert [row['signature'] for row in r['rows']] == ['45','01','24']
assert all(row['sourcesystemid'] == 'MARS_ID' for row in r['rows'])
sql = r['sql']
assert sql.startswith(\"INSERT INTO \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.external_system_ids\` (\"), sql[:120]
assert '::uuid' not in sql and '::timestamptz' not in sql, 'must be GoogleSQL, not Postgres'
for token in ('MOCK_DATA','MANUAL'):
    assert token in sql, token
assert \"TIMESTAMP '2026-06-19 00:00:00+00'\" in sql, 'TIMESTAMP literal not rendered'
assert 'NULL' in sql, 'None cells must render NULL'
assert \"'1b48bdbb-bdbb-7b6f\" in sql, 'STRING uuid must be single-quoted, no cast'

cp = generate_consumer_pii([{'lucid':'C2ID00000000099','consumerkey':'6d74baaa-baaa-7a19-899c-000000000099','signature':'45','isocountry':'ID'}])
assert \"INSERT INTO \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii\`\" in cp['sql']
assert 'mock+' in cp['sql'] and '@example.com' in cp['sql'] and 'MOCK_DATA' in cp['sql']

lk = build_lookup_sql('C2ID00000000010')
assert lk.strip().upper().startswith('SELECT')
assert 'oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii' in lk
assert \"lucid = 'C2ID00000000010'\" in lk
ok, err = SafeBigQueryExecutor(project='oa-apmena-spacecds-ap-dv').validate_query(lk)
assert ok is True, f'lookup SQL must pass blocklist: {err}'
print('ALL mockdata_tool GoogleSQL tests PASS')
"</automated>
  </verify>
  <done>
    `mockdata_tool.py` exists and is pure (no LLM, no stdout prints). All inline assertions pass:
    3 rows with unique `extsystemidskey`; `signature` varied to `['45','01','24']` with other
    columns equal to seed; SQL starts with the fully-qualified backtick `external_system_ids` ref;
    contains `MOCK_DATA`/`MANUAL`; contains NO `::uuid`/`::timestamptz` (GoogleSQL); TIMESTAMP
    columns render as `TIMESTAMP '…+00'`; None cells render bare `NULL`; STRING uuids single-quoted
    without a cast; INT64 columns unquoted. `generate_consumer_pii` emits a synthetic
    `mock+...@example.com` row with `MOCK_DATA`. `build_lookup_sql` returns a fully-qualified DV
    `consumer_pii` SELECT that passes `validate_query`.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| seed/vary input → mockdata_tool | Untrusted seed values are rendered into SQL text that is PRESENTED, never executed by the agent — no injection surface against a live DB from this agent |
| lookup SQL → query_bigquery (Wave 4) | The only generated SQL that touches a live DB is the read-only existence SELECT; it is blocklist-clean by construction |
| .docs/dv_columns.json → generators | Column list + types read from a committed reference; controls which columns appear and how each value is rendered (STRING quote vs numeric) |
| synthetic PII → report file (Wave 4) | Generated consumer_pii rows must contain obviously-fake PII only |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave3-01 | Information Disclosure | generate_consumer_pii synthetic PII | mitigate | Hardcoded obviously-fake values (`mock+<id>@example.com`, `Mock`/`Tester`, MOCK_DATA markers); never derives values from real consumer records |
| T-wave3-02 | Tampering | generated INSERT SQL | mitigate | SQL is returned as text for the report file only; never routed through query_bigquery; blocklist is the backstop if it ever were |
| T-wave3-03 | Tampering | build_lookup_sql | mitigate | Read-only SELECT; all literals single-quoted; no bare blocklist words; verified to pass validate_query |
| T-wave3-04 | Information Disclosure | INFORMATION_SCHEMA fetch (Task 1) | mitigate | Read-only metadata query via the blocklisted executor; commits column NAMES + types only, no row data |
</threat_model>

<verification>
From repo root:
1. `python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.mockdata_tool import generate_external_system_ids, generate_consumer_pii, build_lookup_sql, EXTERNAL_SYSTEM_IDS_COLUMNS; assert len(EXTERNAL_SYSTEM_IDS_COLUMNS)==21; print('OK')"` — exits 0
2. `python -c "import json,pathlib; d=json.loads(pathlib.Path('mockdata_copilot_agent/.docs/dv_columns.json').read_text()); assert len(d['tables']['external_system_ids'])==21 and len(d['tables']['consumer_pii'])>=19; print('confirmed=',d.get('confirmed'))"` — prints confirmed flag
3. `python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.mockdata_tool import generate_external_system_ids as g; s=g({'extsystemidskey':'1b48bdbb-bdbb-7b6f-0003-000000000033','createddatetime':'1900-01-01T00:00:00Z'},{},1,column_types={'extsystemidskey':'STRING','createddatetime':'TIMESTAMP'})['sql']; assert '::uuid' not in s and 'TIMESTAMP ' in s; print('GoogleSQL OK')"` — prints GoogleSQL OK
4. `grep -n "print(" mockdata_copilot_agent/tools/mockdata_tool.py` — returns empty or only stderr-targeted prints (no bare stdout prints)
</verification>

<success_criteria>
- `.docs/dv_columns.json` pins the full DV column metadata for BOTH tables (live-acquired or fallback flagged unconfirmed)
- `mockdata_tool.py` is pure: no LLM calls, no stdout prints, no I/O beyond reading the columns reference
- `generate_external_system_ids` produces N rows with unique `extsystemidskey`, varied named columns, seed-identical other columns
- Generated SQL is valid BigQuery GoogleSQL (backtick FQ table, type-driven literals, TIMESTAMP literals, NULL, MOCK_DATA/MANUAL; NO Postgres casts) [A1 confirmed]
- `generate_consumer_pii` emits obviously-synthetic PII across the full DV column list
- `build_lookup_sql` returns a fully-qualified DV `consumer_pii` SELECT (GoogleSQL) that passes the blocklist
- Confirmed decisions A1 (GoogleSQL), A2/A3 (live types), A4 (lucid) recorded in the module docstring
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-02/phase-kayinleong-02-wave3-SUMMARY.md`
</output>
