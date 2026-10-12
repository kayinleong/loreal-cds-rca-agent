---
status: complete
---
## Goal
Make rca_copilot_agent/run_tool.py shell-safe on macOS and Windows (W5, W6).

## Changes Made
- `rca_copilot_agent/run_tool.py` — docstring/epilog rewritten; new `_build_parser()`, `_load_arguments()`; `--json-file`, `--json -`, `--arg`; UTF-8 stdout/stderr reconfigure at start of `main()`.
- `.gitignore` — appended `.rca_tmp/`.
- `rca_copilot_agent/tests/test_run_tool.py` — 14 offline unittest cases.

## Verification
py_compile OK; unittest 14/14 pass; `run_tool.py --help` renders.

## Regression
`--json '<obj>'` parses identically (dict required, same Error: style). Startup sequence and dispatch untouched.

## Blockers
None.
