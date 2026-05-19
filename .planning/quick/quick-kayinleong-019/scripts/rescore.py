"""
rescore.py — Replay the 64 quick-018 incidents through the v1.1 ticketasg rules
and emit a Markdown comparison vs the v1.0 baseline.

This calls the REAL `assignment_tool.recommend_assignment()` function so we test
the production code path, not a reimplemented scorer.

Usage:
    python rescore.py <incidents_json>

Output: prints Markdown to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Wire up imports so assignment_tool can find `config`
_PKG = Path(__file__).resolve().parent.parent.parent.parent.parent / "ticketasg_copilot_agent"
sys.path.insert(0, str(_PKG))
sys.path.insert(0, str(_PKG / "tools"))

from tools import assignment_tool  # noqa: E402  (path setup above)


def collect_text(rec: dict) -> dict:
    """Same shape as analyze.py — pull all interesting text fields from one record."""
    inc = rec.get("incident", {}) or {}
    return {
        "short_description": inc.get("short_description") or "",
        "description": inc.get("description") or "",
        "category": inc.get("category") or "",
        "subcategory": inc.get("subcategory") or "",
        "comments": " \n".join(c.get("text", "") or "" for c in rec.get("comments", []) or []),
        "work_notes": " \n".join(n.get("text", "") or "" for n in rec.get("work_notes", []) or []),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python rescore.py <incidents_json>", file=sys.stderr)
        sys.exit(1)

    incidents_path = Path(sys.argv[1])
    with incidents_path.open(encoding="utf-8") as fh:
        incidents = json.load(fh)

    # Make sure rules cache is fresh
    assignment_tool._rules_cache = None

    rows = []
    for rec in incidents:
        inc = rec.get("incident", {}) or {}
        text = collect_text(rec)
        cur = (inc.get("assignment_group") or "").strip()
        result = assignment_tool.recommend_assignment(
            incident_number=inc.get("number") or "?",
            short_description=text["short_description"],
            description=text["description"],
            category=text["category"],
            subcategory=text["subcategory"],
            comments_text=text["comments"],
            work_notes_text=text["work_notes"],
            current_group=cur,
        )
        rows.append({
            "number": inc.get("number") or "?",
            "short": (text["short_description"] or "").strip().replace("\n", " ")[:80],
            "current": cur or "(unassigned)",
            "recommended": result["recommended_group"],
            "confidence": result["confidence"],
            "reason": result["reason"],
            "matches_current": cur == result["recommended_group"],
        })

    # Stats
    total = len(rows)
    matches = sum(1 for r in rows if r["matches_current"])
    # v1.0 baseline numbers from quick-018 FINDINGS.md (recomputed there)
    BASELINE_TOTAL = 64
    BASELINE_MATCHES = 11

    print("# Re-score of 64 quick-018 incidents under v1.1 rules")
    print()
    print(f"Re-ran `recommend_assignment` against the same 64 incidents fetched in quick-018.")
    print(f"This calls the actual production function so the result reflects the real code path.")
    print()
    print("## Headline")
    print()
    print("| Rules version | Match rate (current = recommended) |")
    print("|---|---:|")
    print(f"| v1.0 (quick-018 baseline) | {BASELINE_MATCHES}/{BASELINE_TOTAL} = {round(BASELINE_MATCHES*100/BASELINE_TOTAL,1)} % |")
    print(f"| v1.1 (this rewrite)       | {matches}/{total} = {round(matches*100/max(total,1),1)} % |")
    delta = matches - BASELINE_MATCHES
    sign = "+" if delta >= 0 else ""
    print()
    print(f"**Delta: {sign}{delta} incidents** (absolute), "
          f"{sign}{round((matches-BASELINE_MATCHES)*100/BASELINE_TOTAL,1)} pp.")
    print()
    print("## Per-incident comparison")
    print()
    print("| # | Incident | Short Description | Current | v1.1 Recommended | Conf | Match? |")
    print("|---|---|---|---|---|---:|:---:|")
    for i, r in enumerate(rows, 1):
        cg = r["current"].replace("APAC - ", "").replace("TECH FNDN - ", "")
        rg = r["recommended"].replace("APAC - ", "").replace("TECH FNDN - ", "")
        short = r["short"].replace("|", "\\|")
        match = "✓" if r["matches_current"] else "✗"
        print(f"| {i} | `{r['number']}` | {short} | {cg} | {rg} | {r['confidence']} | {match} |")
    print()

    # By-group breakdown
    from collections import Counter, defaultdict
    by_current: defaultdict[str, list] = defaultdict(list)
    for r in rows:
        by_current[r["current"]].append(r)
    print("## Match rate by current group")
    print()
    print("| Current Group | Incidents | Matched | Rate |")
    print("|---|---:|---:|---:|")
    for g, rs in sorted(by_current.items(), key=lambda x: -len(x[1])):
        m = sum(1 for r in rs if r["matches_current"])
        rate = round(m * 100 / len(rs), 1)
        gs = g.replace("APAC - ", "").replace("TECH FNDN - ", "")
        print(f"| {gs} | {len(rs)} | {m} | {rate} % |")
    print()

    # New mispredictions by destination (where v1.1 sends the misses)
    misses = [r for r in rows if not r["matches_current"]]
    print(f"## Where the {len(misses)} v1.1 mispredictions land")
    print()
    print("| Predicted Group | Count |")
    print("|---|---:|")
    miss_dest: Counter = Counter()
    for r in misses:
        miss_dest[r["recommended"]] += 1
    for g, c in miss_dest.most_common():
        gs = g.replace("APAC - ", "").replace("TECH FNDN - ", "")
        print(f"| {gs} | {c} |")
    print()


if __name__ == "__main__":
    main()
