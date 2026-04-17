"""
Investigation Wiki — Karpathy's Wiki Pattern for RCA
=====================================================
Persistent scratchpad that accumulates findings across iterations.
The LLM writes to it (update_findings) and reads from it (read_wiki)
so knowledge compounds instead of evaporating between tool calls.

Wiki pages:
  - timeline:    Chronological events
  - evidence:    Validated data points
  - hypothesis:  Theories being tested
  - conclusion:  Confirmed findings
  - action_item: Remediation steps
  - log:         Append-only operation log (Karpathy's log.md)
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class InvestigationWiki:
    """
    In-memory wiki that mirrors Karpathy's raw/ + wiki/ + log.md pattern.
    
    - Pages are categories of findings
    - Each entry has content, confidence, source, and timestamp
    - The log tracks every operation for auditability
    """

    def __init__(self, persist_dir: str = None):
        self.pages: dict[str, list[dict]] = {
            "timeline": [],
            "evidence": [],
            "hypothesis": [],
            "conclusion": [],
            "action_item": [],
        }
        self.log: list[str] = []
        self.persist_dir = Path(persist_dir) if persist_dir else None

    def update(self, category: str, content: str,
               confidence: str = "medium", source: str = "") -> str:
        """Add a finding to a wiki page. Returns confirmation."""
        if category not in self.pages:
            return f"Unknown category '{category}'. Use: {list(self.pages.keys())}"

        entry = {
            "content": content,
            "confidence": confidence,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        }
        self.pages[category].append(entry)

        log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] " \
                     f"Added {category} ({confidence}): {content[:80]}..."
        self.log.append(log_entry)

        if self.persist_dir:
            self._persist()

        return f"Recorded [{confidence.upper()}] {category}: {content[:100]}"

    def read(self, category: str = "all") -> str:
        """Read wiki pages. Returns formatted content for LLM."""
        if category != "all" and category not in self.pages:
            return f"Unknown category '{category}'. Available: {list(self.pages.keys())}"

        pages_to_read = (
            self.pages if category == "all"
            else {category: self.pages[category]}
        )

        if not any(pages_to_read.values()):
            return "Investigation wiki is empty. No findings recorded yet."

        lines = ["── INVESTIGATION WIKI ──"]
        for page_name, entries in pages_to_read.items():
            if not entries:
                continue
            lines.append(f"\n## {page_name.upper()} ({len(entries)} entries)")
            for e in entries:
                conf = e.get("confidence", "?").upper()
                src = f" (from: {e['source']})" if e.get("source") else ""
                lines.append(f"  [{conf}] {e['content']}{src}")
        return "\n".join(lines)

    def get_structured(self) -> dict:
        """Return raw wiki data for report generation."""
        return {
            "pages": self.pages,
            "log": self.log,
        }

    def to_index(self) -> str:
        """Generate index.md — Karpathy's content-oriented catalog."""
        lines = ["# Investigation Index", ""]
        for page_name, entries in self.pages.items():
            count = len(entries)
            if count > 0:
                summary = entries[-1]["content"][:60] + "..."
                lines.append(f"- **{page_name}** ({count} entries) — latest: {summary}")
            else:
                lines.append(f"- **{page_name}** (empty)")
        lines.append(f"\nTotal operations: {len(self.log)}")
        return "\n".join(lines)

    def _persist(self):
        """Save wiki state to disk for crash recovery."""
        if not self.persist_dir:
            return
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "pages": self.pages,
            "log": self.log,
            "saved_at": datetime.now().isoformat(),
        }
        path = self.persist_dir / "wiki_state.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def load_from_disk(self):
        """Restore wiki state from disk."""
        if not self.persist_dir:
            return
        path = self.persist_dir / "wiki_state.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
            self.pages = state.get("pages", self.pages)
            self.log = state.get("log", [])
            logger.info(f"[WIKI] Restored state from {path}")


# ── Module-level singleton and tool functions ────────────────────────────────

_wiki: Optional[InvestigationWiki] = None


def init_wiki(persist_dir: str = None) -> InvestigationWiki:
    """Initialize the global wiki instance."""
    global _wiki
    _wiki = InvestigationWiki(persist_dir=persist_dir)
    if persist_dir:
        _wiki.load_from_disk()
    return _wiki


def get_wiki() -> InvestigationWiki:
    global _wiki
    if _wiki is None:
        _wiki = InvestigationWiki()
    return _wiki


def update_findings(category: str, content: str,
                    confidence: str = "medium", source: str = "") -> str:
    """Record a validated finding to the investigation wiki."""
    return get_wiki().update(category, content, confidence, source)


def read_wiki(category: str = "all") -> str:
    """Read current investigation findings from the wiki."""
    return get_wiki().read(category)
