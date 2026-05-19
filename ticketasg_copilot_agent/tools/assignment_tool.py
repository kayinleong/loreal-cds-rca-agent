"""
assignment_tool.py — Deterministic ticket assignment routing.
=============================================================
Pure functions — no LLM calls, no side effects beyond logging.
Loads routing rules from assignment_rules.json (path resolved via config.py).

Two public functions:
  get_assignment_rules()   — returns routing matrix as formatted text for LLM inspection
  recommend_assignment()   — scores incident signals and returns top group + alternatives

[USER-CONFIRM] The routing keywords in assignment_rules.json are inferred from group names.
Verify against the official SharePoint routing matrix before production use.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Canonical list of the 10 L2 assignment groups — order is significant (tie-break by index)
ASSIGNMENT_GROUPS = [
    "APAC - SGP - SPACE CDS SAPMENA L2 Support",
    "APAC - THN - Retail IT",
    "APAC - ZN - iBeauty 2.0 - Retail - L2",
    "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2",
    "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2",
    "APAC - ZN - O+O.CRM - L2",
    "APAC - ZN - O+O.NGLORA - L2",
    "APAC - ZN - O+O.OPERATIONS - L2",
    "APAC - ZN - SPACE B2C Hypercare",
    "TECH FNDN - WW - HIP INCIDENT L2",
]

# Fallback group when no keywords match
_FALLBACK_GROUP = "APAC - ZN - O+O.OPERATIONS - L2"

# Module-level rules cache — loaded once on first call (same singleton pattern as bigquery_tool.py)
_rules_cache: Optional[dict] = None


def _load_rules() -> dict:
    """Load assignment_rules.json. Caches result on first call."""
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    try:
        from config import load_config  # noqa: PLC0415
        cfg = load_config()
        path = Path(cfg.assignment_rules_file)
        if path.exists():
            _rules_cache = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"[ASSIGNMENT] Loaded rules v{_rules_cache.get('version', '?')} from {path}")
        else:
            logger.warning(f"[ASSIGNMENT] Rules file not found at {path} — using built-in defaults")
            _rules_cache = _builtin_defaults()
    except Exception as exc:
        logger.warning(f"[ASSIGNMENT] Could not load rules: {exc} — using built-in defaults")
        _rules_cache = _builtin_defaults()
    return _rules_cache


def _builtin_defaults() -> dict:
    """Minimal hardcoded rules used when assignment_rules.json is absent."""
    return {
        "version": "builtin-fallback",
        "groups": {
            "APAC - SGP - SPACE CDS SAPMENA L2 Support": {
                "keywords": ["SAP", "SAPMENA", "Singapore", "CDS", "ERP"],
                "boundary_keywords": ["CDS", "SGP"],
                "weight": 1.0,
            },
            "APAC - THN - Retail IT": {
                "keywords": ["Thailand retail"],
                "boundary_keywords": ["THN"],
                "weight": 1.0,
            },
            "APAC - ZN - iBeauty 2.0 - Retail - L2": {
                "keywords": ["iBeauty 2.0", "Beauty Advisor"],
                "boundary_keywords": ["BA"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2": {
                "keywords": ["OMNISALES", "MARS Ops", "retail Ops team"],
                "boundary_keywords": [],
                "weight": 1.0,
            },
            "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2": {
                "keywords": ["SFCC", "EBTQ", "Arvato"],
                "boundary_keywords": ["CED"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.CRM - L2": {
                "keywords": ["SFMC", "SFDC", "CRM001", "consent", "GDPR"],
                "boundary_keywords": [],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.NGLORA - L2": {
                "keywords": ["Rule-500", "points redemption"],
                "boundary_keywords": ["NGL", "NGLORA"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.OPERATIONS - L2": {
                "keywords": ["data pipeline failure", "ETL job"],
                "boundary_keywords": [],
                "weight": 1.0,
            },
            "APAC - ZN - SPACE B2C Hypercare": {
                "keywords": ["hypercare", "B2C", "go live", "go-live", "launch", "LS team"],
                "boundary_keywords": ["LS"],
                "weight": 1.0,
            },
            "TECH FNDN - WW - HIP INCIDENT L2": {
                "keywords": ["HIP", "infrastructure", "CloudSQL", "Cloudflare"],
                "boundary_keywords": ["HIP", "SSO", "SSL"],
                "weight": 1.0,
            },
        },
    }


def get_assignment_rules() -> str:
    """
    Return the full assignment routing matrix as formatted text.
    Intended for LLM inspection before calling recommend_assignment.
    """
    rules = _load_rules()
    version = rules.get("version", "unknown")
    groups_dict = rules.get("groups", {})

    lines = [
        f"ASSIGNMENT RULES (version {version})",
        f"Total groups: {len(ASSIGNMENT_GROUPS)}",
        "",
    ]
    for group_name in ASSIGNMENT_GROUPS:
        g = groups_dict.get(group_name, {})
        keywords = g.get("keywords", [])
        boundary_keywords = g.get("boundary_keywords", [])
        description = g.get("description", "")
        evidence_status = g.get("evidence_status", "")
        lines.append(f"  {group_name}")
        if evidence_status:
            lines.append(f"    Evidence: {evidence_status}")
        if description:
            lines.append(f"    Description: {description}")
        if keywords:
            lines.append(f"    Keywords (substring): {', '.join(keywords)}")
        if boundary_keywords:
            lines.append(f"    Keywords (word-boundary): {', '.join(boundary_keywords)}")
        lines.append("")
    return "\n".join(lines)


def recommend_assignment(
    incident_number: str,
    short_description: str,
    description: str,
    category: str = "",
    subcategory: str = "",
    comments_text: str = "",
    work_notes_text: str = "",
    current_group: str = "",
) -> dict:
    """
    Score incident text against routing rules and return a ranked recommendation.

    Scoring algorithm:
    - Combine all text fields (lowercased)
    - For each group: count keyword matches, multiply by weight
    - Rank groups by score descending
    - Confidence = top_score / total_score (proportion of all hits)
    - Fallback: if no group scores > 0, return _FALLBACK_GROUP with zero confidence

    Returns:
        {
            "recommended_group": str,       # exact canonical group name
            "confidence": float,            # 0.0–1.0
            "reason": str,                  # matched keywords or fallback explanation
            "alternatives": [               # top 3 runner-up groups with scores
                {"group": str, "score": float}, ...
            ],
            "reassignment_needed": bool,    # True if current_group != recommended_group
            "reassignment_reason": str,     # populated when reassignment_needed is True
        }
    """
    rules = _load_rules()
    groups_dict = rules.get("groups", {})

    # Combine all text fields; lowercase for case-insensitive matching
    full_text = " ".join([
        short_description or "",
        description or "",
        category or "",
        subcategory or "",
        comments_text or "",
        work_notes_text or "",
    ]).lower()

    scores: dict[str, float] = {}
    hit_keywords: dict[str, list[str]] = {}

    for group_name in ASSIGNMENT_GROUPS:
        g = groups_dict.get(group_name, {})
        keywords: list[str] = g.get("keywords", [])
        boundary_keywords: list[str] = g.get("boundary_keywords", [])
        weight: float = float(g.get("weight", 1.0))
        # Substring matches — case-insensitive, anywhere in text
        substring_hits = {kw for kw in keywords if kw.lower() in full_text}
        # Word-boundary matches — case-insensitive regex on full_text, with re.escape
        # so callers don't have to worry about regex metacharacters in their keywords
        boundary_hits: set[str] = set()
        for kw in boundary_keywords:
            if not kw:
                continue
            pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
            if pattern.search(full_text):
                boundary_hits.add(kw)
        # Union: unique keyword strings across both buckets
        hits = list(substring_hits | boundary_hits)
        score = len(hits) * weight
        scores[group_name] = score
        hit_keywords[group_name] = hits

    # Sort descending; tie-break by ASSIGNMENT_GROUPS order (stable sort preserves index order)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_group, top_score = ranked[0]

    # Confidence: proportion of total keyword hits captured by the top group
    total_score = sum(s for _, s in ranked)
    if total_score > 0:
        confidence = round(top_score / total_score, 3)
    else:
        # No matches at all — use fallback group with zero confidence
        top_group = _FALLBACK_GROUP
        confidence = 0.0

    # Build human-readable reason
    if hit_keywords.get(top_group):
        reason = (
            f"Matched {len(hit_keywords[top_group])} keyword(s): "
            f"{', '.join(sorted(hit_keywords[top_group]))}."
        )
    elif total_score == 0:
        reason = (
            f"No keyword matches found in incident text. "
            f"Defaulting to fallback group '{_FALLBACK_GROUP}'."
        )
    else:
        reason = f"Highest score by weight ({top_score}) with no explicit keyword match."

    # Reassignment decision
    reassignment_needed = bool(current_group and current_group.strip() != top_group)
    reassignment_reason = (
        f"Ticket is currently assigned to '{current_group}' "
        f"but signals point to '{top_group}'."
        if reassignment_needed
        else ""
    )

    logger.info(
        f"[ASSIGNMENT] {incident_number} → {top_group} "
        f"(confidence={confidence}, hits={hit_keywords.get(top_group, [])})"
    )

    return {
        "recommended_group": top_group,
        "confidence": confidence,
        "reason": reason,
        "alternatives": [
            {"group": g, "score": round(s, 3)}
            for g, s in ranked[1:4]  # top 3 runners-up
        ],
        "reassignment_needed": reassignment_needed,
        "reassignment_reason": reassignment_reason,
    }


# ════════════════════════════════════════════════════════════════════════════
# v2 — hybrid routing (hard rules + keyword + retrieval + L3 escalation)
# ════════════════════════════════════════════════════════════════════════════

# Compiled regex caches (built lazily, refreshed on rules reload)
_hard_rules_compiled: Optional[list] = None
_escalation_signals_compiled: Optional[list] = None


def _compile_hard_rules() -> list:
    """Return list of (compiled_regex, target_group, reason) tuples.

    Rules default to case-insensitive matching. Set `"case_sensitive": true`
    on a rule when the pattern relies on uppercase to avoid substring collisions
    (e.g. MARS-ID vs mars-id customer identifier).
    """
    global _hard_rules_compiled
    if _hard_rules_compiled is not None:
        return _hard_rules_compiled
    rules = _load_rules()
    hard = rules.get("hard_rules", [])
    out = []
    for r in hard:
        pattern = r.get("pattern")
        target = r.get("target")
        reason = r.get("reason", "")
        case_sensitive = bool(r.get("case_sensitive", False))
        if not pattern or not target:
            continue
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            out.append((re.compile(pattern, flags), target, reason))
        except re.error as e:
            logger.warning(f"[ASSIGNMENT] Skipping invalid hard-rule pattern {pattern!r}: {e}")
    _hard_rules_compiled = out
    return out


def _compile_escalation_signals() -> list:
    """Return list of compiled escalation-signal regexes."""
    global _escalation_signals_compiled
    if _escalation_signals_compiled is not None:
        return _escalation_signals_compiled
    rules = _load_rules()
    signals = rules.get("l3_escalation", {}).get("escalation_signals", [])
    out = []
    for pat in signals:
        try:
            out.append(re.compile(pat, re.IGNORECASE))
        except re.error as e:
            logger.warning(f"[ASSIGNMENT] Skipping invalid escalation signal {pat!r}: {e}")
    _escalation_signals_compiled = out
    return out


def _check_hard_rules(text: str) -> Optional[dict]:
    """Run all hard_rules against `text`. Returns first match info, or None."""
    for regex, target, reason in _compile_hard_rules():
        m = regex.search(text)
        if m:
            return {
                "target": target,
                "reason": reason,
                "matched_text": m.group(0)[:80],
            }
    return None


def _check_escalation_signals(text: str) -> list[str]:
    """Return the matched escalation signal strings (or [] if none)."""
    hits: list[str] = []
    for regex in _compile_escalation_signals():
        m = regex.search(text)
        if m:
            hits.append(m.group(0)[:60])
    return hits


def recommend_assignment_v2(
    incident_number: str,
    short_description: str,
    description: str,
    category: str = "",
    subcategory: str = "",
    comments_text: str = "",
    work_notes_text: str = "",
    current_group: str = "",
    retrieval_index_path: str = "",
    retrieval_top_k: int = 5,
) -> dict:
    """
    Hybrid recommender that combines three signals deterministically:

    1. **Hard rules** — `hard_rules` regex patterns run first; if any match, that
       group wins immediately with confidence 0.95.
    2. **Keyword scoring** — calls `recommend_assignment` (v1) for the substring +
       boundary keyword score.
    3. **Retrieval** — sentence-transformers kNN over the cached index; reports
       top-1 neighbour, top-k list, and a weighted vote (sum-of-scores per group).

    A final `recommended_group` is computed by combining the signals:
      - hard_rules match → use it
      - else if any L3-escalation signal hits AND keyword winner has an L3
        counterpart in `l3_escalation.l2_to_l3` → use the L3 counterpart
      - else if retrieval top-1 score >= 0.7 AND retrieval top-1 group is the
        keyword winner OR retrieval top-1 group has 2+ neighbours in top_k →
        use retrieval top-1
      - else fall back to the keyword winner

    The full signal dict is returned so the downstream LLM (Claude / Copilot)
    can override the combined recommendation when it has reason to.
    """
    full_text = " ".join([
        short_description or "",
        description or "",
        category or "",
        subcategory or "",
        comments_text or "",
        work_notes_text or "",
    ])

    rules = _load_rules()
    l3_map: dict[str, str] = rules.get("l3_escalation", {}).get("l2_to_l3", {})

    # ── Signal 1: Hard rules ───────────────────────────────────────────────
    hard_hit = _check_hard_rules(full_text)

    # ── Signal 2: Keyword scoring (v1) ─────────────────────────────────────
    kw_result = recommend_assignment(
        incident_number=incident_number,
        short_description=short_description,
        description=description,
        category=category,
        subcategory=subcategory,
        comments_text=comments_text,
        work_notes_text=work_notes_text,
        current_group=current_group,
    )

    # ── Signal 3: Retrieval (kNN) ──────────────────────────────────────────
    retrieval_block: dict = {"available": False}
    try:
        from tools import retrieval_tool  # noqa: PLC0415
        idx_path = retrieval_index_path
        if not idx_path:
            # Default sits next to this package
            idx_path = str(Path(__file__).resolve().parent.parent / "retrieval_index.npz")
        if Path(idx_path).exists():
            neighbours = retrieval_tool.find_similar(
                query_text=full_text,
                top_k=retrieval_top_k,
                index_path=idx_path,
                exclude_number=incident_number,
            )
            if neighbours:
                top1 = neighbours[0]
                weighted_group, weighted_sum, weighted_tally = retrieval_tool.vote_group(
                    neighbours, mode="weighted"
                )
                # Also count groups in top_k for the "2+ neighbours" heuristic
                from collections import Counter  # noqa: PLC0415
                group_counts = Counter([n["group"] for n in neighbours if n.get("group")])
                retrieval_block = {
                    "available": True,
                    "top1": {
                        "number": top1["number"],
                        "group": top1["group"],
                        "score": round(top1["score"], 3),
                    },
                    "neighbours": [
                        {
                            "number": n["number"],
                            "group": n["group"],
                            "score": round(n["score"], 3),
                        }
                        for n in neighbours
                    ],
                    "weighted_vote": {
                        "group": weighted_group,
                        "sum_of_scores": round(weighted_sum, 3),
                        "tally": {k: round(v, 3) for k, v in weighted_tally.items()},
                    },
                    "group_counts": dict(group_counts),
                }
    except RuntimeError as e:
        retrieval_block = {"available": False, "error": str(e)}
    except Exception as e:
        logger.warning(f"[ASSIGNMENT-V2] Retrieval error: {type(e).__name__}: {e}")
        retrieval_block = {"available": False, "error": str(e)}

    # ── L3 escalation check ────────────────────────────────────────────────
    # Two text views: short text (short_description + description) is the
    # canonical issue statement. Long text (full_text) includes work_notes
    # and comments, which contain HISTORICAL routing attempts that may have
    # been reverted — we treat those as weaker evidence.
    short_text = " ".join([short_description or "", description or ""])
    short_hits = _check_escalation_signals(short_text)
    full_hits = _check_escalation_signals(full_text)
    escalation_hits = full_hits  # full set is reported in `signals`

    kw_winner = kw_result["recommended_group"]
    escalated_to: Optional[str] = None

    if escalation_hits:
        l3_target_from_kw = l3_map.get(kw_winner)
        # Conservative escalation rule — avoid second-guessing tickets that
        # are ALREADY correctly placed in a canonical L2:
        #
        #   1. If short_description / description contain an escalation
        #      signal → the canonical issue itself describes L3 work
        #      → escalate.
        #   2. Else if the ticket is NOT currently in the L2 we'd escalate
        #      FROM (i.e. it sits somewhere else like B2C Hypercare or
        #      already in an L3 group) → escalate.
        #   3. Else (current_group equals kw_winner AND L3 signals appear
        #      only in work_notes/comments) → DO NOT escalate. The L3
        #      mentions are history from prior routing attempts; the L2
        #      placement is the most recent human decision.
        if l3_target_from_kw:
            if short_hits or (current_group.strip() != kw_winner):
                escalated_to = l3_target_from_kw
        elif retrieval_block.get("available"):
            r_top_group = retrieval_block["top1"]["group"]
            l3_target_from_retrieval = l3_map.get(r_top_group)
            if l3_target_from_retrieval and (
                short_hits or current_group.strip() != r_top_group
            ):
                escalated_to = l3_target_from_retrieval

    # ── Combine signals into a deterministic final recommendation ──────────
    final_group: str
    combined_confidence: float
    combined_reason: str
    source: str  # "hard_rule" | "l3_escalation" | "retrieval+keyword" | "retrieval_top1" | "keyword"

    if hard_hit:
        final_group = hard_hit["target"]
        combined_confidence = 0.95
        combined_reason = f"Hard rule matched: {hard_hit['reason']} (text: {hard_hit['matched_text']!r})"
        source = "hard_rule"
    elif escalated_to:
        final_group = escalated_to
        combined_confidence = 0.85
        combined_reason = (
            f"Escalated to L3 — L2 winner '{kw_winner}' has L3 counterpart '{escalated_to}' "
            f"and escalation signals fired: {', '.join(escalation_hits[:3])}"
        )
        source = "l3_escalation"
    elif retrieval_block.get("available"):
        top1 = retrieval_block["top1"]
        top1_score = top1["score"]
        top1_group = top1["group"]
        group_count_in_topk = retrieval_block["group_counts"].get(top1_group, 0)
        kw_confidence = kw_result["confidence"]

        # Retrieval-override rules — designed to be conservative so a small,
        # noisy corpus can't override a confident keyword winner:
        #
        #   A. If retrieval top-1 group == keyword winner AND top-1 score >= 0.6
        #      → both signals agree → high confidence in that group.
        #   B. If keyword winner has confidence >= 0.4 AND retrieval disagrees
        #      → trust the keyword scorer. The kNN corpus is small (one user's
        #      active queue) and can drag tickets toward over-represented groups.
        #   C. If keyword confidence < 0.4 (essentially a fallback) AND retrieval
        #      top-1 score >= 0.7 AND >= 2 of top-5 share that group
        #      → retrieval can override.
        #   D. Else → keep keyword winner.
        if top1_group == kw_winner and top1_score >= 0.6:
            final_group = top1_group
            combined_confidence = round(min(0.95, 0.5 + top1_score / 2), 3)
            combined_reason = (
                f"Retrieval top-1 ({top1['number']}, score {top1_score}) and keyword scorer "
                f"agree on '{top1_group}'."
            )
            source = "retrieval+keyword"
        elif (
            kw_confidence < 0.4
            and top1_score >= 0.7
            and group_count_in_topk >= 2
        ):
            final_group = top1_group
            combined_confidence = round(min(0.95, 0.5 + top1_score / 2), 3)
            combined_reason = (
                f"Keyword scorer was uncertain (conf {kw_confidence}). Retrieval top-1 "
                f"score {top1_score} >= 0.7 and {group_count_in_topk} of top-5 neighbours "
                f"share group '{top1_group}'."
            )
            source = "retrieval_top1"
        else:
            final_group = kw_winner
            combined_confidence = kw_confidence
            combined_reason = (
                f"Keyword scorer chose '{kw_winner}' (conf {kw_confidence}). "
                f"Retrieval top-1 was '{top1_group}' (score {top1_score}) — "
                "insufficient to override keyword."
            )
            source = "keyword"
    else:
        final_group = kw_winner
        combined_confidence = kw_result["confidence"]
        combined_reason = kw_result["reason"] + " (retrieval index not available)"
        source = "keyword"

    reassignment_needed = bool(current_group and current_group.strip() != final_group)
    reassignment_reason = (
        f"Ticket is currently assigned to '{current_group}' but signals point to '{final_group}'."
        if reassignment_needed
        else ""
    )

    logger.info(
        f"[ASSIGNMENT-V2] {incident_number} → {final_group} "
        f"(source={source}, confidence={combined_confidence})"
    )

    return {
        # Combined deterministic answer (LLM may override)
        "recommended_group": final_group,
        "confidence": combined_confidence,
        "reason": combined_reason,
        "source": source,
        "reassignment_needed": reassignment_needed,
        "reassignment_reason": reassignment_reason,
        # Individual signals (for LLM-as-judge layer to weigh)
        "signals": {
            "hard_rule": hard_hit,  # None when no match
            "keyword": {
                "recommended_group": kw_winner,
                "confidence": kw_result["confidence"],
                "reason": kw_result["reason"],
                "alternatives": kw_result["alternatives"],
            },
            "retrieval": retrieval_block,
            "l3_escalation": {
                "signals_matched": escalation_hits,
                "escalated_from_to": (
                    {"from": kw_winner, "to": escalated_to} if escalated_to else None
                ),
            },
        },
    }
