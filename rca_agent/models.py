"""
RCA Agent — Data Models
=======================
Pydantic models for tool I/O, agent state, and the final RCA report.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Tool Input Models ────────────────────────────────────────────────────────

class BQQueryInput(BaseModel):
    """Input for the BigQuery validation tool."""
    sql: str = Field(..., description="Read-only SQL query (SELECT/WITH only). "
                     "Use fully-qualified backtick table names.")
    rationale: str = Field(..., description="Why this query helps the investigation — "
                          "what hypothesis are you validating?")


class IncidentSearchInput(BaseModel):
    """Input for searching within loaded incident data."""
    keyword: str = Field(..., description="Search term to look for")
    section: str = Field("all", description="Where to search: "
                        "'comments', 'work_notes', 'description', 'attachments_ocr', or 'all'")


class FindingInput(BaseModel):
    """Input for recording a validated finding."""
    category: str = Field(..., description="One of: 'timeline', 'evidence', "
                         "'hypothesis', 'conclusion', 'action_item'")
    content: str = Field(..., description="The finding text")
    confidence: str = Field("medium", description="'high', 'medium', or 'low'")
    source: str = Field("", description="Where this finding came from "
                       "(e.g., 'BQ query', 'work_note #3', 'attachment OCR')")


class SchemaLookupInput(BaseModel):
    """Input for looking up BigQuery table schemas."""
    table_pattern: str = Field("", description="Table name or pattern to search for. "
                              "Leave empty to list all tables in the dataset.")


# ── Agent State ──────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    """Persistent state across the ReAct loop iterations."""
    messages: list[dict] = field(default_factory=list)
    iteration: int = 0
    findings: dict[str, list[str]] = field(default_factory=lambda: {
        "timeline": [],
        "evidence": [],
        "hypothesis": [],
        "conclusion": [],
        "action_item": [],
    })
    queries_executed: list[dict] = field(default_factory=list)
    done: bool = False


# ── RCA Report ───────────────────────────────────────────────────────────────

class RCACheck(BaseModel):
    """A single check performed during investigation."""
    system: str = Field(..., description="System checked (e.g., 'Order DB', 'LOY', 'BigQuery')")
    action: str = Field(..., description="What was checked")
    result: str = Field(..., description="What was found")
    evidence: str = Field("", description="Query, screenshot ref, or data snippet")


class RCAReport(BaseModel):
    """Structured RCA report matching the required format."""
    incident_number: str = ""
    incident_title: str = ""
    investigated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # ── WHAT HAPPENED ──
    what_happened: str = Field("", description="One sentence. The symptom, not the cause.")

    # ── WHAT WE CHECKED ──
    checks: list[RCACheck] = Field(default_factory=list,
        description="Bullet each system/action. One line per check with evidence.")

    # ── WHAT WE FOUND ──
    what_we_found: str = Field("", description="The conclusion from checks. "
                               "One or two sentences with evidence.")

    # ── WHAT WE NEED / DID ──
    what_we_need: str = Field("", description="If resolved: what was done. "
                              "If pending: who needs to do what, by when.")

    # ── Raw data for traceability ──
    queries_executed: list[dict] = Field(default_factory=list)
    raw_findings: dict = Field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [
            f"# RCA Report: {self.incident_number}",
            f"**{self.incident_title}**",
            f"*Investigated: {self.investigated_at}*",
            "",
            "---",
            "",
            "## WHAT HAPPENED",
            self.what_happened,
            "",
            "## WHAT WE CHECKED",
        ]
        for c in self.checks:
            ev = f" — *{c.evidence}*" if c.evidence else ""
            lines.append(f"→ Checked **{c.system}** — {c.result}{ev}")
        lines.extend([
            "",
            "## WHAT WE FOUND",
            self.what_we_found,
            "",
            "## WHAT WE NEED / DID",
            self.what_we_need,
        ])

        if self.queries_executed:
            lines.extend(["", "---", "", "### Appendix: Queries Executed"])
            for i, q in enumerate(self.queries_executed, 1):
                lines.append(f"\n**Query {i}** — {q.get('rationale', 'N/A')}")
                lines.append(f"```sql\n{q.get('sql', '')}\n```")
                lines.append(f"Result: {q.get('summary', 'N/A')}")

        return "\n".join(lines)
