---
wave: 1
depends_on: []
files_modified:
  - ticketasg_copilot_agent/__init__.py
  - ticketasg_copilot_agent/config.py
  - ticketasg_copilot_agent/tools/__init__.py
  - ticketasg_copilot_agent/assignment_rules.json
autonomous: true
requirements:
  - phase-kayinleong-01
must_haves:
  - ticketasg_copilot_agent/ package directory exists with __init__.py
  - config.py has ServiceNowConfig with assignment_rules_file field
  - load_config() reads ASSIGNMENT_RULES_FILE env var
  - assignment_rules.json has all 10 L2 groups with keyword arrays
  - tools/__init__.py exists as package marker
---

<objective>
Create the package scaffold: `__init__.py` markers, `config.py` (with new `assignment_rules_file`
field), and `assignment_rules.json` (the routing matrix that drives the entire agent).

Purpose: All subsequent waves import from this package. The routing matrix must be committed so
the executor can validate keyword coverage without live SNOW access.

Output: 4 files — `__init__.py`, `tools/__init__.py`, `config.py`, `assignment_rules.json`.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/CLAUDE.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/CLAIM.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/01-PATTERNS.md

<interfaces>
<!-- Copy target from rca_copilot_agent/config.py — extend, do not replace -->

From rca_copilot_agent/config.py:
```python
@dataclass
class ServiceNowConfig:
    instance_url: str
    cookie: str
    x_user_token: str
    reports_dir: str
    attachments_dir: str
    # ADD: assignment_rules_file: str

def load_config(env_file: str = ".env") -> ServiceNowConfig: ...
def load_smtp_config(env_file: str = ".env") -> SmtpConfig: ...
```

Routing matrix — [USER-CONFIRM]: keywords are inferred from group names (SharePoint was behind
SSO). Implement these values; user should verify before production use.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create package __init__ markers</name>
  <files>
    ticketasg_copilot_agent/__init__.py
    ticketasg_copilot_agent/tools/__init__.py
  </files>
  <read_first>
    rca_copilot_agent/__init__.py — exact comment text to update
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 34-49 — __init__.py pattern
  </read_first>
  <action>
Create `ticketasg_copilot_agent/__init__.py` with exactly:
```python
# Ticket Assignment Copilot Agent — ServiceNow ticket triage tools for GitHub Copilot
# No LLM calls in this package; GitHub Copilot provides the reasoning.
```

Create `ticketasg_copilot_agent/tools/__init__.py` with exactly:
```python
# Ticket Assignment tools — no LLM calls.
```

Both are empty package markers. Do not add imports or other code.
  </action>
  <verify>
    <automated>python -c "import ticketasg_copilot_agent" 2>&1 && echo OK</automated>
  </verify>
  <done>
    Both files exist. `python -c "import ticketasg_copilot_agent"` exits 0 from repo root.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create config.py with assignment_rules_file field</name>
  <files>
    ticketasg_copilot_agent/config.py
  </files>
  <read_first>
    rca_copilot_agent/config.py — copy verbatim, then add assignment_rules_file
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 54-116 — exact diff showing the one new field
  </read_first>
  <behavior>
    - load_config() with no .env returns ServiceNowConfig with assignment_rules_file ending in "assignment_rules.json"
    - load_config() with ASSIGNMENT_RULES_FILE env var set to "/tmp/custom.json" returns that path
    - SmtpConfig.enabled is False when SMTP_HOST is empty
  </behavior>
  <action>
Copy `rca_copilot_agent/config.py` verbatim. Make exactly these three changes:

1. Module docstring — add one line to the "Optional:" block:
   ```
   ASSIGNMENT_RULES_FILE  Path to assignment_rules.json (default: <pkg_dir>/assignment_rules.json)
   ```

2. `ServiceNowConfig` dataclass — add one new field after `attachments_dir`:
   ```python
   assignment_rules_file: str  # path to assignment_rules.json; overridable via env var
   ```

3. `load_config()` return statement — add one new kwarg:
   ```python
   assignment_rules_file=get(
       "ASSIGNMENT_RULES_FILE",
       str(_PKG_DIR / "assignment_rules.json"),
   ),
   ```

The `_PKG_DIR` constant, `_load_env_file()`, `_find_env_data()`, `SmtpConfig`, and
`load_smtp_config()` are copied verbatim from `rca_copilot_agent/config.py`.

The `_PKG_DIR` line in the new file must resolve to `ticketasg_copilot_agent/`, not
`rca_copilot_agent/`. It will — `Path(__file__).resolve().parent` is correct because this is
`ticketasg_copilot_agent/config.py`.
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python -c "import sys; sys.path.insert(0,'ticketasg_copilot_agent'); from config import load_config, ServiceNowConfig; cfg = load_config(); assert hasattr(cfg,'assignment_rules_file'); assert 'assignment_rules.json' in cfg.assignment_rules_file; print('PASS')"</automated>
  </verify>
  <done>
    `load_config()` returns `ServiceNowConfig` with `assignment_rules_file` field pointing to
    `ticketasg_copilot_agent/assignment_rules.json`. Importing `config` from the new package
    does not accidentally import `rca_copilot_agent/config.py`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create assignment_rules.json routing matrix</name>
  <files>
    ticketasg_copilot_agent/assignment_rules.json
  </files>
  <read_first>
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 763-818 — full JSON structure
    .planning/phases/phase-kayinleong-01/01-RESEARCH.md lines 230-263 — inferred routing logic table
  </read_first>
  <action>
Create `ticketasg_copilot_agent/assignment_rules.json` with EXACTLY this content. All keywords
are [USER-CONFIRM] — inferred from group names because the SharePoint routing matrix is behind
SSO. The JSON structure is the contract; keyword values should be verified by the user.

```json
{
  "version": "1.0",
  "note": "[USER-CONFIRM] Routing matrix for SPACE CDS L2 assignment groups. Keywords are inferred — verify against SharePoint routing matrix before production use. Update keywords here — no code changes needed.",
  "groups": {
    "APAC - SGP - SPACE CDS SAPMENA L2 Support": {
      "keywords": ["SAP", "SAPMENA", "SGP", "Singapore", "pipeline", "CDS", "SPACE CDS", "SAP order", "product sync", "ERP"],
      "description": "SAP/ERP integration issues; Singapore-hosted SPACE CDS services; product data sync failures",
      "weight": 1.0
    },
    "APAC - THN - Retail IT": {
      "keywords": ["Thailand", "THN", "POS", "point of sale", "retail store", "in-store", "cashier", "terminal", "store network", "printer"],
      "description": "Thailand retail IT, in-store POS systems, store network issues",
      "weight": 1.0
    },
    "APAC - ZN - iBeauty 2.0 - Retail - L2": {
      "keywords": ["iBeauty", "beauty advisor", "BA", "in-store app", "clienteling", "advisor app", "consultation", "skin", "shade", "retail app"],
      "description": "iBeauty POS application issues, in-store retail app",
      "weight": 1.0
    },
    "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2": {
      "keywords": ["OMNISALES", "omni", "MARS", "Capgemini", "GDC", "click and collect", "ship from store", "inventory", "retail order", "MARS integration"],
      "description": "Omnichannel retail operations (Capgemini MARS team)",
      "weight": 1.0
    },
    "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2": {
      "keywords": ["CED", "e-commerce", "online", "web order", "cart", "checkout", "SPACE GDS", "online store", "SPACE-GDS"],
      "description": "Online e-commerce platform issues (Capgemini SPACE GDS team)",
      "weight": 1.0
    },
    "APAC - ZN - O+O.CRM - L2": {
      "keywords": ["CRM", "loyalty", "consumer profile", "lucid", "registration", "account", "consent", "GDPR", "Salesforce", "marketing", "email campaign"],
      "description": "CRM, consumer identity, loyalty programme issues",
      "weight": 1.0
    },
    "APAC - ZN - O+O.NGLORA - L2": {
      "keywords": ["NGLORA", "LORA", "ORA", "loyalty rewards", "points", "tier", "redemption", "rewards programme"],
      "description": "NGLORA loyalty platform issues",
      "weight": 1.0
    },
    "APAC - ZN - O+O.OPERATIONS - L2": {
      "keywords": ["operations", "ops", "batch", "ETL", "pipeline", "data sync", "integration", "API", "webhook", "data ingestion"],
      "description": "Operational issues: ETL, API integrations, data pipelines",
      "weight": 1.0
    },
    "APAC - ZN - SPACE B2C Hypercare": {
      "keywords": ["hypercare", "go live", "go-live", "launch", "cutover", "P1", "escalation", "new market", "B2C", "regression", "critical"],
      "description": "Post-go-live hypercare support for new market launches",
      "weight": 1.0
    },
    "TECH FNDN - WW - HIP INCIDENT L2": {
      "keywords": ["infrastructure", "HIP", "platform", "cloud", "server", "network", "certificate", "SSL", "DNS", "database", "auth", "SSO"],
      "description": "Technical foundation: infrastructure, cloud platform, certificates",
      "weight": 1.0
    }
  }
}
```
  </action>
  <verify>
    <automated>python -c "import json,pathlib; d=json.loads(pathlib.Path('ticketasg_copilot_agent/assignment_rules.json').read_text()); assert len(d['groups'])==10; print('groups:', list(d['groups'].keys()))"</automated>
  </verify>
  <done>
    File exists with valid JSON. Exactly 10 groups. Every group has a non-empty `keywords` list
    and a `weight` field. The `grep` check:
    `grep -c '"keywords"' ticketasg_copilot_agent/assignment_rules.json` returns 10.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| filesystem → config.py | .env file read from cwd or package dir; attacker with filesystem write could inject env values |
| assignment_rules.json → assignment_tool.py | JSON config parsed at runtime; malformed file triggers fallback to defaults |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave1-01 | Tampering | assignment_rules.json | accept | Config file — no secrets, committed to repo; integrity maintained via git |
| T-wave1-02 | Information Disclosure | config.py `_find_env_data()` | mitigate | Never log env values; follows rca_copilot_agent pattern exactly |
</threat_model>

<verification>
From repo root:
1. `python -c "import ticketasg_copilot_agent"` — exits 0
2. `python -c "import sys; sys.path.insert(0,'ticketasg_copilot_agent'); from config import load_config; c=load_config(); print(c.assignment_rules_file)"` — prints path ending in `assignment_rules.json`
3. `python -c "import json; d=json.load(open('ticketasg_copilot_agent/assignment_rules.json')); print(len(d['groups']), 'groups')"` — prints `10 groups`
4. `grep -c '"keywords"' ticketasg_copilot_agent/assignment_rules.json` — prints `10`
</verification>

<success_criteria>
- Package is importable from repo root
- `ServiceNowConfig` has `assignment_rules_file` field
- `load_config()` defaults `assignment_rules_file` to `ticketasg_copilot_agent/assignment_rules.json`
- `ASSIGNMENT_RULES_FILE` env var overrides the default path
- `assignment_rules.json` has exactly 10 groups matching the canonical names from phase planning
- All 10 group names match exactly: "APAC - SGP - SPACE CDS SAPMENA L2 Support", "APAC - THN - Retail IT", "APAC - ZN - iBeauty 2.0 - Retail - L2", "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2", "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2", "APAC - ZN - O+O.CRM - L2", "APAC - ZN - O+O.NGLORA - L2", "APAC - ZN - O+O.OPERATIONS - L2", "APAC - ZN - SPACE B2C Hypercare", "TECH FNDN - WW - HIP INCIDENT L2"
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-01/phase-kayinleong-01-wave1-SUMMARY.md`
</output>
