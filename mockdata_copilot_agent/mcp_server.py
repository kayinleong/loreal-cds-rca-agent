"""
Mock Data Copilot MCP Server
=============================
Generates BigQuery GoogleSQL mock-data INSERTs (external_system_ids +
consumer_pii) for the L'Oreal CDS B2C DV (SEA) replica dataset, and presents
them for a human to run manually. Exposes 4 tools via the Model Context Protocol
(MCP). GitHub Copilot (or any MCP client) calls these tools; the LLM reasoning
stays entirely inside the client — this server contains NO LLM calls.

Tools:
  ensure_login          Ensure L'Oreal GCP login (gcloud user creds + ADC); default project = DV
  lookup_consumer       Read-only consumer_pii existence check against the DV dataset
  generate_mockdata     Generate N mock external_system_ids rows (+ optional consumer_pii rows)
  save_mockdata_report  Write mockdata/<MMDDYYSS>.md and present the SQL

No LLM calls in this server. The agent PRESENTS SQL only — it never executes
writes. The only live BigQuery access is the read-only consumer_pii existence
lookup built by build_lookup_sql (a SELECT, blocklist-clean by construction).
Generated INSERT text is NEVER routed through query_bigquery.

USAGE:
    python mcp_server.py

    # Override the output directory
    python mcp_server.py --output-dir ./mockdata

ENVIRONMENT (via .env or shell):
    BQ_PROJECT           GCP billing project for the read-only lookup
                         (default: oa-apmena-spacecds-ap-dv — the DV project)
    BQ_DATASET           DV dataset name
                         (default: space_cds_b2c_ds_replica_ase1_dv_public)
    MOCKDATA_OUTPUT_DIR  Directory for generated mockdata/<MMDDYYSS>.md files

No ServiceNow credentials and no email notifications exist here. BigQuery uses gcloud ADC.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Allow running as `python mockdata_copilot_agent/mcp_server.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ── MCP server (using mcp SDK) ────────────────────────────────────────────────

def create_mcp_server(output_dir: str):
    from mcp.server import Server
    from mcp.types import Tool, TextContent

    server = Server("mockdata-copilot")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="ensure_login",
                description=(
                    "Ensure the L'Oreal GCP login is valid (gcloud user credentials + "
                    "Application Default Credentials), defaulting the billing project to the "
                    "DV project. Call this once before lookup_consumer. This agent presents "
                    "SQL only and never executes writes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="lookup_consumer",
                description=(
                    "Read-only consumer_pii existence check against the DV dataset. Builds a "
                    "SELECT keyed on lucid (with optional consumerkey/signature/isocountry "
                    "disambiguators) and runs it through the blocklisted read-only executor. "
                    "Returns {lucid, exists, result}. This is the ONLY tool that touches a live "
                    "database; it never executes an INSERT. The agent presents SQL only and "
                    "never executes writes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lucid": {
                            "type": "string",
                            "description": "Consumer LUCID to check for existence.",
                        },
                        "consumerkey": {
                            "type": "string",
                            "description": "Optional consumerkey disambiguator.",
                        },
                        "signature": {
                            "type": "string",
                            "description": "Optional signature disambiguator.",
                        },
                        "isocountry": {
                            "type": "string",
                            "description": "Optional ISO country disambiguator.",
                        },
                    },
                    "required": ["lucid"],
                },
            ),
            Tool(
                name="generate_mockdata",
                description=(
                    "Generate N mock external_system_ids rows from a seed + variation spec, and "
                    "optionally synthetic consumer_pii rows for any absent_lucids the agent has "
                    "already confirmed missing via lookup_consumer. Returns the generated INSERT "
                    "SQL plus the row data — as TEXT only. This tool never executes any SQL and "
                    "never calls lookup_consumer; the agent orchestrates lookups across calls. "
                    "The agent presents SQL only and never executes writes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "seed": {
                            "type": "object",
                            "description": "Seed row dict (column -> value) for external_system_ids.",
                        },
                        "vary": {
                            "type": "object",
                            "description": (
                                "Map of column_name -> value-list (cycled per row) or scalar "
                                "(constant). extsystemidskey is always varied automatically."
                            ),
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of rows to generate.",
                        },
                        "absent_lucids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Lucids the agent confirmed absent via lookup_consumer; "
                                "synthetic consumer_pii rows are generated for these."
                            ),
                        },
                    },
                    "required": ["seed", "vary", "count"],
                },
            ),
            Tool(
                name="save_mockdata_report",
                description=(
                    "Write a mockdata/<MMDDYYSS>.md report (collision-safe) echoing the prompt, "
                    "the generated external_system_ids INSERT, the optional consumer_pii INSERT, "
                    "a summary, and the mandatory 'review & run manually / does not execute "
                    "writes' reminder. Returns the saved path. The agent presents SQL only and "
                    "never executes writes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The user's request, echoed verbatim into the report.",
                        },
                        "external_sql": {
                            "type": "string",
                            "description": "The generated external_system_ids INSERT block.",
                        },
                        "consumer_sql": {
                            "type": "string",
                            "description": "Optional generated consumer_pii INSERT block.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Short summary of what was generated.",
                        },
                    },
                    "required": ["prompt", "external_sql", "summary"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = await _dispatch(name, arguments, output_dir)
        except Exception as exc:
            result = f"Tool error ({name}): {type(exc).__name__}: {exc}"
            logger.error(result)

        return [TextContent(type="text", text=str(result))]

    return server


async def _dispatch(name: str, arguments: dict, output_dir: str) -> str:
    """Route tool calls to their implementations. Exactly 4 tools + final else.

    Offline-safe: only ensure_login and lookup_consumer touch gcloud/BigQuery,
    and they do so LAZILY (auth is invoked inside the branch, never at import).
    """

    if name == "ensure_login":
        from tools.gcloud_tool import ensure_gcloud_auth, get_active_gcloud_account
        ensure_gcloud_auth("loreal.com")
        acct = get_active_gcloud_account() or "(unknown)"
        return json.dumps(
            {"account": acct, "project": os.environ.get("BQ_PROJECT", ""), "adc": "checked"},
            indent=2,
        )

    elif name == "lookup_consumer":
        # Lazy auth — only the live-DB tool triggers a gcloud login check.
        try:
            from tools.gcloud_tool import ensure_gcloud_auth
            ensure_gcloud_auth("loreal.com")
        except Exception as exc:
            logger.warning(f"[GCLOUD] Auth check failed: {type(exc).__name__}: {exc}")

        from tools.mockdata_tool import build_lookup_sql
        from tools.bigquery_tool import query_bigquery
        sql = build_lookup_sql(
            lucid=arguments["lucid"],
            consumerkey=arguments.get("consumerkey"),
            signature=arguments.get("signature"),
            isocountry=arguments.get("isocountry"),
        )
        raw = query_bigquery(sql, rationale="consumer_pii existence check")
        # Existence heuristic: a successful query that returned no rows reports
        # "0 rows" / "No results"; a failure surfaces an error string.
        exists = (
            "0 rows" not in raw
            and "No results" not in raw
            and "error" not in raw.lower()
            and "FAILED" not in raw
        )
        return json.dumps(
            {"lucid": arguments["lucid"], "exists": exists, "result": raw},
            indent=2,
        )

    elif name == "generate_mockdata":
        from tools.mockdata_tool import generate_external_system_ids, generate_consumer_pii
        gen = generate_external_system_ids(
            arguments["seed"], arguments["vary"], int(arguments["count"])
        )
        out = {
            "external_system_ids_sql": gen["sql"],
            "rows": gen["rows"],
            "lucids": gen["lucids"],
            "consumerkeys": gen["consumerkeys"],
        }
        absent = arguments.get("absent_lucids") or []
        if absent:
            consumers = [r for r in gen["rows"] if r.get("lucid") in absent]
            cp = generate_consumer_pii(consumers)
            out["consumer_pii_sql"] = cp["sql"]
        return json.dumps(out, indent=2)

    elif name == "save_mockdata_report":
        return _save_mockdata_report(output_dir, arguments)

    else:
        return f"Unknown tool: {name}"


def _save_mockdata_report(output_dir: str, args: dict) -> str:
    """Collision-safe mockdata/<MMDDYYSS>.md writer (A6).

    Filename = MMDDYY + a 2-digit sequence (00-99) chosen by scanning existing
    same-day files. If 00-99 are exhausted, fall back to MMDDYY_HHMMSS.md.
    """
    from datetime import datetime

    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now()
    base = now.strftime("%m%d%y")  # MMDDYY
    existing = {p.stem for p in Path(output_dir).glob(f"{base}*.md")}
    seq = next((f"{i:02d}" for i in range(100) if f"{base}{i:02d}" not in existing), None)
    stem = f"{base}{seq}" if seq is not None else now.strftime(f"{base}_%H%M%S")
    path = Path(output_dir) / f"{stem}.md"

    prompt = args.get("prompt", "")
    external_sql = args.get("external_sql", "")
    consumer_sql = args.get("consumer_sql")
    summary = args.get("summary", "")

    consumer_block = (
        f"```sql\n{consumer_sql}\n```"
        if consumer_sql
        else "No consumer_pii rows needed — all consumers already exist."
    )

    reminder = (
        "Review and run these INSERTs manually against the BigQuery DV dataset "
        "(oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public). "
        "This agent does not execute writes.\n\n"
        "Dialect: BigQuery GoogleSQL [A1 confirmed 2026-06-24]."
    )

    body = (
        f"# Mock Data — {stem}\n\n"
        f"_Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}_\n\n"
        f"## Prompt\n\n{prompt}\n\n"
        f"## external_system_ids\n\n```sql\n{external_sql}\n```\n\n"
        f"## consumer_pii\n\n{consumer_block}\n\n"
        f"## Summary\n\n{summary}\n\n"
        f"{reminder}\n"
    )

    path.write_text(body, encoding="utf-8")
    return f"Mock data report saved: {path}"


def _run_jsonrpc_fallback(output_dir: str) -> None:
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
                    {"name": t, "description": f"mockdata-copilot tool: {t}"}
                    for t in [
                        "ensure_login",
                        "lookup_consumer",
                        "generate_mockdata",
                        "save_mockdata_report",
                    ]
                ]}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                text = asyncio.run(_dispatch(tool_name, tool_args, output_dir))
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
    parser = argparse.ArgumentParser(description="Mock Data Copilot MCP Server")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for generated mockdata/<MMDDYYSS>.md files "
             "(overrides MOCKDATA_OUTPUT_DIR env var)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    from config import load_mockdata_config
    cfg = load_mockdata_config()
    output_dir = args.output_dir or cfg.output_dir
    os.makedirs(output_dir, exist_ok=True)
    os.environ.setdefault("BQ_PROJECT", cfg.bq_project)  # DV default — BEFORE auth

    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except Exception as bq_err:
        logger.warning(f"[BQ] Not available: {bq_err}")

    # NOTE: gcloud auth is intentionally NOT invoked at server startup. The
    # interactive `ensure_gcloud_auth("loreal.com")` check is deferred to the
    # tools that actually touch GCP/BigQuery (ensure_login, lookup_consumer),
    # where it runs LAZILY inside _dispatch. This keeps the server (and the
    # offline tools generate_mockdata / save_mockdata_report) startable with
    # zero credentials and avoids blocking on an interactive login prompt.
    # BQ_PROJECT is already set above (DV default) before any auth/BQ call.

    try:
        import mcp  # noqa: F401
        import asyncio
        from mcp.server.stdio import stdio_server
        from mcp.server.models import InitializationOptions
        from mcp.server.lowlevel.server import NotificationOptions

        server = create_mcp_server(output_dir)

        init_options = InitializationOptions(
            server_name="mockdata-copilot",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

        async def run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, init_options)

        logger.info(f"[MCP] Starting mockdata-copilot server. Output dir: {output_dir}")
        asyncio.run(run())

    except ImportError:
        logger.warning("[MCP] mcp SDK not installed. Running JSON-RPC fallback.")
        _run_jsonrpc_fallback(output_dir)


if __name__ == "__main__":
    main()
