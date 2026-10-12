---
status: complete
---
## Goal
One-command setup (setup.sh / setup.cmd -> scripts/bootstrap.py) plus offline doctor and VS Code tasks.

## Changes Made
- `scripts/_reqs.py` (new, shared parser/agent table/re-exec rule), `scripts/bootstrap.py`, `scripts/doctor.py`
- `setup.sh` (executable), `setup.cmd` (CRLF, ASCII), `.vscode/tasks.json`
- `scripts/tests/test_bootstrap_doctor.py` (28 tests)

## Verification
28 unit tests pass on Python 3.12; `sh -n setup.sh` ok; bootstrap --help on 3.9 prints friendly message; real doctor run on this Mac does not crash, masks account, prints no secrets.

## Regression
New files only; no existing file modified.

## Blockers
setup.cmd not executed (no Windows host); bootstrap not run for real (orchestrator's scratch e2e). git mode +x for setup.sh needs `git update-index --chmod=+x`.
