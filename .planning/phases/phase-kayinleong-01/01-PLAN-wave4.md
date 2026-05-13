---
wave: 4
depends_on: [wave3]
files_modified:
  - ticketasg_copilot_agent/AGENTS.md
  - .claude/skills/ticketasg-copilot/SKILL.md
  - .github/agents/ticketasg_copilot.agent.md
autonomous: true
requirements:
  - phase-kayinleong-01
must_haves:
  - AGENTS.md documents all 11 tool names with when-to-use guidance
  - SKILL.md has valid YAML frontmatter with name, description, invocation: /ticketasg-copilot
  - ticketasg_copilot.agent.md has valid YAML frontmatter with name and tools list
  - Both agent files include MANDATORY SEQUENCE (analyze → get_assignment_rules → recommend_assignment → save_assignment_report → send_assignment_email)
  - SKILL.md tool invocation table lists all 11 tools with exact run_tool.py commands
---

<objective>
Create the three documentation/agent-definition files that enable the agent to be invoked
from GitHub Copilot and Claude Code.

Purpose: Without these files the tooling exists but no agent can use it. These files are the
interface between the tool layer (Wave 2-3) and the AI clients.

Output: `AGENTS.md`, `.claude/skills/ticketasg-copilot/SKILL.md`,
`.github/agents/ticketasg_copilot.agent.md`.
</objective>

<execution_context>
@/Users/ka.yin.leong/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ka.yin.leong/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/CLAUDE.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.planning/phases/phase-kayinleong-01/01-PATTERNS.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/rca_copilot_agent/AGENTS.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.claude/skills/rca-copilot/SKILL.md
@/Users/ka.yin.leong/Documents/Development/space-cds-etl-core-feature-rca-agent/.github/agents/rca_copilot.agent.md

<interfaces>
<!-- Exact 11 tool names for documentation tables -->
fetch_incidents, get_incident, get_incident_summary, list_incidents,
analyze_incident, search_incidents, post_comment,
recommend_assignment, get_assignment_rules,
save_assignment_report, send_assignment_email

<!-- Mandatory sequence for agent instructions -->
1. analyze_incident (one-stop: fetch + identifiers)
2. get_assignment_rules (load routing matrix)
3. recommend_assignment (score incident fields)
4. Write assignment recommendation report
5. save_assignment_report (MANDATORY — before outputting)
6. send_assignment_email (MANDATORY — once per session, after all saves)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create ticketasg_copilot_agent/AGENTS.md</name>
  <files>
    ticketasg_copilot_agent/AGENTS.md
  </files>
  <read_first>
    rca_copilot_agent/AGENTS.md — structural template; all sections to replicate
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 639-666 — AGENTS.md adaptation rules
  </read_first>
  <action>
Create `ticketasg_copilot_agent/AGENTS.md` with these sections. Follow the structure of
`rca_copilot_agent/AGENTS.md` exactly; replace RCA-specific content with assignment content.

```markdown
# AGENTS.md — Ticket Assignment Copilot Agent

> Instruction schema for GitHub Copilot (or any MCP-aware LLM client).
> All LLM reasoning stays in the client. This server exposes only pure-function tools.

## Purpose

Analyse ServiceNow incidents for L'Oréal SPACE CDS and recommend the correct L2 assignment group
from 10 known groups. Reads comments, work notes, and attachments to identify routing signals.
Can post assignment recommendations back to ServiceNow as work notes.

## Tool Inventory

| Tool | When to use |
|------|-------------|
| `analyze_incident` | ONE-STOP: fetch incident + attachments + identifiers |
| `get_assignment_rules` | Load the routing matrix before calling recommend_assignment |
| `recommend_assignment` | **CORE** — score incident signals → recommended group + confidence |
| `fetch_incidents` | Bulk-download all incidents from a SNOW list URL |
| `get_incident` | Fetch a single live incident by number |
| `get_incident_summary` | Read full incident text from local cache |
| `list_incidents` | Discover what is locally available |
| `search_incidents` | Keyword-search across all local incidents |
| `post_comment` | Post assignment recommendation as work note to SNOW (confirm with user first) |
| `save_assignment_report` | **MANDATORY** — save every completed recommendation to disk |
| `send_assignment_email` | **MANDATORY** — notify the human when the session is done |

## Assignment Groups (10 L2 Groups)

[USER-CONFIRM] The routing keywords below are inferred from group names. Verify against the
official SharePoint routing matrix before production use.

| Group | Inferred Trigger Signals |
|-------|--------------------------|
| APAC - SGP - SPACE CDS SAPMENA L2 Support | SAP, SAPMENA, SGP, Singapore, CDS pipeline, ERP, product sync |
| APAC - THN - Retail IT | Thailand, THN, POS, retail store, printer, hardware, store network |
| APAC - ZN - iBeauty 2.0 - Retail - L2 | iBeauty, beauty advisor, BA, in-store app, clienteling, consultation |
| APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | OMNISALES, MARS, Capgemini, GDC, click and collect, ship from store, omnichannel |
| APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2 | CED, e-commerce, online, web order, cart, checkout, SPACE GDS |
| APAC - ZN - O+O.CRM - L2 | CRM, loyalty, consumer profile, lucid, registration, consent, GDPR, marketing |
| APAC - ZN - O+O.NGLORA - L2 | NGLORA, LORA, ORA, rewards, points, tier, redemption |
| APAC - ZN - O+O.OPERATIONS - L2 | operations, ETL, batch, pipeline, data sync, API, webhook (default fallback) |
| APAC - ZN - SPACE B2C Hypercare | hypercare, go-live, launch, B2C, cutover, P1, escalation, new market |
| TECH FNDN - WW - HIP INCIDENT L2 | HIP, infrastructure, network, server, SSL, certificate, DNS, SSO, cloud |

## Environment Setup

### ServiceNow Credentials (auto-refreshed)

At startup the server checks whether `COOKIE` and `X_USERTOKEN` in `.env` are valid.
If missing or expired, a Microsoft Edge window opens automatically for SSO login.
Credentials are written back to `.env` after login — no manual DevTools copy-paste needed.

**First-time setup (one-time only):**
```bash
pip install playwright
```

If playwright is not installed, the server falls back to the manual instructions in `.env.example`.

## Running Without MCP (Skills / CLI Mode)

L'Oréal's environment does not allow MCP servers. Use `run_tool.py` instead:

```bash
# ONE-STOP: analyse a single incident
python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'

# Show routing matrix
python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'

# Recommend assignment group
python ticketasg_copilot_agent/run_tool.py recommend_assignment \
    --json '{"incident_number": "INC10403788", "short_description": "SAP pipeline error", "description": "SAPMENA sync failed", "current_group": "APAC - ZN - O+O.OPERATIONS - L2"}'

# List locally cached incidents
python ticketasg_copilot_agent/run_tool.py list_incidents --json '{}'

# Save recommendation report (MANDATORY after each incident)
python ticketasg_copilot_agent/run_tool.py save_assignment_report \
    --json '{"incident_number": "INC10403788", "report_text": "## RECOMMENDED ASSIGNMENT GROUP\n..."}'

# Send email notification (MANDATORY once per session, after all reports saved)
python ticketasg_copilot_agent/run_tool.py send_assignment_email \
    --json '{"session_summary": "Analysed INC10403788 — recommended SGP group", "subject": "Assignment Analysis Complete — INC10403788"}'
```

**For Claude Code users:** invoke the `/ticketasg-copilot` skill (`.claude/skills/ticketasg-copilot/SKILL.md`)

**For GitHub Copilot users:** the `.github/agents/ticketasg_copilot.agent.md` agent definition
uses `run_in_terminal` to call `run_tool.py` directly.

**All 11 tool names** (valid `<tool_name>` values):

| Tool | Description |
|------|-------------|
| `list_incidents` | List locally cached incidents |
| `fetch_incidents` | Download all incidents from a SNOW list URL |
| `get_incident` | Fetch a single incident from SNOW by number |
| `get_incident_summary` | Read locally cached incident full text |
| `analyze_incident` | ONE-STOP: fetch + identifiers |
| `search_incidents` | Keyword-search local incidents |
| `post_comment` | Post comment / work note to SNOW |
| `recommend_assignment` | Score incident signals → recommended group |
| `get_assignment_rules` | Show the routing matrix |
| `save_assignment_report` | **MANDATORY** — save completed recommendation to disk |
| `send_assignment_email` | **MANDATORY** — notify reviewer when session done |

## Investigation Workflow

### Phase 1 — INGEST
1. Call `analyze_incident` for each incident under investigation.
   - Do NOT call `get_incident_summary` + `download_attachments` separately.
2. Extract from the result: system names, vendor references, geography codes, error types.
3. Note the current assignment group.

### Phase 2 — ANALYSE
1. Call `get_assignment_rules` to load the routing matrix (shows all 10 groups and their keywords).
2. Call `recommend_assignment` with the extracted incident fields:
   - `short_description`, `description` — required
   - `category`, `subcategory` — if available
   - `comments_text` — concatenate all comment bodies
   - `work_notes_text` — concatenate all work note bodies
   - `current_group` — include so `reassignment_needed` is populated
3. Inspect the returned `recommended_group`, `confidence`, `alternatives`, and `signals_found`.
4. Compare with the full incident context — the tool is a heuristic signal, not an oracle.
   Use your own reasoning to confirm or override the recommendation.

### Phase 3 — CONCLUDE
1. Write the assignment recommendation report using the template below.
2. Call `save_assignment_report` immediately after finishing each report.
3. Call `send_assignment_email` once, after ALL reports are saved.
   - `session_summary`: plain-text list of incidents analysed and recommended groups.
   - `subject`: e.g. "Assignment Analysis Complete — INC10403788".

> **Never ask the user for verification before calling `send_assignment_email`.**
> The email IS the notification. The user will respond when ready.

## Report Template

```markdown
# Assignment Recommendation: {incident_number}
**{incident_short_description}**
*Analysed: {date}*

---

## RECOMMENDED ASSIGNMENT GROUP
{group_name}

**Confidence:** {confidence_pct}%

## REASSIGNMENT NEEDED
{Yes — reason} / {No}

## SIGNALS THAT DROVE THIS RECOMMENDATION
→ {signal_1} — {explanation}
→ {signal_2} — {explanation}

## ALTERNATIVE GROUPS CONSIDERED
| Group | Score |
|-------|-------|
| {runner_up_1} | {score} |
| {runner_up_2} | {score} |
| {runner_up_3} | {score} |

## CURRENT ASSIGNMENT
{current_group}

## WHAT WE CHECKED
→ Checked incident text — {what found}
→ Checked routing matrix — {top keywords matched}

## RECOMMENDED NEXT ACTION
{Reassign to group X / Confirm current assignment is correct / Escalate for manual review}
```
```

(Note the code fence above closes the markdown block — the template is the content between the fences.)
  </action>
  <verify>
    <automated>grep -c "recommend_assignment\|save_assignment_report\|send_assignment_email" ticketasg_copilot_agent/AGENTS.md</automated>
  </verify>
  <done>
    File exists. `grep -c "recommend_assignment" ticketasg_copilot_agent/AGENTS.md` returns >= 3. All 10 group names appear in the file. `grep "save_assignment_report" ticketasg_copilot_agent/AGENTS.md` returns at least 2 lines (tool inventory + CLI example).
  </done>
</task>

<task type="auto">
  <name>Task 2: Create SKILL.md and ticketasg_copilot.agent.md</name>
  <files>
    .claude/skills/ticketasg-copilot/SKILL.md
    .github/agents/ticketasg_copilot.agent.md
  </files>
  <read_first>
    .claude/skills/rca-copilot/SKILL.md — structural template for SKILL.md
    .github/agents/rca_copilot.agent.md — structural template for agent.md
    .planning/phases/phase-kayinleong-01/01-PATTERNS.md lines 670-759 — exact frontmatter and section patterns
  </read_first>
  <action>
**Create `.claude/skills/ticketasg-copilot/SKILL.md`**

This is a Claude Code skill file. Use `.claude/skills/rca-copilot/SKILL.md` as the structural
template. Replace all RCA-specific content with assignment content.

Exact YAML frontmatter:
```yaml
---
name: ticketasg-copilot
description: >
  Ticket Assignment agent for L'Oréal SPACE CDS ServiceNow incidents.
  Uses Bash tool to call ticketasg_copilot_agent/run_tool.py — no MCP server required.
  Analyses incident text and recommends the correct L2 assignment group from 10 known groups.
invocation: /ticketasg-copilot
---
```

Body sections (follow exact structure of rca-copilot SKILL.md):

**## Ticket Assignment Copilot Skill — No-MCP Mode**

Brief description: use this skill to analyse ServiceNow incidents and recommend L2 assignment groups.

**## Prerequisites**
```
1. Python virtual environment activated: `source .venv/bin/activate`
2. `.env` file present with `COOKIE` and `X_USERTOKEN` set (see `.env.example`)
3. gcloud ADC configured: `gcloud auth application-default login` (only needed for BQ)
4. `schema.json` present in repo root
```

**## Tool Invocation Reference**

Exact table mapping (include all 11 tools):
```markdown
| Task | Bash command |
|------|-------------|
| List local incidents | `python ticketasg_copilot_agent/run_tool.py list_incidents --json '{}'` |
| Fetch from SNOW URL | `python ticketasg_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "..."}'` |
| Fetch single incident | `python ticketasg_copilot_agent/run_tool.py get_incident --json '{"incident_number": "INCx"}'` |
| Read local incident text | `python ticketasg_copilot_agent/run_tool.py get_incident_summary --json '{"incident_number": "INCx"}'` |
| **Full analysis (use this)** | `python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INCx"}'` |
| Search local incidents | `python ticketasg_copilot_agent/run_tool.py search_incidents --json '{"keyword": "...", "section": "all"}'` |
| Post work note to SNOW | `python ticketasg_copilot_agent/run_tool.py post_comment --json '{"incident_number": "INCx", "text": "...", "as_work_note": true}'` |
| Show routing matrix | `python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'` |
| **Recommend group (CORE)** | `python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{"incident_number": "INCx", "short_description": "...", "description": "...", "current_group": "..."}'` |
| **Save report (MANDATORY)** | `python ticketasg_copilot_agent/run_tool.py save_assignment_report --json '{"incident_number": "INCx", "report_text": "..."}'` |
| **Send email (MANDATORY)** | `python ticketasg_copilot_agent/run_tool.py send_assignment_email --json '{"session_summary": "...", "subject": "Assignment Complete — INCx"}'` |
```

**## Assignment Workflow (No-MCP)**

### Step 0 — Detect intent

| Signal | Intent |
|--------|--------|
| Contains a ServiceNow URL | FETCH then analyse |
| Contains a ticket number (`INC\d+`) | Analyse that specific ticket |
| "all", "all incidents", no ticket | Batch — analyse all local |
| "post comment", "post work note" | Analyse + post recommendation back |

### Step 1 — Ensure incident data is available

(Same structure as rca-copilot: fetch if URL given, list_incidents if not.)

### Step 2 — Analyse and recommend

Single-ticket mode:
```bash
# Step 2a: ONE-STOP analysis
python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "<INCx>"}'

# Step 2b: Load routing matrix
python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'

# Step 2c: Score incident signals
python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{
  "incident_number": "<INCx>",
  "short_description": "<from analyze_incident output>",
  "description": "<from analyze_incident output>",
  "category": "<from analyze_incident output>",
  "subcategory": "<from analyze_incident output>",
  "comments_text": "<all comments concatenated>",
  "work_notes_text": "<all work notes concatenated>",
  "current_group": "<current assignment_group from incident>"
}'
```

Write the assignment report. Then:
```bash
# MANDATORY — save before outputting
python ticketasg_copilot_agent/run_tool.py save_assignment_report \
    --json '{"incident_number": "<INCx>", "report_text": "<full report text>"}'

# MANDATORY — send once per session, after ALL reports saved
python ticketasg_copilot_agent/run_tool.py send_assignment_email \
    --json '{"session_summary": "<plain text: which incidents, recommended groups>", "subject": "Assignment Complete — <INCx>"}'
```

Do NOT ask the user for verification before calling `send_assignment_email`.

Batch mode: `list_incidents`, loop single-ticket steps, call `send_assignment_email` once at end.

### Step 3 — Post as work note (only on post-comment intent)

Show all recommendations first. Ask: "Ready to post the above recommendation(s) as work notes. Confirm?"

On confirmation:
```bash
python ticketasg_copilot_agent/run_tool.py post_comment --json '{"incident_number": "<INCx>", "text": "<recommendation text>", "as_work_note": true}'
```

Never post without confirmation. Always `as_work_note: true` — recommendations are internal.

## Assignment Report Format (MANDATORY)

```
# Assignment Recommendation: {incident_number}
**{short_description}**
*Analysed: {date}*

---

## RECOMMENDED ASSIGNMENT GROUP
{group_name}

**Confidence:** {confidence_pct}%

## REASSIGNMENT NEEDED
{Yes — reason} / {No — current group is correct}

## SIGNALS THAT DROVE THIS RECOMMENDATION
→ {signal_1} — {explanation}

## ALTERNATIVE GROUPS CONSIDERED
| Group | Score |
|-------|-------|
| {group} | {score} |

## CURRENT ASSIGNMENT
{current_group}
```

## Output Rules

- Output ONLY the assignment report block. Start with `# Assignment Recommendation:`.
- After the report, append: `Report saved: <path>` then `Email sent.` (or the error).
- In batch mode, separate blocks with `---`, each followed by `Report saved: <path>`.
- After posting a work note: `Posted work note to [INC number].` only.

## Analysis Rules

- Only use data from Bash tool outputs. Never invent facts, system names, or error messages.
- The `recommend_assignment` tool output is a heuristic signal — verify against full ticket context.
- If `confidence` < 0.3, explicitly note low confidence and show top 3 alternatives.
- Never post work notes without confirmation. The `post_comment` tool writes live to ServiceNow.

---

**Create `.github/agents/ticketasg_copilot.agent.md`**

This is a GitHub Copilot agent definition. Use `.github/agents/rca_copilot.agent.md` as the
structural template. Replace all RCA-specific content with assignment content.

Exact YAML frontmatter:
```yaml
---
name: Ticket Assignment Copilot Agent
description: >
  Ticket Assignment agent for L'Oréal SPACE CDS ServiceNow incidents.
  Analyses incident text (description, comments, work notes) to recommend
  the correct L2 assignment group from 10 known groups.
  Can post recommendations back as internal work notes.
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

Body sections (follow exact structure of rca_copilot.agent.md):

**## ABSOLUTE TOOL RESTRICTION (READ THIS FIRST)**

You MUST use `run_in_terminal` to call `ticketasg_copilot_agent/run_tool.py` for all data
operations. The command pattern is:
```
python ticketasg_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'
```

**Tool name → CLI mapping table** (11 rows, matching SKILL.md table above but in agent.md table format):

| Task | Command |
|------|---------|
| List local incidents | `run_tool.py list_incidents --json '{}'` |
| Fetch from SNOW URL | `run_tool.py fetch_incidents --json '{"list_url": "..."}'` |
| Fetch single incident | `run_tool.py get_incident --json '{"incident_number": "INCx"}'` |
| Full analysis (use this) | `run_tool.py analyze_incident --json '{"incident_number": "INCx"}'` |
| Search local incidents | `run_tool.py search_incidents --json '{"keyword": "..."}'` |
| Show routing matrix | `run_tool.py get_assignment_rules --json '{}'` |
| **Recommend group (CORE)** | `run_tool.py recommend_assignment --json '{"incident_number": "INCx", "short_description": "...", "description": "...", "current_group": "..."}'` |
| Post work note | `run_tool.py post_comment --json '{"incident_number": "INCx", "text": "...", "as_work_note": true}'` |
| **Save report** | `run_tool.py save_assignment_report --json '{"incident_number": "INCx", "report_text": "..."}'` |
| **Send email** | `run_tool.py send_assignment_email --json '{"session_summary": "...", "subject": "Assignment Complete — INCx"}'` |

**MANDATORY SEQUENCE — no exceptions:**

1. Call `analyze_incident` to gather all incident data.
2. Call `get_assignment_rules` to load the routing matrix.
3. Call `recommend_assignment` with the incident fields extracted from step 1.
4. Write the assignment recommendation report.
5. Call `save_assignment_report` BEFORE outputting the report. If you skip this, you have failed.
6. After ALL `save_assignment_report` calls, call `send_assignment_email` ONCE.
   Do NOT ask the human for verification before sending — the email IS the notification.

**## Core Workflow section** — replicate the Step 0–3 structure from rca_copilot.agent.md,
adapted for assignment (same intent-detection table, same FETCH/LIST/ANALYSE pattern, but
Step 2 uses analyze → get_assignment_rules → recommend_assignment instead of analyze → BQ).

**## Report Format section** — use the Assignment Report Format from SKILL.md above.

**## Tool Use Rules, Output Rules, Analysis Rules** — replicate from rca_copilot.agent.md with
assignment-specific content. Key differences:
- "post_comment" always uses `as_work_note: true` for assignment recommendations
- Low confidence (< 0.3) requires showing alternatives before recommending
  </action>
  <verify>
    <automated>python -c "
import re, pathlib

# Validate SKILL.md frontmatter
skill = pathlib.Path('.claude/skills/ticketasg-copilot/SKILL.md').read_text()
assert 'name: ticketasg-copilot' in skill, 'SKILL.md missing name'
assert 'invocation: /ticketasg-copilot' in skill, 'SKILL.md missing invocation'
assert 'recommend_assignment' in skill, 'SKILL.md missing recommend_assignment'
assert 'save_assignment_report' in skill, 'SKILL.md missing save_assignment_report'
print('SKILL.md: OK')

# Validate agent.md frontmatter
agent = pathlib.Path('.github/agents/ticketasg_copilot.agent.md').read_text()
assert 'name: Ticket Assignment Copilot Agent' in agent, 'agent.md missing name'
assert 'execute/runInTerminal' in agent, 'agent.md missing runInTerminal tool'
assert 'MANDATORY SEQUENCE' in agent, 'agent.md missing MANDATORY SEQUENCE'
assert 'recommend_assignment' in agent, 'agent.md missing recommend_assignment'
print('ticketasg_copilot.agent.md: OK')
print('ALL checks PASS')
"</automated>
  </verify>
  <done>
    Both files exist. SKILL.md has valid YAML with `invocation: /ticketasg-copilot`. Agent.md has `name: Ticket Assignment Copilot Agent` and `execute/runInTerminal` in the tools list. Both files contain "MANDATORY SEQUENCE" and all 3 core tool names: `analyze_incident`, `recommend_assignment`, `save_assignment_report`.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| agent instruction → LLM | These files instruct the LLM; no code execution risk |
| SKILL.md Bash calls → run_tool.py | CLI invocations; arguments passed as JSON strings |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-wave4-01 | Elevation of Privilege | post_comment (agent instruction) | mitigate | Both agent files enforce confirmation before posting; `as_work_note: true` used for assignment recommendations |
| T-wave4-02 | Information Disclosure | AGENTS.md group names | accept | Group names are internal labels, not secrets; already in phase planning documentation |
</threat_model>

<verification>
1. `cat .claude/skills/ticketasg-copilot/SKILL.md | grep "invocation"` — returns `invocation: /ticketasg-copilot`
2. `cat .github/agents/ticketasg_copilot.agent.md | grep "name:"` — returns `name: Ticket Assignment Copilot Agent`
3. `grep -c "recommend_assignment" ticketasg_copilot_agent/AGENTS.md` — returns >= 3
4. `grep "MANDATORY SEQUENCE" .github/agents/ticketasg_copilot.agent.md` — returns one line
</verification>

<success_criteria>
- SKILL.md is discoverable by Claude Code at `/ticketasg-copilot`
- Both agent files reference `ticketasg_copilot_agent/run_tool.py` (not `rca_copilot_agent`)
- AGENTS.md documents all 11 tool names
- MANDATORY SEQUENCE is present in both the GitHub agent and the Claude skill
- All 10 assignment group names appear in AGENTS.md
</success_criteria>

<output>
After completion, create `.planning/phases/phase-kayinleong-01/phase-kayinleong-01-wave4-SUMMARY.md`
</output>
