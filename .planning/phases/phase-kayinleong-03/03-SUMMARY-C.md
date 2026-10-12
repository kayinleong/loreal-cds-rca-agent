---
status: complete
---
## Goal
Add pure module `rca_copilot_agent/tools/rca_report_tool.py` (interface contract C): canonical RCA template, validation, evidence log, report rendering/saving, and a persistent email registry.

## Changes Made
- `rca_copilot_agent/tools/rca_report_tool.py` (new) — all contract C functions.
- `rca_copilot_agent/tests/test_rca_report_tool.py` (new) — 19 offline unittest cases.

## Verification
py_compile OK; `unittest discover ... test_rca_report_tool.py` -> 19 tests OK.

## Regression
No existing file modified; module not yet imported by anything (wave 2 wires it).

## Blockers
None. Bare single-word shortforms (LOY, MARS, HIP, CRM, Ops...) are intentionally not warned (legit system names); multi-word shortforms plus iBeauty/SFCC are.
