#!/usr/bin/env python3
r"""
run_tool.py — Unified CLI for rca_copilot_agent tools.

No venv activation needed: after running the setup script once (./setup.sh on
macOS/Linux, setup.cmd on Windows, from the repo root) this script re-launches
itself inside <repo>/.venv automatically, whichever Python started it.

Usage (cross-platform; pick ONE way to pass arguments):

    python3 rca_copilot_agent/run_tool.py <tool>                            # no args -> {}
    python3 rca_copilot_agent/run_tool.py <tool> --json-file <path>         # RECOMMENDED
    python3 rca_copilot_agent/run_tool.py <tool> --json -                   # JSON from stdin (UTF-8)
    python3 rca_copilot_agent/run_tool.py <tool> --arg key=value [--arg k2=v2 ...]
    python3 rca_copilot_agent/run_tool.py <tool> --json '<JSON object>'     # POSIX shells only

    macOS/Linux: python3 ...     Windows: python ...   or   py -3 ...

Recommended (macOS + Windows, any shell, any text): write the arguments as JSON
to a scratch file, then pass it with --json-file. UTF-8 with or without BOM is
accepted. Apostrophes ("L'Oreal"), quotes, %, newlines and non-ASCII are safe.
Scratch files live in .rca_tmp/ (git-ignored; may contain ticket text / PII):

    # 1. write .rca_tmp/args.json with your editor / file-write tool:
    #    {"sql": "SELECT 1", "rationale": "test"}
    # 2. run:
    python3 rca_copilot_agent/run_tool.py query_bigquery --json-file .rca_tmp/args.json
    py -3 rca_copilot_agent\run_tool.py query_bigquery --json-file .rca_tmp\args.json

Simple scalar values: --arg (values are strings; exactly true/false -> boolean;
split on the first "=" only; --arg values override keys from the JSON object):

    python3 rca_copilot_agent/run_tool.py analyze_incident --arg incident_number=INC10403788
    python rca_copilot_agent/run_tool.py get_schema --arg table_name=purchase

--json '...' works only in POSIX shells (bash/zsh) and breaks if the text
contains an apostrophe. It does NOT work in cmd.exe, and Windows PowerShell 5.1
strips the embedded double quotes. Prefer --json-file or --arg.
--json and --json-file are mutually exclusive; --arg combines with either.

Examples:
    python3 rca_copilot_agent/run_tool.py list_incidents
    python3 rca_copilot_agent/run_tool.py save_rca_report --json-file .rca_tmp/report.json
    python3 rca_copilot_agent/run_tool.py send_rca_email --json-file .rca_tmp/email.json
    python3 rca_copilot_agent/run_tool.py fetch_incidents --arg list_url=https://loreal.service-now.com/...

Tool names:
    list_incidents        List all locally cached incidents
    fetch_incidents       Download all incidents from a SNOW list-view URL
    get_incident          Fetch a single incident from SNOW by number
    get_incident_summary  Read a locally cached incident's full text
    analyze_incident      ONE-STOP: fetch + attachments + identifiers for one incident
    search_incidents      Keyword-search across all local incidents
    extract_identifiers   Extract order IDs / emails / EAN codes from an incident
    download_attachments  Download attachment files for an incident
    post_comment          Preview a comment/work note; posts only with confirmed=true (after user approval)
    list_bq_tables        List all BQ tables with RCA purpose
    get_schema            Get BQ table schema (from local schema.json)
    query_bigquery        Run a read-only SELECT query (pass incident_number to log evidence)
    get_rca_template      Print the canonical RCA report template (call before writing an RCA)
    save_rca_report       Validate + save a completed RCA report to disk
    send_rca_email        Email all saved, not-yet-emailed reports
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

REEXEC_ENV = "RCA_VENV_REEXEC"
_LOCAL_MODULES = ("config", "tools", "dispatcher")

# Allow running from repo root: `python rca_copilot_agent/run_tool.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an rca_copilot_agent tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", help="Tool name (see list above)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--json",
        metavar="ARGS",
        default=None,
        help="JSON object of tool arguments (POSIX shells only), or '-' to read from stdin",
    )
    group.add_argument(
        "--json-file",
        metavar="PATH",
        default=None,
        help="Path to a UTF-8 JSON file (BOM tolerated) with the tool arguments",
    )
    parser.add_argument(
        "--arg",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        help="Repeatable key=value argument; 'true'/'false' become booleans, "
        "everything else is a string. Overrides keys from --json/--json-file.",
    )
    return parser


def _repo_venv_python(repo_root, os_name=None):
    """Path of the interpreter inside <repo_root>/.venv for the given OS."""
    name = os_name if os_name is not None else os.name
    sub = ("Scripts", "python.exe") if name == "nt" else ("bin", "python")
    return Path(repo_root, ".venv", *sub)


def _reexec_in_repo_venv(repo_root=None, prefix=None, environ=None, argv=None,
                         script=None, os_name=None) -> None:
    """Re-run this script inside <repo>/.venv when started by another Python.

    No-op when the marker env var is set, the venv does not exist, or the
    current interpreter already lives in that venv. Otherwise runs the venv
    interpreter with the same arguments (stdio inherited) and exits with its
    return code. Pure stdlib and Python 3.8-compatible so an old system Python
    can get this far.
    """
    environ = os.environ if environ is None else environ
    if environ.get(REEXEC_ENV):
        return
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent.parent
    venv_py = _repo_venv_python(root, os_name)
    if not venv_py.is_file():
        return
    cur = os.path.realpath(prefix if prefix is not None else sys.prefix)
    if cur == os.path.realpath(str(root / ".venv")):
        return
    script = script if script is not None else str(Path(__file__).resolve())
    argv = sys.argv[1:] if argv is None else argv
    env = dict(environ)
    env[REEXEC_ENV] = "1"
    rc = subprocess.call([str(venv_py), script, *argv], env=env)
    sys.exit(rc)


def _missing_package_hint(exc: ModuleNotFoundError) -> None:
    """Print the setup hint for a missing third-party package and exit 1."""
    name = (exc.name or str(exc)).split(".")[0]
    print(
        f"Missing Python package '{name}'. Run ./setup.sh (macOS/Linux) or "
        "setup.cmd (Windows) from the repo root, then retry.",
        file=sys.stderr,
    )
    sys.exit(1)


def _fail(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _parse_json_object(text: str, source: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        _fail(f"{source} is not valid JSON: {e}")
    if not isinstance(data, dict):
        _fail(f"{source} must be a JSON object, got {type(data).__name__}")
    return data


def _load_arguments(ns: argparse.Namespace, stdin=None) -> dict:
    """Build the tool-arguments dict from a parsed namespace (exits on error)."""
    if ns.json_file is not None:
        try:
            with open(ns.json_file, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except OSError as e:
            _fail(f"cannot read --json-file {ns.json_file!r}: {e}")
        except UnicodeDecodeError as e:
            _fail(f"--json-file {ns.json_file!r} is not valid UTF-8: {e}")
        arguments = _parse_json_object(text, "--json-file")
    elif ns.json == "-":
        stream = stdin if stdin is not None else sys.stdin
        buf = getattr(stream, "buffer", None)
        try:
            raw = buf.read() if buf is not None else stream.read()
            text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw.lstrip("\ufeff")
        except UnicodeDecodeError as e:
            _fail(f"stdin is not valid UTF-8: {e}")
        arguments = _parse_json_object(text, "--json - (stdin)")
    elif ns.json is not None:
        arguments = _parse_json_object(ns.json, "--json")
    else:
        arguments = {}

    for item in ns.arg or []:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            _fail(f"--arg {item!r} must be in key=value form with a non-empty key")
        low = value.lower()
        if low in ("true", "false"):
            arguments[key] = low == "true"
        else:
            arguments[key] = value
    return arguments


def main() -> None:
    _reexec_in_repo_venv()
    try:
        _main()
    except ModuleNotFoundError as e:
        if (e.name or "").split(".")[0] in _LOCAL_MODULES:
            raise
        _missing_package_hint(e)


def _main() -> None:
    # Force UTF-8 so non-ASCII output never raises on Windows (cp1252) consoles.
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")

    args = _build_parser().parse_args()

    from dispatcher import TOOL_HELP, TOOL_NAMES, _dispatch
    if args.tool not in TOOL_NAMES:
        width = max(len(n) for n in TOOL_NAMES)
        listing = "\n".join(f"  {n.ljust(width)}  {TOOL_HELP.get(n, '')}" for n in TOOL_NAMES)
        _fail(f"unknown tool {args.tool!r}. Valid tools:\n{listing}")

    arguments = _load_arguments(args)

    from config import load_config
    cfg = load_config()
    reports_dir = os.environ.get("REPORTS_DIR") or cfg.reports_dir

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(cfg.attachments_dir, exist_ok=True)

    # Initialize BigQuery schema (non-fatal if unavailable)
    try:
        from tools.bigquery_tool import init_from_schema
        init_from_schema()
    except ModuleNotFoundError:
        raise
    except Exception as e:
        logger.warning(f"[BQ] Not available: {e}")

    # Pre-load incident store if _all_incidents.json exists
    combined = os.path.join(reports_dir, "_all_incidents.json")
    if os.path.exists(combined):
        from tools.incident_store import load_store
        load_store(combined)

    # Check ServiceNow credentials (non-fatal — tool will surface auth errors naturally)
    try:
        from tools.auth_tool import ensure_credentials
        ensure_credentials(instance_url=cfg.instance_url)
    except ModuleNotFoundError:
        raise
    except Exception as e:
        logger.warning(f"[AUTH] Credential check failed: {type(e).__name__}: {e}")

    # Check gcloud user credentials used by the bq CLI (non-fatal)
    try:
        from tools.gcloud_tool import ensure_gcloud_auth
        ensure_gcloud_auth()
    except ModuleNotFoundError:
        raise
    except Exception as e:
        logger.warning(f"[GCLOUD] Auth check failed: {type(e).__name__}: {e}")

    try:
        result = asyncio.run(_dispatch(args.tool, arguments, reports_dir))
        print(result)
    except ModuleNotFoundError:
        raise
    except Exception as e:
        print(f"Tool error ({args.tool}): {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
