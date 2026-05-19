# Claim: quick-kayinleong-018
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: done
- summary: Research improvement of ticketasg_copilot_agent assignment logic — fetched 64 real SNOW incidents (current open queue), studied comments/work-notes/descriptions to discover real routing signals, tabled findings (research-only claim; no code changes)

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

Research-only claim — no source code or rules modified. New files added under
`.planning/quick/quick-kayinleong-018/`:

1. `FINDINGS.md` — tabled report with 6 sections (TL;DR, sample caveats, per-incident
   trace, per-keyword drift, real-text signals, recommendations).
2. `ANALYSIS-RAW.md` — full 64-row per-incident trace + per-group token counts + per-keyword
   diagnostic (drift = fraction of matches that landed in the wrong group).
3. `HANDOFFS-RAW.md` — 215 explicit reassignment / handoff phrases extracted from work-notes
   and comments via regex sentence patterns.
4. `scripts/analyze.py` — regenerator for ANALYSIS-RAW.md.
5. `scripts/handoffs.py` — regenerator for HANDOFFS-RAW.md.

Side-effects on disk (gitignored, NOT committed):
- `./my_reports/INC*.json` — 64 individual incident JSON files (~3-30 MB each with
  embedded text + attachment metadata)
- `./my_reports/_all_incidents.json` — combined fetch output (~295 MB total dir)
- `./my_reports/attachments/INC*/` — downloaded screenshots/files (may contain PII)
- `.env` — fresh `COOKIE` and `X_USERTOKEN` written by `auth_tool.capture_credentials_via_browser`

Source code remained untouched:
- `git diff` shows ZERO changes to `rca_copilot_agent/`, `ticketasg_copilot_agent/`,
  `rca_agent/`, `requirements.txt`, `schema.json`, `CLAUDE.md`, or any other tracked source

## Verification

### What was tested

1. **Auth flow** — `ensure_credentials` correctly detected the stale 22-byte cookie, opened
   Edge for SSO, captured a 495-byte cookie + 72-byte token, and wrote them back to `.env`.
2. **SNOW URL parser** — the navigation-wrapped URL with `assignment_group DYNAMIC` filter
   was parsed by `parse_list_url` to `incident` table + correct sysparm_query.
3. **Fetch** — 64 incidents successfully downloaded with attachments. `_all_incidents.json`
   matches sum of individual files (64 records, every record has `incident.assignment_group`,
   `comments`, `work_notes`, `attachments`, `downloaded_files`).
4. **`analyze.py`** — produced 283-line ANALYSIS-RAW.md with no Python errors. Verified by
   spot-checking 3 incidents:
   - INC10293500 ([MARS-ANZ] Sales rep) → predicted OMNISALES, actually in SAPMENA L2 — confirms
     `MARS` keyword false positive
   - INC10387135 (FindConsumerProfile 504) → predicted + actual SAPMENA L2 — confirms
     `SAPMENA` + `CDS` discriminate correctly
   - INC10142664 (Unable to merge duplicate account, B2C Hypercare) → predicted CRM via
     `lucid`+`account` — confirms `lucid`/`account` false positives in CRM rule
5. **`handoffs.py`** — extracted 215 phrases. Manual sample on INC10312845:
   - "Reassigning the ticket to CDS L3, any update on the fix will be tracked under PRB0082698" ✓
   - "this is related to MARS, you can directly discuss with user" ✓
   These match what I read directly from the work_notes — extraction is faithful.

### What passed

- All 64 fetches: 0 errors reported by `fetch_incidents_from_list`
- All scripts: exit 0, valid Markdown output
- All 11 ✓ rows in the match-rate table validated by manually checking the matched keywords
  against the raw incident JSON

### Regression Report

- **No source code touched** — `git diff -- rca_copilot_agent/ ticketasg_copilot_agent/ rca_agent/ requirements.txt schema.json` is empty.
- **No tracked configuration changed** — the only file `auth_tool` modified is `.env`,
  which is gitignored.
- **Secrets hygiene** — `.env` was NOT staged; `git status` shows it remains untracked.
  COOKIE / X_USERTOKEN values are never logged or echoed in any of the artifact files
  (verified with `grep -E "Cookie:|COOKIE=" .planning/quick/quick-kayinleong-018/*.md`).
- **No PII leaked into committed artifacts** — `FINDINGS.md`, `ANALYSIS-RAW.md`, and
  `HANDOFFS-RAW.md` contain only incident *numbers* (INCnnnnnn) and short descriptions /
  work-note snippets. Per-customer LUCID and MARSID values, phone numbers, and emails
  surface in `my_reports/INC*.json` which is gitignored.
- **`my_reports/` and `attachments/` confirmed gitignored** via `grep -E '^(my_reports|attachments)/' .gitignore`.
- **No changes to the recommender code** — the 17.2 % match rate is a *measurement* of the
  current rules' behaviour, not a degradation caused by this work. Follow-up claim will
  implement the recommended changes.

### What was ruled out and why

- **Did not modify `assignment_rules.json`** — by claim definition this is research-only.
  Implementation belongs in a follow-up quick claim once the recommendations are reviewed.
- **Did not validate the 8 canonical groups with 0 tickets in the sample** — the "my groups"
  dynamic filter restricted the sample. The FINDINGS.md §5.4 explicitly flags this and
  recommends a wider fetch (`active=true^state!=6`) as the next step.
- **Did not attempt the structural schema change** (L2 ↔ L3 modelling, word-boundary
  regex, negative keywords) — proposed in §5.1 of FINDINGS.md but deferred to follow-up
  implementation claim where it can be planned and tested properly.
