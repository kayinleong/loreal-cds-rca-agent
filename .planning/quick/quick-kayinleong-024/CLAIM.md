# Claim: quick-kayinleong-024
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-21
- status: claimed
- summary: Bring ticketasg_copilot_agent to RCA-parity with rca_copilot_agent (same RCA format, with a final "Reassignment Decision" section appended when applicable). Read CDS_Incident_Handling_Guidebook 2.docx and produce a research.md, then improve the ticketasg_copilot_agent based on guidebook findings.

## Trigger

User invoked `/gsd-quick --research` with the following request:

> I want you to research rca_copilot_agent and ticketasg_copilot_agent.
> Now the ticketasg_copilot_agent will generate rca but not the rca that is generated in rca_copilot_agent.
> I want the ticketasg_copilot_agent to generate a rca just like in rca_copilot_agent, then add in reassignment grouping (if needed) in rca last session.
> Also improve the ticketasg_copilot_agent by reading the CDS_Incident_Handling_Guidebook 2.docx:
> 1. generate a research md
> 2. improve the ticketasg_copilot_agent

## What Will Change

1. **research.md** — Synthesis document in `.planning/quick/quick-kayinleong-024/RESEARCH.md` covering:
   - rca_copilot_agent's RCA report shape (template, sections, MCP tool wiring)
   - ticketasg_copilot_agent's current report shape (recommend_assignment_v2 + RCA template variant)
   - Gap analysis — what's missing in ticketasg that rca has
   - Guidebook findings — process rules, escalation matrix, evidence requirements, KPIs
   - Recommended improvements to ticketasg_copilot_agent (tools, prompts, report sections)

2. **ticketasg_copilot_agent updates** — code/doc changes to make the agent:
   - Generate the same RCA report structure as rca_copilot_agent
   - Append a `### Reassignment Decision` section at the end (only when reassignment is recommended)
   - Apply additional improvements surfaced in the guidebook research

3. **AGENTS.md / SKILL.md / .github/agents/ticketasg_copilot.agent.md** — kept in sync with the new report contract

## Verification

_To be filled in after execution._
