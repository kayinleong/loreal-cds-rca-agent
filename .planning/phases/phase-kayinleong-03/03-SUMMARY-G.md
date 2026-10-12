---
status: complete
---
## Goal
Fix review findings 1-8 in rca_report_tool.py (executor G).

## Changes Made
- `rca_copilot_agent/tools/rca_report_tool.py` — str/comma/list/None incident filter; tolerant heading parser (`_heading_name`); evidence window (`save_report`, `load_evidence(since=)`, `RCA_SESSION_WINDOW_HOURS`); stale unfiltered pending cutoff; `_registry_lock` around save/mark_emailed; abspath in registry; `_clean_inc` title sanitising; `MARS Ops`/`Azure team` excluded from shortform warnings (`_NO_WARN_FORMS`).
- `rca_copilot_agent/tests/test_rca_report_tool.py` — 23 new tests (42 total in file).
- Timestamps now timezone-aware ISO (local offset) for `ts`, `saved_at`, `emailed_at`, `generated_at`; naive legacy values parsed as local.

## Verification
Full suite `unittest discover`: 119 tests OK. py_compile OK. Regex checked for backtracking on long punctuation input.

## Regression
Public signatures unchanged (additions: `load_evidence(..., since=None)`, `pending_reports` accepts str/tuple). `save_report`/`mark_emailed` return and registry fields unchanged (path now absolute).

## Blockers
None. Inline-body bold headings (`**WHAT HAPPENED:** text`) are intentionally not treated as headings.
