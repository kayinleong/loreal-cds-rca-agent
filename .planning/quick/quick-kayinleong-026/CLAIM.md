# Claim: quick-kayinleong-026
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-26
- status: in-progress
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

(pending)

## Verification

(pending)
