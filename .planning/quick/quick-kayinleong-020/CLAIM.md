# Claim: quick-kayinleong-020
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-19
- status: in-progress
- summary: Implement hybrid ticket-assignment routing for ticketasg_copilot_agent — hard rules + retrieval (sentence-transformers kNN) + LLM-as-judge layer. Adds `l3_escalation` schema so L3 groups become recommendable. Verify by re-scoring the 64 quick-018 incidents against the v1.1 keyword-only baseline (current 31.2 %).

## What Will Change

### Source code (under `ticketasg_copilot_agent/` + repo root)

1. **`requirements.txt`** — add `sentence-transformers>=2.5.0`. First-run downloads `all-MiniLM-L6-v2` (~80 MB) into the HuggingFace cache.
2. **`ticketasg_copilot_agent/assignment_rules.json`** — schema v1.1 → v2.0:
   - Add top-level `l3_escalation` map: `{ L2_group_name → L3_group_name }` for the canonical L2s that have a real L3 counterpart in our 64-ticket sample (SAPMENA L2 → SAPMENA L3; NGLORA L2 → CHN Loyalty L3; B2C Hypercare retains current routing)
   - Add top-level `escalation_signals` list: regex patterns that trigger L2 → L3 escalation (`PRB\d+`, `data patch`, `patch script`, `tracked under PRB`, `CDS L3`, `LOY L3`, `Assign to .* L3`, `Reassigning .* L3`)
   - Add top-level `hard_rules` array: high-confidence regex shortcuts (`MARS-{country}` → OMNISALES, `Linux Host|CAPLINERR|FS /mnt|usage above 90` → HIP, `Aesop hypercare` → B2C Hypercare, `SFCC -> CDS` → SAPMENA L2)
3. **`ticketasg_copilot_agent/tools/retrieval_tool.py`** — NEW module
   - `build_index(incidents_json_path, cache_path)` — loads `_all_incidents.json`, builds per-ticket embeddings via sentence-transformers, persists `(numbers[], group[], embeddings.npy)` as a `.npz` file
   - `find_similar(query_text, top_k=5)` — embeds query, computes cosine similarity to cached index, returns top-k `(number, group, score)`
   - Lazy-loads model + index; caches both in module state
4. **`ticketasg_copilot_agent/tools/assignment_tool.py`** — extend
   - Add `recommend_assignment_v2(...)` — new function that:
     1. Runs hard-rules layer first (short-circuit on regex match → confidence 0.95)
     2. Runs keyword scorer (existing v1 logic)
     3. Calls retrieval to find top-5 similar tickets, votes by group
     4. Checks for L3 escalation signals — if present, lookup L3 counterpart of the L2 winner
     5. Returns ALL signals separately + a deterministic combined `recommended_group` (used by re-scoring; LLM can override)
   - Keep `recommend_assignment` (v1) unchanged for backward-compat
   - Add `_load_hard_rules()` and `_load_l3_escalation()` helpers parallel to `_load_rules`
5. **`ticketasg_copilot_agent/mcp_server.py`** — register two new tools
   - `find_similar_incidents` — surfaces retrieval directly
   - `recommend_assignment_v2` — full hybrid routing (existing `recommend_assignment` kept too)
   - Both routed via `_dispatch` so `run_tool.py` picks them up automatically
6. **`ticketasg_copilot_agent/AGENTS.md`** — rewrite the mandatory sequence
   - New step ordering: `analyze_incident → get_assignment_rules → find_similar_incidents → recommend_assignment_v2 → reason about the three signals → save_assignment_report`
   - Add explicit guidance: "If retrieval and keyword scoring disagree, prefer retrieval. If L3 escalation signals are present, recommend the L3 counterpart even if keywords point to L2."
7. **`.claude/skills/ticketasg-copilot/SKILL.md`** — same updates as AGENTS.md

### Planning artifacts

8. `CLAIM.md` (this file), `SUMMARY.md` (on completion), `RESCORE.md` (full 64-row before/after), `scripts/rescore_v2.py` (regenerator)

## What Has Changed

(To be filled when complete.)

## Verification

(To be filled when complete.)

## Success criteria

| Gate | v1.1 baseline | v2.0 target |
|---|---:|---:|
| Overall match rate (all 64 incidents) | 31.2 % | **≥ 50 %** |
| Canonical-group + L3 match rate | 31.4 % (canonical only; L3 was 0/29) | **≥ 60 %** |
| Zero regressions on the 20 v1.1 matches | 20 / 20 | 20 / 20 |
| Hard-rules fire correctly when applicable | n/a | All hard-rule incidents in sample match expected target |
| L3 escalation routes SAPMENA L3 tickets to L3 not L2 | 0/22 | **≥ 15/22** |

If overall match rate < 45 % after v2.0, this claim becomes `abandoned` — no
rollout. The v1.1 commit stays as the active production rules.

## Scope discipline (NOT in this claim)

- **No edits to `rca_copilot_agent/`** — stays untouched.
- **No retrain or hyperparameter tuning of the embedding model** — use `all-MiniLM-L6-v2` defaults.
- **No fetch of resolved tickets** — corpus is the 64 active tickets from quick-018. Wider/historical corpus is a future enhancement.
- **No negative keywords** — additive feature; defer to a future claim.
- **No automatic posting back to SNOW** — `recommend_assignment_v2` is read-only; existing `post_comment` semantics unchanged.

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| `sentence-transformers` install pulls ~250 MB of torch deps into `.venv` | Documented in requirements.txt with a comment. Existing `.venv` already has torch via `mcp`/related deps — incremental footprint smaller than fresh install. |
| First-run model download (~80 MB) requires network access | Run once at index-build time. Subsequent runs use HuggingFace cache (`~/.cache/huggingface/`). |
| Retrieval over only 64 tickets is small; neighbours may be noisy for under-represented groups | Acknowledged in success criteria — the 4 groups in the sample have at least 7 tickets each so kNN is meaningful for those. For the other 6 groups, retrieval will rarely fire and the hard rules / keywords carry the load. |
| Adding `l3_escalation` could route ALL tickets to L3 by mistake | Only escalate when an `escalation_signals` regex matches in the text. Default behaviour stays L2. |
| LLM-as-judge instruction in AGENTS.md may be ignored by the LLM | The tool output already returns a deterministic `recommended_group`. AGENTS.md update just adds *better* reasoning when the LLM is asked to explain — it doesn't force the LLM to override the deterministic answer. |
