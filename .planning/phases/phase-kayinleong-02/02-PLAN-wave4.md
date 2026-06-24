---
wave: 4
depends_on: [wave3]
files_modified:
  - mockdata_copilot_agent/mcp_server.py
  - mockdata_copilot_agent/run_tool.py
autonomous: true
requirements:
  - phase-kayinleong-02
must_haves:
  - mcp_server.py exports async _dispatch(name, arguments, output_dir) routing exactly 4 tools without raising KeyError
  - 4 tools registered: ensure_login, lookup_consumer, generate_mockdata, save_mockdata_report
  - mcp_server.py and run_tool.py set os.environ.setdefault("BQ_PROJECT", cfg.bq_project) BEFORE ensure_gcloud_auth() so the DV project is the default
  - NO ServiceNow startup (no ensure_credentials, no incident-store preload) and NO SMTP anywhere
  - lookup_consumer runs a read-only SELECT via the reused query_bigquery (never INSERT)
  - generate_mockdata + save_mockdata_report contain NO LLM calls
  - save_mockdata_report writes mockdata/<MMDDYYSS>.md (MMDDYY + collision-safe 2-digit sequence) with prompt echo + SQL sections + summary + "review & run manually" reminder
  - run_tool.py callable as `python mockdata_copilot_agent/run_tool.py <tool> --json '{}'` and imports _dispatch from local mcp_server
---

<objective>
Create the agent surface: `mcp_server.py` (4-tool registration + flat `_dispatch`) and
`run_tool.py` (CLI entry that delegates to `_dispatch`), plus the collision-safe
`mockdata/<MMDDYYSS>.md` report writer inside `save_mockdata_report`. Both startup paths default
the BQ project to DV via the env var set from config, then run the reused gcloud auth check —
NO ServiceNow, NO SMTP.

Purpose: `run_tool.py` is the primary runtime interface (L'Oreal blocks MCP servers).
`_dispatch` is the single source of truth shared by the CLI and any MCP client. The four tools
implement the full per-prompt flow: ensure GCP login → generate mock external_system_ids rows →
look up each consumer (read-only) and generate a synthetic consumer_pii row when absent → write
the SQL report and present it.

Output: 2 files — `mcp_server.py`, `run_tool.py`.

## Artifacts this wave produces
- New files: `mockdata_copilot_agent/mcp_server.py`, `mockdata_copilot_agent/run_tool.py`
- New tools (CLI tool-names): `ensure_login`, `lookup_consumer`, `generate_mockdata`,
  `save_mockdata_report`
- New function: `_dispatch(name, arguments, output_dir)` (shared CLI + MCP routing)
- New report-writer behavior: `mockdata/<MMDDYYSS>.md` with collision-safe sequence
- New CLI: `python mockdata_copilot_agent/run_tool.py <tool> --json '<JSON args>'`
- Server name: `mockdata-copilot`

## Assumptions surfaced this wave
- [A6 — filename]: `MMDDYYSS` = `MM`+`DD`+`YY` + 2-digit sequence (00-99), NOT literal seconds;
  collision-safe by scanning existing same-day files. Fallback `MMDDYY_HHMMSS.md` if 00-99
  exhaust.
- [A1 — dialect: GoogleSQL — CONFIRMED 2026-06-24]: the report header notes that generated
  INSERTs are BigQuery GoogleSQL for the DV dataset; the agent does not execute writes — the user
  runs them against BigQuery.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/CLAUDE.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-RESEARCH.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/ticketasg_copilot_agent/mcp_server.py
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/ticketasg_copilot_agent/run_tool.py

<interfaces>
<!-- 4 tools in mockdata_copilot_agent/mcp_server.py -->

| Tool | args | returns | analog |
|------|------|---------|--------|
| ensure_login | {} | status string (account, ADC ok, project) | ticketasg main() ensure_gcloud_auth startup call |
| lookup_consumer | {"lucid": str, "consumerkey"?: str, "signature"?: str, "isocountry"?: str} | existence JSON {exists: bool, rows: ...} | ticketasg query_bigquery branch |
| generate_mockdata | {"seed": dict, "vary": dict, "count": int, "absent_lucids"?: list} | JSON {external_system_ids_sql, rows, lucids, consumerkeys, consumer_pii_sql?} | NEW — wraps mockdata_tool pure fns |
| save_mockdata_report | {"prompt": str, "external_sql": str, "consumer_sql"?: str, "summary": str} | saved path string | ticketasg save_assignment_report |

Startup project defaulting [02-RESEARCH lines 466-477] — in BOTH run_tool.main() and
mcp_server.main(), BEFORE ensure_gcloud_auth():
```python
import os
from config import load_mockdata_config
cfg = load_mockdata_config()
os.environ.setdefault("BQ_PROJECT", cfg.bq_project)   # DV
```

generate_mockdata wiring: call mockdata_tool.generate_external_system_ids(seed, vary, count);
if `absent_lucids` provided (the LLM passes back the lucids that lookup_consumer reported
absent), also call generate_consumer_pii for those and include `consumer_pii_sql`. The tool does
NOT itself call lookup_consumer or decide which lucids are absent — the agent body (Copilot/
Claude) orchestrates that across calls (no LLM in the tool).

lookup_consumer wiring: build SQL via mockdata_tool.build_lookup_sql(...), then
`from tools.bigquery_tool import query_bigquery; query_bigquery(sql, rationale="consumer_pii existence check")`.
Parse the JSON result; return {"exists": <bool>, "matched": <rows or summary>}. NEVER send an
INSERT through query_bigquery.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create mcp_server.py (4-tool registration + flat _dispatch + report writer)</name>
  <files>
    mockdata_copilot_agent/mcp_server.py
  </files>
  <read_first>
    ticketasg_copilot_agent/mcp_server.py lines 1-100 — module docstring, sys.path.insert, structure
    ticketasg_copilot_agent/mcp_server.py lines 570-660 — _dispatch head + a query_bigquery-style branch to mirror
    ticketasg_copilot_agent/mcp_server.py lines 904-954 — save_assignment_report branch (report-writer pattern) + final else
    ticketasg_copilot_agent/mcp_server.py lines 1039-1108 — main() startup (KEEP bigquery init + gcloud auth; DROP SNOW + incident-store; DROP SMTP)
    mockdata_copilot_agent/tools/mockdata_tool.py — generate_external_system_ids, generate_consumer_pii, build_lookup_sql signatures
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 256-275 — output file MMDDYYSS naming + collision handling + markdown sections (Q7)
  </read_first>
  <action>
Create `mockdata_copilot_agent/mcp_server.py` by adapting the ticketasg analog DOWN to 4 tools.

**1. Module docstring** — server name `mockdata-copilot`; describe the 4 tools; state plainly
"No LLM calls in this server. The agent PRESENTS SQL only — it never executes writes. The only
live BigQuery access is the read-only consumer_pii existence lookup." Document env vars
`BQ_PROJECT` (default DV), `BQ_DATASET`, `MOCKDATA_OUTPUT_DIR`. NO COOKIE/X_USERTOKEN/SMTP.

**2. `sys.path.insert`** — copy verbatim:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

**3. DROP** `_build_reader`, `_auto_load_store`, `_ensure_store_loaded`, `_resolve_sys_id` —
there is no ServiceNow here.

**4. `create_mcp_server(output_dir)`** — `server = Server("mockdata-copilot")`. Register exactly
these 4 Tool objects (inputSchema per the interfaces table):
  - `ensure_login` — `inputSchema={"type":"object","properties":{}}`
  - `lookup_consumer` — required `["lucid"]`; optional `consumerkey`, `signature`, `isocountry`
  - `generate_mockdata` — required `["seed","vary","count"]`; optional `absent_lucids` (array)
  - `save_mockdata_report` — required `["prompt","external_sql","summary"]`; optional
    `consumer_sql`
  Each description must note the agent presents SQL and never executes writes.

**5. `_dispatch(name, arguments, output_dir)`** — flat if/elif, exactly 4 branches + final else:

  ```python
  if name == "ensure_login":
      from tools.gcloud_tool import ensure_gcloud_auth, get_active_gcloud_account
      ensure_gcloud_auth("loreal.com")
      acct = get_active_gcloud_account() or "(unknown)"
      return json.dumps({"account": acct, "project": os.environ.get("BQ_PROJECT", ""), "adc": "checked"}, indent=2)

  elif name == "lookup_consumer":
      from tools.mockdata_tool import build_lookup_sql
      from tools.bigquery_tool import query_bigquery
      sql = build_lookup_sql(
          lucid=arguments["lucid"],
          consumerkey=arguments.get("consumerkey"),
          signature=arguments.get("signature"),
          isocountry=arguments.get("isocountry"),
      )
      raw = query_bigquery(sql, rationale="consumer_pii existence check")
      # parse raw for row presence; return existence verdict + matched summary
      exists = ("0 rows" not in raw) and ("No results" not in raw) and ("error" not in raw.lower())
      return json.dumps({"lucid": arguments["lucid"], "exists": exists, "result": raw}, indent=2)

  elif name == "generate_mockdata":
      from tools.mockdata_tool import generate_external_system_ids, generate_consumer_pii
      gen = generate_external_system_ids(arguments["seed"], arguments["vary"], int(arguments["count"]))
      out = {"external_system_ids_sql": gen["sql"], "rows": gen["rows"],
             "lucids": gen["lucids"], "consumerkeys": gen["consumerkeys"]}
      absent = arguments.get("absent_lucids") or []
      if absent:
          # build consumer dicts from generated rows whose lucid is in `absent`
          consumers = [r for r in gen["rows"] if r.get("lucid") in absent]
          cp = generate_consumer_pii(consumers)
          out["consumer_pii_sql"] = cp["sql"]
      return json.dumps(out, indent=2)

  elif name == "save_mockdata_report":
      return _save_mockdata_report(output_dir, arguments)

  else:
      return f"Unknown tool: {name}"
  ```
  IMPORTANT: do NOT route any generated INSERT through `query_bigquery`. Only `build_lookup_sql`
  output (a SELECT) is ever executed.

**6. `_save_mockdata_report(output_dir, arguments)`** — the collision-safe writer (A6):
  ```python
  def _save_mockdata_report(output_dir: str, args: dict) -> str:
      from datetime import datetime
      os.makedirs(output_dir, exist_ok=True)
      base = datetime.now().strftime("%m%d%y")            # MMDDYY
      existing = {p.stem for p in Path(output_dir).glob(f"{base}*.md")}
      seq = next((f"{i:02d}" for i in range(100) if f"{base}{i:02d}" not in existing), None)
      stem = f"{base}{seq}" if seq is not None else datetime.now().strftime(f"{base}_%H%M%S")
      path = Path(output_dir) / f"{stem}.md"
      ...
  ```
  The markdown body has these sections (Q7): `# Mock Data — <stem>` + generated timestamp;
  `## Prompt` (verbatim echo of `args["prompt"]`); `## external_system_ids` (the
  `args["external_sql"]` block); `## consumer_pii` (`args.get("consumer_sql")` if present, else
  the literal line "No consumer_pii rows needed — all consumers already exist."); `## Summary`
  (`args["summary"]`) followed by the mandatory reminder line:
  "Review and run these INSERTs manually against the BigQuery DV dataset
  (oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public). This agent does not execute
  writes." Also include a note that the dialect is BigQuery GoogleSQL [A1 confirmed 2026-06-24].
  Return `f"Mock data report saved: {path}"`.

**7. `_run_jsonrpc_fallback(output_dir)`** — copy the analog's structure; tool name list = the 4
tools.

**8. `main()`** — adapt the analog: argparse description "Mock Data Copilot MCP Server";
`--output-dir` flag overriding `MOCKDATA_OUTPUT_DIR`/config. Startup sequence:
  ```python
  from config import load_mockdata_config
  cfg = load_mockdata_config()
  output_dir = args.output_dir or cfg.output_dir
  os.makedirs(output_dir, exist_ok=True)
  os.environ.setdefault("BQ_PROJECT", cfg.bq_project)      # DV default — BEFORE auth
  try: from tools.bigquery_tool import init_from_schema; init_from_schema()
  except Exception as e: logger.warning(f"[BQ] Not available: {e}")
  try: from tools.gcloud_tool import ensure_gcloud_auth; ensure_gcloud_auth("loreal.com")
  except Exception as e: logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")
  ```
  Do NOT call `ensure_credentials` (SNOW) or `load_store`. `InitializationOptions(server_name=
  "mockdata-copilot", ...)`. Keep the `import mcp` try/except → `_run_jsonrpc_fallback` fallback.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import sys, asyncio, json, tempfile
sys.path.insert(0,'mockdata_copilot_agent')
from mcp_server import _dispatch
# unknown tool returns error string, no raise
assert 'Unknown tool' in asyncio.run(_dispatch('nope_xyz', {}, tempfile.mkdtemp()))
# generate_mockdata works offline (pure)
SEED={'extsystemidskey':'1b48bdbb-bdbb-7b6f-0003-000000000033','consumerkey':'6d74baaa-baaa-7a19-899c-000000000032','isocountry':'ID','signature':1,'lucid':'C2ID00000000010','sourceconsumerid':'ID011000000001C','createddatetime':'1900-01-01T00:00:00Z','createdsourcesystemid':'MOCK_DATA','lastupdatedsourcesystemid':'MANUAL'}
r = asyncio.run(_dispatch('generate_mockdata', {'seed':SEED,'vary':{'signature':['45','01']},'count':2}, tempfile.mkdtemp()))
d = json.loads(r)
assert 'external_system_ids_sql' in d and d['external_system_ids_sql'].startswith('INSERT INTO external_system_ids (')
# save_mockdata_report writes MMDDYYSS file with reminder
td = tempfile.mkdtemp()
p = asyncio.run(_dispatch('save_mockdata_report', {'prompt':'vary signature x2','external_sql':d['external_system_ids_sql'],'summary':'2 rows'}, td))
import re, pathlib
fp = p.split('saved:')[-1].strip()
txt = pathlib.Path(fp).read_text()
assert re.search(r'/\d{8}\.md$', fp), f'filename not MMDDYYSS: {fp}'
assert 'does not execute writes' in txt
assert '## Prompt' in txt and '## external_system_ids' in txt and '## Summary' in txt
print('mcp_server _dispatch tests PASS')
"</automated>
  </verify>
  <done>
    `mcp_server.py` exists. `_dispatch` is importable and routes the 4 tools.
    `_dispatch("nope_xyz", {}, dir)` returns "Unknown tool: nope_xyz" (no exception).
    `generate_mockdata` returns JSON whose `external_system_ids_sql` starts with
    `INSERT INTO external_system_ids (`. `save_mockdata_report` writes a file named `<8 digits>.md`
    containing `## Prompt`, `## external_system_ids`, `## Summary`, and the "does not execute
    writes" reminder. `grep -c "mockdata-copilot" mockdata_copilot_agent/mcp_server.py` returns
    >= 2. `grep "ensure_credentials\|load_store\|send_.*email\|SMTP" mockdata_copilot_agent/mcp_server.py`
    returns empty.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create run_tool.py (CLI delegating to _dispatch; DV default before auth, no SNOW/SMTP)</name>
  <files>
    mockdata_copilot_agent/run_tool.py
  </files>
  <read_first>
    ticketasg_copilot_agent/run_tool.py — full file; copy structure, REMOVE the SNOW credential check + incident-store preload
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 466-477 — startup project defaulting (set BQ_PROJECT before auth)
    mockdata_copilot_agent/config.py — load_mockdata_config() returns bq_project + output_dir
  </read_first>
  <action>
Create `mockdata_copilot_agent/run_tool.py` by adapting the ticketasg analog.

1. **Module docstring** — list the 4 tools and usage:
```
run_tool.py — Unified CLI for mockdata_copilot_agent tools (no MCP server required).

Usage:
    python mockdata_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'

Examples:
    python mockdata_copilot_agent/run_tool.py ensure_login --json '{}'
    python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {...}, "vary": {"signature": ["45","01"]}, "count": 2}'
    python mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "C2ID00000000010"}'
    python mockdata_copilot_agent/run_tool.py save_mockdata_report --json '{"prompt": "...", "external_sql": "...", "summary": "..."}'

Tool names:
    ensure_login          Ensure L'Oreal GCP login (gcloud user creds + ADC); default project = DV
    lookup_consumer       Read-only consumer_pii existence check against the DV dataset
    generate_mockdata     Generate N mock external_system_ids rows (+ optional consumer_pii rows)
    save_mockdata_report  Write mockdata/<MMDDYYSS>.md and present the SQL

This agent PRESENTS SQL only — it never executes writes against any database.
```

2. **`argparse` description** — `"Run a mockdata_copilot_agent tool without starting an MCP server."`

3. **Startup body** (replace the ticketasg SNOW/store/auth block):
```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
...
from config import load_mockdata_config
cfg = load_mockdata_config()
output_dir = os.environ.get("MOCKDATA_OUTPUT_DIR") or cfg.output_dir
os.makedirs(output_dir, exist_ok=True)
os.environ.setdefault("BQ_PROJECT", cfg.bq_project)        # DV default — BEFORE auth

# Initialize BigQuery schema (non-fatal)
try:
    from tools.bigquery_tool import init_from_schema
    init_from_schema()
except Exception as e:
    logger.warning(f"[BQ] Not available: {e}")

# Check gcloud ADC / L'Oreal login (non-fatal)
try:
    from tools.gcloud_tool import ensure_gcloud_auth
    ensure_gcloud_auth("loreal.com")
except Exception as e:
    logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")

from mcp_server import _dispatch
result = asyncio.run(_dispatch(args.tool, arguments, output_dir))
print(result)
```
Do NOT include `ensure_credentials` (SNOW), `load_store`, attachments_dir, or any SMTP. The
only output dir is `output_dir` (passed to `_dispatch` as the 3rd arg).

`from mcp_server import _dispatch` resolves to the LOCAL `mockdata_copilot_agent/mcp_server.py`
because `sys.path.insert(0, str(Path(__file__).resolve().parent))` puts the package dir first.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python mockdata_copilot_agent/run_tool.py --help 2>&1 | head -5 && echo "---grepcount---" && grep -c "ensure_credentials\|load_store\|SMTP\|rca_copilot_agent\|ticketasg_copilot_agent" mockdata_copilot_agent/run_tool.py</automated>
  </verify>
  <done>
    `python mockdata_copilot_agent/run_tool.py --help` exits 0 and prints usage containing
    "mockdata_copilot_agent". The grep for `ensure_credentials|load_store|SMTP|rca_copilot_agent|
    ticketasg_copilot_agent` returns `0` (no SNOW credential check, no incident-store preload, no
    SMTP, no cross-package references). `grep "from mcp_server import _dispatch"
    mockdata_copilot_agent/run_tool.py` returns one line. `grep
    "os.environ.setdefault(\"BQ_PROJECT\"" mockdata_copilot_agent/run_tool.py` returns one line,
    and it appears BEFORE the `ensure_gcloud_auth` call.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI args → run_tool.py | `--json` parsed with `json.loads()`; invalid JSON exits 1 with an error |
| MCP/CLI tool args → _dispatch | Untrusted tool arguments; all branch errors caught and returned as strings |
| lookup_consumer → DV BigQuery | The ONLY live DB access; read-only SELECT via the blocklisted executor |
| generated SQL → save_mockdata_report file | INSERT SQL flows to the report file + the user, NEVER to a database |
| BQ_PROJECT env → reused tools | Set from config at startup before auth; non-secret DV project id |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave4-01 | Tampering | _dispatch generate_mockdata / lookup_consumer | mitigate | Generated INSERTs are returned as text only; only `build_lookup_sql` SELECT output is sent to `query_bigquery`, which enforces the blocklist |
| T-wave4-02 | Tampering | _save_mockdata_report filename | mitigate | Filename built from `datetime` + numeric sequence only (no user-controlled path segment); output confined to `output_dir` |
| T-wave4-03 | Information Disclosure | save_mockdata_report output | mitigate | Written to `output_dir` (default `<pkg>/mockdata`, gitignored Wave 1); synthetic PII only; report carries "never staged / run manually" reminder |
| T-wave4-04 | Information Disclosure | gcloud auth at startup | mitigate | Reused `ensure_gcloud_auth` forwards gcloud stdout to stderr; gcloud ADC only; no COOKIE/token/SMTP secrets exist in this agent |
| T-wave4-05 | Elevation of Privilege | accidental write path | mitigate | No tool can execute an INSERT — generated SQL never reaches `query_bigquery`; the only executed statement is the read-only existence SELECT |
</threat_model>

<verification>
From repo root:
1. `python mockdata_copilot_agent/run_tool.py --help` — exits 0, prints "mockdata_copilot_agent"
2. `python -c "import sys, asyncio; sys.path.insert(0,'mockdata_copilot_agent'); from mcp_server import _dispatch; assert 'Unknown tool' in asyncio.run(_dispatch('nope',{},'/tmp'))"` — exits 0
3. `python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {"extsystemidskey":"1b48bdbb-bdbb-7b6f-0003-000000000033","consumerkey":"6d74baaa-baaa-7a19-899c-000000000032","isocountry":"ID","signature":1,"lucid":"C2ID00000000010","createddatetime":"1900-01-01T00:00:00Z","createdsourcesystemid":"MOCK_DATA","lastupdatedsourcesystemid":"MANUAL"}, "vary": {"signature": ["45","01"]}, "count": 2}' | python -c "import sys,json; d=json.load(sys.stdin); assert d['external_system_ids_sql'].startswith('INSERT INTO'); assert 'space_cds_b2c_ds_replica_ase1_dv_public.external_system_ids' in d['external_system_ids_sql']; print('PASS')"` — prints PASS
4. `grep -c "mockdata-copilot" mockdata_copilot_agent/mcp_server.py` — returns >= 2
5. `grep -c "ensure_credentials\|load_store\|SMTP\|send_.*email" mockdata_copilot_agent/mcp_server.py mockdata_copilot_agent/run_tool.py` — returns 0 for both files
</verification>

<success_criteria>
- `run_tool.py --help` exits 0 without any credentials
- `_dispatch` routes exactly 4 tools (`ensure_login`, `lookup_consumer`, `generate_mockdata`, `save_mockdata_report`) and returns "Unknown tool: <name>" for anything else
- Both startup paths set `BQ_PROJECT=oa-apmena-spacecds-ap-dv` (from config) BEFORE `ensure_gcloud_auth`
- NO ServiceNow startup (no `ensure_credentials`, no `load_store`) and NO SMTP anywhere
- `lookup_consumer` executes only a read-only SELECT; no tool ever sends an INSERT to `query_bigquery`
- `save_mockdata_report` writes `mockdata/<MMDDYYSS>.md` (collision-safe) with prompt echo, SQL sections, summary, and the "review & run manually / does not execute writes" reminder + A1 dialect note
- No cross-package imports from `rca_copilot_agent` or `ticketasg_copilot_agent`
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-02/phase-kayinleong-02-wave4-SUMMARY.md`
</output>