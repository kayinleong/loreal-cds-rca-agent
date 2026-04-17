#!/usr/bin/env python
"""
RCA Pipeline — End-to-End
==========================
Chains the full workflow:
  1. Fetch incidents from ServiceNow (snow_story_reader.py)
  2. OCR on image attachments (snow_image_ocr_agent.py)
  3. Run RCA investigation (agent_runner.py)
  4. Post RCA report as a comment back to the ServiceNow ticket

USAGE:
    # Investigate a single incident from an already-fetched list
    python run_pipeline.py --incident INC0012345

    # Investigate and post RCA comment to ServiceNow
    python run_pipeline.py --incident INC0012345 --post-comment

    # Fetch fresh data first, then investigate + post comment
    python run_pipeline.py --incident INC0012345 --fetch --post-comment \\
        --list-link "https://loreal.service-now.com/..."

    # Batch: investigate all active incidents and post comments
    python run_pipeline.py --all --post-comment

    # Just fetch + OCR (no RCA)
    python run_pipeline.py --fetch-only \\
        --list-link "https://loreal.service-now.com/..."
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_cmd(cmd: list[str], description: str) -> int:
    """Run a command with live output."""
    print(f"\n{'─'*60}")
    print(f"  {description}")
    print(f"  $ {' '.join(cmd)}")
    print(f"{'─'*60}\n")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def step_fetch(args) -> bool:
    """Step 1: Fetch incidents from ServiceNow."""
    if not args.list_link:
        print("[SKIP] No --list-link provided, using existing data.")
        return True

    cmd = [
        sys.executable, "snow_story_reader.py",
        "--list-link", args.list_link,
        "--download",
        "--report-dir", args.reports_dir,
        "--limit", str(args.limit),
    ]
    rc = run_cmd(cmd, "Step 1: Fetching incidents from ServiceNow")
    return rc == 0


def step_ocr(args) -> bool:
    """Step 2: OCR on image attachments."""
    incidents_file = os.path.join(args.reports_dir, "_all_incidents.json")
    if not os.path.exists(incidents_file):
        print(f"[SKIP] No incidents file at {incidents_file}")
        return True

    cmd = [
        sys.executable, "snow_image_ocr_agent.py",
        "--input", incidents_file,
        "--attachments-root", args.attachments_dir,
    ]
    rc = run_cmd(cmd, "Step 2: Running OCR on image attachments")
    # OCR failure is non-fatal (images may not exist)
    if rc != 0:
        print("[WARN] OCR step had errors (non-fatal, continuing)")
    return True


def step_investigate(args, incident_number: str) -> tuple[bool, str]:
    """Step 3: Run RCA investigation. Returns (success, output_path)."""
    incidents_file = os.path.join(args.reports_dir, "_all_incidents.json")
    if not os.path.exists(incidents_file):
        print(f"[ERROR] Incidents file not found: {incidents_file}")
        return False, ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = os.path.join(args.output_dir, f"RCA_{incident_number}_{timestamp}.md")

    cmd = [
        sys.executable, "agent_runner.py",
        "--incident", incident_number,
        "--incidents-file", incidents_file,
        "--output", output,
    ]
    if args.provider:
        cmd.extend(["--provider", args.provider])
    if args.model:
        cmd.extend(["--model", args.model])
    if args.max_steps:
        cmd.extend(["--max-steps", str(args.max_steps)])

    rc = run_cmd(cmd, f"Step 3: Investigating {incident_number}")
    return rc == 0, output if rc == 0 else ""


def _rca_markdown_to_plain(md: str) -> str:
    """
    Convert the RCA markdown report to clean plain text for ServiceNow comments.
    Strips markdown headers/bold/italic but keeps the structured sections.
    """
    lines = []
    for line in md.splitlines():
        # Skip the appendix (SQL queries) — keep the comment focused
        if line.strip().startswith("### Appendix"):
            break
        # Convert ## headers to plain uppercase labels
        if line.startswith("## "):
            lines.append(line[3:].strip())
            continue
        # Strip H1 title line (# RCA Report: ...)
        if line.startswith("# "):
            continue
        # Strip horizontal rules
        if line.strip() == "---":
            continue
        # Strip bold/italic markers
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        lines.append(line)

    return "\n".join(lines).strip()


def step_post_comment(args, incident_number: str, rca_path: str) -> bool:
    """Step 4: Post the generated RCA report as a comment on the ServiceNow ticket."""
    if not rca_path or not os.path.exists(rca_path):
        print(f"[SKIP] RCA report not found at '{rca_path}', skipping comment post.")
        return False

    # Read the generated RCA markdown
    with open(rca_path, encoding="utf-8") as f:
        rca_md = f.read()

    comment_text = _rca_markdown_to_plain(rca_md)

    # Look up the incident sys_id from the downloaded report
    incident_json = os.path.join(args.reports_dir, f"{incident_number}.json")
    sys_id = None
    if os.path.exists(incident_json):
        with open(incident_json, encoding="utf-8") as f:
            data = json.load(f)
        sys_id = data.get("incident", {}).get("sys_id")

    if not sys_id:
        print(f"[ERROR] Could not find sys_id for {incident_number} in {incident_json}")
        return False

    print(f"\n{'─'*60}")
    print(f"  Step 4: Posting RCA comment to {incident_number} ({sys_id})")
    print(f"{'─'*60}\n")
    print("[COMMENT PREVIEW]")
    print(comment_text[:500] + ("..." if len(comment_text) > 500 else ""))
    print()

    # Import and use ServiceNowReader directly (avoids subprocess + re-auth overhead)
    sys.path.insert(0, str(Path(__file__).parent))
    from snow_story_reader import ServiceNowReader, INSTANCE_URL

    snow_table = _snow_table_for(incident_number)

    client = ServiceNowReader(INSTANCE_URL)
    client.authenticate_from_env()
    if not client.validate():
        print("[FAIL] ServiceNow session invalid — cannot post comment.")
        return False

    return client.post_comment(sys_id, comment_text, as_work_note=False, table=snow_table)


_TERMINAL_STATES = frozenset({"resolved", "closed", "cancelled", "complete", "completed"})


def _snow_table_for(record_number: str) -> str:
    """Return the ServiceNow table name for a record number prefix."""
    from snow_story_reader import INCIDENT_TABLE
    if record_number.upper().startswith("RITM"):
        return "sc_req_item"
    return INCIDENT_TABLE


def get_active_incidents(reports_dir: str) -> list[str]:
    """Get list of open/active record numbers from _all_incidents.json.

    Works for both INC (state='Active') and RITM (state='Open', 'Work in Progress',
    etc.) by excluding terminal states rather than requiring a specific active state.
    """
    path = os.path.join(reports_dir, "_all_incidents.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        incidents = json.load(f)
    numbers = []
    for inc in incidents:
        i = inc.get("incident", {})
        number = i.get("number", "")
        if not number:
            continue
        state = (i.get("state") or "").strip().lower()
        if state not in _TERMINAL_STATES:
            numbers.append(number)
    return numbers


def main():
    parser = argparse.ArgumentParser(description="RCA Pipeline — End-to-End")

    # What to investigate
    parser.add_argument("--incident", type=str,
                        help="Single incident number to investigate")
    parser.add_argument("--all", action="store_true",
                        help="Investigate all active incidents")

    # Data fetching
    parser.add_argument("--fetch", action="store_true",
                        help="Fetch fresh data from ServiceNow before investigating")
    parser.add_argument("--fetch-only", action="store_true",
                        help="Only fetch + OCR, don't run RCA")
    parser.add_argument("--list-link", type=str,
                        help="ServiceNow list view URL")
    parser.add_argument("--limit", type=int, default=200,
                        help="Max incidents to fetch (default: 200)")

    # Paths
    parser.add_argument("--reports-dir", type=str, default="./my_reports")
    parser.add_argument("--attachments-dir", type=str, default="./attachments")
    parser.add_argument("--output-dir", type=str, default="./rca_reports")

    # LLM config
    parser.add_argument("--provider", type=str, help="LLM provider override")
    parser.add_argument("--model", type=str, help="LLM model override")
    parser.add_argument("--max-steps", type=int, help="Max investigation steps")

    # Comment posting
    parser.add_argument("--post-comment", action="store_true",
                        help="Post the generated RCA report as a comment on the ServiceNow ticket")

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Step 1: Fetch ──
    if args.fetch or args.fetch_only:
        if not step_fetch(args):
            print("[FAIL] Fetch step failed.")
            sys.exit(1)
        step_ocr(args)

    if args.fetch_only:
        print("\n[DONE] Fetch + OCR complete.")
        sys.exit(0)

    # ── Steps 3 + 4: Investigate (+ optionally post comment) ──
    if args.incident:
        # Single incident
        success, rca_path = step_investigate(args, args.incident)
        if success and args.post_comment:
            step_post_comment(args, args.incident, rca_path)
        sys.exit(0 if success else 1)

    elif args.all:
        # All active incidents
        numbers = get_active_incidents(args.reports_dir)
        if not numbers:
            print("[INFO] No active incidents found.")
            sys.exit(0)

        print(f"\n[BATCH] Investigating {len(numbers)} active incident(s)...\n")
        results = {}
        for i, number in enumerate(numbers, 1):
            print(f"\n{'='*60}")
            print(f"  [{i}/{len(numbers)}] {number}")
            print(f"{'='*60}")
            success, rca_path = step_investigate(args, number)
            results[number] = success
            if success and args.post_comment:
                step_post_comment(args, number, rca_path)

        # Summary
        succeeded = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)
        print(f"\n{'='*60}")
        print(f"  BATCH COMPLETE: {succeeded} succeeded, {failed} failed")
        print(f"{'='*60}")
        for number, ok in results.items():
            status = "✓" if ok else "✗"
            print(f"  {status} {number}")
        sys.exit(0 if failed == 0 else 1)

    else:
        parser.print_help()
        print("\nError: Specify --incident <number> or --all")
        sys.exit(1)


if __name__ == "__main__":
    main()
