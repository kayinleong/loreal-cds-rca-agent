# Claim: quick-kayinleong-026
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-26
- status: done
- summary: mockdata — add read-only `fetch_seed` tool so the agent pulls a live external_system_ids seed row instead of asking the user to paste JSON.

## What will change

The mockdata copilot agent currently has no way to *obtain* a seed row — `generate_mockdata`
requires one. When the user doesn't paste a seed, both the Claude skill and the GitHub Copilot
agent fall back to asking the user to "paste the seed row as JSON". The user wants the agent to
fetch a real seed from BigQuery itself.

Add a new read-only tool `fetch_seed`:
- `mockdata_tool.build_seed_sql(...)` — pure function returning a blocklist-clean `SELECT` of the
  18 live `external_system_ids` columns, with optional whitelisted WHERE filters
  (`isocountry`, `signature`, `sourcesystemid`, `lucid`) and a clamped `LIMIT`.
- `bigquery_tool.query_bigquery_rows(...)` — structured variant of `query_bigquery` returning
  `(rows, error)` instead of an LLM string.
- `mcp_server._dispatch` — `fetch_seed` branch (lazy gcloud auth) returning
  `{seed, rows, row_count, sql}`; register the Tool in `list_tools` and the JSON-RPC fallback list.
- `run_tool.py` — add `fetch_seed` to the docstring and the `_BQ_TOOLS` auth set.
- Docs: SKILL.md, `.github/agents/mockdata_copilot.agent.md`, AGENTS.md — add `fetch_seed` to the
  tool inventory, Step 0 intent ("no seed pasted → fetch_seed"), and the mandatory sequence.

Read-only only — `fetch_seed` runs a SELECT through the existing blocklisted executor. The agent
still PRESENTS INSERTs only; it never executes writes.

## What has changed

- **`tools/mockdata_tool.py`** — added `build_seed_sql(filters, limit, …)` (pure) and the
  `_SEED_FILTER_COLUMNS` whitelist. Builds a read-only `SELECT` of the 18 live
  `external_system_ids` columns (never `SELECT *`), optional whitelisted WHERE filters
  (values single-quoted via `_sq`), `LIMIT` clamped to 1..25. No existing function touched.
- **`tools/bigquery_tool.py`** — added `query_bigquery_rows(sql, rationale) -> (rows, error)`,
  a structured-output sibling of `query_bigquery` reusing the same `_pick_executor` +
  `validate_query` + `_bq_cli_execute` read-only path. No existing function touched.
- **`mcp_server.py`** — registered the `fetch_seed` Tool in `list_tools`, added the
  `fetch_seed` branch in `_dispatch` (lazy gcloud auth, returns `{seed, rows, row_count, sql,
  error}`), added `fetch_seed` to the JSON-RPC fallback tool list and the module docstring.
- **`run_tool.py`** — added `fetch_seed` to the docstring/examples and the `_BQ_TOOLS` auth set
  (so the CLI runs the lazy gcloud check on that path).
- **Docs** — `AGENTS.md`, `.claude/skills/mockdata-copilot/SKILL.md`,
  `.github/agents/mockdata_copilot.agent.md`: added `fetch_seed` to the tool inventory, the
  Step 0 intent table ("no seed pasted → `fetch_seed`, do NOT ask the user"), and the mandatory
  sequence (new step 2). Corrected the AGENTS.md "single live BQ access" claim to name both
  read-only SELECTs.

## Verification

**What was tested (all via `run_tool.py` against the live DV dataset, `@loreal.com` ADC):**
- `fetch_seed` no-filter `{}` → returned a real row (lucid `C2AU00001750974`), bounded 18-col
  `SELECT … LIMIT 1`, `error: null`.
- `fetch_seed` filtered `{signature:"YSL", isocountry:"AU", limit:2}` → 2 rows, WHERE clause
  correct, `row_count: 2`.
- **Injection / clamp unit checks**: generated `SELECT` passes
  `SafeBigQueryExecutor.validate_query` (read-only); `limit` 0→1, 999→25, "foo"→1; a
  non-whitelisted filter key carrying `1=1; DROP TABLE x` is dropped entirely (never reaches
  SQL); a value with a quote (`O'Brien`) is escaped to `O''Brien` and still validates.
- **End-to-end**: `fetch_seed` → `generate_mockdata` (vary `sourceconsumerid`+`lucid` increment,
  count 3) → 3 distinct lucids, `extsystemidskey` suffixed unique → `lookup_consumer` per lucid
  (seed lucid `exists:true`, two incremented lucids `exists:false`) → `generate_mockdata` with
  `absent_lucids` → `consumer_pii_sql` present with obviously-fake `mock+…@example.com` emails →
  `save_mockdata_report` wrote `mockdata/06262601.md`.

**What passed:** all of the above. Existing tools (`ensure_login`, `generate_mockdata`,
`lookup_consumer`, `save_mockdata_report`) regression-confirmed working in the same chain.

**Regression surface ruled out:**
- Existing functions in `mockdata_tool.py` / `bigquery_tool.py` were not modified — `build_seed_sql`
  and `query_bigquery_rows` are new additions (diff is insert-only for those files). The
  `query_bigquery` string API is untouched, so `lookup_consumer` behaviour is unchanged.
- `_dispatch` change is a new `elif` branch only; the existing branches and the `else` fallthrough
  are unchanged.
- `fetch_seed` is read-only — it routes through the same blocklist/validate path as
  `lookup_consumer` and can never emit a write (verified the generated SELECT passes the
  validator; `DANGEROUS_KEYWORDS` still apply).
- Module imports OK (`mcp_server`, `tools.mockdata_tool`, `tools.bigquery_tool`).
- Cost: `external_system_ids` is 365 MB (< the 500 MB scan ceiling); `fetch_seed` selects only the
  18 scalar columns (excludes the `datastream_metadata` STRUCT), so the scan stays under budget.

**Not committed:** `mockdata/*.md` reports (gitignored, may contain real consumer values from the
seed fetch), `schema.json`, and the unrelated pre-existing edits to `ticketasg_copilot_agent/*`.
