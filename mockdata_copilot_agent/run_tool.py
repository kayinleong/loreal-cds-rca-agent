#!/usr/bin/env python3
"""
run_tool.py — Unified CLI for mockdata_copilot_agent tools (no MCP server required).

Usage:
    python mockdata_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'

Examples:
    python mockdata_copilot_agent/run_tool.py ensure_login --json '{}'
    python mockdata_copilot_agent/run_tool.py generate_mockdata --json '{"seed": {...}, "vary": {"signature": ["45","01"]}, "count": 2}'
    python mockdata_copilot_agent/run_tool.py lookup_consumer --json '{"lucid": "C2ID00000000010"}'
    python mockdata_copilot_agent/run_tool.py save_mockdata_report --json '{"prompt": "...", "external_sql": "...", "summary": "..."}'

Tool names:
    ensure_login          Ensure L'Oreal GCP login (gcloud user creds + ADC); default project = DV
    lookup_consumer       Read-only consumer_pii existence check against the DV dataset
    generate_mockdata     Generate N mock external_system_ids rows (+ optional consumer_pii rows)
    save_mockdata_report  Write mockdata/<MMDDYYSS>.md and present the SQL

This agent PRESENTS SQL only — it never executes writes against any database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root: `python mockdata_copilot_agent/run_tool.py`.
# Puts the package dir first so the local mcp_server module (and its _dispatch)
# resolves to mockdata_copilot_agent/mcp_server.py, not any other on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a mockdata_copilot_agent tool without starting an MCP server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", help="Tool name (see list above)")
    parser.add_argument(
        "--json",
        metavar="ARGS",
        default="{}",
        help="JSON object of tool arguments, e.g. '{\"lucid\": \"C2ID00000000010\"}'",
    )
    args = parser.parse_args()

    try:
        arguments = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"Error: --json is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    from config import load_mockdata_config
    cfg = load_mockdata_config()
    output_dir = os.environ.get("MOCKDATA_OUTPUT_DIR") or cfg.output_dir
    os.makedirs(output_dir, exist_ok=True)
    os.environ.setdefault("BQ_PROJECT", cfg.bq_project)  # DV default — BEFORE auth

    # Initialize BigQuery schema (non-fatal if unavailable)
    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except Exception as e:
        logger.warning(f"[BQ] Not available: {e}")

    # Check gcloud ADC / L'Oreal login (non-fatal) — ONLY for the BigQuery-
    # touching tools. The offline tools (generate_mockdata, save_mockdata_report)
    # never need auth and must run with zero credentials, so we do not trigger
    # the interactive gcloud login check on their paths. ensure_login and
    # lookup_consumer also re-check lazily inside _dispatch.
    _BQ_TOOLS = {"ensure_login", "lookup_consumer"}
    if args.tool in _BQ_TOOLS:
        try:
            from tools.gcloud_tool import ensure_gcloud_auth
            ensure_gcloud_auth("loreal.com")
        except Exception as e:
            logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")

    # Dispatch to the LOCAL mcp_server._dispatch
    from mcp_server import _dispatch
    result = asyncio.run(_dispatch(args.tool, arguments, output_dir))
    print(result)


if __name__ == "__main__":
    main()
