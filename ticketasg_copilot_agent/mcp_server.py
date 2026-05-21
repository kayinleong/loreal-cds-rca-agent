"""
Ticket Assignment Copilot MCP Server
======================================
Exposes ServiceNow tools + assignment routing via Model Context Protocol (MCP).
GitHub Copilot (or any MCP client) calls these tools; the LLM reasoning stays
entirely inside Copilot — this server contains NO LLM calls.

ServiceNow tools:
  fetch_incidents      — Download all incidents from a ServiceNow list URL
  get_incident         — Fetch a single incident by number (live from SNOW)
  get_incident_summary — Get full formatted text of a loaded incident
  list_incidents       — List all locally stored incidents
  analyze_incident     — ONE-STOP: fetch + identifiers + attachments for one incident
  search_incidents     — Search incident text for a keyword
  post_comment         — Post a comment (or work note) to an incident
  extract_identifiers  — Pull structured identifiers (LUCID, Mars ID, orders, EAN) from a cached incident
  download_attachments — Download all attachments for an incident (screenshots are evidence)

BigQuery tools (RCA-parity with rca_copilot_agent):
  query_bigquery       — Read-only SELECT/WITH against SPACE CDS dataset
  get_schema           — Table schema + ready-to-use query patterns from local schema.json
  list_bq_tables       — List all tables in the SPACE CDS dataset

Assignment tools:
  get_assignment_rules     — Show the routing matrix (10 groups + keywords + hard rules + L3 escalation)
  recommend_assignment     — Legacy v1 keyword-only path (kept for back-compat)
  recommend_assignment_v2  — Hybrid: hard rules + keyword + kNN retrieval + L3 escalation
  find_similar_incidents   — kNN nearest-neighbour retrieval over local corpus
  build_retrieval_index    — Rebuild sentence-transformers index after fetch_incidents
  save_assignment_report   — Save a completed RCA + reassignment report to disk
  send_assignment_email    — Send HTML email notification when analysis is complete

USAGE:
    python mcp_server.py

    # Override reports directory
    python mcp_server.py --reports-dir ./my_reports

ENVIRONMENT (via .env or shell):
    COOKIE              Full Cookie header from an active ServiceNow session
    X_USERTOKEN         X-UserToken CSRF token from the same session
    SNOW_INSTANCE       ServiceNow base URL (default: https://loreal.service-now.com)
    REPORTS_DIR         Directory for downloaded JSON
    ATTACHMENTS_DIR     Directory for downloaded attachments
    ASSIGNMENT_RULES_FILE  Path to assignment_rules.json (default: <pkg_dir>/assignment_rules.json)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Allow running as `python ticketasg_copilot_agent/mcp_server.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _build_reader():
    """Instantiate and authenticate a ServiceNowReader from config."""
    from config import load_config
    from tools.snow_reader import ServiceNowReader

    cfg = load_config()
    if not cfg.cookie or not cfg.x_user_token:
        raise RuntimeError(
            "COOKIE and X_USERTOKEN must be set in .env or environment. "
            "See .env.example for instructions."
        )

    reader = ServiceNowReader(instance_url=cfg.instance_url)
    reader.authenticate(cookie=cfg.cookie, x_user_token=cfg.x_user_token)
    return reader, cfg


def _auto_load_store(reports_dir: str) -> int:
    """Load the incident store from _all_incidents.json if it exists."""
    combined = os.path.join(reports_dir, "_all_incidents.json")
    if os.path.exists(combined):
        from tools.incident_store import load_store
        count = load_store(combined)
        logger.info(f"[MCP] Auto-loaded {count} incidents from {combined}")
        return count
    return 0


# ── MCP server (using mcp SDK) ────────────────────────────────────────────────

def create_mcp_server(reports_dir: str):
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    server = Server("ticketasg-copilot")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="fetch_incidents",
                description=(
                    "Download all incidents from a ServiceNow list-view URL and save them "
                    "locally as JSON files. Must be called before get_incident_summary or "
                    "search_incidents if local data does not exist. "
                    "Returns a summary of how many incidents were fetched."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "list_url": {
                            "type": "string",
                            "description": (
                                "Full ServiceNow list-view URL. "
                                "Supports /now/nav/ui/classic/... navigation URLs and "
                                "sysparm_tiny short links."
                            ),
                        },
                        "download_attachments": {
                            "type": "boolean",
                            "description": "Also download attachment files to disk (default: false)",
                            "default": False,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max number of incidents to process (default: 500)",
                            "default": 500,
                        },
                    },
                    "required": ["list_url"],
                },
            ),
            Tool(
                name="get_incident",
                description=(
                    "Fetch a single incident live from ServiceNow by its display number "
                    "(e.g., INC10403788). Saves to local reports and reloads the store. "
                    "Use when the incident is not in local data or when you need the latest."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                        "download_attachments": {
                            "type": "boolean",
                            "description": "Also download attachment files (default: false)",
                            "default": False,
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
            Tool(
                name="get_incident_summary",
                description=(
                    "Get the complete text of a specific incident from local data, including "
                    "description, all comments, work notes, attachment names, and related stories. "
                    "Pass this text to your assignment analysis. "
                    "Call fetch_incidents first if the incident is not yet available locally."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
            Tool(
                name="list_incidents",
                description=(
                    "List all incidents currently stored locally, with number, state, "
                    "priority, and title. Use to discover what is available before calling "
                    "get_incident_summary."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "max_count": {
                            "type": "integer",
                            "description": "Maximum incidents to list (default: 100)",
                            "default": 100,
                        },
                    },
                },
            ),
            Tool(
                name="analyze_incident",
                description=(
                    "ONE-STOP analysis tool for a single incident. "
                    "Fetches full incident data, extracts structured identifiers (LUCID, Mars ID, "
                    "orders, EAN), and downloads any attachments (screenshots ARE evidence per the "
                    "CDS Incident Handling Guidebook, Section 8). Returns the complete context "
                    "needed for both RCA investigation and assignment analysis. "
                    "ALWAYS use this as the first step — do NOT call get_incident_summary, "
                    "extract_identifiers, or download_attachments separately."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
            Tool(
                name="search_incidents",
                description=(
                    "Search all locally stored incident text for a keyword. "
                    "Returns matching snippets from description, comments, or work notes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Search term (case-insensitive)",
                        },
                        "section": {
                            "type": "string",
                            "description": "Where to search: 'description', 'comments', 'work_notes', or 'all'",
                            "default": "all",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Cap on returned matches (default: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["keyword"],
                },
            ),
            Tool(
                name="post_comment",
                description=(
                    "Post a comment or work note to a ServiceNow incident. "
                    "Use this to post the assignment recommendation back to the ticket. "
                    "The comment is posted live to ServiceNow — confirm with the user before calling."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                        "text": {
                            "type": "string",
                            "description": "Comment body (plain text)",
                        },
                        "as_work_note": {
                            "type": "boolean",
                            "description": (
                                "True → post as internal work note (not visible to customer); "
                                "False → post as customer-visible comment (default: false)"
                            ),
                            "default": False,
                        },
                    },
                    "required": ["incident_number", "text"],
                },
            ),
            Tool(
                name="get_assignment_rules",
                description=(
                    "Return the full L2 assignment routing matrix — all 10 groups with their "
                    "keyword lists and descriptions. Read this before calling recommend_assignment "
                    "to understand the routing logic. "
                    "[USER-CONFIRM] Keywords are inferred — verify against SharePoint matrix."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="recommend_assignment",
                description=(
                    "Score incident text against the L2 assignment routing rules and return "
                    "the recommended assignment group with confidence score and reason. "
                    "Returns: recommended_group, confidence (0.0-1.0), reason, alternatives (top 3), "
                    "reassignment_needed, reassignment_reason. "
                    "If reassignment_needed is True, include reassignment_reason in your RCA report."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number (for logging), e.g. INC10403788",
                        },
                        "short_description": {
                            "type": "string",
                            "description": "Incident short description",
                        },
                        "description": {
                            "type": "string",
                            "description": "Full incident description",
                        },
                        "category": {
                            "type": "string",
                            "description": "Incident category (optional)",
                            "default": "",
                        },
                        "subcategory": {
                            "type": "string",
                            "description": "Incident subcategory (optional)",
                            "default": "",
                        },
                        "comments_text": {
                            "type": "string",
                            "description": "All comments and work notes concatenated (optional)",
                            "default": "",
                        },
                        "current_group": {
                            "type": "string",
                            "description": "Current assignment group (used to detect reassignment need)",
                            "default": "",
                        },
                    },
                    "required": ["incident_number", "short_description", "description"],
                },
            ),
            Tool(
                name="recommend_assignment_v2",
                description=(
                    "Hybrid recommender combining (1) hard-rules regex shortcuts, "
                    "(2) keyword scoring (the v1 path), (3) sentence-transformers kNN retrieval "
                    "over the local incident corpus, and (4) L2 → L3 escalation when PRB / "
                    "data-patch / L3 signals are present. Returns a deterministic "
                    "`recommended_group` plus all three individual signals in `signals` so the "
                    "LLM client can override the combined answer when it has reason to. "
                    "Source field tells you which signal won: "
                    "'hard_rule' | 'l3_escalation' | 'retrieval+keyword' | 'retrieval_top1' | 'keyword'."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {"type": "string"},
                        "short_description": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string", "default": ""},
                        "subcategory": {"type": "string", "default": ""},
                        "comments_text": {"type": "string", "default": ""},
                        "work_notes_text": {"type": "string", "default": ""},
                        "current_group": {"type": "string", "default": ""},
                        "retrieval_index_path": {"type": "string", "default": ""},
                        "retrieval_top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["incident_number", "short_description", "description"],
                },
            ),
            Tool(
                name="find_similar_incidents",
                description=(
                    "kNN nearest-neighbour retrieval over the local incident corpus. "
                    "Given a query_text (or a locally-cached incident_number), returns the top_k "
                    "most semantically-similar incidents and their current assignment groups, "
                    "plus a sum-of-scores tally per group. Useful as a second-opinion signal "
                    "when keyword scoring is ambiguous, and especially for L3 routing where "
                    "the static rules schema cannot represent every L3 group."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_text": {
                            "type": "string",
                            "description": "Free-form text to search by. Either this OR incident_number must be supplied.",
                        },
                        "incident_number": {
                            "type": "string",
                            "description": "Look up a locally-cached incident and use its summary as the query. Excluded from neighbours.",
                        },
                        "top_k": {"type": "integer", "default": 5},
                        "retrieval_index_path": {"type": "string", "default": ""},
                    },
                },
            ),
            Tool(
                name="build_retrieval_index",
                description=(
                    "Build (or rebuild) the sentence-transformers retrieval index from "
                    "_all_incidents.json. Run this once after a fetch_incidents to refresh the "
                    "kNN corpus used by recommend_assignment_v2 and find_similar_incidents."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incidents_json_path": {"type": "string", "default": ""},
                        "retrieval_index_path": {"type": "string", "default": ""},
                    },
                },
            ),
            Tool(
                name="extract_identifiers",
                description=(
                    "Extract structured identifiers (LUCID, Mars ID, order numbers, EAN codes, "
                    "emails, customercodes) from a locally-cached incident's text. Use to obtain "
                    "the exact values to feed into BigQuery queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
            Tool(
                name="download_attachments",
                description=(
                    "Download all attachments for a specific incident to the local attachments directory. "
                    "Call this after analyze_incident when screenshots or files are referenced — "
                    "the CDS Incident Handling Guidebook (Section 8) treats screenshots as evidence "
                    "and requires mandatory fields (LUCID, country, source datetime, External System ID "
                    "status, Source Consumer Key) to be visible. Returns the list of downloaded file paths."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
            Tool(
                name="query_bigquery",
                description=(
                    "Execute a read-only SELECT or WITH query against the SPACE CDS BigQuery dataset. "
                    "Use to verify the migrated-vs-ongoing question and to validate routing hypotheses "
                    "with data: confirm the consumer is in CONSUMER_PII_TBL, check EXTERNAL_SYSTEM_IDS_TBL "
                    "for Mars ID + status, look up orders in PURCHASE_TBL, etc. Blocked from INSERT/UPDATE/"
                    "DELETE/DROP. Always add a LIMIT clause. Use backticks for table refs: "
                    "`oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public.table_name`. "
                    "Call get_schema first to confirm column names."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "GoogleSQL SELECT or WITH query. Must include LIMIT.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "One sentence explaining what you are looking for (for audit logs).",
                        },
                    },
                    "required": ["sql"],
                },
            ),
            Tool(
                name="get_schema",
                description=(
                    "Get schema info for a BigQuery table from local schema.json, or list all tables "
                    "when no table name is given. Returns column names, types, relationships, and "
                    "ready-to-use query patterns. Faster than a live BQ call — always use this before "
                    "writing a query to confirm column names."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": (
                                "Exact table name (e.g. 'consumer_pii') or a partial substring to "
                                "search. Leave empty to list all tables in the dataset."
                            ),
                            "default": "",
                        },
                    },
                },
            ),
            Tool(
                name="list_bq_tables",
                description=(
                    "List all tables in the SPACE CDS BigQuery dataset with their RCA purpose. "
                    "Reads from local schema.json — instant, no BQ cost. "
                    "Use to discover which table to query before calling get_schema."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="save_assignment_report",
                description=(
                    "Save a completed assignment analysis report to the local reports directory. "
                    "ALWAYS call this after generating the assignment analysis. "
                    "The saved path is tracked for send_assignment_email. "
                    "Returns the path where the report was saved."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number, e.g. INC10403788",
                        },
                        "report_text": {
                            "type": "string",
                            "description": "The complete assignment analysis report text",
                        },
                    },
                    "required": ["incident_number", "report_text"],
                },
            ),
            Tool(
                name="send_assignment_email",
                description=(
                    "Send an HTML email to notify the human reviewer that assignment analysis is complete. "
                    "Call this AFTER all save_assignment_report calls for the session are done. "
                    "Automatically attaches all report files saved in this session. "
                    "Requires SMTP settings in .env (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, "
                    "SMTP_FROM, SMTP_TO). Returns success/failure message."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_summary": {
                            "type": "string",
                            "description": (
                                "Plain-text summary of what was analysed this session — "
                                "which incidents were reviewed and assignment recommendations made."
                            ),
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line.",
                            "default": "Ticket Assignment Analysis Complete — Please Review",
                        },
                    },
                    "required": ["session_summary"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = await _dispatch(name, arguments, reports_dir)
        except Exception as exc:
            result = f"Tool error ({name}): {type(exc).__name__}: {exc}"
            logger.error(result)

        return [TextContent(type="text", text=str(result))]

    return server


async def _dispatch(name: str, arguments: dict, reports_dir: str) -> str:
    """Route tool calls to their implementations."""

    if name == "fetch_incidents":
        reader, _ = _build_reader()
        list_url = arguments["list_url"]
        download = arguments.get("download_attachments", False)
        limit = arguments.get("limit", 500)

        reports, combined_path = reader.fetch_incidents_from_list(
            list_url=list_url,
            output_dir=reports_dir,
            download_files=download,
            limit=limit,
        )

        if combined_path and os.path.exists(combined_path):
            from tools.incident_store import load_store
            load_store(combined_path)

        return (
            f"Fetched {len(reports)} incident(s) from ServiceNow.\n"
            f"Saved to: {combined_path}\n"
            f"Run get_incident_summary or list_incidents to inspect the data."
        )

    elif name == "get_incident":
        reader, cfg = _build_reader()
        number = arguments["incident_number"]
        download = arguments.get("download_attachments", False)

        if number.upper().startswith("RITM"):
            table = "sc_req_item"
        elif number.upper().startswith("TASK"):
            table = "sc_task"
        else:
            table = "incident"

        records = reader.search_records(
            table=table,
            query=f"number={number}",
            limit=1,
            fields="sys_id,number,short_description,state",
        )
        rec = records[0] if records else None
        if not rec:
            return f"Incident {number} not found in ServiceNow (searched table: {table})."

        sys_id = rec["sys_id"]
        report = reader.get_full_incident_report(
            sys_id=sys_id,
            table_name=table,
            download_files=download,
            attachments_dir=cfg.attachments_dir,
        )
        reader.upsert_incident_report(report, reports_dir=reports_dir)

        combined = os.path.join(reports_dir, "_all_incidents.json")
        if os.path.exists(combined):
            from tools.incident_store import load_store
            load_store(combined)

        i = report["incident"]
        return (
            f"Fetched {i.get('number')} — {i.get('short_description')}\n"
            f"State: {i.get('state')}, Priority: {i.get('priority')}\n"
            f"Assignment Group: {i.get('assignment_group', 'N/A')}\n"
            f"Comments: {len(report.get('comments', []))}, "
            f"Work notes: {len(report.get('work_notes', []))}\n"
            f"Run analyze_incident for full assignment analysis."
        )

    elif name == "get_incident_summary":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        return get_store().get_incident_summary(arguments["incident_number"])

    elif name == "list_incidents":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        return get_store().list_all(max_incidents=arguments.get("max_count", 100))

    elif name == "analyze_incident":
        number = arguments["incident_number"]
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        store = get_store()

        inc = store.get_incident(number)
        if not inc:
            try:
                reader, cfg = _build_reader()
                if number.upper().startswith("RITM"):
                    table = "sc_req_item"
                elif number.upper().startswith("TASK"):
                    table = "sc_task"
                else:
                    table = "incident"

                records = reader.search_records(
                    table=table,
                    query=f"number={number}",
                    limit=1,
                    fields="sys_id,number,short_description,state",
                )
                rec = records[0] if records else None
                if rec:
                    report = reader.get_full_incident_report(
                        sys_id=rec["sys_id"],
                        table_name=table,
                        download_files=False,
                        attachments_dir=cfg.attachments_dir,
                    )
                    reader.upsert_incident_report(report, reports_dir=reports_dir)
                    combined = os.path.join(reports_dir, "_all_incidents.json")
                    if os.path.exists(combined):
                        from tools.incident_store import load_store
                        load_store(combined)
                    store = get_store()
            except Exception as e:
                return f"Could not fetch {number} from ServiceNow: {e}. Call fetch_incidents first."

        summary = store.get_incident_summary(number)

        ids = store.extract_identifiers(number)
        ids_section = (
            f"IDENTIFIERS FOUND:\n{json.dumps(ids, indent=2)}"
            if ids
            else "IDENTIFIERS: None found (no order IDs, LUCID, Mars ID, emails, or EAN codes)."
        )

        attachment_section = "ATTACHMENTS: None."
        inc = store.get_incident(number)
        if inc:
            att = inc.get("attachments", {})
            total = len(att.get("images", [])) + len(att.get("files", []))
            if total > 0:
                attachment_section = await _dispatch(
                    "download_attachments", {"incident_number": number}, reports_dir
                )

        return "\n\n".join([summary, ids_section, attachment_section])

    elif name == "search_incidents":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        results = get_store().search(
            keyword=arguments["keyword"],
            section=arguments.get("section", "all"),
            max_results=arguments.get("max_results", 20),
        )
        if not results:
            return f"No matches for '{arguments['keyword']}'."
        lines = [f"Found {len(results)} match(es) for '{arguments['keyword']}':"]
        for r in results:
            lines.append(f"\n  [{r['incident']}] {r['section']}:")
            lines.append(f"  {r['snippet']}")
        return "\n".join(lines)

    elif name == "post_comment":
        reader, _cfg = _build_reader()
        number = arguments["incident_number"]
        text = arguments["text"]
        as_work_note = arguments.get("as_work_note", False)

        if number.upper().startswith("RITM"):
            table = "sc_req_item"
        elif number.upper().startswith("TASK"):
            table = "sc_task"
        else:
            table = "incident"

        sys_id = _resolve_sys_id(number, reader, reports_dir, table=table)
        if not sys_id:
            return f"Cannot resolve sys_id for {number}. Fetch the incident first."

        success = reader.post_comment(
            incident_sys_id=sys_id,
            text=text,
            as_work_note=as_work_note,
            table=table,
        )
        label = "work note" if as_work_note else "comment"
        if success:
            return f"✓ Posted {label} to {number}."
        return f"✗ Failed to post {label} to {number}. Check logs."

    elif name == "get_assignment_rules":
        from tools.assignment_tool import get_assignment_rules
        return get_assignment_rules()

    elif name == "recommend_assignment":
        from tools.assignment_tool import recommend_assignment
        result = recommend_assignment(
            incident_number=arguments["incident_number"],
            short_description=arguments["short_description"],
            description=arguments["description"],
            category=arguments.get("category", ""),
            subcategory=arguments.get("subcategory", ""),
            comments_text=arguments.get("comments_text", ""),
            work_notes_text=arguments.get("work_notes_text", ""),
            current_group=arguments.get("current_group", ""),
        )
        return json.dumps(result, indent=2)

    elif name == "recommend_assignment_v2":
        from tools.assignment_tool import recommend_assignment_v2
        result = recommend_assignment_v2(
            incident_number=arguments["incident_number"],
            short_description=arguments["short_description"],
            description=arguments["description"],
            category=arguments.get("category", ""),
            subcategory=arguments.get("subcategory", ""),
            comments_text=arguments.get("comments_text", ""),
            work_notes_text=arguments.get("work_notes_text", ""),
            current_group=arguments.get("current_group", ""),
            retrieval_index_path=arguments.get("retrieval_index_path", ""),
            retrieval_top_k=int(arguments.get("retrieval_top_k", 5)),
        )
        return json.dumps(result, indent=2)

    elif name == "find_similar_incidents":
        from tools import retrieval_tool
        from pathlib import Path as _P
        idx_path = arguments.get("retrieval_index_path") or str(
            _P(__file__).resolve().parent / "retrieval_index.npz"
        )
        query_text = arguments.get("query_text") or ""
        if not query_text and arguments.get("incident_number"):
            # If only an incident number given, pull its text from the local store
            from tools.incident_store import get_summary
            try:
                query_text = get_summary(arguments["incident_number"]) or ""
            except Exception:
                query_text = ""
        if not query_text:
            return json.dumps({"error": "Provide query_text or a locally-cached incident_number."})
        top_k = int(arguments.get("top_k", 5))
        try:
            neighbours = retrieval_tool.find_similar(
                query_text=query_text,
                top_k=top_k,
                index_path=idx_path,
                exclude_number=arguments.get("incident_number", ""),
            )
        except FileNotFoundError as exc:
            return json.dumps({"error": str(exc), "hint": "Build the index with build_retrieval_index first."})
        return json.dumps({
            "neighbours": [
                {"number": n["number"], "group": n["group"], "score": round(n["score"], 3)}
                for n in neighbours
            ],
            "weighted_vote": {
                k: round(v, 3) for k, v in retrieval_tool.vote_group(neighbours, mode="weighted")[2].items()
            },
        }, indent=2)

    elif name == "build_retrieval_index":
        from tools import retrieval_tool
        from pathlib import Path as _P
        idx_path = arguments.get("retrieval_index_path") or str(
            _P(__file__).resolve().parent / "retrieval_index.npz"
        )
        incidents_json = arguments.get("incidents_json_path") or os.path.join(
            reports_dir, "_all_incidents.json"
        )
        info = retrieval_tool.build_index(
            incidents_json_path=incidents_json,
            index_path=idx_path,
        )
        return json.dumps(info, indent=2)

    elif name == "extract_identifiers":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        ids = get_store().extract_identifiers(arguments["incident_number"])
        if not ids:
            return f"No structured identifiers found in {arguments['incident_number']}."
        return json.dumps(ids, indent=2)

    elif name == "download_attachments":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        number = arguments["incident_number"]
        inc = get_store().get_incident(number)
        if not inc:
            return f"Incident {number} not found locally. Fetch it first with get_incident."

        incident_meta = inc.get("incident", {})
        sys_id = incident_meta.get("sys_id", "")
        if not sys_id:
            return f"Cannot determine sys_id for {number}."

        if number.upper().startswith("RITM"):
            att_table = "sc_req_item"
        elif number.upper().startswith("TASK"):
            att_table = "sc_task"
        else:
            att_table = "incident"

        reader, cfg = _build_reader()
        safe_number = number.replace("/", "_").replace("\\", "_")
        save_dir = os.path.join(cfg.attachments_dir, safe_number)
        paths = reader.download_all_attachments(att_table, sys_id, save_dir)

        if not paths:
            att = inc.get("attachments", {})
            total = len(att.get("images", [])) + len(att.get("files", []))
            if total == 0:
                return f"No attachments found for {number}."
            return f"Attachment metadata shows {total} file(s) but none could be downloaded. Check credentials."

        lines = [f"Downloaded {len(paths)} attachment(s) for {number} → {save_dir}"]
        for p in paths:
            lines.append(f"  {os.path.basename(p)}")
        return "\n".join(lines)

    elif name == "query_bigquery":
        from tools.bigquery_tool import is_enabled, query_bigquery as bq_query, _BQ_UNAVAILABLE
        if not is_enabled():
            return _BQ_UNAVAILABLE
        return bq_query(
            sql=arguments["sql"],
            rationale=arguments.get("rationale", ""),
        )

    elif name == "get_schema":
        from tools.bigquery_tool import get_schema_from_file
        return get_schema_from_file(arguments.get("table_name", ""))

    elif name == "list_bq_tables":
        from tools.bigquery_tool import get_schema_from_file
        return get_schema_from_file("")

    elif name == "save_assignment_report":
        number = arguments["incident_number"]
        report_text = arguments["report_text"]
        safe_number = number.replace("/", "_").replace("\\", "_")

        report_dir = os.path.join(reports_dir, "assignment_reports")
        os.makedirs(report_dir, exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_number}_assignment_{timestamp}.md"
        filepath = os.path.join(report_dir, filename)

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(f"# Assignment Analysis Report — {number}\n\n")
            fh.write(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n")
            fh.write(report_text)

        from tools.email_tool import register_report
        register_report(filepath)

        return f"✓ Assignment report saved: {filepath}"

    elif name == "send_assignment_email":
        from config import load_smtp_config
        smtp = load_smtp_config()
        if not smtp.enabled:
            return (
                "✗ SMTP not configured. Set SMTP_HOST, SMTP_FROM, and SMTP_TO in .env "
                "to enable email notifications."
            )

        from tools.email_tool import send_rca_email as _send
        subject = arguments.get("subject", "Ticket Assignment Analysis Complete — Please Review")
        session_summary = arguments["session_summary"]

        return _send(
            smtp_host=smtp.host,
            smtp_port=smtp.port,
            smtp_user=smtp.user,
            smtp_password=smtp.password,
            smtp_from=smtp.from_addr,
            smtp_to=smtp.to_addrs,
            use_tls=smtp.use_tls,
            subject=subject,
            session_summary=session_summary,
            verify_ssl=smtp.verify_ssl,
        )

    else:
        return f"Unknown tool: {name}"


def _ensure_store_loaded(reports_dir: str) -> None:
    """Load the incident store if it is empty."""
    from tools.incident_store import get_store
    store = get_store()
    if not store.incidents:
        combined = os.path.join(reports_dir, "_all_incidents.json")
        if os.path.exists(combined):
            from tools.incident_store import load_store
            count = load_store(combined)
            logger.info(f"[MCP] Loaded {count} incidents from {combined}")
        else:
            logger.warning(
                f"[MCP] No incidents file at {combined}. "
                "Call fetch_incidents first."
            )


def _resolve_sys_id(number: str, reader, reports_dir: str, table: str = "incident") -> str:
    """Resolve incident number to sys_id via local store or live SNOW lookup."""
    from tools.incident_store import get_store
    inc = get_store().get_incident(number)
    if inc:
        return inc.get("incident", {}).get("sys_id", "")

    records = reader.search_records(
        table=table,
        query=f"number={number}",
        limit=1,
        fields="sys_id,number,short_description,state",
    )
    return records[0].get("sys_id", "") if records else ""


def _run_jsonrpc_fallback(reports_dir: str) -> None:
    """Minimal JSON-RPC 2.0 server for environments without the mcp SDK."""
    import asyncio
    print("[MCP] Running JSON-RPC fallback (mcp SDK not installed)", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = {}
        try:
            req = json.loads(line)
            method = req.get("method", "")
            params = req.get("params", {})

            if method == "tools/list":
                result = {"tools": [
                    {"name": t, "description": f"ticketasg tool: {t}"}
                    for t in [
                        "fetch_incidents", "get_incident", "get_incident_summary",
                        "list_incidents", "analyze_incident", "search_incidents", "post_comment",
                        "extract_identifiers", "download_attachments",
                        "query_bigquery", "get_schema", "list_bq_tables",
                        "get_assignment_rules", "recommend_assignment", "recommend_assignment_v2",
                        "find_similar_incidents", "build_retrieval_index",
                        "save_assignment_report", "send_assignment_email",
                    ]
                ]}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                text = asyncio.run(_dispatch(tool_name, tool_args, reports_dir))
                result = {"content": [{"type": "text", "text": text}]}
            else:
                result = {"error": f"Unknown method: {method}"}

            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": result}), flush=True)

        except Exception as exc:
            print(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "error": {"code": -1, "message": str(exc)},
                }),
                flush=True,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ticket Assignment Copilot MCP Server")
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=None,
        help="Directory for incident JSON files (overrides REPORTS_DIR env var)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    from config import load_config
    cfg = load_config()
    reports_dir = args.reports_dir or cfg.reports_dir
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cfg.attachments_dir, exist_ok=True)

    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except Exception as bq_err:
        logger.warning(f"[BQ] Not available: {bq_err}")

    _auto_load_store(reports_dir)

    try:
        from tools.auth_tool import ensure_credentials
        ensure_credentials(instance_url=cfg.instance_url)
    except Exception as auth_err:
        logger.warning(f"[AUTH] Credential check failed: {type(auth_err).__name__}: {auth_err}")

    try:
        from tools.gcloud_tool import ensure_gcloud_auth
        ensure_gcloud_auth()
    except Exception as gcloud_err:
        logger.warning(f"[GCLOUD] Auth check failed: {type(gcloud_err).__name__}: {gcloud_err}")

    try:
        import mcp  # noqa: F401
        import asyncio
        from mcp.server.stdio import stdio_server
        from mcp.server.models import InitializationOptions
        from mcp.server.lowlevel.server import NotificationOptions

        server = create_mcp_server(reports_dir)

        init_options = InitializationOptions(
            server_name="ticketasg-copilot",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

        async def run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, init_options)

        logger.info(f"[MCP] Starting ticketasg-copilot server. Reports dir: {reports_dir}")
        asyncio.run(run())

    except ImportError:
        logger.warning("[MCP] mcp SDK not installed. Running JSON-RPC fallback.")
        _run_jsonrpc_fallback(reports_dir)


if __name__ == "__main__":
    main()
