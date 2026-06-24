# Claim: quick-kayinleong-025
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-24
- status: done
- summary: Implement the vary "increment" strategy in mockdata_copilot_agent/tools/mockdata_tool.py (auto-bump a seed value's trailing letter/number per row) and make unknown vary strategy strings raise a clear error instead of being silently emitted as literal values.

## What Will Change

`mockdata_copilot_agent/tools/mockdata_tool.py`:
- `_vary_value(strategy, row_index, seed_value)` — support the reserved string `"increment"` (auto-increment the seed value per row); raise `ValueError` for any other bare string strategy (footgun fix); lists continue to cycle.
- Add `_increment_suffix(value, offset)` — bump a trailing digit-run (numeric, width-preserving) or trailing letter (A→B…), used by the increment strategy.
- Document the `vary` contract in the `generate_external_system_ids` docstring.

Companion docs (`AGENTS.md`, `SKILL.md`, agent.md): brief note on the `vary` contract (list of values, or `"increment"`).

## What Has Changed

`mockdata_copilot_agent/tools/mockdata_tool.py`:
- Added `_increment_suffix(value, offset)` — bumps a trailing digit-run (numeric, width-preserving) or trailing letter (A→B…, wraps at Z); appends `-<offset>` as a last resort; passes through None/empty/offset-0.
- Reworked `_vary_value`: lists still cycle; the reserved string `"increment"` now calls `_increment_suffix` per row; any other bare string raises `ValueError` (no more silent literals); non-string scalars still treated as constants.
- Documented the `vary` contract in the `generate_external_system_ids` docstring.

Companion docs updated with the `vary` contract: `AGENTS.md` (new "Variation (`vary`) contract" subsection), `.claude/skills/mockdata-copilot/SKILL.md`, `.github/agents/mockdata_copilot.agent.md`.

## Verification

### What was tested
- Unit: `_increment_suffix("ID011000000001C", 0/1/2)` → C/D/E; `("ID0370", 2)` → `ID0372`; `("ID0160",1)` → `ID0161`; `(None,3)` → None.
- `_vary_value("incrment", …)` raises `ValueError` (typo fails loudly).
- `generate_external_system_ids(seed, {"sourceconsumerid":"increment", "signature":[...]}, 3)` → sourceconsumerid C/D/E, no literal `'increment'` in SQL.
- List strategy unchanged (`signature:["A","B"]` → A,B).
- CLI end-to-end: `run_tool.py generate_mockdata` with `"sourceconsumerid":"increment"` → C/D/E in the emitted GoogleSQL.
- Regression smoke: live 18-col esi / 32-col cpi still load; GoogleSQL shape intact (no `::` casts, `TIMESTAMP '…'`); `consumer_pii` STRUCT → NULL; lookup SQL passes the blocklist.

### What passed
All of the above.

### Regression Report
- Behavior change is confined to `vary` strategy resolution. Previously a bare string became a literal constant; now `"increment"` is a real strategy and other bare strings error (intended footgun fix). No internal caller passes a bare non-`increment` string — `mcp_server.generate_mockdata` / `run_tool.py` pass user JSON straight through, and committed verifies use lists. Lists and `extsystemidskey` auto-increment are unchanged. No change to BQ access, the blocklist, the GoogleSQL renderer, or the schema-driven column logic. New `_increment_suffix` is a pure function. No secrets touched.
