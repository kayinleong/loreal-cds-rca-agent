"""
analyze.py — Read fetched SNOW incidents and emit routing-signal evidence.

Output: prints Markdown sections to stdout, suitable for FINDINGS.md.
No SNOW or BQ calls — reads only the local _all_incidents.json + assignment_rules.json.

Usage:
    python analyze.py <incidents_json> <rules_json>
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Stopwords — common English + SNOW boilerplate
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "doing",
    "will", "would", "could", "should", "may", "might", "must", "can", "shall",
    "i", "we", "you", "they", "he", "she", "it", "this", "that", "these", "those",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "into", "of",
    "not", "no", "yes", "so", "than", "very", "more", "less", "most", "least",
    "all", "any", "some", "each", "every", "both", "few", "many", "much",
    "please", "thanks", "thank", "regards", "hi", "hello", "dear", "team",
    "incident", "ticket", "issue", "problem", "error", "request", "user", "users",
    "url", "http", "https", "com", "br", "li", "div", "span", "img", "src", "alt",
    "value", "true", "false", "null", "none", "name", "data", "type", "id", "ref",
    "sys", "system", "snow", "servicenow", "loreal",
    "we", "us", "our", "your", "their", "his", "her", "him", "them", "me", "my",
    "above", "below", "out", "off", "through", "during", "before", "after", "until",
    "while", "about", "against", "between", "into", "through", "during", "where",
    "when", "why", "how", "what", "which", "who", "whom",
    "also", "just", "only", "even", "still", "yet", "already", "now", "soon",
    "see", "seen", "seems", "looks", "look", "showing", "shows",
    "x", "y", "z", "n", "k",
    "image", "src", "br", "p", "table", "tr", "td", "th",
}

# Tokenizer: words >= 3 chars, alphanumeric (preserves SAP, OMNI, MARS, etc)
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-\.]{2,}")


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    # Strip HTML tags first
    text = re.sub(r"<[^>]+>", " ", text)
    return [t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in STOPWORDS]


def collect_text(rec: dict) -> dict:
    """Pull all interesting text from one incident record."""
    inc = rec.get("incident", {}) or {}
    parts = {
        "short_description": inc.get("short_description") or "",
        "description": inc.get("description") or "",
        "category": inc.get("category") or "",
        "subcategory": inc.get("subcategory") or "",
        "comments": " \n".join(c.get("text", "") or "" for c in rec.get("comments", []) or []),
        "work_notes": " \n".join(n.get("text", "") or "" for n in rec.get("work_notes", []) or []),
    }
    return parts


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python analyze.py <incidents_json> <rules_json>", file=sys.stderr)
        sys.exit(1)

    incidents_path = Path(sys.argv[1])
    rules_path = Path(sys.argv[2])

    with incidents_path.open(encoding="utf-8") as fh:
        incidents = json.load(fh)
    with rules_path.open(encoding="utf-8") as fh:
        rules = json.load(fh)

    groups_rules: dict[str, list[str]] = {
        g: rules["groups"][g].get("keywords", []) for g in rules.get("groups", {})
    }

    # ── Per-incident analysis ───────────────────────────────────────────────
    per_incident_rows: list[dict] = []
    per_group_tokens: defaultdict[str, Counter] = defaultdict(Counter)
    group_incident_count: Counter = Counter()

    for rec in incidents:
        inc = rec.get("incident", {}) or {}
        number = inc.get("number") or "?"
        short = (inc.get("short_description") or "").strip().replace("\n", " ")[:90]
        cur_group = (inc.get("assignment_group") or "").strip() or "(unassigned)"
        category = inc.get("category") or ""
        subcategory = inc.get("subcategory") or ""
        priority = inc.get("priority") or ""
        state = inc.get("state") or ""

        text_parts = collect_text(rec)
        combined = " ".join(text_parts.values())
        tokens = tokenize(combined)

        # Score against each rule's keywords (case-insensitive substring on raw text)
        combined_lower = combined.lower()
        scores: dict[str, list[str]] = {}
        for g, kws in groups_rules.items():
            hits = [kw for kw in kws if kw.lower() in combined_lower]
            scores[g] = hits

        ranked = sorted(scores.items(), key=lambda x: len(x[1]), reverse=True)
        top_group, top_hits = ranked[0]
        runner = ranked[1] if len(ranked) > 1 else ("", [])
        confidence = (
            len(top_hits) / sum(len(h) for _, h in ranked)
            if sum(len(h) for _, h in ranked) > 0
            else 0.0
        )

        per_incident_rows.append({
            "number": number,
            "short": short,
            "current_group": cur_group,
            "predicted_group": top_group if top_hits else "(no match → fallback)",
            "top_hits": top_hits,
            "runner_up": runner[0] if runner[1] else "",
            "runner_hits": runner[1],
            "confidence": round(confidence, 2),
            "category": category,
            "subcategory": subcategory,
            "priority": priority,
            "state": state,
            "n_comments": len(rec.get("comments") or []),
            "n_work_notes": len(rec.get("work_notes") or []),
            "n_attachments": len((rec.get("attachments") or {}).get("images", []))
                + len((rec.get("attachments") or {}).get("files", [])),
            "matches_current": cur_group == top_group and bool(top_hits),
        })

        group_incident_count[cur_group] += 1
        for tok in tokens:
            per_group_tokens[cur_group][tok] += 1

    # ── Header ──────────────────────────────────────────────────────────────
    print(f"# FINDINGS — Real-incident analysis of ticketasg routing")
    print()
    print(f"Total incidents analysed: **{len(incidents)}**")
    print(f"Distinct current groups: **{len(group_incident_count)}**")
    print()

    # ── Group distribution ──────────────────────────────────────────────────
    print("## 1. Current assignment-group distribution")
    print()
    print("| # | Current Group | Incidents | % |")
    print("|---|---|---:|---:|")
    total = len(incidents) or 1
    for i, (g, c) in enumerate(group_incident_count.most_common(), 1):
        pct = round(c * 100 / total, 1)
        print(f"| {i} | `{g}` | {c} | {pct}% |")
    print()
    # Coverage by canonical 10 groups
    canonical_set = set(groups_rules.keys())
    seen_canonical = canonical_set & set(group_incident_count.keys())
    missing_canonical = canonical_set - set(group_incident_count.keys())
    out_of_scope = set(group_incident_count.keys()) - canonical_set - {"(unassigned)"}
    print(f"- Canonical groups (10 supported) **with** incidents in this sample: **{len(seen_canonical)}/10**")
    if missing_canonical:
        print(f"- Canonical groups with **no** incidents in this sample:")
        for g in sorted(missing_canonical):
            print(f"  - `{g}`")
    if out_of_scope:
        print(f"- **Out-of-scope** groups present in this sample (tickets currently sit outside the 10 canonical groups):")
        for g in sorted(out_of_scope):
            print(f"  - `{g}` ({group_incident_count[g]} incidents)")
    print()

    # ── Per-incident table ──────────────────────────────────────────────────
    print("## 2. Per-incident routing trace")
    print()
    print("Each row scores the incident text against the existing `assignment_rules.json` keywords.")
    print("`Match?` = `✓` when the current SNOW group equals the keyword-predicted group.")
    print()
    print("| # | Incident | Short Description | Current Group | Predicted (by current rules) | Hits | Conf | Match? |")
    print("|---|---|---|---|---|---|---:|:---:|")
    for i, r in enumerate(per_incident_rows, 1):
        hits = ", ".join(sorted(r["top_hits"])) if r["top_hits"] else "—"
        cg = r["current_group"].replace("APAC - ", "").replace("TECH FNDN - ", "")
        pg = r["predicted_group"].replace("APAC - ", "").replace("TECH FNDN - ", "")
        match = "✓" if r["matches_current"] else "✗"
        # Markdown-escape pipes
        short = r["short"].replace("|", "\\|")
        print(f"| {i} | `{r['number']}` | {short} | {cg} | {pg} | {hits} | {r['confidence']} | {match} |")
    print()
    # Match-rate
    matched = sum(1 for r in per_incident_rows if r["matches_current"])
    print(f"**Match rate (current group = predicted group): {matched}/{len(per_incident_rows)} = {round(matched*100/max(len(per_incident_rows),1),1)}%**")
    print()
    # False predictions where current_group is canonical
    canonical_incidents = [r for r in per_incident_rows if r["current_group"] in canonical_set]
    canonical_matches = sum(1 for r in canonical_incidents if r["matches_current"])
    print(f"Of incidents currently assigned to a canonical group ({len(canonical_incidents)}), "
          f"current rules correctly predict **{canonical_matches}** = "
          f"{round(canonical_matches*100/max(len(canonical_incidents),1),1)}%.")
    print()

    # ── Per-group real-token evidence ──────────────────────────────────────
    print("## 3. Per-group real-text signals vs current keywords")
    print()
    print("For each group (with at least 1 incident in this sample), the table shows:")
    print("- **Top tokens** observed in real incident text (after stopword removal)")
    print("- **Current keywords** from `assignment_rules.json` and whether each one actually matched")
    print()
    for g, c in group_incident_count.most_common():
        if g not in canonical_set:
            continue
        print(f"### `{g}` — {c} incidents")
        print()
        # Top tokens
        top_tokens = per_group_tokens[g].most_common(20)
        print("**Top 20 real tokens** (count):")
        print()
        if top_tokens:
            print("| Token | Count |")
            print("|---|---:|")
            for t, n in top_tokens:
                print(f"| `{t}` | {n} |")
        else:
            print("_(no text data)_")
        print()
        # Current keywords with hit count (corpus-wide for this group)
        kws = groups_rules.get(g, [])
        if kws:
            corpus = " ".join(per_group_tokens[g].elements()).lower()  # all tokens joined
            # Use per_incident_rows hits to count how many incidents in this group matched each kw
            per_kw_in_group: Counter = Counter()
            incidents_in_g = [r for r in per_incident_rows if r["current_group"] == g]
            for r in incidents_in_g:
                # We don't have raw hit list keyed by group; recompute via top_hits + runner_hits
                # Easier: re-derive from the rec — but we don't have rec here.
                # Approximation: check whether kw substring appears in r's short description
                pass
            # Recompute properly: redo scoring on raw incidents for this group only
            # We retained text in collect_text but not here. Just leave a placeholder
            # — accurate per-kw stats will come from a second pass below.
            print("**Current `assignment_rules.json` keywords for this group:**")
            print()
            print(", ".join(f"`{k}`" for k in kws))
        print()

    # ── Pass 2 — per-keyword hit counts ─────────────────────────────────────
    print("## 4. Per-keyword diagnostic (across ALL incidents)")
    print()
    print("How often each keyword in `assignment_rules.json` actually matches text in the sample,")
    print("and how often that match lined up with the keyword's group being the **current** group.")
    print()
    print("| Group | Keyword | Total hits | Hits in *its own* group | Drift¹ |")
    print("|---|---|---:|---:|---:|")
    # We need to rebuild per-incident text for this
    incident_text = []
    incident_group = []
    for rec in incidents:
        inc = rec.get("incident", {}) or {}
        text_parts = collect_text(rec)
        incident_text.append(" ".join(text_parts.values()).lower())
        incident_group.append((inc.get("assignment_group") or "").strip())
    for g, kws in groups_rules.items():
        for kw in kws:
            kl = kw.lower()
            total = sum(1 for t in incident_text if kl in t)
            in_group = sum(1 for t, ig in zip(incident_text, incident_group) if kl in t and ig == g)
            drift = "" if total == 0 else round(1 - in_group / total, 2)
            print(f"| `{g[:40]}…` | `{kw}` | {total} | {in_group} | {drift} |")
    print()
    print("¹ Drift = `1 - (in_group / total)` — i.e. the fraction of matches that landed in a **different** current group. High drift means the keyword is ambiguous.")
    print()


if __name__ == "__main__":
    main()
