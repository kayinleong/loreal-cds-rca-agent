# Phase 01: Ticket Assignment Agent — Research

**Researched:** 2026-05-13
**Domain:** Python skills-based agent — ServiceNow ticket triage, assignment group routing
**Confidence:** HIGH (primary source: direct codebase analysis; all key patterns verified by reading production files)

---

## Summary

This phase creates `ticketasg_copilot_agent` — a new agent package that mirrors the structure and
patterns of the existing `rca_copilot_agent`. The implementation is almost entirely a structural
clone plus one net-new tool (`assignment_tool.py`). Ninety percent of the code is reused verbatim
or with trivial naming changes.

The assignment agent analyses ServiceNow incident text (short description, description, comments,
work notes) and maps the signal to one of 10 named L2 assignment groups. The routing logic cannot
be fully determined from the codebase alone — the SharePoint routing matrix is behind corporate
SSO and could not be accessed. Inferred routing rules are documented below with `[ASSUMED]` tags;
the planner must flag these for user confirmation before locking into implementation.

The skills-based delivery pattern (no MCP server, `run_tool.py` CLI + `.claude/skills/` +
`.github/agents/`) is fully understood and verified from the existing `rca_copilot_agent` files.

**Primary recommendation:** Clone `rca_copilot_agent` structure, replace the `save_rca_report` /
`send_rca_email` pair with `recommend_assignment`, and implement a `get_assignment_rules` tool
that returns the routing matrix from a config file (so rules can be updated without code changes).

---

## Project Constraints (from CLAUDE.md)

- Python 3.11+ (verified: `.venv` uses Python 3.13.7) [VERIFIED: python3 --version]
- No LLM calls inside `mcp_server.py` or any `tools/*.py` — MCP layer is LLM-agnostic [CITED: project CLAUDE.md]
- Do not commit `my_reports/`, `attachments/`, or `rca_agent/rca_reports/` (gitignored; may contain PII) [CITED: project CLAUDE.md]
- `COOKIE` and `X_USERTOKEN` are live session tokens — never log, echo, or commit [CITED: project CLAUDE.md]
- All config tunables go in `config.py` with env-var overrides [CITED: project CLAUDE.md]
- New tools: create in `<package>/tools/<name>_tool.py`, register in `mcp_server.py` if MCP needed [CITED: project CLAUDE.md]
- Update `AGENTS.md` with every new tool's name, description, inputs/outputs [CITED: project CLAUDE.md]
- `schema.json` must not be staged alongside code changes [CITED: project CLAUDE.md]
- Agent spawning: never use `isolation: "worktree"` [CITED: ~/.claude/CLAUDE.md]

---

## Architecture Analysis (what exists in rca_copilot_agent)

### Verified package structure [VERIFIED: filesystem read]

```
rca_copilot_agent/
  __init__.py              Empty package marker
  config.py                ServiceNowConfig + SmtpConfig dataclasses; _find_env_data() pattern
  mcp_server.py            MCP server + _dispatch() async router; all tool logic lives here
  run_tool.py              CLI: argparse tool/--json; calls asyncio.run(_dispatch()); shares routing with mcp_server
  tools/
    __init__.py            Empty
    auth_tool.py           ensure_credentials() — playwright SSO refresh
    bigquery_tool.py       SafeBigQueryExecutor; get_schema_from_file(); query_bigquery()
    email_tool.py          send_rca_email(); register_report(); _session_reports list
    gcloud_tool.py         ensure_gcloud_auth()
    incident_store.py      IncidentStore class; get_store()/load_store() singletons
    snow_reader.py         ServiceNowReader; get_full_incident_report(); post_comment()
  AGENTS.md                Tool inventory + workflows for human/LLM readers
```

### run_tool.py dispatch pattern [VERIFIED: rca_copilot_agent/run_tool.py]

The CLI is a thin wrapper. It:
1. Parses `tool` positional arg and `--json ARGS` keyword arg
2. Loads config (`load_config()`) and resolves `reports_dir`
3. Initialises BQ schema, loads incident store, runs auth checks (all non-fatal)
4. Calls `from mcp_server import _dispatch` then `asyncio.run(_dispatch(args.tool, arguments, reports_dir))`
5. Prints the result to stdout

The key insight: `run_tool.py` does NOT duplicate routing logic — it imports `_dispatch` from
`mcp_server.py`. The new `ticketasg_copilot_agent/run_tool.py` must do the same.

### _dispatch() routing pattern [VERIFIED: rca_copilot_agent/mcp_server.py]

```python
async def _dispatch(name: str, arguments: dict, reports_dir: str) -> str:
    if name == "tool_name":
        # direct implementation inline or delegating to tools/ module
        ...
    elif name == "other_tool":
        from tools.some_tool import some_function
        return some_function(...)
    else:
        return f"Unknown tool: {name}"
```

All tool routing is a flat `if/elif` chain in `_dispatch()`. No plugin registry, no class hierarchy.

### config.py pattern [VERIFIED: rca_copilot_agent/config.py]

- `_find_env_data()` searches cwd then `__file__` dir for `.env`
- `load_config()` returns `ServiceNowConfig` dataclass — `instance_url, cookie, x_user_token, reports_dir, attachments_dir`
- `load_smtp_config()` returns `SmtpConfig` dataclass — `host, port, user, password, from_addr, to_addrs, use_tls, verify_ssl`
- The new package needs the same `ServiceNowConfig`; SMTP is optional (assignment agent doesn't need email unless we want notification parity)

### incident data structure [VERIFIED: filesystem analysis + incident_store.py]

Every incident JSON has this shape:
```json
{
  "incident": {
    "sys_id": "...",
    "number": "INCxxxxxxxx",
    "short_description": "...",
    "description": "...",
    "state": "Active",
    "priority": "5 - Normal",
    "severity": "...",
    "assigned_to": "...",
    "assignment_group": "APAC - SGP - SPACE CDS SAPMENA L2 Support",
    "category": "Application Service",
    "subcategory": null,
    "created": "...",
    "updated": "..."
  },
  "comments": [{"date": "...", "author": "...", "text": "..."}],
  "work_notes": [{"date": "...", "author": "...", "text": "..."}],
  "attachments": {"images": [...], "files": [...]},
  "related_stories": [...],
  "downloaded_files": [...]
}
```

**Fields most useful for assignment routing:**
- `short_description` — free-text title; often contains system name, country code, or error type
- `description` — longer text; may contain platform name, vendor system, or geography
- `category` / `subcategory` — structured classification (observed: "Application Service")
- `assignment_group` — current group (used for analysis of correct vs incorrect assignment)
- `comments` — support team updates; may contain system names or escalation paths
- `work_notes` — internal notes; may reference specific sub-systems

### .github/agents/*.agent.md YAML frontmatter [VERIFIED: rca_copilot.agent.md]

```yaml
---
name: RCA Copilot Agent
description: >
  [multi-line description]
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

Then the body is a plain Markdown agent instruction file.
The `tools:` list restricts which VS Code tools the agent can use.
`execute/runInTerminal` is the key one for calling `run_tool.py`.

### .claude/skills/*/SKILL.md format [VERIFIED: .claude/skills/rca-copilot/SKILL.md]

```yaml
---
name: rca-copilot
description: >
  [description]
invocation: /rca-copilot
---
```

Then body = workflow instructions for Claude Code. Uses `Bash` tool to call `run_tool.py`.

---

## Tool Inventory

### Tools that can be reused verbatim (copy files, change imports/paths)

| Tool file | Reuse strategy | Notes |
|-----------|---------------|-------|
| `tools/snow_reader.py` | Copy verbatim | No changes needed; pure ServiceNow HTTP client |
| `tools/incident_store.py` | Copy verbatim | Pure data store; no domain-specific code |
| `tools/bigquery_tool.py` | Copy verbatim | BQ may be needed for context enrichment |
| `tools/auth_tool.py` | Copy verbatim | Credential refresh is identical |
| `tools/gcloud_tool.py` | Copy verbatim | ADC check is identical |
| `tools/email_tool.py` | Copy verbatim or skip | Only needed if email notification desired |
| `config.py` | Copy + extend | Add `ASSIGNMENT_RULES_FILE` env var tunable |

**Alternative to copying:** The files are pure functions with no domain coupling.
The cleaner approach is to **copy** (not symlink) each file so the two packages remain independent.
Symlinks create a hidden coupling that would break if `rca_copilot_agent` is refactored.

### Existing MCP tools that map directly to the new agent

All SNOW read tools are reusable as-is:

| Tool name | Keep? | Reason |
|-----------|-------|--------|
| `analyze_incident` | YES — rename to `analyze_ticket_for_assignment` or keep same name | Core data gathering |
| `get_incident` | YES | Live SNOW fetch |
| `get_incident_summary` | YES | Formatted text output |
| `list_incidents` | YES | Batch discovery |
| `fetch_incidents` | YES | Bulk download |
| `search_incidents` | YES | Keyword search |
| `extract_identifiers` | YES | May help identify system-specific patterns |
| `download_attachments` | YES | Images may contain system names/screenshots |
| `post_comment` | YES | Post assignment recommendation back to ticket |
| `query_bigquery` | OPTIONAL | Could look up BQ data to contextualise (e.g., is this a B2B vs B2C issue?) |
| `get_schema` | OPTIONAL | Only needed if BQ queries used |
| `list_bq_tables` | OPTIONAL | Only needed if BQ queries used |
| `save_rca_report` | RENAME → `save_assignment_report` | Save assignment recommendation to disk |
| `send_rca_email` | RENAME → `send_assignment_email` | Optional email notification |

### Net-new tools required

| Tool name | File | Purpose |
|-----------|------|---------|
| `recommend_assignment` | `tools/assignment_tool.py` | **Core new tool.** Takes structured incident signals, returns recommended group + confidence + reason |
| `get_assignment_rules` | `tools/assignment_tool.py` | Returns the routing matrix (from config file or hardcoded dict) so the LLM can inspect the rules |

**Why `recommend_assignment` is a tool (not LLM reasoning):**
The tool takes incident signals (keywords, category, subcategory, geography) and returns a
deterministic recommendation. The LLM then decides whether to accept it or override with its
own reasoning based on full ticket context. Pure function — no LLM calls inside.

---

## Assignment Group Routing Logic

### The 10 groups

```
1. APAC - SGP - SPACE CDS SAPMENA L2 Support
2. APAC - THN - Retail IT
3. APAC - ZN - iBeauty 2.0 - Retail - L2
4. APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2
5. APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2
6. APAC - ZN - O+O.CRM - L2
7. APAC - ZN - O+O.NGLORA - L2
8. APAC - ZN - O+O.OPERATIONS - L2
9. APAC - ZN - SPACE B2C Hypercare
10. TECH FNDN - WW - HIP INCIDENT L2
```

### Inferred routing logic (from group names)

**Note: All inferences below are `[ASSUMED]`. The SharePoint routing matrix was inaccessible
(corporate SSO). User must confirm before these become locked implementation decisions.**

| Group | Inferred Trigger | Signal Keywords | Confidence |
|-------|-----------------|-----------------|------------|
| SGP - SPACE CDS SAPMENA L2 | SAP/MENA platform issues; Singapore-hosted SPACE CDS services; SAP integration failures | "SAP", "MENA", "SAPMENA", "Singapore", "SGP", "pipeline", "CDS" | `[ASSUMED]` MEDIUM |
| THN - Retail IT | Thailand Retail IT hardware or POS system issues | "Thailand", "THN", "retail", "POS", "store", "printer", "hardware" | `[ASSUMED]` MEDIUM |
| iBeauty 2.0 - Retail - L2 | iBeauty POS/retail application issues (L'Oréal's in-store beauty tech) | "iBeauty", "beauty advisor", "BA", "in-store", "consultation", "skin", "shade" | `[ASSUMED]` MEDIUM |
| O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Omnichannel MARS/OMNISALES run issues; Capgemini-managed MARS integration for retail ordering | "OMNISALES", "MARS", "omnichannel", "retail order", "Capgemini", "GDC" | `[ASSUMED]` LOW-MEDIUM |
| O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2 | Online CED (Consumer E-commerce Division?) run issues; Capgemini SPACE-GDS managed | "CED", "SPACE-GDS", "online", "e-commerce", "SPACE GDS", "Capgemini" | `[ASSUMED]` LOW |
| O+O.CRM - L2 | CRM platform issues (Salesforce, loyalty program, consumer profiles) | "CRM", "Salesforce", "loyalty", "consumer profile", "email campaign", "marketing" | `[ASSUMED]` MEDIUM |
| O+O.NGLORA - L2 | NGLORA subsystem (possibly Next-Gen LORA/LOR platform — data routing or analytics) | "NGLORA", "LORA", "LOR", "analytics", "reporting" | `[ASSUMED]` LOW |
| O+O.OPERATIONS - L2 | Operational issues not fitting other O+O categories; general pipeline/ops | "operations", "pipeline", "ETL", "data ingestion", "sync", "batch" | `[ASSUMED]` LOW |
| SPACE B2C Hypercare | Post-go-live support for B2C features recently launched; elevated support window | "B2C", "launch", "go-live", "hypercare", "new feature", "regression" + recency of ticket | `[ASSUMED]` MEDIUM |
| TECH FNDN - WW - HIP INCIDENT L2 | Hardware/Infrastructure Platform issues worldwide; networking, server, auth infrastructure | "HIP", "infrastructure", "network", "server", "authentication", "SSO", "certificate", "DNS" | `[ASSUMED]` LOW-MEDIUM |

### Structural patterns in group names

- `SGP` = Singapore (city code, not country ISO)
- `THN` = Thailand (3-letter country code variant)
- `ZN` = Zone (APAC zone)
- `O+O` = Online + Offline (L'Oréal's omnichannel programme)
- `CAPGEMINI-GDC-*` = Capgemini Global Delivery Centre — indicates Capgemini is the run vendor
- `MARS` = L'Oréal's internal middleware/integration platform
- `CED` = likely Consumer E-commerce Division
- `NGLORA` = likely Next-Gen LORA (a specific internal system)
- `HIP` = Hardware/Infrastructure Platform
- `Hypercare` = post-launch heightened support; time-limited window
- `WW` = Worldwide (not region-specific)

### Routing heuristic (proposed implementation approach) [ASSUMED]

A keyword-based scoring function that takes incident text and returns top-1 group + score:

```python
def score_groups(text: str) -> list[tuple[str, float]]:
    """Return groups sorted by match score, highest first."""
    ...
```

The scoring approach:
1. Normalise text (lowercase, strip punctuation)
2. For each group, count weighted keyword hits in short_description, description, and top 5 comments
3. Apply tie-breakers: category/subcategory match > description match > comment match
4. Return ranked list with confidence ratio

This keeps the tool deterministic (pure function) while allowing the LLM to override with its
full reasoning on the raw ticket text.

---

## Open Questions

These require user input before implementation can be locked. Flag in PLAN.md as `[USER-CONFIRM]`.

1. **SharePoint routing matrix**: The SharePoint spreadsheet at the provided URL contains the
   definitive routing rules. It was inaccessible (corporate SSO). The user should extract and
   paste the routing decision table so it can be embedded as config. Without it, all routing
   logic is inferred and may be wrong.
   - Recommendation: embed as `ticketasg_copilot_agent/assignment_rules.json` (committed)

2. **Routing signals from BQ data**: Should the agent query BigQuery to enrich routing?
   For example, if the ticket has a B2B customer code, should it query BQ to confirm the
   customer's region and use that to discriminate between SGP/ZN groups?
   - Recommendation: start without BQ enrichment; add in a follow-up phase if needed

3. **Confidence threshold**: What confidence score warrants a hard recommendation vs. "needs
   human review"? Without data on how many tickets are borderline, this cannot be set.
   - Recommendation: output top-1 group + top-3 alternatives + per-group score; let the LLM decide

4. **`save_assignment_report` format**: Should the assignment report be a Markdown file (like
   RCA reports) or a structured JSON? JSON would be easier to ingest by downstream tooling.
   - Recommendation: Markdown (consistent with RCA pattern); add JSON summary block at the top

5. **Email notification**: Is email notification needed for assignment recommendations?
   The RCA agent sends an email after each session. Should the assignment agent do the same?
   - Recommendation: include `send_assignment_email` for parity; make it optional (non-fatal
     if SMTP not configured)

6. **`post_comment` behaviour**: When the agent recommends reassignment, should it post a
   work note or a customer-visible comment?
   - Recommendation: work note (`as_work_note: true`) — assignment recommendations are internal

7. **`APAC - ZN - SPACE B2C Hypercare` scope**: Is this group time-limited (only for tickets
   created during a hypercare window) or permanent? If time-limited, the routing logic needs
   a date-range check.

8. **`O+O.NGLORA` definition**: What is NGLORA? This is an internal system name that is not
   obvious from the group label. User should provide the trigger keywords.

---

## Technical Approach

### File organisation

Mirror `rca_copilot_agent` exactly:

```
ticketasg_copilot_agent/
  __init__.py
  config.py             # Same structure; add ASSIGNMENT_RULES_FILE env var
  mcp_server.py         # Identical pattern; different tool set
  run_tool.py           # Identical pattern; imports _dispatch from local mcp_server
  tools/
    __init__.py
    assignment_tool.py  # NEW — routing logic; get_assignment_rules() + recommend_assignment()
    auth_tool.py        # COPY from rca_copilot_agent
    bigquery_tool.py    # COPY from rca_copilot_agent
    email_tool.py       # COPY from rca_copilot_agent (rename email labels)
    gcloud_tool.py      # COPY from rca_copilot_agent
    incident_store.py   # COPY from rca_copilot_agent
    snow_reader.py      # COPY from rca_copilot_agent
  assignment_rules.json # NEW — routing matrix (committed; not secrets)
  AGENTS.md             # NEW — tool inventory and workflow for this agent
.claude/skills/ticketasg-copilot/SKILL.md   # NEW
.github/agents/ticketasg_copilot.agent.md   # NEW
```

### assignment_tool.py design

```python
# tools/assignment_tool.py — pure functions, no LLM calls

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

def get_assignment_rules() -> str:
    """Return the routing matrix as formatted text for LLM inspection."""
    ...

def recommend_assignment(
    incident_number: str,       # for logging
    short_description: str,
    description: str,
    category: str,
    subcategory: str,
    comments_text: str,         # concatenated comment bodies
    work_notes_text: str,       # concatenated work note bodies
    current_group: str = "",    # existing group (for context, not a factor in scoring)
) -> dict:
    """
    Returns:
    {
        "recommended_group": "...",
        "confidence": 0.0-1.0,
        "reason": "...",
        "alternatives": [
            {"group": "...", "score": 0.0},
            ...
        ],
        "reassignment_needed": bool,  # True if recommended != current_group
        "reassignment_reason": "..."  # populated when reassignment_needed is True
    }
    """
    ...
```

### mcp_server.py tool set for ticketasg_copilot_agent

Required tools (subset of rca_copilot_agent + new):
- `analyze_incident` — identical logic
- `get_incident` — identical
- `get_incident_summary` — identical
- `list_incidents` — identical
- `fetch_incidents` — identical
- `search_incidents` — identical
- `post_comment` — identical (for posting assignment recommendations)
- `recommend_assignment` — NEW
- `get_assignment_rules` — NEW
- `save_assignment_report` — adapted from `save_rca_report`
- `send_assignment_email` — adapted from `send_rca_email`

Tools NOT needed:
- `extract_identifiers` — not needed for assignment (no BQ lookup needed by default)
- `download_attachments` — optional; skip for simplicity unless screenshot analysis is needed
- `query_bigquery` / `get_schema` / `list_bq_tables` — skip for initial version

### run_tool.py dispatch

`run_tool.py` in the new package will:
1. Copy `rca_copilot_agent/run_tool.py` exactly
2. Change the `sys.path.insert` to point to this package's directory
3. The `_dispatch` import automatically picks up the new `mcp_server.py`

No other changes needed — the pattern is identical.

### config.py extension

Add one new optional tunable:
```python
ASSIGNMENT_RULES_FILE  # path to assignment_rules.json; default: <pkg_dir>/assignment_rules.json
```

### assignment_rules.json structure (proposed)

```json
{
  "version": "1.0",
  "groups": {
    "APAC - SGP - SPACE CDS SAPMENA L2 Support": {
      "keywords": ["SAP", "SAPMENA", "SGP", "Singapore", "pipeline", "CDS"],
      "categories": ["Application Service"],
      "weight": 1.0
    },
    ...
  }
}
```

This allows the user to update routing rules without code changes.

### GitHub agent definition pattern [VERIFIED: .github/agents/rca_copilot.agent.md]

The `ticketasg_copilot.agent.md` file needs:
1. YAML frontmatter with `name`, `description`, `tools: [execute/runInTerminal, ...]`
2. `## ABSOLUTE TOOL RESTRICTION` section explaining `run_in_terminal` + `run_tool.py` pattern
3. Tool invocation table
4. Mandatory sequence (analyze → recommend → save → email)
5. Output format for assignment recommendation

### Claude Code skill definition pattern [VERIFIED: .claude/skills/rca-copilot/SKILL.md]

The `SKILL.md` needs:
1. YAML frontmatter: `name`, `description`, `invocation: /ticketasg-copilot`
2. Prerequisites (venv, .env, gcloud ADC)
3. Tool invocation reference table
4. Workflow: detect intent → fetch/list → analyze → recommend → save → (optionally post comment)
5. Output format for assignment recommendation

### Assignment report format (proposed)

```markdown
# Assignment Recommendation: {incident_number}
**{short_description}**
*Analysed: {date}*

---

## RECOMMENDED ASSIGNMENT GROUP
{group_name}

**Confidence:** {confidence_pct}%

## REASSIGNMENT NEEDED
{Yes/No} — {reason if yes}

## WHAT SIGNALS DROVE THIS RECOMMENDATION
→ {signal_1} — {explanation}
→ {signal_2} — {explanation}

## ALTERNATIVE GROUPS CONSIDERED
| Group | Score |
|-------|-------|
| ... | ... |

## CURRENT ASSIGNMENT
{current_group}
```

---

## File Inventory (every file to create or modify)

### New files to create

| File | Type | Description |
|------|------|-------------|
| `ticketasg_copilot_agent/__init__.py` | New | Empty package marker |
| `ticketasg_copilot_agent/config.py` | New (from rca copy + extend) | Config dataclass; add ASSIGNMENT_RULES_FILE |
| `ticketasg_copilot_agent/mcp_server.py` | New (from rca copy + adapt) | Tool list + _dispatch router; new tool names |
| `ticketasg_copilot_agent/run_tool.py` | New (from rca copy + path fix) | CLI entry; imports _dispatch from local mcp_server |
| `ticketasg_copilot_agent/tools/__init__.py` | New | Empty |
| `ticketasg_copilot_agent/tools/assignment_tool.py` | New (net new) | get_assignment_rules() + recommend_assignment() |
| `ticketasg_copilot_agent/tools/auth_tool.py` | New (copy from rca) | Identical |
| `ticketasg_copilot_agent/tools/bigquery_tool.py` | New (copy from rca) | Identical |
| `ticketasg_copilot_agent/tools/email_tool.py` | New (copy + minor rename) | Change "RCA" → "Assignment" in labels |
| `ticketasg_copilot_agent/tools/gcloud_tool.py` | New (copy from rca) | Identical |
| `ticketasg_copilot_agent/tools/incident_store.py` | New (copy from rca) | Identical |
| `ticketasg_copilot_agent/tools/snow_reader.py` | New (copy from rca) | Identical |
| `ticketasg_copilot_agent/assignment_rules.json` | New | Routing matrix config |
| `ticketasg_copilot_agent/AGENTS.md` | New | Tool inventory + workflow docs |
| `.claude/skills/ticketasg-copilot/SKILL.md` | New | Claude Code skill definition |
| `.github/agents/ticketasg_copilot.agent.md` | New | GitHub Copilot agent definition |

### Files to modify

None — this is a greenfield package. No existing files need to change.

---

## Dependencies and Risks

### Dependencies (all already in requirements.txt) [VERIFIED: requirements.txt]

| Package | Version | Used for |
|---------|---------|----------|
| `requests` | 2.33.1 | ServiceNow REST API calls (via snow_reader.py) |
| `python-dotenv` | 1.2.2 | .env loading in config.py + auth_tool.py |
| `google-cloud-bigquery` | 3.41.0 | BQ queries (optional for this agent) |
| `mcp` | 1.27.0 | MCP server mode (optional; run_tool.py works without) |
| `playwright` | 1.59.0 | SSO browser login for credential refresh |

No new dependencies required. [VERIFIED: rca_copilot_agent uses all the same libraries]

### Risks

**R1 — Routing logic accuracy [HIGH RISK]**
The SharePoint document with definitive routing rules was inaccessible. All inferred routing
is based on group name parsing. The implementation must be designed so rules can be updated
from `assignment_rules.json` without code changes. User must provide the routing matrix
before the assignment logic is finalized.

**R2 — `recommend_assignment` tool is a heuristic, not ground truth [MEDIUM]**
The LLM must be instructed that the tool's recommendation is a starting signal, not a final
answer. The agent persona should always show the LLM the full ticket text AND the tool output
and let the LLM reason about the final recommendation.

**R3 — Limited test data [MEDIUM]**
Only 1 incident was found in local `my_reports/` (`_all_incidents.json` in repo root). It is
assigned to `APAC - SGP - SPACE CDS SAPMENA L2 Support`. This is insufficient to validate
routing accuracy across all 10 groups during execution. The planner should note that real
incident data will be needed for verification.

**R4 — `assignment_rules.json` must be committed but not contain secrets [LOW]**
The routing matrix is config, not secrets. It is safe to commit. However, if group names or
routing criteria are considered internal-only, the user should confirm before committing.

**R5 — `mcp_server.py` not needed in practice [LOW]**
The phase description says "no MCP server — same pattern as rca_copilot_agent with run_tool.py
CLI". The rca_copilot_agent has both `mcp_server.py` AND `run_tool.py`. For consistency, both
should be created, but only `run_tool.py` is needed for the skills-based operation described.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Incident data fetch | rca_copilot_agent/ServiceNow REST | — | Reused verbatim from existing agent |
| Assignment routing logic | ticketasg_copilot_agent/assignment_tool.py | — | Pure function in tools layer; no LLM |
| LLM reasoning for final recommendation | LLM client (GitHub Copilot / Claude Code) | — | Agent body — never in tools/ |
| Routing rules configuration | assignment_rules.json (committed config) | ASSIGNMENT_RULES_FILE env var | Updateable without code changes |
| Report persistence | ticketasg_copilot_agent/mcp_server.py (save_assignment_report) | run_tool.py CLI | Same pattern as rca_copilot_agent |
| Comment posting back to SNOW | ticketasg_copilot_agent/tools/snow_reader.py | — | Reused verbatim |
| Email notification | ticketasg_copilot_agent/tools/email_tool.py | — | Optional; copied with label changes |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | Yes | 3.13.7 | — |
| `requests` | snow_reader.py | Yes | 2.33.1 | — |
| `python-dotenv` | config.py, auth_tool.py | Yes | 1.2.2 | — |
| `google-cloud-bigquery` | bigquery_tool.py | Yes | 3.41.0 | BQ skippable |
| `mcp` | mcp_server.py | Yes | 1.27.0 | run_tool.py works without |
| `playwright` | auth_tool.py | Yes | 1.59.0 | Manual credential copy |
| `certifi` | email_tool.py | Yes | 2026.4.22 | Falls back to system SSL |
| ServiceNow live session | SNOW tools | Requires .env (COOKIE, X_USERTOKEN) | — | auth_tool.py auto-refresh |
| gcloud ADC | bigquery_tool.py | Must run `gcloud auth application-default login` | — | BQ features disabled until auth |

---

## Validation Architecture

> No `.planning/config.json` found — treating `nyquist_validation` as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected (no pytest.ini, no tests/ directory) |
| Config file | None — would need Wave 0 creation |
| Quick run command | `python -m pytest ticketasg_copilot_agent/ -x -q` (after framework install) |
| Full suite command | `python -m pytest ticketasg_copilot_agent/ -v` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Notes |
|-----|----------|-----------|-------|
| REQ-01 | `recommend_assignment()` returns correct group given known-good signals | Unit | Pure function — testable without SNOW |
| REQ-02 | `get_assignment_rules()` returns the 10 groups correctly formatted | Unit | Pure function |
| REQ-03 | `config.py` reads ASSIGNMENT_RULES_FILE from env | Unit | No network needed |
| REQ-04 | `run_tool.py recommend_assignment` CLI invocation returns valid JSON | Smoke | Requires .env present |
| REQ-05 | Assignment recommendation posted as work note to SNOW | Manual | Live SNOW credentials |
| REQ-06 | `save_assignment_report` creates Markdown file | Unit | File system only |

### Wave 0 Gaps

- [ ] `tests/__init__.py` and `tests/test_assignment_tool.py` — covers REQ-01, REQ-02
- [ ] `tests/test_config.py` — covers REQ-03
- [ ] Framework install: `pip install pytest` (not in requirements.txt)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SGP group handles Singapore-hosted SPACE CDS / SAP-MENA incidents | Routing Logic | Wrong routing for Singapore tickets |
| A2 | THN group handles Thailand Retail IT (hardware/POS/network) | Routing Logic | Wrong routing for Thailand tickets |
| A3 | iBeauty group handles in-store beauty consultation app incidents | Routing Logic | Wrong routing for iBeauty tickets |
| A4 | OMNISALES.RETAIL is for MARS integration + retail order issues | Routing Logic | Wrong routing for omnichannel retail |
| A5 | ONLINE.CED is for Consumer E-commerce Division online incidents | Routing Logic | Wrong routing for online/e-commerce |
| A6 | O+O.CRM is for CRM/Salesforce/loyalty/marketing incidents | Routing Logic | Wrong routing for CRM tickets |
| A7 | NGLORA is a specific internal system (not widely documented) | Routing Logic | NGLORA tickets routed to wrong group |
| A8 | O+O.OPERATIONS handles general pipeline/ETL/operational incidents | Routing Logic | Catch-all mismatch |
| A9 | SPACE B2C Hypercare is for post-go-live B2C support regardless of time window | Routing Logic | Over/under-routing to Hypercare |
| A10 | HIP is Hardware/Infrastructure Platform — network, infra, auth | Routing Logic | Infrastructure tickets misrouted |
| A11 | `recommend_assignment` should be a keyword-scoring function (deterministic) | Technical Approach | If rules are more complex, scoring may fail |
| A12 | Email notification should be included (parity with rca_copilot_agent) | Tool Inventory | Unnecessary complexity if not needed |
| A13 | BQ enrichment not needed for initial version | Technical Approach | May miss group signals that require data lookup |

---

## Sources

### Primary (HIGH confidence)
- `rca_copilot_agent/run_tool.py` — dispatch pattern, CLI structure [VERIFIED: file read]
- `rca_copilot_agent/mcp_server.py` — tool list, _dispatch routing, 13 tools [VERIFIED: file read]
- `rca_copilot_agent/config.py` — config dataclass pattern [VERIFIED: file read]
- `rca_copilot_agent/tools/snow_reader.py` — ServiceNow client API [VERIFIED: file read]
- `rca_copilot_agent/tools/incident_store.py` — data structure, field names [VERIFIED: file read]
- `rca_copilot_agent/tools/bigquery_tool.py` — BQ executor pattern [VERIFIED: file read]
- `.github/agents/rca_copilot.agent.md` — agent definition format [VERIFIED: file read]
- `.claude/skills/rca-copilot/SKILL.md` — skill definition format [VERIFIED: file read]
- `my_reports/_all_incidents.json` — live incident data showing field names [VERIFIED: python3 extraction]
- `requirements.txt` — all installed packages and versions [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- Group name parsing and acronym interpretation [ASSUMED: training knowledge; no official doc]

---

## Metadata

**Confidence breakdown:**
- rca_copilot_agent structure: HIGH — read every file
- run_tool.py / _dispatch pattern: HIGH — read production code
- Incident data fields: HIGH — extracted from live JSON
- Tool reuse assessment: HIGH — direct code analysis
- Assignment group routing rules: LOW — SharePoint inaccessible; all inferred from names
- File count to create: HIGH — derived from verified structure

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (stable codebase; routing rules need user confirmation regardless)

---

## RESEARCH COMPLETE
