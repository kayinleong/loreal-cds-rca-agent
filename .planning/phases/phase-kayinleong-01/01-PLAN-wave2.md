---
wave: 2
depends_on: [wave1]
files_modified:
  - ticketasg_copilot_agent/tools/assignment_tool.py
  - ticketasg_copilot_agent/tools/snow_reader.py
  - ticketasg_copilot_agent/tools/incident_store.py
  - ticketasg_copilot_agent/tools/auth_tool.py
  - ticketasg_copilot_agent/tools/gcloud_tool.py
  - ticketasg_copilot_agent/tools/bigquery_tool.py
  - ticketasg_copilot_agent/tools/email_tool.py
autonomous: true
requirements:
  - phase-kayinleong-01
must_haves:
  - assignment_tool.py exports get_assignment_rules() and recommend_assignment()
  - recommend_assignment() returns dict with recommended_group, confidence, reason, alternatives, reassignment_needed, reassignment_reason
  - get_assignment_rules() returns formatted string listing all 10 groups with their keywords
  - All 5 copy-verbatim tools exist in ticketasg_copilot_agent/tools/
  - email_tool.py send_rca_email function signature is unchanged (aliased in mcp_server as _send)
---

<objective>
Create all tool files. Five files are verbatim copies of `rca_copilot_agent/tools/` counterparts.
One file (`email_tool.py`) is a copy with 3 user-visible string updates. One file
(`assignment_tool.py`) is net-new — the scoring engine that drives all routing.

Purpose: Wave 3 (`mcp_server.py`, `run_tool.py`) imports from these files. The
`assignment_tool.py` must be complete and fully testable in isolation.

Output: 7 files in `ticketasg_copilot_agent/tools/`.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/CLAUDE.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/01-PATTERNS.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/01-RESEARCH.md

<interfaces>
<!-- assignment_tool.py public interface — fully specified -->

```python
# ticketasg_copilot_agent/tools/assignment_tool.py

ASSIGNMENT_GROUPS: list[str]  # 10 canonical group names in order

def get_assignment_rules() -> str:
    """Return routing matrix as formatted text for LLM inspection."""

def recommend_assignment(
    incident_number: str,
    short_description: str,
    description: str,
    category: str = "",
    subcategory: str = "",
    comments_text: str = "",
    work_notes_text: str = "",
    current_group: str = "",
) -> dict:
    """
    Returns:
    {
        "recommended_group": str,   # exact canonical group name
        "confidence": float,        # 0.0–1.0, rounded to 3 decimal places
        "reason": str,              # human-readable explanation
        "alternatives": [           # top 3 non-winning groups
            {"group": str, "score": float},
            ...
        ],
        "reassignment_needed": bool,
        "reassignment_reason": str,
    }
    """
```

<!-- email_tool.py — function signature MUST be preserved exactly -->
From rca_copilot_agent/tools/email_tool.py:
```python
def send_rca_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from: str,
    smtp_to: list[str],
    use_tls: bool,
    subject: str,
    session_summary: str,
    report_paths: list[str] | None = None,
    verify_ssl: bool = True,
) -> str:
    ...

def register_report(path: str) -> None: ...
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Copy verbatim tools (snow_reader, incident_store, auth_tool, gcloud_tool, bigquery_tool)</name>
  <files>
    ticketasg_copilot_agent/tools/snow_reader.py
    ticketasg_copilot_agent/tools/incident_store.py
    ticketasg_copilot_agent/tools/auth_tool.py
    ticketasg_copilot_agent/tools/gcloud_tool.py
    ticketasg_copilot_agent/tools/bigquery_tool.py
  </files>
  <read_first>
    rca_copilot_agent/tools/snow_reader.py — copy verbatim; update module docstring header only
    rca_copilot_agent/tools/incident_store.py — copy verbatim; update module docstring header only
    rca_copilot_agent/tools/auth_tool.py — copy truly verbatim (no strings reference RCA)
    rca_copilot_agent/tools/gcloud_tool.py — copy truly verbatim
    rca_copilot_agent/tools/bigquery_tool.py — copy truly verbatim; _SCHEMA_JSON path depth is identical (3 levels from repo root)
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 560-598 — verbatim copy rules
  </read_first>
  <action>
Copy each file with the following rules:

1. `snow_reader.py` — Copy verbatim. Optionally update the first comment line from
   "RCA Copilot Agent" to "Ticket Assignment Copilot Agent" if it appears in the module
   docstring. All function signatures and logic unchanged.

2. `incident_store.py` — Copy verbatim. The module docstring says
   "Extracted from rca_agent/tools/snow_tool.py" — update to
   "Used by ticketasg_copilot_agent". All function signatures and logic unchanged.

3. `auth_tool.py` — Copy truly verbatim. No strings reference "RCA" — no changes at all.

4. `gcloud_tool.py` — Copy truly verbatim. All gcloud paths and logic are identical.

5. `bigquery_tool.py` — Copy truly verbatim. The `_SCHEMA_JSON` path at line 72 is:
   ```python
   _SCHEMA_JSON = Path(__file__).resolve().parent.parent.parent / "schema.json"
   ```
   This resolves correctly for both packages (both are 3 levels deep). Do NOT change this line.

For all 5 files: `from config import load_config` imports will resolve to the local
`ticketasg_copilot_agent/config.py` when `sys.path` includes the package dir (which
`mcp_server.py` and `run_tool.py` both do via `sys.path.insert`).
  </action>
  <verify>
    <automated>python -c "
import sys
sys.path.insert(0, 'ticketasg_copilot_agent')
from tools.snow_reader import ServiceNowReader
from tools.incident_store import get_store, IncidentStore
print('snow_reader: OK')
print('incident_store: OK')
"</automated>
  </verify>
  <done>
    All 5 files exist in `ticketasg_copilot_agent/tools/`. Python import of `ServiceNowReader`
    and `IncidentStore` succeeds. `grep -r "rca_copilot_agent" ticketasg_copilot_agent/tools/snow_reader.py` returns empty.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create email_tool.py (copy + 3 string updates)</name>
  <files>
    ticketasg_copilot_agent/tools/email_tool.py
  </files>
  <read_first>
    rca_copilot_agent/tools/email_tool.py — read the FULL file; locate the 3 user-visible strings
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 608-636 — exact 3 changes listed
  </read_first>
  <action>
Copy `rca_copilot_agent/tools/email_tool.py` verbatim. Then make exactly 3 string changes in
the `_build_html()` function body:

1. The `<h1>` text: `"RCA Analysis Complete"` → `"Ticket Assignment Analysis Complete"`
2. The badge/status text: `"ANALYSIS COMPLETE"` → `"ASSIGNMENT COMPLETE"`
3. The footer agent name: `"RCA Copilot Agent"` → `"Ticket Assignment Copilot Agent"`

Do NOT change:
- The function name `send_rca_email` — mcp_server.py imports it as `from tools.email_tool import send_rca_email as _send`
- The function signature — it must remain identical to the analog
- `register_report()` and `_session_reports` — copy verbatim
- All SMTP logic — copy verbatim

Search for these strings in the analog file before editing to confirm their exact location.
  </action>
  <verify>
    <automated>grep -n "Ticket Assignment" ticketasg_copilot_agent/tools/email_tool.py | wc -l</automated>
  </verify>
  <done>
    File exists. `grep -n "Ticket Assignment" ticketasg_copilot_agent/tools/email_tool.py` returns at least 2 matches (h1 and footer). `grep "def send_rca_email" ticketasg_copilot_agent/tools/email_tool.py` returns exactly one match (function name preserved). `grep "RCA Analysis Complete\|ANALYSIS COMPLETE\|RCA Copilot Agent" ticketasg_copilot_agent/tools/email_tool.py` returns empty.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Create assignment_tool.py (net-new routing engine)</name>
  <files>
    ticketasg_copilot_agent/tools/assignment_tool.py
  </files>
  <read_first>
    ticketasg_copilot_agent/assignment_rules.json — the routing matrix this file loads
    ticketasg_copilot_agent/config.py — ServiceNowConfig.assignment_rules_file field
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 361-556 — full implementation design
    rca_copilot_agent/tools/bigquery_tool.py lines 1-80 — module structure pattern (constants, singleton, pure functions)
  </read_first>
  <behavior>
    - recommend_assignment("INC001", "SAP pipeline failure", "SAPMENA sync error", current_group="APAC - ZN - O+O.OPERATIONS - L2") returns recommended_group="APAC - SGP - SPACE CDS SAPMENA L2 Support" and reassignment_needed=True
    - recommend_assignment("INC002", "Thailand POS printer not working", "THN retail store", current_group="APAC - THN - Retail IT") returns recommended_group="APAC - THN - Retail IT" and reassignment_needed=False
    - recommend_assignment("INC003", "no matching signals here", "", current_group="") returns a dict with reassignment_needed=False (current_group is empty) and confidence < 0.5
    - get_assignment_rules() returns a string containing "APAC - SGP - SPACE CDS SAPMENA L2 Support" and "TECH FNDN - WW - HIP INCIDENT L2"
    - recommend_assignment result dict has keys: recommended_group, confidence, reason, alternatives, reassignment_needed, reassignment_reason
    - alternatives list has exactly 3 entries
  </behavior>
  <action>
Create `ticketasg_copilot_agent/tools/assignment_tool.py` with this complete implementation:

```python
"""
assignment_tool.py — Deterministic ticket assignment routing.
=============================================================
Pure functions — no LLM calls, no side effects beyond logging.
Loads routing rules from assignment_rules.json (path resolved via config.py).

Two public functions:
  get_assignment_rules()   — returns routing matrix as formatted text for LLM inspection
  recommend_assignment()   — scores incident signals and returns top group + alternatives

[USER-CONFIRM] The routing keywords in assignment_rules.json are inferred from group names.
Verify against the official SharePoint routing matrix before production use.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Canonical list of the 10 L2 assignment groups — order is significant (tie-break by index)
ASSIGNMENT_GROUPS = [
    "APAC - SGP - SPACE CDS SAPMENA L2 Support",
    "APAC - THN - Retail IT",
    "APAC - ZN - iBeauty 2.0 - Retail - L2",
    "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2",
    "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2",
    "APAC - ZN - O+O.CRM - L2",
    "APAC - ZN - O+O.NGLORA - L2",
    "APAC - ZN - O+O.OPERATIONS - L2",
    "APAC - ZN - SPACE B2C Hypercare",
    "TECH FNDN - WW - HIP INCIDENT L2",
]

# Fallback group when no keywords match
_FALLBACK_GROUP = "APAC - ZN - O+O.OPERATIONS - L2"

# Module-level rules cache — loaded once on first call (same singleton pattern as bigquery_tool.py)
_rules_cache: Optional[dict] = None


def _load_rules() -> dict:
    """Load assignment_rules.json. Caches result on first call."""
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    try:
        # Import inside function to avoid circular imports at module load
        from config import load_config  # noqa: PLC0415
        cfg = load_config()
        path = Path(cfg.assignment_rules_file)
        if path.exists():
            _rules_cache = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"[ASSIGNMENT] Loaded rules v{_rules_cache.get('version', '?')} from {path}")
        else:
            logger.warning(f"[ASSIGNMENT] Rules file not found at {path} — using built-in defaults")
            _rules_cache = _builtin_defaults()
    except Exception as exc:
        logger.warning(f"[ASSIGNMENT] Could not load rules: {exc} — using built-in defaults")
        _rules_cache = _builtin_defaults()
    return _rules_cache


def _builtin_defaults() -> dict:
    """Minimal hardcoded rules used when assignment_rules.json is absent."""
    return {
        "version": "builtin-fallback",
        "groups": {
            "APAC - SGP - SPACE CDS SAPMENA L2 Support": {
                "keywords": ["SAP", "SAPMENA", "SGP", "Singapore", "pipeline", "CDS"],
                "weight": 1.0,
            },
            "APAC - THN - Retail IT": {
                "keywords": ["Thailand", "THN", "POS", "retail store", "printer"],
                "weight": 1.0,
            },
            "APAC - ZN - iBeauty 2.0 - Retail - L2": {
                "keywords": ["iBeauty", "beauty advisor"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2": {
                "keywords": ["OMNISALES", "MARS", "Capgemini"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2": {
                "keywords": ["CED", "e-commerce", "online"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.CRM - L2": {
                "keywords": ["CRM", "loyalty", "consumer profile"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.NGLORA - L2": {
                "keywords": ["NGLORA", "LORA"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.OPERATIONS - L2": {
                "keywords": ["operations", "ETL", "pipeline"],
                "weight": 1.0,
            },
            "APAC - ZN - SPACE B2C Hypercare": {
                "keywords": ["B2C", "hypercare", "go-live"],
                "weight": 1.0,
            },
            "TECH FNDN - WW - HIP INCIDENT L2": {
                "keywords": ["HIP", "infrastructure", "network"],
                "weight": 1.0,
            },
        },
    }


def get_assignment_rules() -> str:
    """
    Return the full assignment routing matrix as formatted text.
    Intended for LLM inspection before calling recommend_assignment.
    """
    rules = _load_rules()
    version = rules.get("version", "unknown")
    groups_dict = rules.get("groups", {})

    lines = [
        f"ASSIGNMENT RULES (version {version})",
        f"Total groups: {len(ASSIGNMENT_GROUPS)}",
        "",
    ]
    for group_name in ASSIGNMENT_GROUPS:
        g = groups_dict.get(group_name, {})
        keywords = g.get("keywords", [])
        description = g.get("description", "")
        lines.append(f"  {group_name}")
        if description:
            lines.append(f"    Description: {description}")
        if keywords:
            lines.append(f"    Keywords: {', '.join(keywords)}")
        lines.append("")
    return "\n".join(lines)


def recommend_assignment(
    incident_number: str,
    short_description: str,
    description: str,
    category: str = "",
    subcategory: str = "",
    comments_text: str = "",
    work_notes_text: str = "",
    current_group: str = "",
) -> dict:
    """
    Score incident text against routing rules and return a ranked recommendation.

    Scoring algorithm:
    - Combine all text fields (lowercased)
    - For each group: count keyword matches, multiply by weight
    - Rank groups by score descending
    - Confidence = top_score / total_score (proportion of all hits)
    - Fallback: if no group scores > 0, return _FALLBACK_GROUP with low confidence

    Returns:
        {
            "recommended_group": str,       # exact canonical group name
            "confidence": float,            # 0.0–1.0
            "reason": str,                  # matched keywords or fallback explanation
            "alternatives": [               # top 3 runner-up groups with scores
                {"group": str, "score": float}, ...
            ],
            "reassignment_needed": bool,    # True if current_group != recommended_group
            "reassignment_reason": str,     # populated when reassignment_needed is True
        }
    """
    rules = _load_rules()
    groups_dict = rules.get("groups", {})

    # Combine all text fields; lowercase for case-insensitive matching
    full_text = " ".join([
        short_description or "",
        description or "",
        category or "",
        subcategory or "",
        comments_text or "",
        work_notes_text or "",
    ]).lower()

    scores: dict[str, float] = {}
    hit_keywords: dict[str, list[str]] = {}

    for group_name in ASSIGNMENT_GROUPS:
        g = groups_dict.get(group_name, {})
        keywords: list[str] = g.get("keywords", [])
        weight: float = float(g.get("weight", 1.0))
        # Collect unique matching keywords (case-insensitive)
        hits = list({kw for kw in keywords if kw.lower() in full_text})
        score = len(hits) * weight
        scores[group_name] = score
        hit_keywords[group_name] = hits

    # Sort descending; tie-break by ASSIGNMENT_GROUPS order (stable sort preserves index order)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_group, top_score = ranked[0]

    # Confidence: proportion of total keyword hits captured by the top group
    total_score = sum(s for _, s in ranked)
    if total_score > 0:
        confidence = round(top_score / total_score, 3)
    else:
        # No matches at all — use fallback group with zero confidence
        top_group = _FALLBACK_GROUP
        confidence = 0.0

    # Build human-readable reason
    if hit_keywords.get(top_group):
        reason = (
            f"Matched {len(hit_keywords[top_group])} keyword(s): "
            f"{', '.join(sorted(hit_keywords[top_group]))}."
        )
    elif total_score == 0:
        reason = (
            f"No keyword matches found in incident text. "
            f"Defaulting to fallback group '{_FALLBACK_GROUP}'."
        )
    else:
        reason = f"Highest score by weight ({top_score}) with no explicit keyword match."

    # Reassignment decision
    reassignment_needed = bool(current_group and current_group.strip() != top_group)
    reassignment_reason = (
        f"Ticket is currently assigned to '{current_group}' "
        f"but signals point to '{top_group}'."
        if reassignment_needed
        else ""
    )

    logger.info(
        f"[ASSIGNMENT] {incident_number} → {top_group} "
        f"(confidence={confidence}, hits={hit_keywords.get(top_group, [])})"
    )

    return {
        "recommended_group": top_group,
        "confidence": confidence,
        "reason": reason,
        "alternatives": [
            {"group": g, "score": round(s, 3)}
            for g, s in ranked[1:4]  # top 3 runners-up
        ],
        "reassignment_needed": reassignment_needed,
        "reassignment_reason": reassignment_reason,
    }
```
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python -c "
import sys
sys.path.insert(0, 'ticketasg_copilot_agent')
from tools.assignment_tool import recommend_assignment, get_assignment_rules, ASSIGNMENT_GROUPS

# Test 1: SAP keywords → SGP group
r1 = recommend_assignment('INC001', 'SAP pipeline failure', 'SAPMENA sync error', current_group='APAC - ZN - O+O.OPERATIONS - L2')
assert r1['recommended_group'] == 'APAC - SGP - SPACE CDS SAPMENA L2 Support', f'Expected SGP, got {r1[\"recommended_group\"]}'
assert r1['reassignment_needed'] == True
print('Test 1 PASS: SAP→SGP group, reassignment_needed=True')

# Test 2: Thailand retail → THN group, no reassignment
r2 = recommend_assignment('INC002', 'Thailand POS printer', 'THN retail store', current_group='APAC - THN - Retail IT')
assert r2['recommended_group'] == 'APAC - THN - Retail IT'
assert r2['reassignment_needed'] == False
print('Test 2 PASS: THN group, reassignment_needed=False')

# Test 3: no signal → fallback, no reassignment (current_group empty)
r3 = recommend_assignment('INC003', 'xyz abc', 'lorem ipsum', current_group='')
assert 'recommended_group' in r3
assert r3['reassignment_needed'] == False
assert len(r3['alternatives']) == 3
print('Test 3 PASS: fallback, correct dict shape')

# Test 4: get_assignment_rules lists all groups
rules_text = get_assignment_rules()
assert 'APAC - SGP - SPACE CDS SAPMENA L2 Support' in rules_text
assert 'TECH FNDN - WW - HIP INCIDENT L2' in rules_text
print('Test 4 PASS: get_assignment_rules contains all groups')

assert len(ASSIGNMENT_GROUPS) == 10
print('ALL TESTS PASS')
"</automated>
  </verify>
  <done>
    `assignment_tool.py` exists. All 4 inline test assertions pass. The module exports:
    - `ASSIGNMENT_GROUPS` (10 elements)
    - `get_assignment_rules()` returning string with all group names
    - `recommend_assignment()` returning dict with 6 required keys
    - `alternatives` list has exactly 3 entries
    - `reassignment_needed` is True when `current_group` differs from `recommended_group`
    - `confidence` is 0.0 when no keywords match
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| incident text → assignment_tool.py | Untrusted incident text from ServiceNow is scored but never executed |
| assignment_rules.json → _load_rules() | JSON parsed from filesystem; malformed JSON triggers fallback |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave2-01 | Tampering | assignment_tool.py keyword matching | accept | Pure string matching on lowercased text — no code execution, no injection surface |
| T-wave2-02 | Information Disclosure | auth_tool.py credential refresh | mitigate | Copied verbatim from rca_copilot_agent — never logs COOKIE or X_USERTOKEN values |
| T-wave2-03 | Denial of Service | bigquery_tool.py | mitigate | Copied verbatim — hard ceiling on maximum_bytes_billed already enforced |
</threat_model>

<verification>
From repo root:
1. `python -c "import sys; sys.path.insert(0,'ticketasg_copilot_agent'); from tools.assignment_tool import recommend_assignment, ASSIGNMENT_GROUPS; assert len(ASSIGNMENT_GROUPS)==10; print('OK')"` — exits 0
2. `grep "def send_rca_email" ticketasg_copilot_agent/tools/email_tool.py` — returns one line
3. `grep -c "Ticket Assignment" ticketasg_copilot_agent/tools/email_tool.py` — returns >= 2
4. `grep "RCA Analysis Complete" ticketasg_copilot_agent/tools/email_tool.py` — returns empty
5. `python -c "import sys; sys.path.insert(0,'ticketasg_copilot_agent'); from tools.snow_reader import ServiceNowReader; from tools.incident_store import IncidentStore; print('OK')"` — exits 0
</verification>

<success_criteria>
- `assignment_tool.py` is fully self-contained and unit-testable without SNOW/BQ credentials
- `recommend_assignment()` returns a 6-key dict for any input (no exceptions on empty strings)
- `get_assignment_rules()` returns a string containing all 10 canonical group names
- All 5 verbatim-copy tool files exist and import cleanly
- `email_tool.py` has no occurrences of "RCA Analysis Complete", "ANALYSIS COMPLETE", or "RCA Copilot Agent" in user-visible strings
- `send_rca_email` function name is preserved in `email_tool.py`
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-01/phase-kayinleong-01-wave2-SUMMARY.md`
</output>
