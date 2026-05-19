"""
rescore_v2.py — Replay the 64 quick-018 incidents through the v2 hybrid recommender
and emit a Markdown comparison vs the v1.0 keyword-only baseline AND the v1.1 rules.

Production code path used (calls assignment_tool.recommend_assignment_v2 directly).

Usage:
    python rescore_v2.py <incidents_json> [<retrieval_index.npz>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Wire up imports
_PKG = Path(__file__).resolve().parent.parent.parent.parent.parent / "ticketasg_copilot_agent"
sys.path.insert(0, str(_PKG))
sys.path.insert(0, str(_PKG / "tools"))

from tools import assignment_tool  # noqa: E402


def collect_text(rec: dict) -> dict:
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
        print("Usage: python rescore_v2.py <incidents_json> [<retrieval_index.npz>]", file=sys.stderr)
        sys.exit(1)

    incidents_path = Path(sys.argv[1])
    idx_path = sys.argv[2] if len(sys.argv) > 2 else str(_PKG / "retrieval_index.npz")

    with incidents_path.open(encoding="utf-8") as fh:
        incidents = json.load(fh)

    # Refresh caches
    assignment_tool._rules_cache = None
    assignment_tool._hard_rules_compiled = None
    assignment_tool._escalation_signals_compiled = None

    rows = []
    source_counter: Counter = Counter()
    for rec in incidents:
        inc = rec.get("incident", {}) or {}
        text = collect_text(rec)
        cur = (inc.get("assignment_group") or "").strip()
        # Exclude the ticket itself from retrieval neighbours
        result = assignment_tool.recommend_assignment_v2(
            incident_number=inc.get("number") or "?",
            short_description=text["short_description"],
            description=text["description"],
            category=text["category"],
            subcategory=text["subcategory"],
            comments_text=text["comments"],
            work_notes_text=text["work_notes"],
            current_group=cur,
            retrieval_index_path=idx_path,
        )
        source_counter[result.get("source", "?")] += 1
        rows.append({
            "number": inc.get("number") or "?",
            "short": (text["short_description"] or "").strip().replace("\n", " ")[:80],
            "current": cur or "(unassigned)",
            "recommended": result["recommended_group"],
            "source": result.get("source", "?"),
            "confidence": result["confidence"],
            "matches_current": cur == result["recommended_group"],
        })

    total = len(rows)
    matches = sum(1 for r in rows if r["matches_current"])
    BASELINE_V10_MATCHES = 11
    BASELINE_V11_MATCHES = 20

    print("# Re-score of 64 quick-018 incidents under v2.0 hybrid rules")
    print()
    print("`recommend_assignment_v2` invoked directly (production code path).")
    print(f"Retrieval index: `{idx_path}`")
    print()

    print("## Headline — match rate progression")
    print()
    print("| Rules version | Match rate | Δ vs prior |")
    print("|---|---:|---:|")
    print(f"| v1.0 (quick-018 baseline) | {BASELINE_V10_MATCHES}/{total} = {round(BASELINE_V10_MATCHES*100/total,1)} % | — |")
    print(f"| v1.1 (quick-019)          | {BASELINE_V11_MATCHES}/{total} = {round(BASELINE_V11_MATCHES*100/total,1)} % | +{BASELINE_V11_MATCHES-BASELINE_V10_MATCHES} ({round((BASELINE_V11_MATCHES-BASELINE_V10_MATCHES)*100/total,1)} pp) |")
    print(f"| v2.0 (this claim)         | {matches}/{total} = {round(matches*100/total,1)} % | +{matches-BASELINE_V11_MATCHES} ({round((matches-BASELINE_V11_MATCHES)*100/total,1)} pp) |")
    print()
    print(f"**Net gain over v1.0:** +{matches-BASELINE_V10_MATCHES} incidents ({round((matches-BASELINE_V10_MATCHES)*100/total,1)} pp)")
    print()

    print("## Signal source distribution (where v2 got its answers from)")
    print()
    print("| Source | Count |")
    print("|---|---:|")
    for s, c in source_counter.most_common():
        print(f"| `{s}` | {c} |")
    print()

    print("## Match rate by current group")
    print()
    by_current: defaultdict[str, list] = defaultdict(list)
    for r in rows:
        by_current[r["current"]].append(r)
    print("| Current Group | Incidents | Matched | Rate |")
    print("|---|---:|---:|---:|")
    for g, rs in sorted(by_current.items(), key=lambda x: -len(x[1])):
        m = sum(1 for r in rs if r["matches_current"])
        rate = round(m * 100 / len(rs), 1)
        gs = g.replace("APAC - ", "").replace("TECH FNDN - ", "")
        print(f"| {gs} | {len(rs)} | {m} | {rate} % |")
    print()

    print("## Per-incident trace")
    print()
    print("| # | Incident | Short Description | Current | v2 Recommended | Source | Conf | Match? |")
    print("|---|---|---|---|---|---|---:|:---:|")
    for i, r in enumerate(rows, 1):
        cg = r["current"].replace("APAC - ", "").replace("TECH FNDN - ", "")
        rg = r["recommended"].replace("APAC - ", "").replace("TECH FNDN - ", "")
        short = r["short"].replace("|", "\\|")
        match = "✓" if r["matches_current"] else "✗"
        print(f"| {i} | `{r['number']}` | {short} | {cg} | {rg} | `{r['source']}` | {r['confidence']} | {match} |")
    print()

    # Where misses land
    misses = [r for r in rows if not r["matches_current"]]
    miss_dest: Counter = Counter()
    for r in misses:
        miss_dest[r["recommended"]] += 1
    print(f"## Where the {len(misses)} v2 mispredictions land")
    print()
    print("| Predicted Group | Count |")
    print("|---|---:|")
    for g, c in miss_dest.most_common():
        gs = g.replace("APAC - ", "").replace("TECH FNDN - ", "")
        print(f"| {gs} | {c} |")


if __name__ == "__main__":
    main()
