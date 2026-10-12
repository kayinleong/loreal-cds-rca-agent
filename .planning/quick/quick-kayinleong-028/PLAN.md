# Plan: quick-kayinleong-028 — one-command setup for the 3 Copilot agents, clean deps, remove legacy

Inputs: `research-deps.md` (dependency audit), `research-install.md` (install approach). User decisions 2026-10-12:
setup installs **all 3 Copilot agents**; delete `rca_agent/` (done, `1c99986`); remove MCP-server mode from
`rca_copilot_agent` (CLI only); rewrite repo `CLAUDE.md`; clean `requirements.txt`.

## Design (locked)
- One shared venv: `<repo>/.venv`. Python **≥ 3.10, 64-bit**; preference 3.12 → 3.11 → 3.13 → 3.10 → newer (warn ≥ 3.14: torch wheels may lag).
- `setup.sh` (macOS/Linux) and `setup.cmd` (Windows, **not** PowerShell — GPO can block .ps1) only locate a suitable
  Python by *probing* candidates, then run `scripts/bootstrap.py "$@"` (stdlib only).
- `scripts/bootstrap.py`: create/repair venv → `pip install --upgrade pip` (pip ≥ 24.2 uses the OS trust store on 3.10+)
  → install each agent independently with `--only-binary=:all:` → per-agent result table → run `scripts/doctor.py`.
- `scripts/doctor.py`: offline self-check (Python, packages per agent, gcloud/bq, Edge, schema.json, .env presence,
  gcloud account domain, proxy/cert env var *names*). Never reads `.env`, never logs in, never calls SNOW/BQ.
- Each `run_tool.py` auto-re-runs itself inside `<repo>/.venv` when launched by another Python → no venv activation.
- Dependencies: direct deps only, major-bounded ranges; heavy/optional features in opt-in files.

## Contracts

### Requirement files (J writes; K reads at runtime; no `-r` inside per-agent files)
| File | Content |
|---|---|
| `rca_copilot_agent/requirements.txt` | `requests>=2.32,<3`, `urllib3>=1.26,<3`, `python-dotenv>=1.0,<2`, `playwright>=1.40,<2` |
| `ticketasg_copilot_agent/requirements.txt` | same four |
| `ticketasg_copilot_agent/requirements-retrieval.txt` | `sentence-transformers>=2.5,<6`, `numpy>=1.24,<3` (kNN; installed by default, failure tolerated) |
| `mockdata_copilot_agent/requirements.txt` | `openpyxl>=3.1,<4` |
| `requirements-mcp.txt` (root) | `mcp>=1.2,<2` — only for ticketasg/mockdata `mcp_server.py`; opt-in `--with-mcp` |
| `requirements.txt` (root) | `-r` the four agent files above (not mcp) — keeps `pip install -r requirements.txt` working |

### bootstrap.py CLI (K)
`--agents rca_copilot,ticketasg,mockdata` (default all) · `--skip-retrieval` · `--with-mcp` · `--index-url URL` ·
`--extra-index-url URL` · `--wheelhouse DIR` (→ `--no-index --find-links DIR`) · `--proxy URL` · `--allow-source`
(drop `--only-binary`) · `--recreate` · `--no-doctor`. Exit: 0 all ok · 2 partial (an agent or extra failed, rca_copilot ok) · 1 fatal.

### run_tool venv re-exec (N implements in rca_copilot; P copies verbatim to the other two)
If `<repo>/.venv/{bin/python | Scripts/python.exe}` exists, `realpath(sys.prefix) != realpath(<repo>/.venv)` and
`RCA_VENV_REEXEC` is unset → `subprocess.call([venv_py, this_file, *argv], env=env+{RCA_VENV_REEXEC:1})`, inherit
stdio, `sys.exit(rc)`. Runs first in `main()`. Missing third-party module afterwards → message telling the user to run
`./setup.sh` / `setup.cmd`.

## Waves
| Wave | Task | Owns (exclusive) |
|---|---|---|
| 1 | **N** rca_copilot CLI-only: move `_dispatch`+helpers to `dispatcher.py`, delete `mcp_server.py`, run_tool import + venv re-exec + missing-module hint, drop ADC step from `ensure_gcloud_auth`, update tests | `rca_copilot_agent/**/*.py` (incl. tests), not docs/requirements |
| 1 | **J** requirement files + coverage test (every third-party import in each package is declared) | the 6 requirement files, `scripts/tests/test_requirements_coverage.py` |
| 1 | **K** bootstrap, doctor, wrappers, VS Code tasks + tests | `scripts/bootstrap.py`, `scripts/doctor.py`, `setup.sh`, `setup.cmd`, `.vscode/tasks.json`, `scripts/tests/test_bootstrap_doctor.py` |
| 2 | **P** copy venv re-exec into ticketasg/mockdata `run_tool.py` | those two files |
| 2 | **L1** rca_copilot docs · **L2** ticketasg + mockdata docs · **L3** root `CLAUDE.md` rewrite + new root `README.md` | disjoint doc files |
| 3 | Verify: all test suites; real end-to-end `setup.sh` in a scratch export of the repo (real PyPI); doctor; re-exec from system Python 3.9; 2 parallel reviewers (setup scripts incl. Windows `.cmd`; dispatcher move) | read-only |

## Out of scope
MCP mode in ticketasg/mockdata (kept, opt-in); shared-module refactor; runtime truststore injection for `requests`
(doctor only hints `REQUESTS_CA_BUNDLE`); live Windows run (no Windows host — reviewer + static checks).
