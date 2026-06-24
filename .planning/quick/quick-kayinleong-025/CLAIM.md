# Claim: quick-kayinleong-025
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-06-24
- status: in-progress
- summary: Implement the vary "increment" strategy in mockdata_copilot_agent/tools/mockdata_tool.py (auto-bump a seed value's trailing letter/number per row) and make unknown vary strategy strings raise a clear error instead of being silently emitted as literal values.

## What Will Change

`mockdata_copilot_agent/tools/mockdata_tool.py`:
- `_vary_value(strategy, row_index, seed_value)` — support the reserved string `"increment"` (auto-increment the seed value per row); raise `ValueError` for any other bare string strategy (footgun fix); lists continue to cycle.
- Add `_increment_suffix(value, offset)` — bump a trailing digit-run (numeric, width-preserving) or trailing letter (A→B…), used by the increment strategy.
- Document the `vary` contract in the `generate_external_system_ids` docstring.

Companion docs (`AGENTS.md`, `SKILL.md`, agent.md): brief note on the `vary` contract (list of values, or `"increment"`).

## What Has Changed

(filled during execution)

## Verification

(filled during execution — Regression Report required before done)
