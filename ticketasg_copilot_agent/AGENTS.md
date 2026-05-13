# AGENTS.md — Ticket Assignment Copilot Agent

> Instruction schema for GitHub Copilot (or any MCP-aware LLM client).
> All LLM reasoning stays in the client. This server exposes only pure-function tools.

## Purpose

Analyse L'Oréal SPACE CDS ServiceNow incidents and recommend the correct L2 assignment group.
The agent reads ticket comments, work notes, and descriptions, then scores them against a
keyword routing matrix to recommend which of the 10 supported L2 groups should own the ticket.

**When reassignment is needed, always state the reason explicitly in the ticket analysis.**

## Tool Inventory

| Tool | When to use |
|------|-------------|
| `analyze_incident` | **START HERE** — ONE-STOP: fetch incident + identifiers |
| `fetch_incidents` | Bulk-download all incidents from a SNOW list URL |
| `get_incident` | Fetch a single live incident by number |
| `get_incident_summary` | Read full incident text from local cache |
| `list_incidents` | Discover what is locally available |
| `search_incidents` | Keyword-search across all local incidents |
| `post_comment` | Post comment / work note to SNOW (confirm with user first) |
| `get_assignment_rules` | **READ BEFORE RECOMMENDING** — show routing matrix (10 groups + keywords) |
| `recommend_assignment` | Score incident text and return recommended group + reason |
| `save_assignment_report` | **MANDATORY** — save every completed analysis to disk |
| `send_assignment_email` | **MANDATORY** — notify the human when the session is done |

## Mandatory Sequence (no exceptions)

1. `analyze_incident` — gather incident data (description, comments, work notes, identifiers)
2. `get_assignment_rules` — read the routing matrix so you understand the groups
3. `recommend_assignment` — score the incident and get the recommended group
4. Write the assignment analysis report (see Report Format below)
5. `save_assignment_report` — **MANDATORY**: save before outputting the report
6. After ALL incidents in the session: `send_assignment_email` — **MANDATORY** notification

**Never skip steps 5 or 6.**

## Report Format

```markdown
## Assignment Analysis — {INCIDENT_NUMBER}

**Incident:** {short_description}
**Current Group:** {assignment_group from incident}
**Recommended Group:** {recommended_group}
**Confidence:** {confidence as percentage}

### Routing Signals
{Explain which keywords or patterns triggered the recommendation}

### Reassignment Decision
{If reassignment_needed is True:}
**REASSIGNMENT NEEDED**
Reason: {reassignment_reason}
Action: Please reassign this ticket to "{recommended_group}".

{If reassignment_needed is False:}
**NO REASSIGNMENT NEEDED**
The current assignment group is correct.

### Alternative Groups
{List the top 3 alternatives with their scores}
```

## Assignment Groups Supported

[USER-CONFIRM] Routing keywords are inferred — verify against SharePoint matrix before production use.

| Group | Routing Signals |
|-------|----------------|
| APAC - SGP - SPACE CDS SAPMENA L2 Support | SAP, SAPMENA, ERP, Singapore, product sync |
| APAC - THN - Retail IT | Thailand, POS, retail store, printer, cashier |
| APAC - ZN - iBeauty 2.0 - Retail - L2 | iBeauty, beauty advisor, in-store app, clienteling |
| APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | OMNISALES, MARS, Capgemini, click and collect |
| APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2 | CED, e-commerce, online, web order, SPACE GDS |
| APAC - ZN - O+O.CRM - L2 | CRM, loyalty, consumer profile, lucid, consent |
| APAC - ZN - O+O.NGLORA - L2 | NGLORA, NGL, loyalty, ORA, rewards, redemption |
| APAC - ZN - O+O.OPERATIONS - L2 | operations, ETL, pipeline, data sync, API (default fallback) |
| APAC - ZN - SPACE B2C Hypercare | hypercare, go live, launch, cutover, P1 escalation |
| TECH FNDN - WW - HIP INCIDENT L2 | infrastructure, HIP, cloud, server, network, SSL, DNS |

## Running Without MCP (Skills / CLI Mode)

L'Oréal's environment does not allow MCP servers. Use `run_tool.py` instead:

```bash
# ONE-STOP analysis
python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'

# Show routing rules
python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'

# Recommend assignment
python ticketasg_copilot_agent/run_tool.py recommend_assignment \
    --json '{"incident_number": "INC123", "short_description": "SAP sync error", "description": "SAPMENA pipeline failure", "current_group": "APAC - ZN - O+O.OPERATIONS - L2"}'

# Save report (MANDATORY)
python ticketasg_copilot_agent/run_tool.py save_assignment_report \
    --json '{"incident_number": "INC123", "report_text": "## Assignment Analysis...\n..."}'

# Send email (MANDATORY, once per session)
python ticketasg_copilot_agent/run_tool.py send_assignment_email \
    --json '{"session_summary": "Analysed INC123 — reassignment needed to SGP group"}'
```

**For Claude Code users:** invoke the `/ticketasg-copilot` skill (`.claude/skills/ticketasg-copilot/SKILL.md`).

**For GitHub Copilot users:** the `.github/agents/ticketasg_copilot.agent.md` agent definition
uses `run_in_terminal` to call `run_tool.py` — no MCP server required.

## Environment Setup

### ServiceNow Credentials (auto-refreshed)

At startup the server checks `COOKIE` and `X_USERTOKEN` in `.env`.
If missing or expired, a browser window opens for SSO login.

### Required .env Keys

| Variable | Source |
|----------|--------|
| `COOKIE` | Chrome DevTools → Network → SNOW request → Cookie header |
| `X_USERTOKEN` | Same request → X-UserToken header |
| `SMTP_HOST` | Your SMTP server (for email notifications) |
| `SMTP_FROM` | From address |
| `SMTP_TO` | Recipient(s), comma-separated |
| `ASSIGNMENT_RULES_FILE` | Optional — path to assignment_rules.json override |
