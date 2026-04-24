"""
RCA Copilot MCP Server
=======================
Exposes ServiceNow + BigQuery tools via Model Context Protocol (MCP).
GitHub Copilot (or any MCP client) calls these tools; the LLM reasoning stays
entirely inside Copilot — this server contains NO LLM calls.

ServiceNow tools:
  fetch_incidents      — Download all incidents from a ServiceNow list URL
  get_incident         — Fetch a single incident by number (live from SNOW)
  get_incident_summary — Get full formatted text of a loaded incident
  list_incidents       — List all locally stored incidents
  search_incidents     — Search incident text for a keyword
  post_comment         — Post a comment (or work note) to an incident
  extract_identifiers  — Extract order IDs, emails, EAN codes from incident text

BigQuery tools (enabled when BQ_PROJECT is set):
  query_bigquery       — Execute a read-only SELECT query
  get_schema           — Get table schema or list all tables in the dataset
  list_bq_tables       — List all tables with row counts and sizes

USAGE:
    python mcp_server.py

    # Override reports directory
    python mcp_server.py --reports-dir ./my_reports

ENVIRONMENT (via .env or shell):
    COOKIE          Full Cookie header from an active ServiceNow session
    X_USERTOKEN     X-UserToken CSRF token from the same session
    SNOW_INSTANCE   ServiceNow base URL (default: https://loreal.service-now.com)
    REPORTS_DIR     Default directory for downloaded JSON (default: ./my_reports)
    ATTACHMENTS_DIR Directory for downloaded attachments (default: ./attachments)
    BQ_PROJECT      GCP project ID (required for BigQuery tools)
    BQ_DATASET      BigQuery dataset name
    BQ_MAX_BYTES    Hard scan ceiling in bytes (default: 500000000)
    BQ_TIMEOUT      Query timeout in seconds (default: 30)
    BQ_MAX_ROWS     Max rows returned per query (default: 100)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Allow running as `python rca_copilot_agent/mcp_server.py` from repo root
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

    server = Server("rca-copilot")

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
                    "Pass this text to your RCA analysis. "
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
                    "Use this when the user asks to 'post comment' or 'add comment'. "
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
                name="extract_identifiers",
                description=(
                    "Extract structured identifiers from an incident's text — "
                    "order IDs, user/customer IDs, EAN codes, email addresses. "
                    "Useful for building follow-up queries or referencing specific entities."
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
                    "Use to look up order data, pipeline events, or any structured data that may explain "
                    "a ServiceNow incident. Blocked from INSERT/UPDATE/DELETE/DROP. "
                    "Always add a LIMIT clause. Use backticks for table refs: "
                    f"`{'{BQ_PROJECT}'}.{'{BQ_DATASET}'}.table_name`."
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
                    "Get the column schema of a specific BigQuery table, or list all tables "
                    "in the dataset when no table name is given. Use before writing a query to "
                    "confirm column names and types."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": (
                                "Exact table name (e.g. 'orders') or a partial substring to search. "
                                "Leave empty to list all tables in the dataset."
                            ),
                            "default": "",
                        },
                    },
                },
            ),
            Tool(
                name="list_bq_tables",
                description=(
                    "List all tables in the SPACE CDS BigQuery dataset with row counts and sizes. "
                    "Use to discover what data is available before writing a query."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
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

        # Reload the in-memory store so subsequent calls see the new data
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

        # Look up sys_id from the number
        rec = reader.get_incident_by_number(number)
        if not rec:
            return f"Incident {number} not found in ServiceNow."

        sys_id = rec["sys_id"]
        report = reader.get_full_incident_report(
            sys_id=sys_id,
            download_files=download,
            attachments_dir=cfg.attachments_dir,
        )
        reader.upsert_incident_report(report, reports_dir=reports_dir)

        # Reload store
        combined = os.path.join(reports_dir, "_all_incidents.json")
        if os.path.exists(combined):
            from tools.incident_store import load_store
            load_store(combined)

        i = report["incident"]
        return (
            f"Fetched {i.get('number')} — {i.get('short_description')}\n"
            f"State: {i.get('state')}, Priority: {i.get('priority')}\n"
            f"Comments: {len(report.get('comments', []))}, "
            f"Work notes: {len(report.get('work_notes', []))}\n"
            f"Run get_incident_summary to read the full content."
        )

    elif name == "get_incident_summary":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        return get_store().get_incident_summary(arguments["incident_number"])

    elif name == "list_incidents":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        return get_store().list_all(max_incidents=arguments.get("max_count", 100))

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

        # Resolve sys_id — try local store first, then live lookup
        sys_id = _resolve_sys_id(number, reader, reports_dir)
        if not sys_id:
            return f"Cannot resolve sys_id for {number}. Fetch the incident first."

        success = reader.post_comment(
            incident_sys_id=sys_id,
            text=text,
            as_work_note=as_work_note,
        )
        label = "work note" if as_work_note else "comment"
        if success:
            return f"✓ Posted {label} to {number}."
        return f"✗ Failed to post {label} to {number}. Check logs."

    elif name == "extract_identifiers":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        ids = get_store().extract_identifiers(arguments["incident_number"])
        if not ids:
            return f"No structured identifiers found in {arguments['incident_number']}."
        return json.dumps(ids, indent=2)

    elif name == "query_bigquery":
        from tools.bigquery_tool import is_enabled, query_bigquery as bq_query, _BQ_UNAVAILABLE
        if not is_enabled():
            return _BQ_UNAVAILABLE
        return bq_query(
            sql=arguments["sql"],
            rationale=arguments.get("rationale", ""),
        )

    elif name == "get_schema":
        from tools.bigquery_tool import is_enabled, lookup_schema, _BQ_UNAVAILABLE
        if not is_enabled():
            return _BQ_UNAVAILABLE
        return lookup_schema(arguments.get("table_name", ""))

    elif name == "list_bq_tables":
        from tools.bigquery_tool import is_enabled, _get_executor, _dataset, _BQ_UNAVAILABLE
        if not is_enabled():
            return _BQ_UNAVAILABLE
        executor = _get_executor()
        tables = executor.list_tables(_dataset)
        if not tables:
            return "No tables found."
        lines = [f"{'TABLE':<50} {'ROWS':>12} {'SIZE MB':>10}"]
        lines.append("-" * 74)
        for t in sorted(tables, key=lambda x: x["table_id"]):
            lines.append(f"{t['full_name']:<50} {t['num_rows']:>12,} {t['size_mb']:>10.1f}")
        return "\n".join(lines)

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


def _resolve_sys_id(number: str, reader, reports_dir: str) -> str:
    """
    Resolve an incident number to its sys_id.
    Tries the local store first; falls back to a live ServiceNow search.
    """
    from tools.incident_store import get_store
    inc = get_store().get_incident(number)
    if inc:
        return inc.get("incident", {}).get("sys_id", "")

    # Live lookup
    rec = reader.get_incident_by_number(number)
    return rec.get("sys_id", "") if rec else ""


# ── Fallback: JSON-RPC over stdin/stdout (no mcp SDK) ─────────────────────────

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
                    {"name": t, "description": f"RCA tool: {t}"}
                    for t in [
                        "fetch_incidents", "get_incident", "get_incident_summary",
                        "list_incidents", "search_incidents", "post_comment",
                        "extract_identifiers",
                        "query_bigquery", "get_schema", "list_bq_tables",
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="RCA Copilot MCP Server — ServiceNow tools")
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=None,
        help="Directory for incident JSON files (overrides REPORTS_DIR env var)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    # Resolve reports + attachments directories
    from config import load_config, load_bq_config
    cfg = load_config()
    reports_dir = args.reports_dir or cfg.reports_dir
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cfg.attachments_dir, exist_ok=True)

    # Initialize BigQuery executor if credentials are present
    bq_cfg = load_bq_config()
    if bq_cfg.enabled:
        from tools.bigquery_tool import init_executor as init_bq
        init_bq(
            project=bq_cfg.project,
            dataset=bq_cfg.dataset,
            max_bytes=bq_cfg.max_bytes,
            timeout=bq_cfg.timeout,
            max_rows=bq_cfg.max_rows,
        )
        logger.info(f"[BQ] Initialized: {bq_cfg.project}.{bq_cfg.dataset}")
    else:
        logger.info("[BQ] BQ_PROJECT not set — BigQuery tools disabled.")

    # Pre-load incidents if they already exist on disk
    _auto_load_store(reports_dir)

    # Run MCP server or fallback
    try:
        import mcp  # noqa: F401
        import asyncio
        from mcp.server.stdio import stdio_server
        from mcp.server.models import InitializationOptions
        from mcp.server.lowlevel.server import NotificationOptions

        server = create_mcp_server(reports_dir)

        init_options = InitializationOptions(
            server_name="rca-copilot",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

        async def run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, init_options)

        logger.info(f"[MCP] Starting MCP server. Reports dir: {reports_dir}")
        asyncio.run(run())

    except ImportError:
        logger.warning("[MCP] mcp SDK not installed. Running JSON-RPC fallback.")
        _run_jsonrpc_fallback(reports_dir)


if __name__ == "__main__":
    main()
