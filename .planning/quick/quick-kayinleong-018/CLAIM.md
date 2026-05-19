# Claim: quick-kayinleong-018
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: in-progress
- summary: Research improvement of ticketasg_copilot_agent assignment logic — fetch real SNOW incidents (current open queue), study comments/work-notes/descriptions to discover real routing signals, table findings (this is a research-only claim; no code changes yet)

## What Will Change

This is a **research-only** quick. Output is a findings report; no code or rules changes
are made in this claim. Follow-up claims will implement any keyword/routing changes.

Deliverables in this directory:
1. `FINDINGS.md` — tabled report:
   - Per-incident summary (number, current group, description signals, recommended group from current rules, confidence)
   - Per-group keyword evidence (which keywords actually appear in real tickets)
   - Gaps: groups with no real ticket coverage; keywords in `assignment_rules.json` that never matched; signals in real tickets that aren't in `assignment_rules.json`
   - Recommended changes to `assignment_rules.json` (no code change made — just proposals)
2. Optionally `data/` (gitignored) — local cache of fetched incidents (if not already under `rca_copilot_agent/my_reports/` or `my_reports/`)

## Source URL

```
https://loreal.service-now.com/now/nav/ui/classic/params/target/incident_list.do?sysparm_userpref_module=b55fbec4c0a800090088e83d7ff500de&sysparm_query=active=true^assignment_groupDYNAMICd6435e965f510100a9ad2572f2b47744^state!=6^EQ&active=true&sysparm_clear_stack=true
```

Filter: `active=true ^ assignment_group DYNAMIC d6435e965f510100a9ad2572f2b47744 ^ state!=6`
(active incidents in "my groups" dynamic filter, excluding resolved).

## Method

1. Refresh SNOW credentials via `auth_tool` (browser SSO) — the local `.env` cookie is stale.
2. `python rca_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "<url>", "limit": 500}'`
3. Read incidents from cache, run them through the current `recommend_assignment` rules to
   spot mismatches between current group and predicted group.
4. Manually study comments / work-notes / short descriptions to discover real routing signals
   per group (i.e. which words and phrases predict each L2 group in practice).
5. Write `FINDINGS.md` with tables.

## Constraints

- No code changes in this claim. Rule changes (if needed) become a separate quick claim.
- No data files committed: SNOW incidents may contain consumer PII — `my_reports/` is gitignored.
- Never log COOKIE or X_USERTOKEN values.

## What Has Changed

(To be filled when complete.)

## Verification

(To be filled when complete.)
