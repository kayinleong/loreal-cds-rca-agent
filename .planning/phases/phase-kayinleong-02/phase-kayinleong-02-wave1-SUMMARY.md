---
phase: phase-kayinleong-02
plan: wave1
subsystem: api
tags: [mockdata, bigquery, gcp, python, config]
status: complete

requires: []
provides:
  - mockdata_copilot_agent Python package (importable from repo root)
  - config.py with MockDataConfig (DV bq_project + bq_dataset + output_dir)
  - load_mockdata_config() reading BQ_PROJECT / BQ_DATASET / MOCKDATA_OUTPUT_DIR overrides
  - mockdata/ gitignored in the PII output block
affects: [wave2, wave3, wave4, wave5]

tech-stack:
  added: []
  patterns: [config-from-env, dataclass-config, dv-project-owned-in-config]

key-files:
  created:
    - mockdata_copilot_agent/__init__.py
    - mockdata_copilot_agent/tools/__init__.py
    - mockdata_copilot_agent/config.py
  modified:
    - .gitignore

key-decisions:
  - "MockDataConfig owns the DV defaults (oa-apmena-spacecds-ap-dv / space_cds_b2c_ds_replica_ase1_dv_public) so the reused gcloud/bigquery tool files never need editing — honors CLAUDE.md 'no hardcoded project outside config.py'"
  - "ServiceNowConfig + SmtpConfig + load_config + load_smtp_config dropped entirely; MockDataConfig is the sole public config surface (no SNOW/SMTP)"
  - "mockdata/ uses a no-leading-slash gitignore pattern so it matches both <pkg>/mockdata/ and a repo-root mockdata/"

patterns-established:
  - "_PKG_DIR + _load_env_file + _find_env_data helpers copied verbatim from ticketasg config; dataclasses swapped"
  - "DV bq_project default lives in config; Wave 4 startup will os.environ.setdefault('BQ_PROJECT', cfg.bq_project) before ensure_gcloud_auth()"

requirements-completed:
  - phase-kayinleong-02

duration: ~6min
completed: 2026-06-24
---

# Phase phase-kayinleong-02 Wave 1 Summary

**mockdata_copilot_agent package scaffold with a stripped config.py exposing MockDataConfig (DV project/dataset/output dir, no SNOW/SMTP) and a mockdata/ gitignore entry.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-06-24
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Importable `mockdata_copilot_agent` Python package created (package + tools sub-package markers)
- `config.py` defines `MockDataConfig` dataclass with `bq_project` (default DV `oa-apmena-spacecds-ap-dv`), `bq_dataset` (default `space_cds_b2c_ds_replica_ase1_dv_public`), and `output_dir` (default `<pkg>/mockdata`)
- `load_mockdata_config()` reads `BQ_PROJECT`, `BQ_DATASET`, `MOCKDATA_OUTPUT_DIR` env overrides; env takes precedence over `.env`
- `ServiceNowConfig`, `SmtpConfig`, `load_config`, `load_smtp_config` deliberately omitted — no cookie/x_user_token/SMTP fields anywhere
- `.gitignore` gains a single `mockdata/` line in the PII output-dir block

## Task Commits

1. **Task 1: Package __init__ markers** — `812098cd`
2. **Task 2: config.py with MockDataConfig (TDD — RED confirmed import failure, then GREEN impl)** — `812098cd`
3. **Task 3: Add mockdata/ to .gitignore PII block** — `812098cd`

(All three tasks committed together as the single wave commit `812098cd`, per the orchestrator's "commit the wave" instruction.)

## Files Created/Modified
- `mockdata_copilot_agent/__init__.py` — package marker; LLM-agnostic + "presents SQL only" comment
- `mockdata_copilot_agent/tools/__init__.py` — tools sub-package marker, no LLM calls
- `mockdata_copilot_agent/config.py` — `MockDataConfig` dataclass + `load_mockdata_config()`; copied `_PKG_DIR`/`_load_env_file`/`_find_env_data` helpers from ticketasg
- `.gitignore` — added `mockdata/` after `rca_reports/` in the PII block

## Verification

All commands run from repo root. Note: the environment exposes `python3` (3.13.7), not `python`; the plan's `python` verify commands were run with `python3` (functionally equivalent).

| # | Command | Expected | Result |
|---|---------|----------|--------|
| 1 | `python3 -c "import mockdata_copilot_agent"` | exit 0, `OK` | PASS |
| 2 | `... from config import load_mockdata_config; print(c.bq_project, c.bq_dataset)` | `oa-apmena-spacecds-ap-dv space_cds_b2c_ds_replica_ase1_dv_public` | PASS |
| 3 | `... assert not hasattr(config,'ServiceNowConfig') and not hasattr(config,'SmtpConfig')` | `no SNOW/SMTP OK` | PASS |
| 4 | `grep -v '^#' .gitignore \| grep -c '^mockdata/$'` | `1` | PASS |
| 5 (behavior) | `BQ_PROJECT=custom-proj MOCKDATA_OUTPUT_DIR=/tmp/md ...` | overrides applied | PASS (`ENV-OVERRIDE PASS`) |

`git check-ignore` confirmed both `mockdata_copilot_agent/mockdata/test.md` and repo-root `mockdata/test.md` are ignored.

## Decisions Made
- DV project/dataset defaults are owned exclusively by `MockDataConfig` (no `load_config` alias), keeping the reused tool files untouched and CLAUDE.md-compliant.

## Deviations from Plan
- **[Tooling]** `python` is not on PATH in this environment; used `python3` for all verify commands. No behavioral difference; all checks pass.
- TDD used for config.py: confirmed RED (`ModuleNotFoundError: No module named 'config'`) before writing the implementation, then GREEN. Per the orchestrator's "commit the wave" instruction, the RED/GREEN/Task-1/Task-3 changes were folded into one wave commit rather than separate test/feat commits.

## Issues Encountered
None.

## Threat Mitigations Applied
- **T-wave1-01 (Information Disclosure):** `.gitignore` line `mockdata/` keeps synthetic-PII output out of git (verified via `git check-ignore`).
- **T-wave1-03 (Information Disclosure):** `_find_env_data()` copied verbatim from ticketasg; never logs env values; no COOKIE/X_USERTOKEN/SMTP fields exist to leak.

## Next Wave Readiness
- Package is importable; `from mockdata_copilot_agent.config import load_mockdata_config` works from repo root.
- Wave 2+ tools can import the DV project/dataset from `MockDataConfig`; Wave 4 startup should `os.environ.setdefault("BQ_PROJECT", cfg.bq_project)` before `ensure_gcloud_auth()`.
- `.docs/` sample files (`external_system_ids mock up.sql`, `external_system_ids.xlsx`) remain untracked and were intentionally NOT staged in this wave.

## Self-Check: PASSED
- `mockdata_copilot_agent/__init__.py` — FOUND
- `mockdata_copilot_agent/tools/__init__.py` — FOUND
- `mockdata_copilot_agent/config.py` — FOUND
- `.gitignore` `mockdata/` line — FOUND
- Commit `812098cd` — FOUND in git log

---
*Phase: phase-kayinleong-02*
*Completed: 2026-06-24*
