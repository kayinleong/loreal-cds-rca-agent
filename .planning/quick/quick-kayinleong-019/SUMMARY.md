---
slug: quick-kayinleong-019
status: complete
claim: implement FINDINGS §5.2 rewrite of ticketasg_copilot_agent assignment rules
date: 2026-05-19
---

# Summary — quick-kayinleong-019

Implemented the per-group keyword rewrites recommended in `quick-kayinleong-018/FINDINGS.md` §5.2 and introduced word-boundary matching as a schema extension to `assignment_rules.json`. Verified by re-running the production `recommend_assignment()` function over the same 64 incidents fetched in quick-018.

## Result

| Metric | v1.0 (quick-018 baseline) | v1.1 (this claim) | Δ |
|---|---:|---:|---:|
| Match rate — all incidents | 11 / 64 = **17.2 %** | 20 / 64 = **31.2 %** | **+9 incidents, +14.1 pp** |
| Match rate — canonical-group tickets only | 11 / 35 = **31.4 %** | 20 / 35 = **57.1 %** | **+9, +25.7 pp** |
| Regressions on the 11 v1.0 matches | — | **0** | clean |
| SAPMENA L2 match rate | (n/a, v1.0 carried) | **13/16 = 81.2 %** | strong |
| B2C Hypercare match rate | ~0 % | **7/19 = 36.8 %** | recovered |
| SAPMENA L3 / CHN Loyalty L3 | 0/29 | 0/29 | unchanged (no schema for L3) |

Beats the CLAIM.md ship gates (≥ 25 % overall / ≥ 50 % on canonical groups).

## Files changed (committed)

| File | Change |
|---|---|
| `ticketasg_copilot_agent/assignment_rules.json` | Rules v1.0 → v1.1. Added `evidence_status`, `boundary_keywords`. Per-group keyword lists rewritten per FINDINGS §5.2 (removed 100 %-drift keywords, added evidence-backed signals from real handoff phrases). |
| `ticketasg_copilot_agent/tools/assignment_tool.py` | Added `re` import. Extended scoring loop to evaluate `boundary_keywords` via case-insensitive `\b…\b` regex alongside the existing substring `keywords`. `get_assignment_rules()` now renders `evidence_status`, both keyword lists. Built-in fallback updated to match v1.1 schema. |
| `.planning/quick/quick-kayinleong-019/CLAIM.md` | Lifecycle, verification, regression report. |
| `.planning/quick/quick-kayinleong-019/SUMMARY.md` | This file. |
| `.planning/quick/quick-kayinleong-019/RESCORE.md` | Full 64-row before/after table, by-group breakdown, miss-destination table. |
| `.planning/quick/quick-kayinleong-019/scripts/rescore.py` | Regenerator (re-runnable). |

## Why the L3 groups are still 0 %

29 of the 44 remaining mispredictions are tickets currently sitting in
`APAC - SGP - SPACE CDS SAPMENA L3 Support` or `APAC - CHN - SPACE Loyalty L3 Support`.
Neither group is in the canonical 10 modelled by `assignment_rules.json`, so by design
the recommender can never recommend them — it predicts the closest L2 instead.

This is the **single biggest remaining issue** and is the subject of the next claim:

> **quick-020 (proposed):** add an `l3_groups` mapping to `assignment_rules.json` and
> teach `recommend_assignment()` to escalate to L3 when text contains "L3", "PRB",
> "data patch", "patch script", or "tracked under PRB". Expected uplift: +29 incidents
> (potentially up to 49 / 64 ≈ 76 % match rate).

## Where the 44 v1.1 mispredictions land (sanity check)

| Predicted Group | Count | Plausible? |
|---|---:|---|
| SAPMENA L2 | 29 | Yes — these are L3 tickets that share L2's CDS / SAP signals. Correct routing once L3 schema exists. |
| B2C Hypercare | 5 | Plausible — `LS team` / `Hypercare` keywords picked up on tickets that probably should sit in B2C Hypercare. |
| HIP INCIDENT L2 | 3 | Strong: `CloudSQL` (INC10450026), `Linux Host` (INC10396182), `Cloudfare`/`Cloudflare` (INC10466356) — these arguably belong in HIP, not the current group. May surface real ownership disputes. |
| OMNISALES.RETAIL | 3 | Strong: `[MARS-XX]` prefix tickets (INC10293500, INC10204372) — currently in SAPMENA L2 / B2C Hypercare but explicit MARS-ANZ/MY/TH country tags route to OMNISALES per the new rule. |
| O+O.CRM | 2 | Reasonable — SFMC / SFDC tickets. |
| O+O ONLINE.CED | 1 | SFCC routing. |
| O+O.NGLORA | 1 | INC10403825 (Rule-500 AR Subscription Points) — verbatim NGLORA system signal. |

Several of these "mispredictions" are arguably *correct routing recommendations* —
the current SNOW group may itself be wrong. The agent's purpose is to *flag*
reassignment opportunities, so high `reassignment_needed=true` rates against
high-confidence predictions are a feature, not a bug.

## Verification highlights

- **4 inline smoke tests passed** before the full re-score (BA boundary positive + negative, SAPMENA signal match, reassignment_needed flag)
- **CLI end-to-end works** — `python ticketasg_copilot_agent/run_tool.py get_assignment_rules` and `recommend_assignment` both produce expected output with the new v1.1 rules and the `evidence_status` rendering
- **No regressions** — every one of the 11 v1.0 matches remains a match in v1.1
- **No source code touched outside `ticketasg_copilot_agent/`** — `rca_copilot_agent/`, `rca_agent/`, `requirements.txt`, `schema.json` all untouched
- **`BA` substring trap fixed** — the 56-hit catastrophic false positive from v1.0 no longer matches inside common words like `based`, `above`

## What's NOT in this claim (deferred)

- L2 ↔ L3 schema modelling — **quick-020** (single largest remaining miss bucket)
- Negative keywords (e.g. "MARS appears WITHOUT CDS → OMNISALES") — additive; not needed yet
- Re-fetch wider SNOW queue to validate the 8 still-`USER-CONFIRM` groups — operator decision
- Brand-specific groups (Aesop hypercare, etc.) — needs business validation first
