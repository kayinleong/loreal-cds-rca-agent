---
wave: 1
depends_on: []
files_modified:
  - mockdata_copilot_agent/__init__.py
  - mockdata_copilot_agent/tools/__init__.py
  - mockdata_copilot_agent/config.py
  - .gitignore
autonomous: true
requirements:
  - phase-kayinleong-02
must_haves:
  - mockdata_copilot_agent/ package directory exists with __init__.py (importable from repo root)
  - config.py defines MockDataConfig dataclass with bq_project (default oa-apmena-spacecds-ap-dv), bq_dataset (default space_cds_b2c_ds_replica_ase1_dv_public), output_dir (default <pkg>/mockdata)
  - load_mockdata_config() reads BQ_PROJECT, BQ_DATASET, MOCKDATA_OUTPUT_DIR env overrides
  - config.py has NO ServiceNowConfig and NO SmtpConfig (SNOW/SMTP dropped per CONTEXT)
  - tools/__init__.py exists as an empty package marker
  - .gitignore contains a literal line `mockdata/` inside the PII output-dir block
---

<objective>
Create the package scaffold for the new Copilot-only agent: `__init__.py` markers, a stripped
`config.py` exposing a new `MockDataConfig` (DV project + dataset + output dir, NO SNOW/SMTP),
and a `.gitignore` entry that keeps the synthetic-PII output directory out of git.

Purpose: Every later wave imports from this package. The DV project/dataset must live in
`config.py` (never hardcoded in the reused tool files), and `mockdata/` must be gitignored
before any output file can be generated.

Output: 4 files touched — `mockdata_copilot_agent/__init__.py`,
`mockdata_copilot_agent/tools/__init__.py`, `mockdata_copilot_agent/config.py`, and an edit to
`.gitignore`.

## Artifacts this wave produces
- New files: `mockdata_copilot_agent/__init__.py`, `mockdata_copilot_agent/tools/__init__.py`,
  `mockdata_copilot_agent/config.py`
- Edited file: `.gitignore` (one new line `mockdata/`)
- New config fields: `MockDataConfig.bq_project`, `MockDataConfig.bq_dataset`,
  `MockDataConfig.output_dir`
- New function: `load_mockdata_config(env_file=".env") -> MockDataConfig`
- New env-var overrides: `BQ_PROJECT`, `BQ_DATASET`, `MOCKDATA_OUTPUT_DIR`
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/CLAUDE.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-CONTEXT.md
@/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents/.planning/phases/phase-kayinleong-02/02-RESEARCH.md

<interfaces>
<!-- Copy target from ticketasg_copilot_agent/config.py — STRIP SNOW + SMTP, ADD MockDataConfig -->

The ticketasg config (the analog) exposes ServiceNowConfig + SmtpConfig with these helpers that
are copied VERBATIM (structure only — the dataclasses themselves are replaced):
  _PKG_DIR = Path(__file__).resolve().parent
  _load_env_file(env_path) -> dict
  _find_env_data(env_file) -> dict

New public interface for this package:
```python
@dataclass
class MockDataConfig:
    bq_project: str   # default "oa-apmena-spacecds-ap-dv"  (DV — differs from rca/ticketasg PD)
    bq_dataset: str   # default "space_cds_b2c_ds_replica_ase1_dv_public"
    output_dir: str   # default str(_PKG_DIR / "mockdata")

def load_mockdata_config(env_file: str = ".env") -> MockDataConfig: ...
```

DV-project rationale [from 02-RESEARCH Q1]: the reused gcloud_tool/bigquery_tool default the
project to PD via `os.environ.get("BQ_PROJECT", "oa-apmena-spacecds-ap-pd")`. To honor the
CLAUDE.md "no hardcoded project outside config.py" rule WITHOUT editing the shared tool files,
this config owns the DV default; Wave 4 startup does `os.environ.setdefault("BQ_PROJECT",
cfg.bq_project)` BEFORE calling `ensure_gcloud_auth()`.

[ASSUMPTION A3 — confirm with user]: schema.json declares the DV ASE1 dataset as "same schema
as primary". The dataset name `space_cds_b2c_ds_replica_ase1_dv_public` is taken from CONTEXT.md
and 02-RESEARCH. If the live DV dataset name differs, only this config default changes.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create package __init__ markers</name>
  <files>
    mockdata_copilot_agent/__init__.py
    mockdata_copilot_agent/tools/__init__.py
  </files>
  <read_first>
    ticketasg_copilot_agent/__init__.py — exact marker-comment style to mirror
    ticketasg_copilot_agent/tools/__init__.py — empty tools marker style
  </read_first>
  <action>
Create `mockdata_copilot_agent/__init__.py` with exactly:
```python
# Mock Data Copilot Agent — generates mock external_system_ids / consumer_pii SQL for L'Oreal CDS B2C DV.
# No LLM calls in this package; GitHub Copilot / Claude provides the reasoning.
# This agent PRESENTS SQL only — it never executes writes against any database.
```

Create `mockdata_copilot_agent/tools/__init__.py` with exactly:
```python
# Mock Data tools — pure functions + read-only BigQuery lookup. No LLM calls.
```

Both are package markers. Do not add imports or other code.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "import mockdata_copilot_agent; print('OK')"</automated>
  </verify>
  <done>
    Both files exist. `python -c "import mockdata_copilot_agent"` exits 0 from repo root and
    prints `OK`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create config.py with MockDataConfig (DV project/dataset, no SNOW/SMTP)</name>
  <files>
    mockdata_copilot_agent/config.py
  </files>
  <read_first>
    ticketasg_copilot_agent/config.py — copy the _PKG_DIR + _load_env_file + _find_env_data helpers verbatim; REPLACE the ServiceNowConfig/SmtpConfig dataclasses with MockDataConfig
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 166-176 — DV-project defaulting rationale (Q1)
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 466-477 — startup project-defaulting code example
  </read_first>
  <behavior>
    - load_mockdata_config() with no .env returns MockDataConfig with bq_project == "oa-apmena-spacecds-ap-dv"
    - load_mockdata_config() with no .env returns bq_dataset == "space_cds_b2c_ds_replica_ase1_dv_public"
    - load_mockdata_config() with no .env returns output_dir ending in "mockdata"
    - load_mockdata_config() with BQ_PROJECT env set to "custom-proj" returns bq_project == "custom-proj"
    - load_mockdata_config() with MOCKDATA_OUTPUT_DIR env set to "/tmp/md" returns output_dir == "/tmp/md"
  </behavior>
  <action>
Create `mockdata_copilot_agent/config.py`. Copy ONLY these elements from
`ticketasg_copilot_agent/config.py` verbatim:
  - the `from __future__ import annotations` / `import os` / `from dataclasses import dataclass`
    / `from pathlib import Path` imports,
  - the `_PKG_DIR = Path(__file__).resolve().parent` constant,
  - the `_load_env_file(env_path)` helper,
  - the `_find_env_data(env_file)` helper.

Then REPLACE all ServiceNow/SMTP content with this new surface (do NOT carry over
`ServiceNowConfig`, `SmtpConfig`, `load_config`, or `load_smtp_config`):

Module docstring must state:
```
Configuration — Mock Data Copilot Agent (GCP / BigQuery DV only).
No LLM configuration; GitHub Copilot / Claude provides the reasoning.
No ServiceNow, no SMTP.

Optional environment variables (or .env keys):
    BQ_PROJECT            GCP project for the read-only consumer_pii lookup
                          (default: oa-apmena-spacecds-ap-dv  — the DV project)
    BQ_DATASET            DV dataset name
                          (default: space_cds_b2c_ds_replica_ase1_dv_public)
    MOCKDATA_OUTPUT_DIR   Directory for generated mockdata/<MMDDYYSS>.md files
                          (default: <pkg_dir>/mockdata)

BigQuery uses gcloud ADC — no credential files. Run once:
    gcloud auth application-default login
```

Dataclass + loader:
```python
@dataclass
class MockDataConfig:
    bq_project: str   # DV project — differs from rca/ticketasg PD default
    bq_dataset: str
    output_dir: str   # generated mockdata/<MMDDYYSS>.md land here


def load_mockdata_config(env_file: str = ".env") -> MockDataConfig:
    """Load mock-data config from env vars, falling back to a .env file.
    Environment variables take precedence over .env values."""
    env_data = _find_env_data(env_file)

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_data.get(key, default)

    return MockDataConfig(
        bq_project=get("BQ_PROJECT", "oa-apmena-spacecds-ap-dv"),
        bq_dataset=get("BQ_DATASET", "space_cds_b2c_ds_replica_ase1_dv_public"),
        output_dir=get("MOCKDATA_OUTPUT_DIR", str(_PKG_DIR / "mockdata")),
    )
```

The `_PKG_DIR` line in the new file resolves to `mockdata_copilot_agent/` because this is
`mockdata_copilot_agent/config.py` — do not change it. Do not add a `load_config` alias; the
DV defaults must come exclusively from `MockDataConfig`.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && python -c "
import sys; sys.path.insert(0,'mockdata_copilot_agent')
from config import load_mockdata_config, MockDataConfig
import config as _c
assert not hasattr(_c,'ServiceNowConfig'), 'ServiceNowConfig must be dropped'
assert not hasattr(_c,'SmtpConfig'), 'SmtpConfig must be dropped'
cfg = load_mockdata_config()
assert cfg.bq_project == 'oa-apmena-spacecds-ap-dv', cfg.bq_project
assert cfg.bq_dataset == 'space_cds_b2c_ds_replica_ase1_dv_public', cfg.bq_dataset
assert cfg.output_dir.endswith('mockdata'), cfg.output_dir
print('PASS')
"</automated>
  </verify>
  <done>
    `load_mockdata_config()` returns `MockDataConfig` with `bq_project ==
    "oa-apmena-spacecds-ap-dv"`, `bq_dataset == "space_cds_b2c_ds_replica_ase1_dv_public"`, and
    `output_dir` ending in `mockdata`. The module has NO `ServiceNowConfig` and NO `SmtpConfig`
    attributes. Verify command prints `PASS`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Add mockdata/ to .gitignore PII block</name>
  <files>
    .gitignore
  </files>
  <read_first>
    .gitignore lines 200-205 — the "ServiceNow incident data (may contain PII)" block listing my_reports/ attachments/ rca_reports/
    .planning/phases/phase-kayinleong-02/02-RESEARCH.md lines 268-275 — gitignore note (Q7) confirming mockdata/ is NOT yet present
  </read_first>
  <action>
Edit `.gitignore`. Locate the existing PII output-dir block:
```
# ServiceNow incident data (may contain PII)
my_reports/
attachments/
rca_reports/
```
Add a single line `mockdata/` to that block, immediately after `rca_reports/`, so the block
reads:
```
# ServiceNow incident data (may contain PII)
my_reports/
attachments/
rca_reports/
mockdata/
```
Use a no-leading-slash pattern (`mockdata/`) so it matches the dir at any depth — covering both
`mockdata_copilot_agent/mockdata/` (the default) and a repo-root `mockdata/`. Do NOT remove or
reorder the existing lines. Make exactly one addition.
  </action>
  <verify>
    <automated>cd "/Users/ka.yin.leong/Documents/Accenture Development/Loreal L2L3 Agents" && grep -v '^#' .gitignore | grep -c '^mockdata/$'</automated>
  </verify>
  <done>
    `.gitignore` contains a line that is exactly `mockdata/`. The verify command (which strips
    comment lines first) returns `1`. The pre-existing `my_reports/`, `attachments/`, and
    `rca_reports/` lines are unchanged.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| filesystem → config.py | `.env` read from cwd or package dir; an attacker with filesystem write could inject env values (BQ_PROJECT/BQ_DATASET) |
| generated output → git | `mockdata/` may contain synthetic PII; gitignore prevents accidental staging |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave1-01 | Information Disclosure | mockdata/ output dir | mitigate | `.gitignore` line `mockdata/` keeps synthetic-PII output out of git; CLAUDE.md "never stage" rule reinforced in later waves |
| T-wave1-02 | Tampering | config.py BQ_PROJECT/BQ_DATASET env | accept | Config values are non-secret project/dataset identifiers; integrity maintained via git; lookup is read-only regardless of project value |
| T-wave1-03 | Information Disclosure | config.py `_find_env_data()` | mitigate | Helper copied verbatim from ticketasg; never logs env values; no COOKIE/X_USERTOKEN/SMTP fields exist to leak |
</threat_model>

<verification>
From repo root:
1. `python -c "import mockdata_copilot_agent"` — exits 0
2. `python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); from config import load_mockdata_config; c=load_mockdata_config(); print(c.bq_project, c.bq_dataset)"` — prints `oa-apmena-spacecds-ap-dv space_cds_b2c_ds_replica_ase1_dv_public`
3. `python -c "import sys; sys.path.insert(0,'mockdata_copilot_agent'); import config; assert not hasattr(config,'ServiceNowConfig') and not hasattr(config,'SmtpConfig'); print('no SNOW/SMTP OK')"` — prints `no SNOW/SMTP OK`
4. `grep -v '^#' .gitignore | grep -c '^mockdata/$'` — prints `1`
</verification>

<success_criteria>
- `mockdata_copilot_agent` package is importable from repo root
- `MockDataConfig` exposes `bq_project`, `bq_dataset`, `output_dir`
- `load_mockdata_config()` defaults `bq_project` to `oa-apmena-spacecds-ap-dv` (DV, not PD)
- `BQ_PROJECT`, `BQ_DATASET`, `MOCKDATA_OUTPUT_DIR` env vars override the defaults
- `config.py` contains no ServiceNow or SMTP config (those are dropped)
- `.gitignore` contains the line `mockdata/`
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-02/phase-kayinleong-02-wave1-SUMMARY.md`
</output>
