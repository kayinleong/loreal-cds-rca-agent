---
status: complete
---
## Goal
Fix review findings 1-12 and close test gaps for setup.sh/setup.cmd/bootstrap/doctor (claim quick-kayinleong-028).

## Changes Made
- `setup.cmd` (rewritten, CRLF): no delayed expansion, `%*` passthrough, Explorer detection via `%cmdcmdline%` + `pause` on every exit (SETUP_NOPAUSE opt-out), errorlevel saved to RC before pause.
- `.gitattributes` (new): 4 eol rules.
- `setup.sh`: absolute candidates first, versioned names, then bare names; `/usr/bin/python3` skipped when `xcode-select -p` fails.
- `scripts/bootstrap.py`: `--no-input --retries 3 --timeout 30` in build_pip_args; `stdin=DEVNULL`; specific-marker hints + `is_network_failure`; SSL hint first with PIP_CERT; early stop on pip-upgrade network failure; Windows long-path warning/hint; stream reconfigure + safe writes; `--recreate` from inside .venv refused; KeyboardInterrupt -> 130.
- `scripts/doctor.py`: gcloud `stdin=DEVNULL`; maybe_reexec OSError fallback; reconfigure; KeyboardInterrupt -> 130.
- `scripts/tests/test_bootstrap_doctor.py`: 52 tests total (was ~28), new MainFlow, HintMatching, DoctorRobustness, static script checks.

## Verification
unittest discover (3.12): 52 OK incl. coverage test; `sh -n setup.sh` ok; setup.sh selection dry-run picks ~/.local/bin/python3.12; `/usr/bin/python3 scripts/bootstrap.py --help` prints friendly 3.9 message; 3.12 --help works.

## Regression
Real bootstrap/setup not run (orchestrator re-runs scratch e2e). Pip arg changes additive; install_agent/summarize logic unchanged.

## Blockers
setup.cmd not executed on Windows (static checks only).
