---
wave: 3
depends_on: [wave2]
files_modified:
  - mockdata_copilot_agent/.docs/consumer_pii.columns.json
  - mockdata_copilot_agent/tools/mockdata_tool.py
autonomous: true
requirements:
  - phase-kayinleong-02
must_haves:
  - .docs/consumer_pii.columns.json exists — the pinned full DV consumer_pii column list (ordinal order) used to build synthetic consumer_pii INSERTs
  - mockdata_tool.py is a pure-function module (no LLM calls, no I/O except reading the committed columns reference) — exports generate_external_system_ids, generate_consumer_pii, build_lookup_sql
  - generate_external_system_ids(seed, vary, count) returns N rows; every extsystemidskey is unique; varied columns differ across rows; non-varied columns equal the seed
  - generated external_system_ids SQL matches the .docs sample style (::uuid / ::timestamptz Postgres casts, MOCK_DATA/MANUAL markers preserved, bare NULL for empty cells)
  - generate_consumer_pii produces synthetic obviously-fake PII (mock+<id>@example.com, fake names) with MOCK_DATA markers across the full DV column list
  - build_lookup_sql(lucid, consumerkey?) returns the fully-qualified DV consumer_pii existence SELECT that passes the blocklist
---

<objective>
Build the single net-new domain module — `mockdata_tool.py`, a pure-function seed→N-row
generator — and pin the full DV `consumer_pii` column set as a committed reference
(`.docs/consumer_pii.columns.json`) acquired once via a live `INFORMATION_SCHEMA.COLUMNS`
query. The module emits Postgres-style INSERT text byte-compatible with the `.docs` sample and
builds the read-only existence-lookup SELECT (executed later in Wave 4).

Purpose: This is where the worked example ("vary signature and sourceconsumerid, N rows")
becomes deterministic SQL. The module has NO LLM and NO side effects beyond reading the
committed columns reference — the LLM (Copilot/Claude) decides WHICH columns to vary and HOW
MANY rows; the tool only transforms.

Output: 2 files — `mockdata_copilot_agent/.docs/consumer_pii.columns.json` (committed reference)
and `mockdata_copilot_agent/tools/mockdata_tool.py` (pure functions).

## Artifacts this wave produces
- New files: `mockdata_copilot_agent/.docs/consumer_pii.columns.json`,
  `mockdata_copilot_agent/tools/mockdata_tool.py`
- New functions:
  - `generate_external_system_ids(seed: dict, vary: dict, count: int) -> dict`
  - `generate_consumer_pii(lucids_or_seeds: list, ...) -> dict`
  - `build_lookup_sql(lucid: str, consumerkey: str | None = None, signature: str | None = None, isocountry: str | None = None) -> str`
  - `parse_seed_xlsx(path: str) -> dict` (optional convenience — paste-JSON is primary)
- Pinned constant: `EXTERNAL_SYSTEM_IDS_COLUMNS` (the 21 columns, ordinal order)

## Assumptions surfaced this wave (CONFIRM with user — do NOT silently drop)
- [A1 — SQL dialect]: Generated SQL matches the `.docs` sample EXACTLY (Postgres `::uuid` /
  `::timestamptz` casts), NOT GoogleSQL. The INSERTs target a Postgres source/staging DB, not
  BigQuery. Emit an A1 `[USER-CONFIRM]` note in the generated output so the user can confirm
  the target dialect. Default: Postgres (match `.docs`).
- [A2 / A3 — full DV consumer_pii schema]: The full column set is acquired live once via
  `INFORMATION_SCHEMA.COLUMNS` (Task 1) and committed. schema.json's 19 PD-curated columns are
  a starting point only and MUST be confirmed against the live DV table.
- [A4 — existence key]: existence lookup keys on `lucid` (+ optional `consumerkey`/`signature`/
  `isocountry`). Default key: `lucid`. lucid is NOT unique across brands, so `build_lookup_sql`
  accepts the optional disambiguators. Surface A4 in the module docstring for confirmation.
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
  isocountry='ID', signature=1(int)->'1', lucid='C2ID00000000010', sourcesystemid='MARS_ID',
  sourceconsumerid='ID011000000001C', creationlocationid='ID0160', locationid=None->NULL,
  creationsalesrepid='IDPGE450000', salesrepid=0(int)->'0', createddatetime='1900-01-01T00:00:00Z',
  status='Close', lastlogindatetime=None->NULL, createdsourcesystemid='MOCK_DATA',
  lastupdatedsourcesystemid='MANUAL', syscreateddatetime='2026-06-19T00:00:00Z',
  sysupdatedatetime='2026-06-23T09:48:27.302993Z', recordstatus=0(int)->'0',
  country_iso_3166_1=360(int)->'360', consumersourcekey=526979(int)->'526979'

Rendering rules (match .docs sample lines 25-40):
  - UUID columns (extsystemidskey, consumerkey) render as `'...'::uuid`
  - datetime columns (createddatetime, lastlogindatetime, syscreateddatetime, sysupdatedatetime)
    render as `'YYYY-MM-DD HH:MM:SS+00'::timestamptz`; normalize ISO-Z input
    `2026-06-19T00:00:00Z` -> `2026-06-19 00:00:00+00`; drop microseconds
  - numeric-typed seed cells coerce to the quoted string form the .sql uses ('1','0','360','526979')
  - None / empty cells render as bare `NULL` (no quotes, no cast)
  - all other values render as single-quoted strings

Function signatures:
```python
def generate_external_system_ids(seed: dict, vary: dict, count: int) -> dict:
    """Pure. Returns {"sql": str, "rows": list[dict], "lucids": list[str], "consumerkeys": list[str]}.
    `vary` maps column_name -> strategy or value-list. extsystemidskey is ALWAYS varied (trailing
    12-digit counter ++) regardless of `vary`, to keep the PK unique. NO LLM, NO I/O."""

def generate_consumer_pii(consumers: list[dict]) -> dict:
    """Pure. `consumers` = list of {"lucid","consumerkey","signature","isocountry", ...} that were
    found ABSENT. Returns {"sql": str, "rows": list[dict]}. Synthetic fake PII only
    (mock+<id>@example.com, fake names, MOCK_DATA markers) across the committed DV column list.
    Reads .docs/consumer_pii.columns.json for the column order."""

def build_lookup_sql(lucid: str, consumerkey: str | None = None,
                     signature: str | None = None, isocountry: str | None = None) -> str:
    """Pure. Returns the fully-qualified DV consumer_pii existence SELECT (passes the blocklist).
    Always uses `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`
    so _pick_executor selects the DV executor. Single-quotes all literal values."""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Acquire and commit the full DV consumer_pii column set</name>
  <files>
    mockdata_copilot_agent/.docs/consumer_pii.columns.json
  </files>
  <read_first>
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 201-215 — full schema acquisition options (Q4), recommendation (c) committed reference
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 452-457 — bq show --schema command
    mockdata_copilot_agent/tools/bigquery_tool.py — query_bigquery available for the INFORMATION_SCHEMA fetch
  </read_first>
  <action>
Acquire the authoritative full DV `consumer_pii` column set ONCE and commit it as a `.docs`
reference. This is the only column source `generate_consumer_pii` will read.

Preferred (needs ADC): run the INFORMATION_SCHEMA query through the reused read-only tool (it
passes the blocklist):
```sql
SELECT column_name, data_type, ordinal_position
FROM `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'consumer_pii'
ORDER BY ordinal_position
```
via `python mockdata_copilot_agent/run_tool.py ...` is NOT yet available (Wave 4). Instead run
it directly:
```bash
python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.bigquery_tool import init_from_schema, query_bigquery; init_from_schema(); print(query_bigquery('SELECT column_name, data_type, ordinal_position FROM \`oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.INFORMATION_SCHEMA.COLUMNS\` WHERE table_name = \"consumer_pii\" ORDER BY ordinal_position'))"
```
or, equivalently, `bq show --schema --format=prettyjson oa-apmena-spacecds-ap-dv:space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii`.

Write `mockdata_copilot_agent/.docs/consumer_pii.columns.json` as:
```json
{
  "source": "INFORMATION_SCHEMA.COLUMNS (oa-apmena-spacecds-ap-dv / space_cds_b2c_ds_replica_ase1_dv_public)",
  "acquired": "<YYYY-MM-DD>",
  "table": "consumer_pii",
  "columns": [
    {"name": "consumerkey", "data_type": "<type>", "ordinal_position": 1},
    {"name": "...",         "data_type": "<type>", "ordinal_position": 2}
  ]
}
```
preserving ordinal order.

ADC-UNAVAILABLE FALLBACK (degrade, do NOT block): if no ADC and `bq show` both fail, write the
file using the 19 PD-curated columns from schema.json as a STARTING POINT, and add
`"confirmed": false` plus a top-level `"note": "[A2/A3 USER-CONFIRM] Columns sourced from
schema.json PD-curated subset (19); NOT confirmed against live DV. Re-run INFORMATION_SCHEMA
with ADC before production."`. When ADC succeeds, set `"confirmed": true`.

The 19 PD columns (ordered) per 02-RESEARCH line 215: consumerkey, isocountry, signature, lucid,
status, consumertype, gender, firstname, lastname, birthyear, birthmonth, birthday, mobile,
phone, email, sourcecreationdatetime, registrationdatetime, withdrawaldatetime, recordstatus.

Do NOT regenerate or stage the repo-root `schema.json` in this commit (CLAUDE.md: schema
regeneration is a separate deliberate action). Commit ONLY `consumer_pii.columns.json` alongside
the Wave 3 code.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import json, pathlib
d = json.loads(pathlib.Path('mockdata_copilot_agent/.docs/consumer_pii.columns.json').read_text())
cols = d['columns']
assert isinstance(cols, list) and len(cols) >= 19, f'expected >=19 columns, got {len(cols)}'
names = [c['name'] for c in cols]
for required in ('consumerkey','lucid','email','firstname','lastname','signature','isocountry'):
    assert required in names, f'missing {required}'
print('confirmed:', d.get('confirmed'), '| columns:', len(cols))
"</automated>
  </verify>
  <done>
    `.docs/consumer_pii.columns.json` exists with a `columns` array of >= 19 entries in ordinal
    order, each having `name` and `data_type`. It includes `consumerkey`, `lucid`, `email`,
    `firstname`, `lastname`, `signature`, `isocountry`. A `confirmed` flag records whether the
    set was acquired live (`true`) or from the schema.json fallback (`false`, with the
    `[A2/A3 USER-CONFIRM]` note). The repo-root `schema.json` is NOT staged in this commit.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create mockdata_tool.py (pure-function generator + lookup SQL builder)</name>
  <files>
    mockdata_copilot_agent/tools/mockdata_tool.py
  </files>
  <read_first>
    mockdata_copilot_agent/.docs/external_system_ids mock up.sql — the exact output style (::uuid/::timestamptz, MOCK_DATA/MANUAL, NULL) to replicate
    mockdata_copilot_agent/.docs/consumer_pii.columns.json — column order for consumer_pii INSERTs
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 226-254 — mock-generation algorithm (Q6): seed parsing, UUID family, variation rules
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 186-199 — existence-lookup SELECT shape (Q3)
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 434-437 — Excel type coercion pitfall (Pitfall 6)
  </read_first>
  <behavior>
    - generate_external_system_ids(SEED, {}, 3) returns 3 rows; len(result["rows"]) == 3
    - every row's extsystemidskey is unique across the 3 rows (trailing 12-digit counter increments)
    - with vary={"signature": ["45","01","24"]}, the 3 rows have signature values "45","01","24" and all OTHER columns equal the seed
    - result["sql"] starts with "INSERT INTO external_system_ids (" and contains "::uuid" and "::timestamptz" and "MOCK_DATA" and "MANUAL"
    - a seed cell that is None renders as bare "NULL" (no quotes, no ::cast) in the SQL — e.g. locationid and lastlogindatetime in the worked-example seed
    - an integer seed cell (signature=1) renders as the quoted string form '1' in the SQL (not 1, not 1::int)
    - an ISO-Z datetime seed cell "2026-06-19T00:00:00Z" renders as "'2026-06-19 00:00:00+00'::timestamptz"
    - generate_consumer_pii([{"lucid":"C2ID00000000099","consumerkey":"6d74baaa-baaa-7a19-899c-000000000099","signature":"45","isocountry":"ID"}]) returns sql containing "INSERT INTO consumer_pii", a mock+...@example.com email, a "MOCK_DATA" marker, and NO real-looking PII
    - build_lookup_sql("C2ID00000000010") returns a string starting with "SELECT" containing the fully-qualified `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii` and "lucid = 'C2ID00000000010'"
    - build_lookup_sql output passes SafeBigQueryExecutor.validate_query (read-only, blocklist-clean)
  </behavior>
  <action>
Create `mockdata_copilot_agent/tools/mockdata_tool.py` — a PURE-function module. NO LLM calls.
NO I/O except reading the committed `.docs/consumer_pii.columns.json`. All diagnostics (if any)
go to stderr; functions RETURN strings, never `print()` to stdout (MCP-stdio safety, Pitfall 5).

Module docstring must state plainly: this module generates SQL only; the agent never executes
writes; and surface assumptions A1 (Postgres dialect — default, confirm with user), A4
(existence key = lucid + optional disambiguators), A5 (UUID family), A8 (MOCK_DATA/MANUAL
preserved), A9 (synthetic fake PII).

Define `EXTERNAL_SYSTEM_IDS_COLUMNS` as the 21-column tuple in ordinal order (from the
interfaces block). Define a `_DV_TABLE` constant
`"oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii"` for the
lookup SQL (the only place a fully-qualified ref is needed) — note the project/dataset literals
here are SQL identifiers in the generated/lookup text, not a Python config of the BQ client, so
this does not violate the "no hardcoded project outside config.py" rule for the executor; the
executor's billing project still comes from Wave 1 config via BQ_PROJECT. If you prefer, accept
the dataset/project as optional args defaulting to those literals.

Implement value rendering (`_render_value(column, value)`):
  - UUID columns {extsystemidskey, consumerkey}: `'<value>'::uuid`
  - datetime columns {createddatetime, lastlogindatetime, syscreateddatetime, sysupdatedatetime,
    sourcecreationdatetime, registrationdatetime, withdrawaldatetime}: normalize ISO-Z
    (`...T...Z`, microseconds dropped) to `YYYY-MM-DD HH:MM:SS+00` then `'<norm>'::timestamptz`
  - None / "" : bare `NULL`
  - int / float : coerce to its string form, single-quoted (e.g. `'1'`, `'360'`)
  - everything else : single-quoted string

Implement `generate_external_system_ids(seed, vary, count)`:
  - For each of `count` rows: deep-copy the seed dict.
  - ALWAYS vary `extsystemidskey`: parse its `GGGG-NNNNNNNNNNNN` tail and increment the trailing
    12-digit counter per row so each PK is unique (A5).
  - For each column named in `vary`: if the value is a list, cycle through it by row index; if a
    scalar/strategy string, apply a deterministic increment (e.g. `sourceconsumerid` suffix
    letter increment `...001C` -> `...001D`; `signature` cycle). Document each strategy inline.
  - Columns not in `vary` (and not extsystemidskey) are copied verbatim from the seed.
  - Render each row via `_render_value` in EXTERNAL_SYSTEM_IDS_COLUMNS order, joined as
    `(v1, v2, ...)`; build the full `INSERT INTO external_system_ids (\n  col,\n  ...\n) VALUES\n
    (row1),\n(row2);` block matching the .docs sample layout.
  - Return `{"sql": ..., "rows": [<dict per row>], "lucids": [...distinct lucid...],
    "consumerkeys": [...distinct consumerkey...]}`.

Implement `generate_consumer_pii(consumers)`:
  - Read column order from `.docs/consumer_pii.columns.json`.
  - For each absent consumer, build a row: copy known keys (lucid, consumerkey, signature,
    isocountry), set provenance/marker columns to `MOCK_DATA`/`MANUAL` where such columns exist,
    fill name/email with OBVIOUSLY FAKE values: `firstname='Mock'`, `lastname='Tester'`,
    `email='mock+' + <lucid-or-counter> + '@example.com'`, phone/mobile fake constants. NEVER
    emit real-looking PII (A9).
  - Render with `_render_value`; build `INSERT INTO consumer_pii (...) VALUES (...);`.
  - Return `{"sql": ..., "rows": [...]}`.

Implement `build_lookup_sql(lucid, consumerkey=None, signature=None, isocountry=None)`:
  - Return the read-only SELECT keyed on `lucid` with optional AND clauses for the provided
    disambiguators (A4), against `_DV_TABLE`, `LIMIT 5`. Single-quote all literals. The result
    must pass `SafeBigQueryExecutor.validate_query` (no bare blocklist words; values quoted).

(Optional) Implement `parse_seed_xlsx(path)` using openpyxl: header row 0 = column names, row 1
= seed values; coerce per the rendering rules. Paste-JSON remains the primary input (A7), so
guard the openpyxl import and degrade gracefully if it is missing.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import sys; sys.path.insert(0,'mockdata_copilot_agent')
from tools.mockdata_tool import generate_external_system_ids, generate_consumer_pii, build_lookup_sql, EXTERNAL_SYSTEM_IDS_COLUMNS
from tools.bigquery_tool import SafeBigQueryExecutor
assert len(EXTERNAL_SYSTEM_IDS_COLUMNS) == 21

SEED = {
 'extsystemidskey':'1b48bdbb-bdbb-7b6f-0003-000000000033','consumerkey':'6d74baaa-baaa-7a19-899c-000000000032',
 'isocountry':'ID','signature':1,'lucid':'C2ID00000000010','sourcesystemid':'MARS_ID',
 'sourceconsumerid':'ID011000000001C','creationlocationid':'ID0160','locationid':None,
 'creationsalesrepid':'IDPGE450000','salesrepid':0,'createddatetime':'1900-01-01T00:00:00Z',
 'status':'Close','lastlogindatetime':None,'createdsourcesystemid':'MOCK_DATA',
 'lastupdatedsourcesystemid':'MANUAL','syscreateddatetime':'2026-06-19T00:00:00Z',
 'sysupdatedatetime':'2026-06-23T09:48:27.302993Z','recordstatus':0,'country_iso_3166_1':360,
 'consumersourcekey':526979}

r = generate_external_system_ids(SEED, {'signature':['45','01','24']}, 3)
assert len(r['rows']) == 3
keys = [row['extsystemidskey'] for row in r['rows']]
assert len(set(keys)) == 3, f'extsystemidskey not unique: {keys}'
sigs = [row['signature'] for row in r['rows']]
assert sigs == ['45','01','24'], sigs
# non-varied column equals seed
assert all(row['sourcesystemid'] == 'MARS_ID' for row in r['rows'])
sql = r['sql']
assert sql.startswith('INSERT INTO external_system_ids (')
for token in ('::uuid','::timestamptz','MOCK_DATA','MANUAL'):
    assert token in sql, token
# NULL for None cells, no quotes/cast
assert 'NULL' in sql
# int coerces to quoted string '1'/'45'..., ISO-Z normalized
assert \"'2026-06-19 00:00:00+00'::timestamptz\" in sql, 'ISO-Z not normalized'

cp = generate_consumer_pii([{'lucid':'C2ID00000000099','consumerkey':'6d74baaa-baaa-7a19-899c-000000000099','signature':'45','isocountry':'ID'}])
assert 'INSERT INTO consumer_pii' in cp['sql']
assert 'mock+' in cp['sql'] and '@example.com' in cp['sql']
assert 'MOCK_DATA' in cp['sql']

lk = build_lookup_sql('C2ID00000000010')
assert lk.strip().upper().startswith('SELECT')
assert 'oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public.consumer_pii' in lk
assert \"lucid = 'C2ID00000000010'\" in lk
ex = SafeBigQueryExecutor(project='oa-apmena-spacecds-ap-dv')
ok, err = ex.validate_query(lk)
assert ok is True, f'lookup SQL must pass blocklist: {err}'
print('ALL mockdata_tool tests PASS')
"</automated>
  </verify>
  <done>
    `mockdata_tool.py` exists and is a pure module (no LLM, no stdout prints). All inline
    assertions pass: 3 rows generated, unique `extsystemidskey`, `signature` varied to
    `['45','01','24']` with other columns equal to seed, SQL starts with
    `INSERT INTO external_system_ids (`, contains `::uuid`/`::timestamptz`/`MOCK_DATA`/`MANUAL`,
    `None` cells render as bare `NULL`, ISO-Z normalized to `+00`::timestamptz, integers
    coerced to quoted strings. `generate_consumer_pii` emits a synthetic `mock+...@example.com`
    row with `MOCK_DATA`. `build_lookup_sql` returns a fully-qualified DV `consumer_pii` SELECT
    that passes `validate_query`.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| seed/vary input → mockdata_tool | Untrusted seed values are rendered into SQL text that is PRESENTED, never executed — no injection surface against a live DB |
| lookup SQL → query_bigquery (Wave 4) | The only generated SQL that touches a live DB is the read-only existence SELECT; it is blocklist-clean by construction |
| .docs/consumer_pii.columns.json → generate_consumer_pii | Column list read from a committed reference; controls which columns appear in synthetic INSERTs |
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
2. `python -c "import json,pathlib; d=json.loads(pathlib.Path('mockdata_copilot_agent/.docs/consumer_pii.columns.json').read_text()); assert len(d['columns'])>=19; print(len(d['columns']),'columns, confirmed=',d.get('confirmed'))"` — prints column count
3. `grep -c "::uuid\|::timestamptz" <(python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from tools.mockdata_tool import generate_external_system_ids; print(generate_external_system_ids({'extsystemidskey':'1b48bdbb-bdbb-7b6f-0003-000000000033','consumerkey':'6d74baaa-baaa-7a19-899c-000000000032','createddatetime':'1900-01-01T00:00:00Z'}, {}, 1)['sql'])")` — returns > 0
4. `grep -n "print(" mockdata_copilot_agent/tools/mockdata_tool.py` — returns empty or only stderr-targeted prints (no bare stdout prints)
</verification>

<success_criteria>
- `.docs/consumer_pii.columns.json` pins the full DV `consumer_pii` column set (live-acquired or schema.json fallback flagged unconfirmed)
- `mockdata_tool.py` is pure: no LLM calls, no stdout prints, no I/O beyond reading the columns reference
- `generate_external_system_ids` produces N rows with unique `extsystemidskey`, varied named columns, seed-identical other columns
- Generated SQL is byte-style-compatible with the `.docs` sample (Postgres casts, MOCK_DATA/MANUAL, bare NULL)
- `generate_consumer_pii` emits obviously-synthetic PII across the full DV column list
- `build_lookup_sql` returns a fully-qualified DV `consumer_pii` SELECT that passes the blocklist
- Assumptions A1/A2/A3/A4/A5/A8/A9 are surfaced in the module docstring / generated output for user confirmation
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-02/phase-kayinleong-02-wave3-SUMMARY.md`
</output>
