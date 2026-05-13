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
                "keywords": ["SAP", "SAPMENA", "SGP", "Singapore", "pipeline", "CDS"],
                "weight": 1.0,
            },
            "APAC - THN - Retail IT": {
                "keywords": ["Thailand", "THN", "POS", "retail store", "printer"],
                "weight": 1.0,
            },
            "APAC - ZN - iBeauty 2.0 - Retail - L2": {
                "keywords": ["iBeauty", "beauty advisor"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2": {
                "keywords": ["OMNISALES", "MARS", "Capgemini"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2": {
                "keywords": ["CED", "e-commerce", "online"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.CRM - L2": {
                "keywords": ["CRM", "loyalty", "consumer profile"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.NGLORA - L2": {
                "keywords": ["NGLORA", "LORA"],
                "weight": 1.0,
            },
            "APAC - ZN - O+O.OPERATIONS - L2": {
                "keywords": ["operations", "ETL", "pipeline"],
                "weight": 1.0,
            },
            "APAC - ZN - SPACE B2C Hypercare": {
                "keywords": ["B2C", "hypercare", "go-live"],
                "weight": 1.0,
            },
            "TECH FNDN - WW - HIP INCIDENT L2": {
                "keywords": ["HIP", "infrastructure", "network"],
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
        description = g.get("description", "")
        lines.append(f"  {group_name}")
        if description:
            lines.append(f"    Description: {description}")
        if keywords:
            lines.append(f"    Keywords: {', '.join(keywords)}")
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
        weight: float = float(g.get("weight", 1.0))
        # Collect unique matching keywords (case-insensitive)
        hits = list({kw for kw in keywords if kw.lower() in full_text})
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
