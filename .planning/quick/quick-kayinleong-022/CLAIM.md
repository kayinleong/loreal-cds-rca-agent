# Claim: quick-kayinleong-022
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: in-progress
- summary: Enforce full canonical assignment-group names in agent-generated RCA / assignment reports. Forbid shortforms like `CDS L3 team` / `LOY` / `MARS team` — the agent must always write the verbatim ServiceNow group name (e.g. `APAC - SGP - SPACE CDS SAPMENA L3 Support`). Docs-only — no code, no rules, no behaviour change.

## Trigger

Example from `my_reports/rca_reports/INC10449165_rca_20260519_213556.md`:

> `### WHAT WE NEED / DID`
> - Assign to **CDS L3 team** as the issue is tracked in DFCT0268807.
> - **CDS** to extract the full outbound file and share it with **LOY**...
> - **LOY** to sync the lucid according to the shared outbound file.

The strings `CDS L3 team`, `CDS`, `LOY`, `MARS team` etc. are operator shorthand from work-notes. They're ambiguous to anyone outside the team and they don't match the SNOW Reassign-Group picker exactly. The agent should ALWAYS expand to the full canonical group name.

## What Will Change

1. **`rca_copilot_agent/AGENTS.md`** — add a "Group names: always canonical, never shortforms" rule + a shortform→canonical mapping table; apply to the RCA report-format block (especially `### WHAT WE NEED / DID`).
2. **`.claude/skills/rca-copilot/SKILL.md`** — same rule + table.
3. **`ticketasg_copilot_agent/AGENTS.md`** — same rule + table (the ticketasg report template already uses full names in examples, but no explicit "never shortform" guardrail).
4. **`.claude/skills/ticketasg-copilot/SKILL.md`** — same rule + table.

## What Will NOT Change

- No code changes in `tools/*` or `mcp_server.py`
- No `assignment_rules.json` change
- The 64-incident match rate (38/64 = 59.4 %) is unaffected — this only changes how the LLM writes its report
- `schema.json`, `requirements.txt`, `CLAUDE.md` — untouched

## Shortform → canonical mapping (to embed in both agents' docs)

| Operator shorthand | Canonical ServiceNow group |
|---|---|
| `CDS L2` / `CDS L2 team` / `SAPMENA CDS group` | `APAC - SGP - SPACE CDS SAPMENA L2 Support` |
| `CDS L3` / `CDS L3 team` | `APAC - SGP - SPACE CDS SAPMENA L3 Support` |
| `LOY` / `LOY team` / `Loyalty` / `Loyalty team` (Loyalty backend issue) | `APAC - ZN - O+O.NGLORA - L2` |
| `LOY L3` / `Loyalty L3` (Loyalty L3 issue, often China/loyalty rules) | `APAC - CHN - SPACE Loyalty L3 Support` |
| `MARS` / `MARS team` / `MARS Ops` / `MARS Operations` / `retail Ops team` | `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2` |
| `iBeauty` / `iBeauty team` / `IBeauty team` / `iBeauty L2` | `APAC - ZN - iBeauty 2.0 - Retail - L2` |
| `SFCC` / `SFCC L2` | `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2` |
| `CRM` / `SFMC team` / `SFDC team` / `CE team` / `CE Ops team` | `APAC - ZN - O+O.CRM - L2` |
| `NGL` / `NGL L2` / `NGLORA` | `APAC - ZN - O+O.NGLORA - L2` |
| `Operations` / `Ops` / `OPS team` (only when nothing more specific fits) | `APAC - ZN - O+O.OPERATIONS - L2` |
| `Hypercare` / `Hypercare team` / `Hypercare group` / `LS team` / `LS Hypercare` / `Aesop hypercare` | `APAC - ZN - SPACE B2C Hypercare` |
| `HIP` / `HIP team` / `Infrastructure team` / `Azure team` (HIP-adjacent) | `TECH FNDN - WW - HIP INCIDENT L2` |
| `THN Retail` / `Thailand Retail` | `APAC - THN - Retail IT` |

L3 groups outside the canonical 10 (also full names, never shortforms):
- `APAC - SGP - SPACE CDS SAPMENA L3 Support`
- `APAC - CHN - SPACE Loyalty L3 Support`
- `APAC - SGP - SPACE Loyalty L3 Support`
- `INFRA - WW - Linux Unix ACN - L3` (per real work-notes)

When uncertain, the agent should ALWAYS pick the closest canonical full name and add a `[USER-CONFIRM]` flag in the justification.

## What Has Changed

(To be filled when complete.)

## Verification

(To be filled when complete.)
