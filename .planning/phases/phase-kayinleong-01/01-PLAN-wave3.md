---
wave: 3
depends_on: [wave2]
files_modified:
  - ticketasg_copilot_agent/mcp_server.py
  - ticketasg_copilot_agent/run_tool.py
autonomous: true
requirements:
  - phase-kayinleong-01
must_haves:
  - mcp_server.py exports async _dispatch(name, arguments, reports_dir) function
  - _dispatch routes all 11 tool names without raising KeyError
  - run_tool.py is callable as `python ticketasg_copilot_agent/run_tool.py <tool> --json '{}'`
  - run_tool.py imports _dispatch from local mcp_server (not rca_copilot_agent)
  - 11 tools registered: fetch_incidents, get_incident, get_incident_summary, list_incidents, analyze_incident, search_incidents, post_comment, recommend_assignment, get_assignment_rules, save_assignment_report, send_assignment_email
---

<objective>
Create `mcp_server.py` (the routing hub with all 11 tools) and `run_tool.py` (the CLI entry
point that delegates to `_dispatch`). Both files follow the same structure as their
`rca_copilot_agent` counterparts — the only changes are the tool set and server name strings.

Purpose: `run_tool.py` is the primary runtime interface. `mcp_server.py` provides the tool
routing used by both `run_tool.py` (CLI) and any MCP client.

Output: 2 files — `mcp_server.py`, `run_tool.py`.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/CLAUDE.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/01-PATTERNS.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/rca_copilot_agent/mcp_server.py

<interfaces>
<!-- Tools in ticketasg_copilot_agent/mcp_server.py — exact 11 tool names -->

SNOW tools (copy _dispatch branches verbatim from rca_copilot_agent/mcp_server.py):
  fetch_incidents, get_incident, get_incident_summary, list_incidents,
  analyze_incident, search_incidents, post_comment

Tools NOT included (stripped from rca version):
  extract_identifiers, query_bigquery, get_schema, list_bq_tables, download_attachments

Renamed/new tools (implement as shown in PATTERNS.md):
  recommend_assignment   — from tools.assignment_tool import recommend_assignment
  get_assignment_rules   — from tools.assignment_tool import get_assignment_rules
  save_assignment_report — adapted from save_rca_report (dir: assignment_reports, header: Assignment Recommendation)
  send_assignment_email  — adapted from send_rca_email (same structure, different subject default)

Server name: "ticketasg-copilot" (was "rca-copilot")
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create mcp_server.py</name>
  <files>
    ticketasg_copilot_agent/mcp_server.py
  </files>
  <read_first>
    rca_copilot_agent/mcp_server.py — read the FULL file; this is the structural template
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 195-345 — exact diff for mcp_server.py
  </read_first>
  <action>
Create `ticketasg_copilot_agent/mcp_server.py` by adapting `rca_copilot_agent/mcp_server.py`.

Key changes from the analog — apply ALL of these:

**1. Module docstring** — update server name and tool list:
```python
"""
Ticket Assignment Copilot MCP Server
======================================
Exposes ServiceNow tools via Model Context Protocol (MCP).
...
ServiceNow tools:
  fetch_incidents, get_incident, get_incident_summary, list_incidents,
  analyze_incident, search_incidents, post_comment,
  recommend_assignment, get_assignment_rules,
  save_assignment_report, send_assignment_email
"""
```

**2. `sys.path.insert`** — copy verbatim (line 52 in analog):
```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

**3. `_build_reader()`** — copy verbatim.

**4. `create_mcp_server()`** — change server name string:
```python
server = Server("ticketasg-copilot")  # was "rca-copilot"
```

**5. `list_tools()` in `create_mcp_server()`** — register exactly these 11 Tool objects:
  - `fetch_incidents` — copy Tool definition verbatim
  - `get_incident` — copy verbatim
  - `get_incident_summary` — copy verbatim
  - `list_incidents` — copy verbatim
  - `analyze_incident` — copy verbatim (update description: replace "RCA" with "assignment analysis")
  - `search_incidents` — copy verbatim
  - `post_comment` — copy verbatim

  Then ADD these 4 new Tool definitions:

  ```python
  Tool(
      name="recommend_assignment",
      description=(
          "Analyse incident signals and return the recommended L2 assignment group. "
          "Takes structured incident fields and returns recommended_group, confidence, "
          "reason, alternatives, and reassignment_needed. "
          "This is a deterministic heuristic — the LLM should verify the recommendation "
          "against the full ticket context before accepting it."
      ),
      inputSchema={
          "type": "object",
          "properties": {
              "incident_number": {"type": "string", "description": "Incident number for logging, e.g. INC10403788"},
              "short_description": {"type": "string", "description": "Incident short description"},
              "description": {"type": "string", "description": "Incident full description"},
              "category": {"type": "string", "description": "Incident category", "default": ""},
              "subcategory": {"type": "string", "description": "Incident subcategory", "default": ""},
              "comments_text": {"type": "string", "description": "Concatenated comment bodies", "default": ""},
              "work_notes_text": {"type": "string", "description": "Concatenated work note bodies", "default": ""},
              "current_group": {"type": "string", "description": "Current assignment group (for reassignment check)", "default": ""},
          },
          "required": ["incident_number", "short_description", "description"],
      },
  ),
  Tool(
      name="get_assignment_rules",
      description=(
          "Return the full assignment routing matrix as formatted text — "
          "group names, trigger keywords, and confidence weights. "
          "Call this before recommend_assignment to understand available groups."
      ),
      inputSchema={"type": "object", "properties": {}},
  ),
  Tool(
      name="save_assignment_report",
      description=(
          "Save a completed assignment recommendation report to disk as a Markdown file. "
          "ALWAYS call this after generating the assignment recommendation for each incident. "
          "The saved path is tracked for the current session so send_assignment_email can attach it. "
          "Returns the path where the report was saved."
      ),
      inputSchema={
          "type": "object",
          "properties": {
              "incident_number": {"type": "string", "description": "Incident number, e.g. INC10403788"},
              "report_text": {"type": "string", "description": "The complete assignment recommendation report text"},
          },
          "required": ["incident_number", "report_text"],
      },
  ),
  Tool(
      name="send_assignment_email",
      description=(
          "Send an HTML email to notify the human reviewer that ticket assignment analysis is complete. "
          "Call this AFTER all save_assignment_report calls for the session. "
          "Requires SMTP settings in .env. Returns success/failure message."
      ),
      inputSchema={
          "type": "object",
          "properties": {
              "session_summary": {
                  "type": "string",
                  "description": "Plain-text summary of which incidents were analysed and their recommended groups.",
              },
              "subject": {
                  "type": "string",
                  "description": "Email subject line.",
                  "default": "Ticket Assignment Analysis Complete — Please Review",
              },
          },
          "required": ["session_summary"],
      },
  ),
  ```

**6. `_dispatch()` function** — adapt `rca_copilot_agent/mcp_server.py` _dispatch:

  Keep these branches VERBATIM (copy from rca_copilot_agent):
  - `fetch_incidents`, `get_incident`, `get_incident_summary`, `list_incidents`
  - `analyze_incident`, `search_incidents`, `post_comment`

  DO NOT include these branches (stripped from the new version):
  - `extract_identifiers`, `query_bigquery`, `get_schema`, `list_bq_tables`, `download_attachments`

  ADD these new/adapted branches:

  ```python
  elif name == "recommend_assignment":
      from tools.assignment_tool import recommend_assignment as _recommend
      result = _recommend(
          incident_number=arguments.get("incident_number", ""),
          short_description=arguments.get("short_description", ""),
          description=arguments.get("description", ""),
          category=arguments.get("category", ""),
          subcategory=arguments.get("subcategory", ""),
          comments_text=arguments.get("comments_text", ""),
          work_notes_text=arguments.get("work_notes_text", ""),
          current_group=arguments.get("current_group", ""),
      )
      return json.dumps(result, indent=2)

  elif name == "get_assignment_rules":
      from tools.assignment_tool import get_assignment_rules as _get_rules
      return _get_rules()

  elif name == "save_assignment_report":
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

  The final `else` branch stays:
  ```python
  else:
      return f"Unknown tool: {name}"
  ```

**7. `_ensure_store_loaded()` and `_resolve_sys_id()`** — copy verbatim from analog.

**8. `_run_jsonrpc_fallback()`** — copy verbatim but update the tool name list to reflect the 11 tools.

**9. `main()`** — copy verbatim with two string changes:
  - `"RCA Copilot MCP Server"` → `"Ticket Assignment Copilot MCP Server"` (argparse description)
  - `server_name="rca-copilot"` → `server_name="ticketasg-copilot"` in InitializationOptions
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python -c "
import sys, asyncio
sys.path.insert(0, 'ticketasg_copilot_agent')
from mcp_server import _dispatch

# Test: unknown tool returns proper error string, does not raise
result = asyncio.run(_dispatch('unknown_tool_xyz', {}, '/tmp'))
assert 'Unknown tool' in result, f'Expected unknown tool error, got: {result}'
print('dispatch unknown tool: OK')

# Test: get_assignment_rules works without SNOW credentials
result2 = asyncio.run(_dispatch('get_assignment_rules', {}, '/tmp'))
assert 'APAC - SGP' in result2, f'Expected group names, got: {result2[:200]}'
print('get_assignment_rules via dispatch: OK')
print('ALL mcp_server dispatch tests PASS')
"</automated>
  </verify>
  <done>
    `mcp_server.py` exists. `_dispatch` is importable. `_dispatch("get_assignment_rules", {}, "/tmp")` returns string with group names. `_dispatch("unknown_tool_xyz", {}, "/tmp")` returns "Unknown tool: unknown_tool_xyz". `grep "ticketasg-copilot" ticketasg_copilot_agent/mcp_server.py` returns at least 2 matches.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create run_tool.py</name>
  <files>
    ticketasg_copilot_agent/run_tool.py
  </files>
  <read_first>
    rca_copilot_agent/run_tool.py — copy verbatim; change docstring and description string only
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 119-191 — exact run_tool.py pattern
  </read_first>
  <action>
Copy `rca_copilot_agent/run_tool.py` verbatim. Make exactly two changes:

1. **Module docstring** — replace the tool name list and usage examples to reflect the 11 new tools:
```python
"""
run_tool.py — Unified CLI for ticketasg_copilot_agent tools (no MCP server required).

Usage:
    python ticketasg_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'

Examples:
    python ticketasg_copilot_agent/run_tool.py list_incidents --json '{}'
    python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'
    python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{"incident_number": "INC001", "short_description": "SAP error", "description": "SAPMENA pipeline failed"}'
    python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'
    python ticketasg_copilot_agent/run_tool.py save_assignment_report --json '{"incident_number": "INC001", "report_text": "..."}'
    python ticketasg_copilot_agent/run_tool.py send_assignment_email --json '{"session_summary": "Analysed INC001"}'

Tool names:
    list_incidents          List all locally cached incidents
    fetch_incidents         Download all incidents from a SNOW list-view URL
    get_incident            Fetch a single incident from SNOW by number
    get_incident_summary    Read a locally cached incident full text
    analyze_incident        ONE-STOP: fetch + identifiers for one incident
    search_incidents        Keyword-search across all local incidents
    post_comment            Post a comment or work note to SNOW (confirm before calling)
    recommend_assignment    Score incident signals → recommended L2 group + confidence
    get_assignment_rules    Show the routing matrix (all 10 groups + keywords)
    save_assignment_report  Save a completed assignment report to disk
    send_assignment_email   Send HTML email notification with attached reports
"""
```

2. **`argparse` description string** — change:
   `"Run an rca_copilot_agent tool without starting an MCP server."`
   to:
   `"Run a ticketasg_copilot_agent tool without starting an MCP server."`

All other code is copied verbatim — the dispatch mechanism is identical:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
...
from mcp_server import _dispatch  # imports from ticketasg_copilot_agent/mcp_server.py
result = asyncio.run(_dispatch(args.tool, arguments, reports_dir))
```

This works correctly because `sys.path.insert(0, str(Path(__file__).resolve().parent))` at line 45
puts `ticketasg_copilot_agent/` at the front of `sys.path`, so `from mcp_server import _dispatch`
resolves to `ticketasg_copilot_agent/mcp_server.py`, not `rca_copilot_agent/mcp_server.py`.
  </action>
  <verify>
    <automated>cd /Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent && python ticketasg_copilot_agent/run_tool.py --help 2>&1 | head -5</automated>
  </verify>
  <done>
    `python ticketasg_copilot_agent/run_tool.py --help` exits 0 and prints usage text containing "ticketasg_copilot_agent". `grep "rca_copilot_agent" ticketasg_copilot_agent/run_tool.py` returns empty (no cross-package references in code). `grep "from mcp_server import _dispatch" ticketasg_copilot_agent/run_tool.py` returns one line.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI args → run_tool.py | `--json` argument parsed with `json.loads()`; invalid JSON exits 1 with error |
| MCP client → mcp_server.py call_tool() | Tool arguments from untrusted MCP client; all errors caught and returned as strings |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave3-01 | Elevation of Privilege | mcp_server.py _dispatch | mitigate | No tools with write access to ServiceNow (except post_comment); post_comment requires explicit caller action |
| T-wave3-02 | Tampering | save_assignment_report | mitigate | Safe filename via `.replace("/", "_")` prevents path traversal; output dir is `reports_dir/assignment_reports/` only |
| T-wave3-03 | Information Disclosure | send_assignment_email SMTP password | mitigate | Password read from config, passed to SMTP lib only; never logged per global CLAUDE.md rules |
</threat_model>

<verification>
From repo root:
1. `python ticketasg_copilot_agent/run_tool.py --help` — exits 0, prints "ticketasg_copilot_agent"
2. `python -c "import sys, asyncio; sys.path.insert(0,'ticketasg_copilot_agent'); from mcp_server import _dispatch; r=asyncio.run(_dispatch('get_assignment_rules',{},'/tmp')); assert 'APAC' in r"` — exits 0
3. `grep "ticketasg-copilot" ticketasg_copilot_agent/mcp_server.py | wc -l` — returns >= 2
4. `grep "rca_copilot_agent" ticketasg_copilot_agent/run_tool.py` — returns empty
</verification>

<success_criteria>
- `run_tool.py --help` exits 0 without SNOW credentials
- `run_tool.py get_assignment_rules --json '{}'` returns formatted routing matrix text
- `_dispatch` has routing branches for all 11 tool names
- `_dispatch("unknown_tool", {}, "/tmp")` returns "Unknown tool: unknown_tool" (no exception)
- No cross-package imports from `rca_copilot_agent` in either file
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-01/phase-kayinleong-01-wave3-SUMMARY.md`
</output>
