"""
RCA Agent Runner — ReAct Loop with Wiki-Based Investigation
=============================================================
Implements Karpathy's wiki-compilation pattern inside a ReAct
(Reason + Act) agent loop. The LLM:

  1. OBSERVE — reads incident data, wiki state, BQ schemas
  2. THINK  — reasons about what happened, forms hypotheses
  3. ACT    — calls tools (BQ query, incident search, wiki update)
  4. REFLECT — evaluates results, decides if more investigation needed

The wiki (tools/wiki_tool.py) is the persistent accumulator — findings
compound across iterations instead of evaporating.

USAGE:
    # As standalone script
    python agent_runner.py --incident INC0012345 \\
                           --incidents-file ./my_reports/_all_incidents.json

    # As imported module
    from agent_runner import RCAAgentRunner
    runner = RCAAgentRunner(config)
    report = runner.investigate("INC0012345")
"""

from __future__ import annotations
import json
import logging
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from pydantic import ValidationError

from config import AgentConfig
from models import (
    AgentState, RCAReport, RCACheck,
    BQQueryInput, IncidentSearchInput, FindingInput, SchemaLookupInput,
)
from llm_providers import create_provider, LLMProvider, LLMResponse
from tools.bigquery_tool import init_executor, query_bigquery, lookup_schema
from tools.snow_tool import init_loader, get_loader, search_incident
from tools.wiki_tool import init_wiki, get_wiki, update_findings, read_wiki

logger = logging.getLogger(__name__)


# ── System Prompt — The "Schema" in Karpathy's pattern ──────────────────────

RCA_SYSTEM_PROMPT = """You are an RCA (Root Cause Analysis) investigator agent for L'Oréal's 
SPACE CDS (Consumer Data Services) platform. You investigate ServiceNow incidents 
by analyzing incident data and validating hypotheses against BigQuery.

## INVESTIGATION PROTOCOL (Karpathy Wiki Pattern)

You maintain an investigation wiki that accumulates findings. Follow this loop:

1. **OBSERVE**: Read the incident data thoroughly. Extract:
   - Timeline of events (when things happened)
   - Affected systems, users, order IDs, EAN codes, MARS IDs
   - Error messages and symptoms reported
   - What the team has already tried (from work notes)

2. **THINK**: Form 2-3 ranked hypotheses about the root cause.
   Common patterns in CDS:
   - Missing MARSID in user profile → orders can't be matched
   - EAN code mismatch between V14 and V21 → product lookup fails
   - Data pipeline delay → records not yet replicated
   - CBR item mapping missing → product not found in catalog

3. **ACT**: Use tools to validate each hypothesis:
   - `query_bigquery` → Run targeted validation queries
   - `search_incident` → Search comments/work notes for evidence
   - `update_findings` → Record validated findings to the wiki
   - `read_wiki` → Review accumulated findings before concluding
   - `lookup_schema` → Discover available BQ tables and columns

4. **REFLECT**: After each tool result, evaluate:
   - Does this confirm or refute my hypothesis?
   - What questions remain?
   - Do I have enough evidence to write the final report?

## QUERY GUIDELINES

- Only SELECT/WITH queries (read-only, enforced by the executor)
- Always use fully-qualified backtick table names: 
  `{bq_dataset}.table_name`
- Prefer targeted queries: COUNT, EXISTS, specific field lookups
- Always include LIMIT (max 100 rows)
- Use parameterized patterns for user-provided IDs
- If a query fails, analyze the error and fix the SQL

## OUTPUT FORMAT

When you have sufficient evidence, produce the final report with EXACTLY these sections:

### WHAT HAPPENED
One sentence. The symptom, not the cause.
e.g. "Order YSLMY0153902 not visible in Order DB for user C5MY79060411672."

### WHAT WE CHECKED
Bullet each system/action. One line per check with evidence.
e.g. "→ Checked Order DB — not found"
e.g. "→ Checked LOY — purchase records exist"

### WHAT WE FOUND
The conclusion from your checks. One or two sentences with evidence.
e.g. "MARSID is empty in profile. Without it, orders cannot be matched."

### WHAT WE NEED / DID
If resolved: what you did. If pending: who needs to do what, by when.
e.g. "CDS to confirm if MARSID was received at ingestion — by 28 Mar."

## RULES
- Cite specific data (row counts, timestamps, field values) — never guess
- If you can't find evidence, say so clearly
- Maximum 15 investigation steps, then produce the report
- Always call update_findings to record important discoveries
- Call read_wiki before writing the final report to review all findings
"""


# ── Tool Registry ────────────────────────────────────────────────────────────

# Unified tool schemas (provider-agnostic, converted per-provider)
TOOL_SCHEMAS = [
    {
        "name": "query_bigquery",
        "description": "Execute a read-only BigQuery query to validate a hypothesis. "
                       "Only SELECT/WITH allowed. Returns formatted results.",
        "parameters": BQQueryInput.model_json_schema(),
    },
    {
        "name": "search_incident",
        "description": "Search loaded ServiceNow incident data (description, comments, "
                       "work_notes, attachment OCR text) for a keyword.",
        "parameters": IncidentSearchInput.model_json_schema(),
    },
    {
        "name": "update_findings",
        "description": "Record a validated finding to the investigation wiki. "
                       "Categories: timeline, evidence, hypothesis, conclusion, action_item.",
        "parameters": FindingInput.model_json_schema(),
    },
    {
        "name": "read_wiki",
        "description": "Read current investigation wiki to review accumulated findings. "
                       "Use 'all' for everything or a specific category.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category to read: 'all', 'timeline', 'evidence', "
                                   "'hypothesis', 'conclusion', 'action_item'",
                    "default": "all",
                }
            },
        },
    },
    {
        "name": "lookup_schema",
        "description": "Look up BigQuery table schemas in the dataset. "
                       "Empty pattern lists all tables. Provide table name for columns.",
        "parameters": SchemaLookupInput.model_json_schema(),
    },
]

# Tool dispatch map
TOOL_FUNCTIONS = {
    "query_bigquery": lambda **kw: query_bigquery(**kw),
    "search_incident": lambda **kw: search_incident(**kw),
    "update_findings": lambda **kw: update_findings(**kw),
    "read_wiki": lambda **kw: read_wiki(**kw),
    "lookup_schema": lambda **kw: lookup_schema(**kw),
}


# ── Agent Runner ─────────────────────────────────────────────────────────────

class RCAAgentRunner:
    """
    Orchestrates the ReAct investigation loop.
    
    Decoupled from LLM provider — swap via config.llm.provider.
    Tools are pure functions, also usable via MCP server.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.provider: LLMProvider = create_provider(
            provider=config.llm.provider,
            model=config.llm.model,
            api_key=config.llm.api_key,
        )
        self.max_iterations = config.max_iterations

    def investigate(self, incident_number: str) -> RCAReport:
        """
        Run a full RCA investigation for a single incident.
        Returns a structured RCAReport.
        """
        loader = get_loader()
        wiki = get_wiki()

        # Get incident summary for context
        incident_summary = loader.get_incident_summary(incident_number)
        if "not found" in incident_summary:
            raise ValueError(f"Incident {incident_number} not found in loaded data")

        # Extract identifiers for BQ query hints
        identifiers = loader.extract_identifiers(incident_number)
        id_context = json.dumps(identifiers, indent=2) if identifiers else "None extracted"

        # Build the initial prompt
        bq_fq = f"`{self.config.bq.fully_qualified}`"
        system_prompt = RCA_SYSTEM_PROMPT.replace("{bq_dataset}", bq_fq)

        user_prompt = f"""Investigate this incident and produce an RCA report.

INCIDENT DATA:
{incident_summary}

EXTRACTED IDENTIFIERS (for BQ queries):
{id_context}

BIGQUERY DATASET: {bq_fq}

Start by using lookup_schema to discover available tables, then systematically
investigate the root cause. Record findings to the wiki as you go.
Begin your investigation."""

        # Initialize conversation
        state = AgentState()
        state.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        print(f"\n{'='*70}")
        print(f"  RCA INVESTIGATION: {incident_number}")
        print(f"  Provider: {self.config.llm.provider} / {self.config.llm.model}")
        print(f"  Max iterations: {self.max_iterations}")
        print(f"{'='*70}\n")

        # ── ReAct Loop ──────────────────────────
        final_content = ""

        for step in range(self.max_iterations):
            state.iteration = step + 1
            print(f"[Step {state.iteration}/{self.max_iterations}] Thinking...")

            try:
                response = self.provider.chat(
                    messages=state.messages,
                    tools=TOOL_SCHEMAS,
                    temperature=self.config.llm.temperature,
                    max_tokens=self.config.llm.max_tokens,
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                print(f"  [ERROR] LLM call failed: {e}")
                break

            # Append assistant response to history
            state.messages.append(
                self.provider.format_assistant_message(response)
            )

            # If there's text content, print a preview
            if response.content:
                preview = response.content[:150].replace("\n", " ")
                print(f"  [Think] {preview}...")
                final_content = response.content

            # If no tool calls, the LLM is done
            if not response.tool_calls:
                print(f"  [Done] Investigation complete at step {state.iteration}")
                break

            # Execute each tool call
            tool_results = []
            for tc in response.tool_calls:
                print(f"  [Act] {tc.name}({json.dumps(tc.arguments)[:100]})")

                fn = TOOL_FUNCTIONS.get(tc.name)
                if not fn:
                    result = f"Error: Unknown tool '{tc.name}'"
                else:
                    try:
                        result = fn(**tc.arguments)
                    except (ValidationError, TypeError) as e:
                        result = f"Validation error: {e}"
                    except Exception as e:
                        result = f"Tool error: {type(e).__name__}: {e}"

                # Log query executions for the report appendix
                if tc.name == "query_bigquery":
                    state.queries_executed.append({
                        "sql": tc.arguments.get("sql", ""),
                        "rationale": tc.arguments.get("rationale", ""),
                        "summary": result[:200],
                    })

                result_preview = result[:100].replace("\n", " ")
                print(f"  [Observe] → {result_preview}")

                # Append tool result in provider-specific format
                tool_msg = self.provider.format_tool_result(tc.id, result)
                state.messages.append(tool_msg)

        else:
            print(f"\n  [WARN] Hit max iterations ({self.max_iterations}). Forcing report.")
            # Ask LLM to produce report with what it has
            state.messages.append({
                "role": "user",
                "content": "You've reached the investigation limit. "
                           "Call read_wiki to review all findings, then produce "
                           "the final RCA report with what you have.",
            })
            try:
                response = self.provider.chat(
                    messages=state.messages,
                    tools=TOOL_SCHEMAS,
                    temperature=self.config.llm.temperature,
                    max_tokens=self.config.llm.max_tokens,
                )
                final_content = response.content
            except Exception:
                pass

        # ── Build structured report ──────────────
        inc = loader.get_incident(incident_number)
        inc_data = inc.get("incident", {}) if inc else {}

        report = RCAReport(
            incident_number=incident_number,
            incident_title=inc_data.get("short_description", ""),
            what_happened=self._extract_section(final_content, "WHAT HAPPENED"),
            what_we_found=self._extract_section(final_content, "WHAT WE FOUND"),
            what_we_need=self._extract_section(final_content, "WHAT WE NEED", "WHAT WE DID"),
            checks=self._extract_checks(final_content),
            queries_executed=state.queries_executed,
            raw_findings=wiki.get_structured(),
        )

        return report

    @staticmethod
    def _extract_section(text: str, *headers: str) -> str:
        """Extract content under a markdown header.

        Tolerates extra text on the header line (e.g. "### WHAT WE NEED / DID").
        """
        if not text:
            return ""
        for header in headers:
            # Match header prefix without requiring an immediate newline,
            # so "### WHAT WE NEED / DID\n" is found by "WHAT WE NEED".
            patterns = [
                f"## {header}",
                f"### {header}",
                f"**{header}**",
                f"{header}",
            ]
            for pat in patterns:
                idx = text.find(pat)
                if idx >= 0:
                    # Advance past the rest of the header line
                    eol = text.find("\n", idx)
                    start = (eol + 1) if eol >= 0 else (idx + len(pat))
                    # Find the next section header
                    next_header = len(text)
                    for marker in ["## ", "### ", "**WHAT"]:
                        pos = text.find(marker, start)
                        if pos > start:
                            next_header = min(next_header, pos)
                    return text[start:next_header].strip()
        return ""

    @staticmethod
    def _extract_checks(text: str) -> list[RCACheck]:
        """Extract check items from the WHAT WE CHECKED section."""
        import re
        checks = []
        section = RCAAgentRunner._extract_section(text, "WHAT WE CHECKED")
        if not section:
            return checks

        for line in section.splitlines():
            line = line.strip()
            if not line or not (line.startswith("→") or line.startswith("-") or line.startswith("*")):
                continue
            # Parse "→ Checked <system> — <result>"
            line = line.lstrip("→-* ").strip()
            match = re.match(r"(?:Checked\s+)?(.+?)\s*[—–-]\s*(.+)", line)
            if match:
                checks.append(RCACheck(
                    system=match.group(1).strip(),
                    action=f"Checked {match.group(1).strip()}",
                    result=match.group(2).strip(),
                ))
            else:
                checks.append(RCACheck(
                    system="General",
                    action=line[:60],
                    result=line,
                ))
        return checks


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RCA Agent — Investigate ServiceNow Incidents")
    parser.add_argument("--incident", type=str, required=True,
                        help="Incident number to investigate (e.g., INC0012345)")
    parser.add_argument("--incidents-file", type=str,
                        default="./my_reports/_all_incidents.json",
                        help="Path to _all_incidents.json from snow_story_reader.py")
    parser.add_argument("--ocr-file", type=str, default=None,
                        help="Path to _ocr_consolidated.json (auto-detected if omitted)")
    parser.add_argument("--provider", type=str, default=None,
                        help="LLM provider: anthropic, openai, google (overrides config)")
    parser.add_argument("--model", type=str, default=None,
                        help="LLM model name (overrides config)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file path for RCA report (.md)")
    parser.add_argument("--max-steps", type=int, default=None,
                        help="Max investigation iterations (default: 15)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Build config
    config = AgentConfig()
    if args.provider:
        config.llm.provider = args.provider
    if args.model:
        config.llm.model = args.model
    if args.max_steps:
        config.max_iterations = args.max_steps

    # Initialize tools
    print("[INIT] Loading incidents...")
    init_loader(args.incidents_file, args.ocr_file)

    print("[INIT] Initializing BigQuery executor...")
    init_executor(
        project=config.bq.project,
        dataset=config.bq.dataset,
        max_bytes=config.bq.max_bytes_billed,
        timeout=config.bq.timeout_seconds,
        max_rows=config.bq.max_rows,
    )

    print("[INIT] Initializing investigation wiki...")
    init_wiki(persist_dir=config.wiki_dir)

    # Run investigation
    runner = RCAAgentRunner(config)
    report = runner.investigate(args.incident)

    # Output
    md = report.to_markdown()
    print(f"\n{'='*70}")
    print(md)
    print(f"{'='*70}")

    # Save
    output_path = args.output or os.path.join(
        config.output_dir,
        f"RCA_{args.incident}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n[SAVED] {output_path}")

    # Also save JSON
    json_path = output_path.replace(".md", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)
    print(f"[SAVED] {json_path}")


if __name__ == "__main__":
    main()
