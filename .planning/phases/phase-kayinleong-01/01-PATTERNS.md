# Phase 01: Ticket Assignment Agent — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 16 new files
**Analogs found:** 15 / 16 (1 net-new: `assignment_tool.py`)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `ticketasg_copilot_agent/__init__.py` | config | — | `rca_copilot_agent/__init__.py` | exact |
| `ticketasg_copilot_agent/config.py` | config | request-response | `rca_copilot_agent/config.py` | exact |
| `ticketasg_copilot_agent/run_tool.py` | CLI | request-response | `rca_copilot_agent/run_tool.py` | exact |
| `ticketasg_copilot_agent/mcp_server.py` | service | request-response | `rca_copilot_agent/mcp_server.py` | exact |
| `ticketasg_copilot_agent/tools/__init__.py` | config | — | `rca_copilot_agent/tools/__init__.py` | exact |
| `ticketasg_copilot_agent/tools/assignment_tool.py` | utility | transform | `rca_copilot_agent/tools/bigquery_tool.py` | partial (pure-function structure only) |
| `ticketasg_copilot_agent/tools/snow_reader.py` | service | request-response | `rca_copilot_agent/tools/snow_reader.py` | exact |
| `ticketasg_copilot_agent/tools/incident_store.py` | service | CRUD | `rca_copilot_agent/tools/incident_store.py` | exact |
| `ticketasg_copilot_agent/tools/auth_tool.py` | middleware | request-response | `rca_copilot_agent/tools/auth_tool.py` | exact |
| `ticketasg_copilot_agent/tools/email_tool.py` | utility | request-response | `rca_copilot_agent/tools/email_tool.py` | exact |
| `ticketasg_copilot_agent/tools/gcloud_tool.py` | utility | request-response | `rca_copilot_agent/tools/gcloud_tool.py` | exact |
| `ticketasg_copilot_agent/tools/bigquery_tool.py` | utility | request-response | `rca_copilot_agent/tools/bigquery_tool.py` | exact |
| `ticketasg_copilot_agent/AGENTS.md` | documentation | — | `rca_copilot_agent/AGENTS.md` | role-match |
| `.claude/skills/ticketasg-copilot/SKILL.md` | documentation | — | `.claude/skills/rca-copilot/SKILL.md` | role-match |
| `.github/agents/ticketasg_copilot.agent.md` | agent-def | — | `.github/agents/rca_copilot.agent.md` | role-match |
| `ticketasg_copilot_agent/assignment_rules.json` | config | — | (none — new concept) | no analog |

---

## Pattern Assignments

### `ticketasg_copilot_agent/__init__.py` (config, package marker)

**Analog:** `rca_copilot_agent/__init__.py`

**DIFFERENCE from analog:** Change the comment text — replace "RCA Copilot Agent" with "Ticket Assignment Copilot Agent".

**Full content to copy** (lines 1-2):
```python
# RCA Copilot Agent — ServiceNow tools for GitHub Copilot
# No LLM calls in this package; GitHub Copilot provides the reasoning.
```

**New version:**
```python
# Ticket Assignment Copilot Agent — ServiceNow ticket triage tools for GitHub Copilot
# No LLM calls in this package; GitHub Copilot provides the reasoning.
```

---

### `ticketasg_copilot_agent/config.py` (config, request-response)

**Analog:** `rca_copilot_agent/config.py`

**DIFFERENCE from analog:** Add one new optional config field `assignment_rules_file` to `ServiceNowConfig`. The SMTP config is unchanged and can be copied verbatim.

**Imports and helpers pattern** (lines 1-48) — copy verbatim:
```python
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent

def _load_env_file(env_path: Path) -> dict:
    """Load KEY=VALUE pairs from a .env file, ignoring comments and blanks."""
    ...

def _find_env_data(env_file: str) -> dict[str, str]:
    """Search for .env in cwd then alongside this file."""
    ...
```

**ServiceNowConfig dataclass — ADD one field** (lines 51-80):
```python
@dataclass
class ServiceNowConfig:
    instance_url: str
    cookie: str
    x_user_token: str
    reports_dir: str
    attachments_dir: str
    assignment_rules_file: str  # ADD THIS — new field not in rca_copilot_agent
```

**load_config() — ADD one line** (lines 60-80):
```python
def load_config(env_file: str = ".env") -> ServiceNowConfig:
    env_data = _find_env_data(env_file)

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_data.get(key, default)

    return ServiceNowConfig(
        instance_url=get("SNOW_INSTANCE", "https://loreal.service-now.com"),
        cookie=get("COOKIE"),
        x_user_token=(
            get("X_USERTOKEN")
            or get("X-UserToken")
            or get("X-usertoken")
        ),
        reports_dir=get("REPORTS_DIR", str(_PKG_DIR / "my_reports")),
        attachments_dir=get("ATTACHMENTS_DIR", str(_PKG_DIR / "attachments")),
        assignment_rules_file=get(          # ADD THIS LINE
            "ASSIGNMENT_RULES_FILE",
            str(_PKG_DIR / "assignment_rules.json"),
        ),
    )
```

**SmtpConfig + load_smtp_config()** (lines 83-128) — copy verbatim from `rca_copilot_agent/config.py`.

---

### `ticketasg_copilot_agent/run_tool.py` (CLI, request-response)

**Analog:** `rca_copilot_agent/run_tool.py`

**DIFFERENCE from analog:** Two changes only: (1) update the module docstring tool list to reflect assignment-agent tools; (2) change the `argparse` description string. The dispatch mechanism is identical — `from mcp_server import _dispatch` pulls from the local `ticketasg_copilot_agent/mcp_server.py`.

**Path injection pattern** (lines 44-45) — copy verbatim:
```python
# Allow running from repo root: `python ticketasg_copilot_agent/run_tool.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

**Config + init pattern** (lines 51-104) — copy verbatim. The init sequence is identical:
```python
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a ticketasg_copilot_agent tool without starting an MCP server.",
        ...
    )
    parser.add_argument("tool", help="Tool name (see list above)")
    parser.add_argument("--json", metavar="ARGS", default="{}", ...)
    args = parser.parse_args()

    try:
        arguments = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"Error: --json is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    from config import load_config
    cfg = load_config()
    reports_dir = os.environ.get("REPORTS_DIR") or cfg.reports_dir

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cfg.attachments_dir, exist_ok=True)

    # Initialize BigQuery schema (non-fatal if unavailable)
    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except Exception as e:
        logger.warning(f"[BQ] Not available: {e}")

    # Pre-load incident store
    combined = os.path.join(reports_dir, "_all_incidents.json")
    if os.path.exists(combined):
        from tools.incident_store import load_store
        load_store(combined)

    # Check ServiceNow credentials (non-fatal)
    try:
        from tools.auth_tool import ensure_credentials
        ensure_credentials(instance_url=cfg.instance_url)
    except Exception as e:
        logger.warning(f"[AUTH] Credential check failed: {type(e).__name__}: {e}")

    # Check gcloud ADC (non-fatal)
    try:
        from tools.gcloud_tool import ensure_gcloud_auth
        ensure_gcloud_auth()
    except Exception as e:
        logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")

    # Dispatch — reuse _dispatch from mcp_server
    from mcp_server import _dispatch

    try:
        result = asyncio.run(_dispatch(args.tool, arguments, reports_dir))
        print(result)
    except Exception as e:
        print(f"Tool error ({args.tool}): {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
```

---

### `ticketasg_copilot_agent/mcp_server.py` (service, request-response)

**Analog:** `rca_copilot_agent/mcp_server.py`

**DIFFERENCE from analog:** This is the largest change. The structure is identical but the tool set is different. Key changes:

1. Module docstring — update server name and tool list
2. `create_mcp_server()` — change `Server("rca-copilot")` to `Server("ticketasg-copilot")`
3. `list_tools()` — replace `save_rca_report` and `send_rca_email` with `save_assignment_report`, `send_assignment_email`, and add `recommend_assignment` + `get_assignment_rules`
4. `_dispatch()` — add routing for the 4 new/renamed tools; keep all SNOW tools verbatim
5. `main()` — update server name strings

**`_build_reader()` helper** (lines 55-69) — copy verbatim:
```python
def _build_reader():
    """Instantiate and authenticate a ServiceNowReader from config."""
    from config import load_config
    from tools.snow_reader import ServiceNowReader

    cfg = load_config()
    if not cfg.cookie or not cfg.x_user_token:
        raise RuntimeError(
            "COOKIE and X_USERTOKEN must be set in .env or environment. "
            "See .env.example for instructions."
        )

    reader = ServiceNowReader(instance_url=cfg.instance_url)
    reader.authenticate(cookie=cfg.cookie, x_user_token=cfg.x_user_token)
    return reader, cfg
```

**`create_mcp_server()` server name** (line 90) — change one string:
```python
# ANALOG (rca_copilot_agent):
server = Server("rca-copilot")

# NEW (ticketasg_copilot_agent):
server = Server("ticketasg-copilot")
```

**Tool registration pattern in `list_tools()`** (lines 93-422) — for each new/renamed tool, copy the `Tool(name=..., description=..., inputSchema=...)` block structure. The two new tools to ADD are:

```python
Tool(
    name="recommend_assignment",
    description=(
        "Analyse incident signals and return the recommended L2 assignment group. "
        "Takes structured incident fields (short_description, description, category, "
        "subcategory, comments_text, work_notes_text, current_group) and returns a "
        "dict with recommended_group, confidence, reason, alternatives, and "
        "reassignment_needed. This is a deterministic heuristic — the LLM should "
        "verify the recommendation against the full ticket context."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "incident_number": {"type": "string", "description": "Incident number for logging"},
            "short_description": {"type": "string"},
            "description": {"type": "string"},
            "category": {"type": "string", "default": ""},
            "subcategory": {"type": "string", "default": ""},
            "comments_text": {"type": "string", "default": ""},
            "work_notes_text": {"type": "string", "default": ""},
            "current_group": {"type": "string", "default": ""},
        },
        "required": ["incident_number", "short_description", "description"],
    },
),
Tool(
    name="get_assignment_rules",
    description=(
        "Return the full assignment routing matrix as formatted text — "
        "group names, trigger keywords, and confidence weights. "
        "Use this to understand available groups before calling recommend_assignment."
    ),
    inputSchema={"type": "object", "properties": {}},
),
```

**`_dispatch()` routing pattern** (lines 437-746) — copy the entire `if/elif` chain for all SNOW tools verbatim. Replace the `save_rca_report` and `send_rca_email` branches with `save_assignment_report` and `send_assignment_email`. Add new branches for `recommend_assignment` and `get_assignment_rules`:

```python
elif name == "recommend_assignment":
    from tools.assignment_tool import recommend_assignment
    return json.dumps(recommend_assignment(
        incident_number=arguments.get("incident_number", ""),
        short_description=arguments.get("short_description", ""),
        description=arguments.get("description", ""),
        category=arguments.get("category", ""),
        subcategory=arguments.get("subcategory", ""),
        comments_text=arguments.get("comments_text", ""),
        work_notes_text=arguments.get("work_notes_text", ""),
        current_group=arguments.get("current_group", ""),
    ), indent=2)

elif name == "get_assignment_rules":
    from tools.assignment_tool import get_assignment_rules
    return get_assignment_rules()

elif name == "save_assignment_report":
    # Same structure as save_rca_report — change directory name and report header
    number = arguments["incident_number"]
    report_text = arguments["report_text"]
    safe_number = number.replace("/", "_").replace("\\", "_")

    asg_dir = os.path.join(reports_dir, "assignment_reports")
    os.makedirs(asg_dir, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_number}_assignment_{timestamp}.md"
    filepath = os.path.join(asg_dir, filename)

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(f"# Assignment Recommendation — {number}\n\n")
        fh.write(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n")
        fh.write(report_text)

    from tools.email_tool import register_report
    register_report(filepath)
    return f"Assignment report saved: {filepath}"

elif name == "send_assignment_email":
    # Same structure as send_rca_email
    from config import load_smtp_config
    smtp = load_smtp_config()
    if not smtp.enabled:
        return (
            "SMTP not configured. Set SMTP_HOST, SMTP_FROM, and SMTP_TO in .env "
            "to enable email notifications."
        )
    from tools.email_tool import send_rca_email as _send
    subject = arguments.get("subject", "Ticket Assignment Analysis Complete — Please Review")
    return _send(
        smtp_host=smtp.host,
        smtp_port=smtp.port,
        smtp_user=smtp.user,
        smtp_password=smtp.password,
        smtp_from=smtp.from_addr,
        smtp_to=smtp.to_addrs,
        use_tls=smtp.use_tls,
        subject=subject,
        session_summary=arguments["session_summary"],
        verify_ssl=smtp.verify_ssl,
    )
```

**`main()` startup pattern** (lines 836-912) — copy verbatim with two string changes:
- `"RCA Copilot MCP Server"` → `"Ticket Assignment Copilot MCP Server"`
- `server_name="rca-copilot"` → `server_name="ticketasg-copilot"`
- `server_version="0.1.0"` → keep the same

---

### `ticketasg_copilot_agent/tools/__init__.py` (config, package marker)

**Analog:** `rca_copilot_agent/tools/__init__.py` (line 1)

**DIFFERENCE from analog:** Change the comment to reflect the new package.

```python
# Ticket Assignment tools — no LLM calls.
```

---

### `ticketasg_copilot_agent/tools/assignment_tool.py` (utility, transform)

**Analog:** `rca_copilot_agent/tools/bigquery_tool.py` (pure-function module structure only — NOT the BQ content)

**DIFFERENCE from analog:** This is a net-new file with no direct analog for the business logic. Use `bigquery_tool.py` only for the module structure pattern: module-level constants, a dataclass result type, pure functions, and a module-level singleton/state.

**Module-level constants pattern** (from `rca_copilot_agent/tools/bigquery_tool.py` lines 76-80):
```python
# Pattern to copy for ASSIGNMENT_GROUPS and ROUTING_RULES constants:
DANGEROUS_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", ...
}
```

**Pure function with logging pattern** (from `bigquery_tool.py` lines 544-554):
```python
def query_bigquery(sql: str, rationale: str = "") -> str:
    """Execute a read-only BigQuery query via bq CLI. Returns LLM-friendly result string."""
    if not _executors:
        raise RuntimeError(_BQ_UNAVAILABLE)
    executor = _pick_executor(sql)
    is_valid, error = executor.validate_query(sql)
    if not is_valid:
        return QueryResult(success=False, error=error, sql=sql).to_llm_context()
    logger.info(f"[BQ] billing_project={executor.project} | {rationale}\n  SQL: {sql[:200]}")
    result = _bq_cli_execute(sql, executor.project, max_rows=executor.max_rows)
    return result.to_llm_context()
```

**Full design for `assignment_tool.py`** (based on RESEARCH.md lines 370-414):

```python
"""
assignment_tool.py — Deterministic ticket assignment routing.
=============================================================
Pure functions — no LLM calls, no side effects beyond logging.
Loads routing rules from assignment_rules.json (path resolved via config.py).

Two public functions:
  get_assignment_rules()   — returns routing matrix as formatted text
  recommend_assignment()   — scores incident signals and returns top group + alternatives
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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

# Module-level cache for loaded rules (same singleton pattern as _executors in bigquery_tool.py)
_rules_cache: Optional[dict] = None


def _load_rules() -> dict:
    """Load assignment_rules.json. Caches on first call."""
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    try:
        from config import load_config  # noqa: PLC0415
        cfg = load_config()
        path = Path(cfg.assignment_rules_file)
        if path.exists():
            _rules_cache = json.loads(path.read_text(encoding="utf-8"))
        else:
            # Fallback: use built-in minimal rules
            _rules_cache = _default_rules()
    except Exception as e:
        logger.warning(f"[ASSIGNMENT] Could not load rules file: {e} — using defaults")
        _rules_cache = _default_rules()
    return _rules_cache


def _default_rules() -> dict:
    """Return minimal hardcoded rules when assignment_rules.json is absent."""
    return {
        "version": "1.0-default",
        "groups": {
            "APAC - SGP - SPACE CDS SAPMENA L2 Support": {
                "keywords": ["SAP", "SAPMENA", "SGP", "Singapore", "pipeline", "CDS"],
                "weight": 1.0,
            },
            # ... other groups
        },
    }


def get_assignment_rules() -> str:
    """Return the routing matrix as formatted text for LLM inspection."""
    rules = _load_rules()
    lines = [
        f"ASSIGNMENT RULES (version {rules.get('version', 'unknown')})",
        f"Groups: {len(ASSIGNMENT_GROUPS)}",
        "",
    ]
    for group_name in ASSIGNMENT_GROUPS:
        g = rules.get("groups", {}).get(group_name, {})
        kws = g.get("keywords", [])
        lines.append(f"  {group_name}")
        if kws:
            lines.append(f"    Keywords: {', '.join(kws)}")
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
    Score incident text against routing rules and return recommendation.

    Returns:
    {
        "recommended_group": str,
        "confidence": float,   # 0.0-1.0
        "reason": str,
        "alternatives": [{"group": str, "score": float}, ...],
        "reassignment_needed": bool,
        "reassignment_reason": str,
    }
    """
    rules = _load_rules()
    full_text = " ".join([
        short_description, description, category, subcategory,
        comments_text, work_notes_text,
    ]).lower()

    scores: dict[str, float] = {}
    hit_keywords: dict[str, list[str]] = {}

    for group_name in ASSIGNMENT_GROUPS:
        g = rules.get("groups", {}).get(group_name, {})
        keywords = g.get("keywords", [])
        weight = g.get("weight", 1.0)
        hits = [kw for kw in keywords if kw.lower() in full_text]
        score = len(hits) * weight
        scores[group_name] = score
        hit_keywords[group_name] = hits

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_group, top_score = ranked[0]
    total = sum(s for _, s in ranked) or 1
    confidence = round(top_score / total, 3)

    reason = (
        f"Matched keywords: {hit_keywords[top_group]}"
        if hit_keywords[top_group]
        else "No strong keyword matches — defaulting to highest-weight group."
    )

    reassignment_needed = bool(current_group and current_group != top_group)
    reassignment_reason = (
        f"Current group '{current_group}' differs from recommended '{top_group}'."
        if reassignment_needed else ""
    )

    logger.info(
        f"[ASSIGNMENT] {incident_number} → {top_group} "
        f"(confidence={confidence}, keywords={hit_keywords[top_group]})"
    )

    return {
        "recommended_group": top_group,
        "confidence": confidence,
        "reason": reason,
        "alternatives": [
            {"group": g, "score": round(s, 3)}
            for g, s in ranked[1:4]
        ],
        "reassignment_needed": reassignment_needed,
        "reassignment_reason": reassignment_reason,
    }
```

---

### `ticketasg_copilot_agent/tools/snow_reader.py` (service, request-response)

**Analog:** `rca_copilot_agent/tools/snow_reader.py`

**DIFFERENCE from analog:** None — copy verbatim. The `ServiceNowReader` class is domain-agnostic. No strings reference "RCA".

---

### `ticketasg_copilot_agent/tools/incident_store.py` (service, CRUD)

**Analog:** `rca_copilot_agent/tools/incident_store.py`

**DIFFERENCE from analog:** None — copy verbatim. The `IncidentStore` class is domain-agnostic. Module docstring says "Extracted from rca_agent/tools/snow_tool.py" — update to "Used by ticketasg_copilot_agent".

---

### `ticketasg_copilot_agent/tools/auth_tool.py` (middleware, request-response)

**Analog:** `rca_copilot_agent/tools/auth_tool.py`

**DIFFERENCE from analog:** None — copy verbatim. The credential refresh logic is fully domain-agnostic. The `from config import load_config` import uses a relative package import that will resolve correctly since both packages have the same `config.py` structure.

**Key pattern to preserve** (lines 169-221): the `ensure_credentials()` function must remain the top-level entry point called from `mcp_server.main()` before asyncio starts.

---

### `ticketasg_copilot_agent/tools/gcloud_tool.py` (utility, request-response)

**Analog:** `rca_copilot_agent/tools/gcloud_tool.py`

**DIFFERENCE from analog:** None — copy verbatim. All gcloud paths and logic are identical.

---

### `ticketasg_copilot_agent/tools/bigquery_tool.py` (utility, request-response)

**Analog:** `rca_copilot_agent/tools/bigquery_tool.py`

**DIFFERENCE from analog:** One line: update the `_SCHEMA_JSON` path. The analog's path navigates 3 levels up (`parent.parent.parent`). In the new package, `ticketasg_copilot_agent/tools/bigquery_tool.py` is also 3 levels deep from repo root, so the path is **identical**. Copy verbatim.

**Path resolution pattern** (line 72 — copy verbatim):
```python
# schema.json lives in the repo root (3 levels up from <package>/tools/)
_SCHEMA_JSON = Path(__file__).resolve().parent.parent.parent / "schema.json"
```

---

### `ticketasg_copilot_agent/tools/email_tool.py` (utility, request-response)

**Analog:** `rca_copilot_agent/tools/email_tool.py`

**DIFFERENCE from analog:** Update user-visible text strings only. The entire function signature and logic is identical. Changes:

1. `_build_html()` footer line 158: `"RCA Copilot Agent"` → `"Ticket Assignment Copilot Agent"`
2. `_build_html()` h1 text line 145: `"RCA Analysis Complete"` → `"Ticket Assignment Analysis Complete"`
3. `_build_html()` badge text line 149: `"ANALYSIS COMPLETE"` → `"ASSIGNMENT COMPLETE"`

**Function signatures to preserve exactly** (lines 42-54):
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
```

Note: keep the function name `send_rca_email` (the import in `mcp_server.py` aliases it: `from tools.email_tool import send_rca_email as _send`). Do not rename the function internally.

---

### `ticketasg_copilot_agent/AGENTS.md` (documentation)

**Analog:** `rca_copilot_agent/AGENTS.md`

**DIFFERENCE from analog:** Substantial content differences. Same sections and structure, different tool inventory and workflows. Key structural sections to replicate:

1. `## Purpose` — describe ticket assignment, not RCA
2. `## Tool Inventory` table — replace RCA-specific tools with assignment tools
3. `## Environment Setup` — identical (same ServiceNow credentials, same gcloud ADC)
4. `## Running Without MCP (Skills / CLI Mode)` — update tool names in example commands
5. `## Investigation Workflow` — replace RCA phases with: INGEST → ANALYSE → RECOMMEND → CONCLUDE
6. `## Report Template` — assignment report format (from RESEARCH.md lines 492-516)
7. `## Assignment Groups` section — list the 10 groups with inferred trigger signals

**Tool inventory table pattern to replicate** (from `rca_copilot_agent/AGENTS.md` lines 14-30):
```markdown
## Tool Inventory

| Tool | When to use |
|------|-------------|
| `analyze_incident` | ONE-STOP: fetch incident + attachments + identifiers |
| `recommend_assignment` | **CORE** — score incident signals against routing matrix |
| `get_assignment_rules` | Inspect the routing matrix before recommending |
| `fetch_incidents` | Bulk-download all incidents from a SNOW list URL |
| ...
| `save_assignment_report` | **MANDATORY** — save every completed recommendation to disk |
| `send_assignment_email` | **MANDATORY** — notify the human when the session is done |
```

---

### `.claude/skills/ticketasg-copilot/SKILL.md` (documentation)

**Analog:** `.claude/skills/rca-copilot/SKILL.md`

**DIFFERENCE from analog:** Different invocation keyword, description, and workflow. Same YAML frontmatter structure and same 4-section body structure.

**YAML frontmatter to replicate** (lines 1-8):
```yaml
---
name: ticketasg-copilot
description: >
  Ticket Assignment agent for L'Oréal SPACE CDS ServiceNow incidents.
  Uses Bash tool to call ticketasg_copilot_agent/run_tool.py — no MCP server required.
  Analyses incident text and recommends the correct L2 assignment group from the 10 known groups.
invocation: /ticketasg-copilot
---
```

**Tool invocation table pattern** (from analog lines 24-42) — replicate with new tool names:
```markdown
| Task | Bash command |
|------|-------------|
| Full analysis (use this) | `python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INCx"}'` |
| Get routing rules | `python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'` |
| Recommend assignment | `python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{"incident_number": "INCx", "short_description": "...", "description": "..."}'` |
| **Save report (MANDATORY)** | `python ticketasg_copilot_agent/run_tool.py save_assignment_report --json '{"incident_number": "INCx", "report_text": "..."}'` |
| **Send email (MANDATORY)** | `python ticketasg_copilot_agent/run_tool.py send_assignment_email --json '{"session_summary": "...", "subject": "Assignment Complete — INCx"}'` |
```

**Workflow section pattern** (from analog lines 43-157) — replicate with assignment-specific steps:
```markdown
### Step 1 — Ensure incident data is available
[same pattern as rca-copilot — fetch or list]

### Step 2 — Analyse and recommend
1. `analyze_incident` for each incident
2. `get_assignment_rules` to load the routing matrix
3. `recommend_assignment` with extracted incident fields
4. Write the assignment report
5. `save_assignment_report` — MANDATORY
6. `send_assignment_email` — MANDATORY, once per session

### Step 3 — Post as work note (only on post-comment intent)
[same confirmation pattern as rca-copilot, but `as_work_note: true`]
```

---

### `.github/agents/ticketasg_copilot.agent.md` (agent-def)

**Analog:** `.github/agents/rca_copilot.agent.md`

**DIFFERENCE from analog:** Different agent name, description, tool list in content. YAML frontmatter structure is identical.

**YAML frontmatter to replicate** (from analog lines 1-19):
```yaml
---
name: Ticket Assignment Copilot Agent
description: >
  Ticket Assignment agent for L'Oréal SPACE CDS ServiceNow incidents.
  Analyses incident text, description, comments and work notes to recommend
  the correct L2 assignment group from 10 known groups.
  Uses run_tool.py CLI — no MCP server required.
tools:
  [
    execute/runNotebookCell,
    execute/executionSubagent,
    execute/getTerminalOutput,
    execute/killTerminal,
    execute/sendToTerminal,
    execute/createAndRunTask,
    execute/runInTerminal,
    execute/runTests,
  ]
---
```

**ABSOLUTE TOOL RESTRICTION section** (from analog lines 21-64) — replicate with `ticketasg_copilot_agent/run_tool.py` path and new tool table.

**MANDATORY SEQUENCE pattern** (from analog lines 49-57) — adapt for assignment:
```markdown
**MANDATORY SEQUENCE — no exceptions:**

1. Call `analyze_incident` for any single ticket
2. Call `get_assignment_rules` to load the routing matrix
3. Call `recommend_assignment` with the incident fields from step 1
4. Write the assignment recommendation report
5. Call `save_assignment_report` BEFORE outputting the recommendation
6. After ALL `save_assignment_report` calls, call `send_assignment_email` ONCE
```

---

### `ticketasg_copilot_agent/assignment_rules.json` (config)

**Analog:** None — new concept.

**Use RESEARCH.md pattern** (lines 453-469) for the JSON structure:
```json
{
  "version": "1.0",
  "note": "Routing matrix for SPACE CDS L2 assignment groups. Update keywords here — no code changes needed.",
  "groups": {
    "APAC - SGP - SPACE CDS SAPMENA L2 Support": {
      "keywords": ["SAP", "SAPMENA", "SGP", "Singapore", "pipeline", "CDS", "SPACE CDS"],
      "categories": ["Application Service"],
      "weight": 1.0
    },
    "APAC - THN - Retail IT": {
      "keywords": ["Thailand", "THN", "retail", "POS", "store", "printer", "hardware"],
      "weight": 1.0
    },
    "APAC - ZN - iBeauty 2.0 - Retail - L2": {
      "keywords": ["iBeauty", "beauty advisor", "BA", "in-store", "consultation"],
      "weight": 1.0
    },
    "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2": {
      "keywords": ["OMNISALES", "MARS", "omnichannel", "retail order", "Capgemini", "GDC"],
      "weight": 1.0
    },
    "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2": {
      "keywords": ["CED", "SPACE-GDS", "online", "e-commerce"],
      "weight": 1.0
    },
    "APAC - ZN - O+O.CRM - L2": {
      "keywords": ["CRM", "Salesforce", "loyalty", "consumer profile", "marketing"],
      "weight": 1.0
    },
    "APAC - ZN - O+O.NGLORA - L2": {
      "keywords": ["NGLORA", "LORA", "analytics"],
      "weight": 1.0
    },
    "APAC - ZN - O+O.OPERATIONS - L2": {
      "keywords": ["operations", "ETL", "data ingestion", "sync", "batch"],
      "weight": 1.0
    },
    "APAC - ZN - SPACE B2C Hypercare": {
      "keywords": ["B2C", "hypercare", "go-live", "regression"],
      "weight": 1.0
    },
    "TECH FNDN - WW - HIP INCIDENT L2": {
      "keywords": ["HIP", "infrastructure", "network", "server", "SSO", "certificate", "DNS"],
      "weight": 1.0
    }
  }
}
```

**IMPORTANT:** The routing keywords above are all `[ASSUMED]` (see RESEARCH.md). The planner must flag this file for `[USER-CONFIRM]` before locking keywords. The JSON structure itself is the pattern; the keyword values need user validation.

---

## Shared Patterns

### `sys.path.insert` entry point pattern
**Source:** `rca_copilot_agent/mcp_server.py` (line 52), `rca_copilot_agent/run_tool.py` (line 45)
**Apply to:** `ticketasg_copilot_agent/mcp_server.py`, `ticketasg_copilot_agent/run_tool.py`
```python
# Allow running as `python ticketasg_copilot_agent/mcp_server.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

### ServiceNow credential validation
**Source:** `rca_copilot_agent/mcp_server.py` (lines 61-69)
**Apply to:** `ticketasg_copilot_agent/mcp_server.py` `_build_reader()`
```python
cfg = load_config()
if not cfg.cookie or not cfg.x_user_token:
    raise RuntimeError(
        "COOKIE and X_USERTOKEN must be set in .env or environment. "
        "See .env.example for instructions."
    )
```

### Non-fatal startup initialization
**Source:** `rca_copilot_agent/run_tool.py` (lines 79-104)
**Apply to:** Both `run_tool.py` and `mcp_server.main()` in the new package
```python
# Initialize BigQuery schema (non-fatal if unavailable)
try:
    from tools.bigquery_tool import init_from_schema
    init_from_schema()
except Exception as e:
    logger.warning(f"[BQ] Not available: {e}")

# Pre-load incident store if _all_incidents.json exists
combined = os.path.join(reports_dir, "_all_incidents.json")
if os.path.exists(combined):
    from tools.incident_store import load_store
    load_store(combined)

# Check credentials (non-fatal)
try:
    from tools.auth_tool import ensure_credentials
    ensure_credentials(instance_url=cfg.instance_url)
except Exception as e:
    logger.warning(f"[AUTH] Credential check failed: {type(e).__name__}: {e}")

try:
    from tools.gcloud_tool import ensure_gcloud_auth
    ensure_gcloud_auth()
except Exception as e:
    logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")
```

### Tool dispatch error wrapping
**Source:** `rca_copilot_agent/mcp_server.py` (lines 424-432)
**Apply to:** `ticketasg_copilot_agent/mcp_server.py` `call_tool()` handler
```python
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments, reports_dir)
    except Exception as exc:
        result = f"Tool error ({name}): {type(exc).__name__}: {exc}"
        logger.error(result)
    return [TextContent(type="text", text=str(result))]
```

### `_dispatch` lazy import pattern
**Source:** `rca_copilot_agent/mcp_server.py` (e.g., lines 641-648)
**Apply to:** All tool branches in `ticketasg_copilot_agent/mcp_server.py`
```python
# Imports are inside the branch to avoid circular imports and startup cost
elif name == "query_bigquery":
    from tools.bigquery_tool import is_enabled, query_bigquery as bq_query, _BQ_UNAVAILABLE
    if not is_enabled():
        return _BQ_UNAVAILABLE
    return bq_query(sql=arguments["sql"], rationale=arguments.get("rationale", ""))
```

### MCP SDK import guard (fallback to JSON-RPC)
**Source:** `rca_copilot_agent/mcp_server.py` (lines 880-908)
**Apply to:** `ticketasg_copilot_agent/mcp_server.py` `main()`
```python
try:
    import mcp  # noqa: F401
    # ... asyncio.run(run()) with stdio_server
except ImportError:
    logger.warning("[MCP] mcp SDK not installed. Running JSON-RPC fallback.")
    _run_jsonrpc_fallback(reports_dir)
```

### `_ensure_store_loaded` helper
**Source:** `rca_copilot_agent/mcp_server.py` (lines 749-763)
**Apply to:** `ticketasg_copilot_agent/mcp_server.py` — copy verbatim
```python
def _ensure_store_loaded(reports_dir: str) -> None:
    """Load the incident store if it is empty."""
    from tools.incident_store import get_store
    store = get_store()
    if not store.incidents:
        combined = os.path.join(reports_dir, "_all_incidents.json")
        if os.path.exists(combined):
            from tools.incident_store import load_store
            count = load_store(combined)
            logger.info(f"[MCP] Loaded {count} incidents from {combined}")
        else:
            logger.warning(
                f"[MCP] No incidents file at {combined}. "
                "Call fetch_incidents first."
            )
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `ticketasg_copilot_agent/assignment_rules.json` | config | — | No JSON config files exist in the codebase. Use RESEARCH.md structure |
| `ticketasg_copilot_agent/tools/assignment_tool.py` (business logic) | utility | transform | No keyword-scoring/routing tools exist anywhere in the codebase. Structure pattern taken from `bigquery_tool.py` module layout |

---

## Files Safe to Copy Verbatim (zero logic changes)

| File | Copy from | Note |
|------|-----------|------|
| `ticketasg_copilot_agent/tools/snow_reader.py` | `rca_copilot_agent/tools/snow_reader.py` | Update module docstring header comment only |
| `ticketasg_copilot_agent/tools/incident_store.py` | `rca_copilot_agent/tools/incident_store.py` | Update module docstring header comment only |
| `ticketasg_copilot_agent/tools/auth_tool.py` | `rca_copilot_agent/tools/auth_tool.py` | Truly verbatim — no strings reference RCA |
| `ticketasg_copilot_agent/tools/gcloud_tool.py` | `rca_copilot_agent/tools/gcloud_tool.py` | Truly verbatim |
| `ticketasg_copilot_agent/tools/bigquery_tool.py` | `rca_copilot_agent/tools/bigquery_tool.py` | Truly verbatim — `_SCHEMA_JSON` path depth is identical |

---

## Metadata

**Analog search scope:** `rca_copilot_agent/`, `.claude/skills/rca-copilot/`, `.github/agents/`
**Files scanned:** 12 source files read in full
**Pattern extraction date:** 2026-05-13
