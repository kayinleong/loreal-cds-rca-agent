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
| `get_assignment_rules` | **READ BEFORE RECOMMENDING** — show routing matrix (10 groups + keywords + hard rules + L3 escalation) |
| `recommend_assignment_v2` | **USE THIS** — hybrid recommender: hard rules + keyword + retrieval + L3 escalation. Returns all three signals separately. |
| `find_similar_incidents` | kNN retrieval — fetch the top-5 semantically-similar tickets in the local corpus. Use it as a second-opinion signal, especially when `recommend_assignment_v2`'s `source` is `keyword` (i.e. retrieval did not strongly agree). |
| `build_retrieval_index` | Run once after `fetch_incidents` to refresh the kNN corpus that `recommend_assignment_v2` and `find_similar_incidents` use. |
| `recommend_assignment` | Legacy v1 keyword-only path. Prefer `recommend_assignment_v2`. Kept for backward-compat. |
| `save_assignment_report` | **MANDATORY** — save every completed analysis to disk |
| `send_assignment_email` | **MANDATORY** — notify the human when the session is done |

## Mandatory Sequence (no exceptions)

1. `analyze_incident` — gather incident data (description, comments, work notes, identifiers)
2. `get_assignment_rules` — read the routing matrix, hard rules, and L3 escalation map so you understand the groups
3. If the local retrieval index does not exist yet (first analysis after `fetch_incidents`), call `build_retrieval_index` — one-time per fetch
4. `recommend_assignment_v2` — get the combined recommendation **plus** the three individual signals
5. **REASON about the three signals** (see "LLM-as-judge" below) — your job is not to blindly accept the combined `recommended_group`; you are expected to weigh keyword vs retrieval vs hard rule and explain your final choice
6. Write the assignment analysis report (see Report Format below)
7. `save_assignment_report` — **MANDATORY**: save before outputting the report
8. After ALL incidents in the session: `send_assignment_email` — **MANDATORY** notification

**Never skip steps 5, 7 or 8.**

## LLM-as-judge — how to read the three signals from `recommend_assignment_v2`

`recommend_assignment_v2` returns a JSON object whose top-level fields are the **deterministic combined answer** (`recommended_group`, `confidence`, `reason`, `source`). The `signals` sub-object gives you the raw inputs.

| Signal | Strong evidence | Weak evidence |
|---|---|---|
| `signals.hard_rule` | Non-null (a regex matched) → **trust it** — these are tested high-precision shortcuts (MARS-{country}, Linux Host, etc). | `null` — no shortcut fired; nothing learned. |
| `signals.keyword.confidence` | ≥ 0.5 with 3+ matched keywords → keyword scorer is confident | ≤ 0.2 with 1 keyword → likely a single substring coincidence |
| `signals.retrieval.top1.score` | ≥ 0.7 → semantically very similar ticket exists in corpus → very strong | < 0.5 → corpus has no close match → ignore retrieval |
| `signals.retrieval.weighted_vote.tally` | One group has > 1.5 summed score AND ≥ 2 neighbours → consensus | scores split roughly equally → no consensus |
| `signals.l3_escalation.signals_matched` | Non-empty AND keyword winner has an `escalated_from_to` → recommend the **L3** group | Empty → stay at L2 |

### Conflict-resolution rules (write your reasoning in the report)

1. **Hard rule** wins everything else. If `signals.hard_rule` is non-null, recommend its target.
2. If **escalation signals fired** and a `escalated_from_to.to` is given, recommend the L3 target unless the hard rule disagrees.
3. If **keyword and retrieval top-1 agree** AND retrieval top-1 score ≥ 0.6, recommend that group with high confidence.
4. If **keyword and retrieval top-1 disagree** — explain both in the report and prefer:
   - Retrieval when retrieval top-1 score ≥ 0.7 and ≥ 2 of top-5 are the same group
   - Keyword otherwise (the rules are validated; retrieval may be noisy on under-represented groups)
5. If **all signals are weak** (no hard rule, keyword conf < 0.2, retrieval top-1 < 0.5) — explicitly flag the recommendation as low-confidence and recommend human review.

### When to consult `find_similar_incidents` separately

Call it when:
- `recommend_assignment_v2.source` was `keyword` AND the recommendation goes to `OPERATIONS - L2` (the fallback) — retrieval may surface a better neighbour
- You want to cite specific historical tickets in your reasoning ("similar to INC10293500 which resolved in OMNISALES")
- The user asks "what other tickets look like this one"

## Report Format — L'Oréal RCA Template (MANDATORY)

Mirror the canonical RCA template used by `rca_copilot_agent`. The reassignment recommendation lands in `### WHAT WE NEED / DID`.

```markdown
## Assignment Analysis — {INCIDENT_NUMBER}

### WHAT HAPPENED
{One sentence stating what was reported and where the ticket currently sits — symptom, not cause.}
Example: "Ticket reports SAP order failure for MY/KIE customer; currently assigned to APAC - ZN - O+O.OPERATIONS - L2."

### WHAT WE CHECKED
→ Hard rules — {matched: rule name + target group / no match}
→ Keyword scorer — {group} (confidence {0.0-1.0}, matched: {kw1, kw2, ...} / no match)
→ kNN retrieval (top-1) — INC{nnnnnn} → {group} (similarity {0.00-1.00})
→ kNN retrieval (weighted vote) — {group: sum, group: sum, ...}
→ L3 escalation signals — {triggered: signal1, signal2, ... / not triggered}

### WHAT WE FOUND
{One or two sentences. Which signals agreed? Which disagreed? What does the evidence point to overall?}
Example: "Hard rule `[MARS-ANZ]` matched explicitly and three of the top-5 nearest neighbours also sit in OMNISALES.RETAIL — both signals point to that L2 group as the correct owner."

### WHAT WE NEED / DID
{If the final choice ≠ current_group:}
**REASSIGN to:** `{your final group choice}`
**Confidence:** {0-100 %}
**Justification:** {Why this group is correct — name the signals that led here, cite specific keywords / similar tickets / hard rules. If you overrode the tool's combined recommendation, explain why.}
**Action:** Please reassign this ticket to `{group}` and add the justification above as a public comment.

{Else:}
**NO REASSIGNMENT NEEDED.** The current assignment group `{current_group}` matches what the routing signals indicate. {One-sentence supporting evidence.}

{Optional: cite up to 3 most-similar past tickets that informed the recommendation.}
**Similar past tickets:**
- INC10293500 (similarity 0.72) — currently in OMNISALES.RETAIL
- INC10204372 (similarity 0.65) — currently in B2C Hypercare
- INC10324255 (similarity 0.58) — currently in SAPMENA L3
```

### Why this format

- Matches the wording L'Oréal L2/L3 operators already use in SNOW work-notes, so the agent's output reads natively
- Placing the recommendation in `### WHAT WE NEED / DID` reflects the canonical "action items" semantics — reassignment is an action item, not a header field
- The four `→ Checked` lines explicitly enumerate the four signals from `recommend_assignment_v2`, making the reasoning auditable

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

# Show routing rules (now includes hard_rules + l3_escalation)
python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'

# Build the kNN retrieval index — run ONCE after each fetch_incidents
python ticketasg_copilot_agent/run_tool.py build_retrieval_index --json '{}'

# v2 recommender — hard rule + keyword + retrieval + L3 escalation
python ticketasg_copilot_agent/run_tool.py recommend_assignment_v2 \
    --json '{"incident_number": "INC123", "short_description": "SFCC -> CDS Missing Order PRB0083209", "description": "Reassigning to CDS L3 — data patch required", "current_group": "APAC - SGP - SPACE CDS SAPMENA L2 Support"}'

# kNN similarity search — second-opinion signal
python ticketasg_copilot_agent/run_tool.py find_similar_incidents \
    --json '{"query_text": "SAPMENA FindConsumerProfile failure", "top_k": 5}'

# Legacy v1 (kept for back-compat — prefer v2)
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
