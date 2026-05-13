#!/usr/bin/env python3
"""
run_tool.py — Unified CLI for ticketasg_copilot_agent tools (no MCP server required).

Usage:
    python ticketasg_copilot_agent/run_tool.py <tool_name> --json '<JSON args>'

Examples:
    python ticketasg_copilot_agent/run_tool.py list_incidents --json '{}'
    python ticketasg_copilot_agent/run_tool.py analyze_incident --json '{"incident_number": "INC10403788"}'
    python ticketasg_copilot_agent/run_tool.py get_assignment_rules --json '{}'
    python ticketasg_copilot_agent/run_tool.py recommend_assignment --json '{"incident_number": "INC123", "short_description": "SAP sync error", "description": "SAPMENA pipeline failure", "current_group": "APAC - ZN - O+O.OPERATIONS - L2"}'
    python ticketasg_copilot_agent/run_tool.py fetch_incidents --json '{"list_url": "https://loreal.service-now.com/..."}'
    python ticketasg_copilot_agent/run_tool.py save_assignment_report --json '{"incident_number": "INC123", "report_text": "..."}'
    python ticketasg_copilot_agent/run_tool.py send_assignment_email --json '{"session_summary": "Analysed INC123"}'

Tool names:
    list_incidents          List all locally cached incidents
    fetch_incidents         Download all incidents from a SNOW list-view URL
    get_incident            Fetch a single incident from SNOW by number
    get_incident_summary    Read a locally cached incident's full text
    analyze_incident        ONE-STOP: fetch + identifiers for one incident
    search_incidents        Keyword-search across all local incidents
    post_comment            Post a comment or work note to SNOW (confirm before calling)
    get_assignment_rules    Show the routing matrix (all 10 L2 groups + keywords)
    recommend_assignment    Score incident signals and recommend the assignment group
    save_assignment_report  Save a completed assignment report to disk
    send_assignment_email   Send HTML email notification with attached reports
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root: `python ticketasg_copilot_agent/run_tool.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a ticketasg_copilot_agent tool without starting an MCP server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", help="Tool name (see list above)")
    parser.add_argument(
        "--json",
        metavar="ARGS",
        default="{}",
        help="JSON object of tool arguments, e.g. '{\"incident_number\": \"INC123\"}'",
    )
    args = parser.parse_args()

    try:
        arguments = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"Error: --json is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    from config import load_config
    cfg = load_config()
    reports_dir = os.environ.get("REPORTS_DIR") or cfg.reports_dir

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cfg.attachments_dir, exist_ok=True)

    # Initialize BigQuery schema (non-fatal if unavailable)
    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except Exception as e:
        logger.warning(f"[BQ] Not available: {e}")

    # Pre-load incident store if _all_incidents.json exists
    combined = os.path.join(reports_dir, "_all_incidents.json")
    if os.path.exists(combined):
        from tools.incident_store import load_store
        load_store(combined)

    # Check ServiceNow credentials (non-fatal)
    try:
        from tools.auth_tool import ensure_credentials
        ensure_credentials(instance_url=cfg.instance_url)
    except Exception as e:
        logger.warning(f"[AUTH] Credential check failed: {type(e).__name__}: {e}")

    # Check gcloud ADC (non-fatal)
    try:
        from tools.gcloud_tool import ensure_gcloud_auth
        ensure_gcloud_auth()
    except Exception as e:
        logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")

    # Dispatch to mcp_server._dispatch
    from mcp_server import _dispatch
    result = asyncio.run(_dispatch(args.tool, arguments, reports_dir))
    print(result)


if __name__ == "__main__":
    main()
