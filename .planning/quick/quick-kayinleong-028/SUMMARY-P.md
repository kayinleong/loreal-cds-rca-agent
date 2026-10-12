---
status: complete
---
## Goal
Give ticketasg_copilot_agent and mockdata_copilot_agent run_tool.py the zero-activation venv re-exec and missing-package hint used by rca_copilot_agent.

## Changes Made
- `ticketasg_copilot_agent/run_tool.py`, `mockdata_copilot_agent/run_tool.py` — docstring note, REEXEC_ENV/_LOCAL_MODULES, verbatim `_repo_venv_python`/`_reexec_in_repo_venv`/`_missing_package_hint`, `main()` = re-exec + wrapper around `_main()` (old body); `except ModuleNotFoundError: raise` before each broad `except Exception`.
- New `tests/test_run_tool_reexec.py` in both packages (8 tests each).

## Verification
Both test files pass (python3.12 bare); `--help` smoke on /usr/bin/python3 (3.9) OK; helper functions byte-identical across three run_tool.py files.

## Regression
Dispatch, tools, MCP code untouched; test_config.py functions run directly.

## Blockers
None.
