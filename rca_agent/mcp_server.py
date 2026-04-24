"""
RCA Agent — MCP Server
=======================
Exposes all investigation tools via Model Context Protocol (MCP).

This is the key architectural piece: tools live here as pure functions,
and ANY MCP-compatible client brings its own LLM reasoning:
  - GitHub Copilot (via .github/agents/*.md)
  - Claude Code (via claude_desktop_config.json)
  - Cursor, Windsurf, etc.
  - Your own agent_runner.py (via direct function calls)

The MCP server is LLM-agnostic. It doesn't know or care which model
is calling the tools. Swap providers by changing the client, not the server.

USAGE:
    # Run as stdio MCP server (for Copilot/Claude Code)
    python mcp_server.py

    # With explicit config
    python mcp_server.py --incidents ./my_reports/_all_incidents.json \\
                         --bq-project oa-apmena-spacecds-ap-pd \\
                         --bq-dataset space_cds_b2c_ds_replica_ae2_pd_public

MCP CONFIG (for Claude Code / claude_desktop_config.json):
    {
      "mcpServers": {
        "rca-agent": {
          "command": "python",
          "args": ["path/to/mcp_server.py"],
          "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/sa-key.json"
          }
        }
      }
    }
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Lazy imports (MCP SDK may not be installed in all environments) ──────────

def _check_mcp_sdk():
    try:
        import mcp
        return True
    except ImportError:
        return False


# ── Tool implementations (thin wrappers around tools/) ──────────────────────

def _init_tools(incidents_path: str, ocr_path: str = None,
                bq_project: str = None, bq_dataset: str = None):
    """Initialize all tool backends."""
    from config import AgentConfig
    config = AgentConfig()

    # ServiceNow data
    from tools.snow_tool import init_loader
    init_loader(incidents_path, ocr_path)
    logger.info(f"[MCP] Incident data loaded from {incidents_path}")

    # BigQuery
    from tools.bigquery_tool import init_executor
    project = bq_project or config.bq.project
    dataset = bq_dataset or config.bq.dataset
    init_executor(
        project=project,
        dataset=dataset,
        max_bytes=config.bq.max_bytes_billed,
        timeout=config.bq.timeout_seconds,
        max_rows=config.bq.max_rows,
    )
    logger.info(f"[MCP] BigQuery executor: {project}.{dataset}")

    # Wiki
    from tools.wiki_tool import init_wiki
    init_wiki(persist_dir=config.wiki_dir)
    logger.info("[MCP] Investigation wiki initialized")


# ── MCP Server (using mcp SDK) ──────────────────────────────────────────────

def create_mcp_server():
    """Create and configure the MCP server with all RCA tools."""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    server = Server("rca-agent")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="query_bigquery",
                description=(
                    "Execute a read-only BigQuery query against the CDS dataset. "
                    "Only SELECT/WITH queries allowed. Use fully-qualified backtick "
                    "table names. Always include LIMIT."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "Read-only SQL query (SELECT/WITH only)",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this query helps the investigation",
                        },
                    },
                    "required": ["sql"],
                },
            ),
            Tool(
                name="search_incident",
                description=(
                    "Search loaded ServiceNow incident data for a keyword. "
                    "Searches description, comments, work notes, and OCR text."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Search term",
                        },
                        "section": {
                            "type": "string",
                            "description": "Where to search: comments, work_notes, "
                                           "description, attachments_ocr, or all",
                            "default": "all",
                        },
                    },
                    "required": ["keyword"],
                },
            ),
            Tool(
                name="update_findings",
                description=(
                    "Record a validated finding to the investigation wiki. "
                    "Categories: timeline, evidence, hypothesis, conclusion, action_item."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["timeline", "evidence", "hypothesis",
                                     "conclusion", "action_item"],
                            "description": "Finding category",
                        },
                        "content": {
                            "type": "string",
                            "description": "The finding text",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "default": "medium",
                        },
                        "source": {
                            "type": "string",
                            "description": "Where this came from (e.g., 'BQ query', 'work_note')",
                            "default": "",
                        },
                    },
                    "required": ["category", "content"],
                },
            ),
            Tool(
                name="read_wiki",
                description=(
                    "Read accumulated investigation findings from the wiki. "
                    "Use before writing the final RCA report."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category to read, or 'all'",
                            "default": "all",
                        },
                    },
                },
            ),
            Tool(
                name="lookup_schema",
                description=(
                    "Look up BigQuery table schemas. Empty pattern lists all tables. "
                    "Provide a table name for detailed column info."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_pattern": {
                            "type": "string",
                            "description": "Table name or pattern (empty for all)",
                            "default": "",
                        },
                    },
                },
            ),
            Tool(
                name="get_incident_summary",
                description=(
                    "Get the full summary of a specific incident by number. "
                    "Includes description, comments, work notes, attachments, OCR text."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number (e.g., INC0012345)",
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
            Tool(
                name="list_incidents",
                description="List all loaded incidents with brief summaries.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "max_count": {
                            "type": "integer",
                            "description": "Max incidents to list",
                            "default": 50,
                        },
                    },
                },
            ),
            Tool(
                name="extract_identifiers",
                description=(
                    "Extract order IDs, user IDs, EAN codes, emails, and other "
                    "identifiers from an incident's text for use in BQ queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_number": {
                            "type": "string",
                            "description": "Incident number",
                        },
                    },
                    "required": ["incident_number"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Dispatch tool calls to implementations."""
        try:
            if name == "query_bigquery":
                from tools.bigquery_tool import query_bigquery
                result = query_bigquery(
                    sql=arguments["sql"],
                    rationale=arguments.get("rationale", ""),
                )

            elif name == "search_incident":
                from tools.snow_tool import search_incident
                result = search_incident(
                    keyword=arguments["keyword"],
                    section=arguments.get("section", "all"),
                )

            elif name == "update_findings":
                from tools.wiki_tool import update_findings
                result = update_findings(
                    category=arguments["category"],
                    content=arguments["content"],
                    confidence=arguments.get("confidence", "medium"),
                    source=arguments.get("source", ""),
                )

            elif name == "read_wiki":
                from tools.wiki_tool import read_wiki
                result = read_wiki(category=arguments.get("category", "all"))

            elif name == "lookup_schema":
                from tools.bigquery_tool import lookup_schema
                result = lookup_schema(
                    table_pattern=arguments.get("table_pattern", ""),
                )

            elif name == "get_incident_summary":
                from tools.snow_tool import get_loader
                result = get_loader().get_incident_summary(
                    arguments["incident_number"]
                )

            elif name == "list_incidents":
                from tools.snow_tool import get_loader
                result = get_loader().get_all_summaries(
                    max_incidents=arguments.get("max_count", 50)
                )

            elif name == "extract_identifiers":
                from tools.snow_tool import get_loader
                ids = get_loader().extract_identifiers(arguments["incident_number"])
                result = json.dumps(ids, indent=2) if ids else "No identifiers found"

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool error ({name}): {type(e).__name__}: {e}"
            logger.error(result)

        return [TextContent(type="text", text=result)]

    return server


# ── Fallback: JSON-RPC over stdin/stdout (no MCP SDK) ───────────────────────

def run_jsonrpc_fallback():
    """
    Minimal JSON-RPC 2.0 server over stdio for environments
    where the mcp SDK isn't available.
    """
    print("Running in JSON-RPC fallback mode (no MCP SDK)", file=sys.stderr)

    tool_dispatch = {
        "query_bigquery": lambda args: __import__("tools.bigquery_tool", fromlist=["query_bigquery"]).query_bigquery(**args),
        "search_incident": lambda args: __import__("tools.snow_tool", fromlist=["search_incident"]).search_incident(**args),
        "update_findings": lambda args: __import__("tools.wiki_tool", fromlist=["update_findings"]).update_findings(**args),
        "read_wiki": lambda args: __import__("tools.wiki_tool", fromlist=["read_wiki"]).read_wiki(**args),
        "lookup_schema": lambda args: __import__("tools.bigquery_tool", fromlist=["lookup_schema"]).lookup_schema(**args),
    }

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method", "")
            params = req.get("params", {})
            req_id = req.get("id")

            if method == "tools/list":
                # Return tool schemas
                result = {"tools": [
                    {"name": name, "description": f"RCA tool: {name}"}
                    for name in tool_dispatch
                ]}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments", {})
                fn = tool_dispatch.get(tool_name)
                if fn:
                    result = {"content": [{"type": "text", "text": fn(args)}]}
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
            else:
                result = {"error": f"Unknown method: {method}"}

            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            print(json.dumps(response), flush=True)

        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": req.get("id") if "req" in dir() else None,
                "error": {"code": -1, "message": str(e)},
            }
            print(json.dumps(response), flush=True)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RCA Agent MCP Server")
    parser.add_argument("--incidents", type=str,
                        default="./my_reports/_all_incidents.json",
                        help="Path to _all_incidents.json")
    parser.add_argument("--ocr", type=str, default=None,
                        help="Path to _ocr_consolidated.json")
    parser.add_argument("--bq-project", type=str, default=None)
    parser.add_argument("--bq-dataset", type=str, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        stream=sys.stderr)

    # Initialize tool backends
    _init_tools(
        incidents_path=args.incidents,
        ocr_path=args.ocr,
        bq_project=args.bq_project,
        bq_dataset=args.bq_dataset,
    )

    # Run MCP server (or fallback)
    if _check_mcp_sdk():
        import asyncio
        from mcp.server.stdio import stdio_server

        server = create_mcp_server()

        async def run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream)

        logger.info("[MCP] Starting MCP server on stdio...")
        asyncio.run(run())
    else:
        logger.warning("[MCP] mcp SDK not found. Running JSON-RPC fallback.")
        run_jsonrpc_fallback()


if __name__ == "__main__":
    main()
