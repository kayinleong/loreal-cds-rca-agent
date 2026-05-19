"""
handoffs.py — Extract explicit reassignment / handoff sentences from work_notes + comments.

These sentences are the highest-signal evidence for what really predicts each L2 group:
human operators state the routing reason in plain English when they reassign.

Output: Markdown table of (incident, group, handoff phrase, target group).

Usage:
    python handoffs.py <incidents_json>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Patterns that typically signal a routing decision in SNOW work notes
HANDOFF_PATTERNS = [
    re.compile(r"(reassign\w*[^.]{0,200})", re.IGNORECASE),
    re.compile(r"(assign\w*\s+to[^.]{0,150})", re.IGNORECASE),
    re.compile(r"(transfer\w*\s+(?:to|the)[^.]{0,150})", re.IGNORECASE),
    re.compile(r"(route\w*\s+to[^.]{0,150})", re.IGNORECASE),
    re.compile(r"(handover\s+to[^.]{0,150})", re.IGNORECASE),
    re.compile(r"((?:this\s+is\s+(?:a\s+)?(?:related\s+to|under|for|owned\s+by)[^.]{0,150}))", re.IGNORECASE),
    re.compile(r"(needs?\s+to\s+(?:be\s+)?(?:handled|owned|investigated)\s+by[^.]{0,150})", re.IGNORECASE),
    re.compile(r"(please\s+(?:check|assist|handle|investigate|reassign|take\s+over|look\s+into)[^.]{0,150})", re.IGNORECASE),
    re.compile(r"(over\s+to\s+[A-Z][^.]{0,100})", re.IGNORECASE),
    re.compile(r"(forwarded\s+to[^.]{0,100})", re.IGNORECASE),
    re.compile(r"((?:wrong|incorrect)\s+(?:assignment|group|team)[^.]{0,150})", re.IGNORECASE),
    re.compile(r"((?:should\s+be|belongs?\s+to)\s+[^.]{0,100})", re.IGNORECASE),
]


def clean_text(s: str) -> str:
    if not s:
        return ""
    # Strip HTML
    s = re.sub(r"<[^>]+>", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_handoffs(text: str) -> list[str]:
    """Return list of unique sentence-like handoff phrases found in text."""
    text = clean_text(text)
    hits: list[str] = []
    seen: set[str] = set()
    for pat in HANDOFF_PATTERNS:
        for m in pat.finditer(text):
            phrase = clean_text(m.group(1))
            # Normalise short key for dedupe
            key = re.sub(r"\W+", " ", phrase.lower()).strip()
            if key and key not in seen and len(phrase) > 6:
                hits.append(phrase[:200])
                seen.add(key)
    return hits


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python handoffs.py <incidents_json>", file=sys.stderr)
        sys.exit(1)

    incidents_path = Path(sys.argv[1])
    with incidents_path.open(encoding="utf-8") as fh:
        incidents = json.load(fh)

    print("# Explicit handoff / reassignment phrases in real SNOW notes")
    print()
    print("Extracted from `work_notes` and `comments` of fetched incidents.")
    print("These are statements human operators wrote when handing tickets between teams.")
    print()
    print("| # | Incident | Current Group | Handoff Phrase (excerpt) |")
    print("|---|---|---|---|")
    row_idx = 0
    for rec in incidents:
        inc = rec.get("incident", {}) or {}
        number = inc.get("number") or "?"
        group = (inc.get("assignment_group") or "").strip() or "(unassigned)"
        # Concat all comments + work_notes into one text
        all_text = " \n".join(
            [n.get("text") or "" for n in (rec.get("work_notes") or [])]
            + [c.get("text") or "" for c in (rec.get("comments") or [])]
        )
        phrases = extract_handoffs(all_text)
        for ph in phrases[:5]:  # cap at 5 per incident
            row_idx += 1
            safe_ph = ph.replace("|", "\\|").replace("\n", " ")
            cg = group.replace("APAC - ", "").replace("TECH FNDN - ", "")
            print(f"| {row_idx} | `{number}` | {cg} | {safe_ph} |")
    print()
    print(f"**Total handoff phrases extracted: {row_idx}**")


if __name__ == "__main__":
    main()
