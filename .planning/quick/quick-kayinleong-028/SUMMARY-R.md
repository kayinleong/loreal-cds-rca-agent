---
status: complete
---
## Goal
Harden `_reexec_in_repo_venv` in the three run_tool.py files (OSError, Ctrl-C, signal exit codes), add tests, fix a garbled docstring.

## Changes Made
- `rca_copilot_agent/run_tool.py`, `ticketasg_copilot_agent/run_tool.py`, `mockdata_copilot_agent/run_tool.py` (`_reexec_in_repo_venv`): OSError -> stderr recreate hint + exit 1; KeyboardInterrupt -> exit 130; negative rc -> 128+N.
- Tests: `rca_copilot_agent/tests/test_run_tool.py`, `ticketasg_copilot_agent/tests/test_run_tool_reexec.py`, `mockdata_copilot_agent/tests/test_run_tool_reexec.py`: ReexecFailureTests + RealReexecTests (real subprocess, fake .venv/bin/python in a temp repo, skipped on Windows).
- `rca_copilot_agent/tools/bigquery_tool.py:597`: docstring wording fixed.

## Verification
rca 138 tests OK, ticketasg 14 OK, mockdata 14 OK (python3.12); `/usr/bin/python3 <pkg>/run_tool.py --help` rc 0 for all three; the three shared functions are byte-identical (ast.get_source_segment).

## Regression
Only the subprocess.call tail changed; existing mocked re-exec tests still pass; no-op paths untouched.

## Blockers
None.
