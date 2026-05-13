---
wave: 5
depends_on: [wave4]
files_modified: []
autonomous: true
requirements:
  - phase-kayinleong-01
must_haves:
  - python ticketasg_copilot_agent/run_tool.py --help exits 0
  - python ticketasg_copilot_agent/run_tool.py list_tools (or get_assignment_rules) returns non-error output
  - recommend_assignment smoke test returns valid JSON with all 6 keys
  - SKILL.md frontmatter is valid YAML
  - agent.md frontmatter is valid YAML
  - No cross-package imports from rca_copilot_agent in any ticketasg_copilot_agent file
---

<objective>
Verify the complete package end-to-end without SNOW credentials or live BQ access. All checks
are purely local — filesystem and Python import validation.

Purpose: Catch wiring mistakes before the user ever invokes the agent. The integration smoke
test validates that `run_tool.py` dispatches correctly through `mcp_server._dispatch()` to
`assignment_tool.py`.

Output: No new files — verification only. Any failures must be fixed before this wave passes.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/CLAUDE.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/CLAIM.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Package structure and import smoke tests</name>
  <files></files>
  <read_first>
    ticketasg_copilot_agent/__init__.py — confirm exists
    ticketasg_copilot_agent/tools/assignment_tool.py — confirm ASSIGNMENT_GROUPS has 10 entries
  </read_first>
  <action>
Run the following checks in sequence. Fix any failures before marking this task done.

**Check 1 — Package structure (all 16 required files exist):**
```bash
for f in \
  ticketasg_copilot_agent/__init__.py \
  ticketasg_copilot_agent/config.py \
  ticketasg_copilot_agent/mcp_server.py \
  ticketasg_copilot_agent/run_tool.py \
  ticketasg_copilot_agent/tools/__init__.py \
  ticketasg_copilot_agent/tools/assignment_tool.py \
  ticketasg_copilot_agent/tools/snow_reader.py \
  ticketasg_copilot_agent/tools/incident_store.py \
  ticketasg_copilot_agent/tools/auth_tool.py \
  ticketasg_copilot_agent/tools/gcloud_tool.py \
  ticketasg_copilot_agent/tools/bigquery_tool.py \
  ticketasg_copilot_agent/tools/email_tool.py \
  ticketasg_copilot_agent/assignment_rules.json \
  ticketasg_copilot_agent/AGENTS.md \
  .claude/skills/ticketasg-copilot/SKILL.md \
  .github/agents/ticketasg_copilot.agent.md; do
  test -f "$f" && echo "OK: $f" || echo "MISSING: $f"
done
```
All must print "OK:". Fix any MISSING before proceeding.

**Check 2 — No cross-package imports:**
```bash
grep -rn "rca_copilot_agent" ticketasg_copilot_agent/
```
Expected: no output (empty). Any line containing `rca_copilot_agent` in the new package is a bug.
Exception: comments are OK but code imports are not.

**Check 3 — Python package importable:**
```bash
python -c "import ticketasg_copilot_agent; print('package import: OK')"
```

**Check 4 — assignment_rules.json valid and complete:**
```bash
python -c "
import json
d = json.load(open('ticketasg_copilot_agent/assignment_rules.json'))
groups = list(d['groups'].keys())
assert len(groups) == 10, f'Expected 10 groups, got {len(groups)}'
print('assignment_rules.json groups:')
for g in groups:
    print(f'  {g}')
print('OK: 10 groups')
"
```

**Check 5 — config.py loads with assignment_rules_file:**
```bash
python -c "
import sys; sys.path.insert(0, 'ticketasg_copilot_agent')
from config import load_config
cfg = load_config()
assert hasattr(cfg, 'assignment_rules_file'), 'Missing assignment_rules_file field'
assert 'assignment_rules.json' in cfg.assignment_rules_file
print(f'config.assignment_rules_file: {cfg.assignment_rules_file}')
print('OK')
"
```

**Check 6 — assignment_tool.py unit test:**
```bash
python -c "
import sys; sys.path.insert(0, 'ticketasg_copilot_agent')
from tools.assignment_tool import recommend_assignment, get_assignment_rules, ASSIGNMENT_GROUPS

assert len(ASSIGNMENT_GROUPS) == 10
rules_text = get_assignment_rules()
assert 'APAC - SGP - SPACE CDS SAPMENA L2 Support' in rules_text
assert 'TECH FNDN - WW - HIP INCIDENT L2' in rules_text

result = recommend_assignment('INC_TEST', 'SAP SAPMENA error', 'Singapore CDS pipeline')
assert set(result.keys()) == {'recommended_group','confidence','reason','alternatives','reassignment_needed','reassignment_reason'}, f'Wrong keys: {result.keys()}'
assert len(result['alternatives']) == 3
assert result['recommended_group'] == 'APAC - SGP - SPACE CDS SAPMENA L2 Support', f'Wrong group: {result[\"recommended_group\"]}'
print(f'recommend_assignment result: {result[\"recommended_group\"]} (confidence={result[\"confidence\"]})')
print('OK')
"
```
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python -c "
import sys; sys.path.insert(0,'ticketasg_copilot_agent')
from tools.assignment_tool import recommend_assignment, ASSIGNMENT_GROUPS
assert len(ASSIGNMENT_GROUPS) == 10
r = recommend_assignment('INC_TEST', 'SAP SAPMENA error', 'Singapore CDS pipeline')
assert set(r.keys()) == {'recommended_group','confidence','reason','alternatives','reassignment_needed','reassignment_reason'}
assert len(r['alternatives']) == 3
print('Task1 PASS')
"</automated>
  </verify>
  <done>
    All 16 files exist. `grep -rn "rca_copilot_agent" ticketasg_copilot_agent/` returns empty (no code imports). Package imports without error. `recommend_assignment` returns correct 6-key dict. `ASSIGNMENT_GROUPS` has 10 elements.
  </done>
</task>

<task type="auto">
  <name>Task 2: run_tool.py integration smoke tests</name>
  <files></files>
  <read_first>
    ticketasg_copilot_agent/run_tool.py — confirm sys.path.insert points to parent dir
    ticketasg_copilot_agent/mcp_server.py — confirm _dispatch has recommend_assignment and get_assignment_rules branches
  </read_first>
  <action>
Run the following CLI checks. These test the full path: `run_tool.py` → `mcp_server._dispatch` → `assignment_tool`.

**Smoke test 1 — --help exits 0:**
```bash
python ticketasg_copilot_agent/run_tool.py --help
```
Must exit 0 and print "ticketasg_copilot_agent" in the output.

**Smoke test 2 — get_assignment_rules (no credentials needed):**
```bash
python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'
```
Must print text containing "APAC - SGP - SPACE CDS SAPMENA L2 Support". Must NOT raise an exception or print "Error".

**Smoke test 3 — recommend_assignment (no credentials needed):**
```bash
python ticketasg_copilot_agent/run_tool.py recommend_assignment \
  --json '{"incident_number": "INC_SMOKE", "short_description": "SAP SAPMENA pipeline failure", "description": "CDS Singapore pipeline error", "current_group": "APAC - ZN - O+O.OPERATIONS - L2"}'
```
Must print valid JSON. Must contain `"recommended_group"` key. Must contain `"reassignment_needed": true`.

**Smoke test 4 — unknown tool returns error string (not exception):**
```bash
python ticketasg_copilot_agent/run_tool.py unknown_tool_xyz --json '{}'
echo "exit code: $?"
```
Must exit non-zero (the script `sys.exit(1)` on tool error). Output must contain "Tool error" or "Unknown tool".

**Smoke test 5 — YAML frontmatter validation for SKILL.md:**
```bash
python -c "
import re, pathlib
content = pathlib.Path('.claude/skills/ticketasg-copilot/SKILL.md').read_text()
# Extract YAML block between first --- markers
m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
assert m, 'No valid YAML frontmatter found'
yaml_block = m.group(1)
assert 'name: ticketasg-copilot' in yaml_block
assert 'invocation: /ticketasg-copilot' in yaml_block
print('SKILL.md frontmatter: OK')
"
```

**Smoke test 6 — YAML frontmatter validation for agent.md:**
```bash
python -c "
import re, pathlib
content = pathlib.Path('.github/agents/ticketasg_copilot.agent.md').read_text()
m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
assert m, 'No valid YAML frontmatter found'
yaml_block = m.group(1)
assert 'name: Ticket Assignment Copilot Agent' in yaml_block
assert 'execute/runInTerminal' in yaml_block
print('ticketasg_copilot.agent.md frontmatter: OK')
"
```

If any smoke test fails: diagnose from the error message, fix the root cause in the earlier
wave's file (not this wave — this wave creates no files), then re-run the failing test.

Common fixes:
- `ModuleNotFoundError: config` → `sys.path.insert` missing or wrong in `mcp_server.py`
- `Unknown tool: get_assignment_rules` → the `elif name == "get_assignment_rules"` branch is missing in `_dispatch()`
- `AttributeError: 'ServiceNowConfig' object has no attribute 'assignment_rules_file'` → `config.py` Wave 1 Task 2 incomplete
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}' 2>/dev/null | grep -c "APAC"</automated>
  </verify>
  <done>
    All 6 smoke tests pass:
    1. `run_tool.py --help` exits 0
    2. `get_assignment_rules` returns text with "APAC - SGP..."
    3. `recommend_assignment` with SAP signals returns JSON with `recommended_group: APAC - SGP - SPACE CDS SAPMENA L2 Support` and `reassignment_needed: true`
    4. Unknown tool returns non-zero exit with "Unknown tool" in stderr/stdout
    5. SKILL.md has valid YAML with correct invocation key
    6. agent.md has valid YAML with `name: Ticket Assignment Copilot Agent`
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Complete `ticketasg_copilot_agent` package:
    - 12 Python files (package + 7 tools + mcp_server + run_tool + config + __init__)
    - assignment_rules.json (10 group routing matrix — [USER-CONFIRM] keywords)
    - AGENTS.md
    - .claude/skills/ticketasg-copilot/SKILL.md
    - .github/agents/ticketasg_copilot.agent.md
  </what-built>
  <how-to-verify>
    1. Run the full smoke test:
       ```bash
       python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'
       ```
       Expected: formatted text listing all 10 assignment groups with their keywords.

    2. Run the assignment recommendation smoke test:
       ```bash
       python ticketasg_copilot_agent/run_tool.py recommend_assignment \
         --json '{"incident_number": "INC_TEST", "short_description": "SAP SAPMENA pipeline failure", "description": "CDS Singapore pipeline error", "current_group": "APAC - ZN - O+O.OPERATIONS - L2"}'
       ```
       Expected: JSON with `"recommended_group": "APAC - SGP - SPACE CDS SAPMENA L2 Support"` and `"reassignment_needed": true`.

    3. [USER-CONFIRM] Review `ticketasg_copilot_agent/assignment_rules.json`:
       - Are the routing keywords for each group correct?
       - Update `keywords` arrays directly in the JSON file — no code changes needed.

    4. (Optional) If you have live SNOW credentials in `.env`:
       ```bash
       python ticketasg_copilot_agent/run_tool.py list_incidents --json '{}'
       ```
       Expected: list of locally cached incidents (or "No incidents found" if cache is empty).
  </how-to-verify>
  <resume-signal>
    Type "approved" when verification passes, or describe any issues found (routing matrix,
    missing tool, wrong output format).
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| smoke test → run_tool.py | CLI invocation with controlled test inputs — no untrusted data |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave5-01 | Repudiation | assignment_rules.json [USER-CONFIRM] keywords | accept | Keywords are flagged as inferred; user review checkpoint is mandatory before production use |
</threat_model>

<verification>
From repo root (all must pass before wave is complete):
1. `python ticketasg_copilot_agent/run_tool.py --help` — exit 0
2. `python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'` — prints "APAC - SGP - SPACE CDS SAPMENA L2 Support"
3. `python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{"incident_number":"X","short_description":"SAP SAPMENA","description":"Singapore"}' | python -c "import sys,json; d=json.load(sys.stdin); assert d['recommended_group']=='APAC - SGP - SPACE CDS SAPMENA L2 Support'; print('PASS')"` — prints PASS
4. `grep -rn "rca_copilot_agent" ticketasg_copilot_agent/*.py ticketasg_copilot_agent/tools/*.py` — empty
</verification>

<success_criteria>
- All 16 files exist with correct content
- `run_tool.py --help` exits 0
- `run_tool.py get_assignment_rules --json '{}'` returns all 10 group names without SNOW credentials
- `run_tool.py recommend_assignment` with SAP/Singapore signals returns SGP group recommendation
- No cross-package imports from `rca_copilot_agent` in the new package
- Human checkpoint approved: routing matrix keywords reviewed and confirmed (or updated)
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-01/phase-kayinleong-01-wave5-SUMMARY.md`

Also update CLAIM.md:
- status: done
- "## What Has Changed" — list all 16 new files
- "## Verification" — paste the smoke test output confirming all checks pass
</output>
