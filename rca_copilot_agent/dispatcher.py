"""
dispatcher.py - Tool routing for rca_copilot_agent (used by run_tool.py).
=========================================================================
Routes a tool name + JSON arguments to the ServiceNow / BigQuery / RCA-report
implementations under ``tools/``. Contains NO LLM calls: the reasoning stays in
the calling assistant (GitHub Copilot, Claude Code, ...).

Run tools through the CLI: ``python3 rca_copilot_agent/run_tool.py <tool> ...``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Every tool handled by _dispatch.
TOOL_NAMES: tuple[str, ...] = (
    "fetch_incidents",
    "get_incident",
    "get_incident_summary",
    "list_incidents",
    "analyze_incident",
    "search_incidents",
    "post_comment",
    "extract_identifiers",
    "query_bigquery",
    "get_schema",
    "list_bq_tables",
    "download_attachments",
    "get_rca_template",
    "save_rca_report",
    "send_rca_email",
)


# One-line help per tool (shown by `run_tool.py --help` and unknown-tool errors).
TOOL_HELP: dict[str, str] = {
    "fetch_incidents": "Download all incidents from a SNOW list-view URL (list_url) to local JSON.",
    "get_incident": "Fetch one incident live from SNOW by number (incident_number) and reload the store.",
    "get_incident_summary": "Read a locally cached incident's full text (description, comments, work notes).",
    "list_incidents": "List all locally cached incidents (number, state, priority, title).",
    "analyze_incident": "ONE-STOP: fetch + attachments + identifiers for one incident (incident_number).",
    "search_incidents": "Keyword-search across all local incidents (keyword).",
    "post_comment": "Preview a comment/work note; posts only with confirmed=true (after user approval).",
    "extract_identifiers": "Extract order IDs / emails / EAN codes from an incident (incident_number).",
    "query_bigquery": "Run a read-only SELECT (sql); pass incident_number to log evidence.",
    "get_schema": "Get a BQ table schema from local schema.json (table_name).",
    "list_bq_tables": "List all BQ tables with their RCA purpose.",
    "download_attachments": "Download attachment files for an incident (incident_number).",
    "get_rca_template": "Print the canonical RCA report template (call before writing an RCA).",
    "save_rca_report": "Validate + save a completed RCA report to disk.",
    "send_rca_email": "Email all saved, not-yet-emailed reports.",
}

# Allow importing sibling packages (config, tools) when run from the repo root.
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

        # Detect table from number prefix
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

    elif name == "analyze_incident":
        number = arguments["incident_number"]
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        store = get_store()

        # Fetch live if not in local store
        inc = store.get_incident(number)
        if not inc:
            try:
                reader, cfg = _build_reader()
                # Detect table from number prefix: RITM → sc_req_item, else incident
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

        # 1. Full incident summary
        summary = store.get_incident_summary(number)

        # 2. Structured identifiers
        ids = store.extract_identifiers(number)
        ids_section = (
            f"IDENTIFIERS FOUND:\n{json.dumps(ids, indent=2)}"
            if ids
            else "IDENTIFIERS: None found (no order IDs, emails, or EAN codes)."
        )

        # 3. Download attachments
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
        number = arguments["incident_number"]
        text = arguments["text"]
        as_work_note = arguments.get("as_work_note", False)

        # Detect correct table from ticket number prefix
        if number.upper().startswith("RITM"):
            table = "sc_req_item"
        elif number.upper().startswith("TASK"):
            table = "sc_task"
        else:
            table = "incident"

        # Confirmation gate: nothing is built or sent until the user approved the text.
        confirmed = arguments.get("confirmed", False)
        if not (confirmed is True or str(confirmed).strip().lower() == "true"):
            kind = "work note (internal)" if as_work_note else "comment (customer-visible)"
            return (
                "⚠ NOT POSTED — preview only.\n"
                f"Target: {number} (table: {table})\n"
                f"Type: {kind}\n"
                "Text:\n---\n"
                f"{text}\n"
                "---\n"
                "Show this to the user. Only after they explicitly approve, call post_comment "
                "again with the same arguments plus confirmed=true."
            )

        reader, _cfg = _build_reader()

        # Resolve sys_id — try local store first, then live lookup on correct table
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

    elif name == "extract_identifiers":
        _ensure_store_loaded(reports_dir)
        from tools.incident_store import get_store
        ids = get_store().extract_identifiers(arguments["incident_number"])
        if not ids:
            return f"No structured identifiers found in {arguments['incident_number']}."
        return json.dumps(ids, indent=2)

    elif name == "query_bigquery":
        from tools.bigquery_tool import is_enabled, _BQ_UNAVAILABLE
        if not is_enabled():
            return _BQ_UNAVAILABLE
        from tools.bigquery_tool import query_bigquery_result
        sql = arguments["sql"]
        rationale = arguments.get("rationale", "")
        result = query_bigquery_result(sql, rationale)
        incident_number = arguments.get("incident_number")
        if incident_number:
            try:
                from tools import rca_report_tool
                rca_report_tool.record_query(
                    reports_dir,
                    incident_number,
                    sql=sql,
                    rationale=rationale,
                    success=result.success,
                    row_count=result.row_count,
                    error=result.error,
                )
            except Exception as exc:  # evidence logging must never break the query
                logger.warning(f"[RCA] Could not record BQ evidence for {incident_number}: {exc}")
        return result.to_llm_context()

    elif name == "get_schema":
        from tools.bigquery_tool import get_schema_from_file
        return get_schema_from_file(arguments.get("table_name", ""))

    elif name == "list_bq_tables":
        from tools.bigquery_tool import get_schema_from_file
        return get_schema_from_file("")

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

        # Detect the source table from the ticket number prefix
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

    elif name == "get_rca_template":
        from tools import rca_report_tool
        return rca_report_tool.get_rca_template()

    elif name == "save_rca_report":
        from tools import rca_report_tool
        number = arguments["incident_number"]
        report_text = arguments["report_text"]

        incident_meta: dict[str, str] = {}
        try:
            _ensure_store_loaded(reports_dir)
            from tools.incident_store import get_store
            inc = get_store().get_incident(number)
            raw = (inc or {}).get("incident", {}) or {}
            for key in _REPORT_META_KEYS:
                val = _display_value(raw.get(key))
                if val:
                    incident_meta[key] = val
        except Exception as exc:
            logger.warning(f"[RCA] Could not load incident metadata for {number}: {exc}")

        try:
            saved = rca_report_tool.save_report(reports_dir, number, report_text, incident_meta)
        except ValueError as exc:
            return f"✗ RCA report NOT saved\n{exc}"

        lines = [
            f"✓ RCA report saved: {saved['path']}",
            f"Evidence: {saved['evidence_count']} BigQuery query(ies) appended to the report.",
        ]
        lines.extend(f"⚠ {w}" for w in saved.get("warnings", []))
        return "\n".join(lines)

    elif name == "send_rca_email":
        from config import load_smtp_config
        smtp = load_smtp_config()
        if not smtp.enabled:
            return (
                "✗ SMTP not configured. Set SMTP_HOST, SMTP_FROM, and SMTP_TO in .env "
                "to enable email notifications."
            )

        from tools.email_tool import send_rca_email as _send
        from tools import rca_report_tool
        subject = arguments.get("subject") or "RCA Analysis Complete — Please Review"
        session_summary = arguments["session_summary"]
        raw_numbers = arguments.get("incident_numbers")
        if isinstance(raw_numbers, str):
            raw_numbers = re.split(r"[,\s]+", raw_numbers)
        if isinstance(raw_numbers, (list, tuple, set)):
            numbers = [str(n).strip() for n in raw_numbers if n is not None and str(n).strip()]
        else:
            numbers = []
        entries = rca_report_tool.pending_reports(reports_dir, numbers or None)

        result = _send(
            smtp_host=smtp.host,
            smtp_port=smtp.port,
            smtp_user=smtp.user,
            smtp_password=smtp.password,
            smtp_from=smtp.from_addr,
            smtp_to=smtp.to_addrs,
            use_tls=smtp.use_tls,
            subject=subject,
            session_summary=session_summary,
            report_entries=entries,
            verify_ssl=smtp.verify_ssl,
        )
        result = str(result)
        if result.startswith("✓"):
            if entries:
                try:
                    rca_report_tool.mark_emailed(reports_dir, [e["path"] for e in entries])
                except Exception as exc:
                    logger.warning(f"[RCA] mark_emailed failed after successful send: {exc}")
                    result += (
                        f"\n⚠ Email sent, but reports could not be marked as emailed "
                        f"({type(exc).__name__}: {exc}) — they may be attached again next time."
                    )
            attached = ", ".join(str(e.get("incident_number")) for e in entries if e.get("incident_number"))
            result += f"\nAttached incidents: {attached or 'none'}"
        return result

    else:
        return f"Unknown tool: {name}"


_REPORT_META_KEYS = (
    "short_description", "state", "priority", "assignment_group", "opened_at", "sys_updated_on",
)


def _display_value(value) -> str:
    """Normalise a SNOW field (str, or {"display_value": ..., "value": ...}) to text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("display_value") or value.get("value")
        if value is None:
            return ""
    return str(value).strip()


def _ensure_store_loaded(reports_dir: str) -> None:
    """Load the incident store if it is empty."""
    from tools.incident_store import get_store
    store = get_store()
    if not store.incidents:
        combined = os.path.join(reports_dir, "_all_incidents.json")
        if os.path.exists(combined):
            from tools.incident_store import load_store
            count = load_store(combined)
            logger.info(f"[RCA] Loaded {count} incidents from {combined}")
        else:
            logger.warning(
                f"[RCA] No incidents file at {combined}. "
                "Call fetch_incidents first."
            )


def _resolve_sys_id(number: str, reader, reports_dir: str, table: str = "incident") -> str:
    """
    Resolve an incident number to its sys_id.
    Tries the local store first; falls back to a live ServiceNow search on the correct table.
    """
    from tools.incident_store import get_store
    inc = get_store().get_incident(number)
    if inc:
        return inc.get("incident", {}).get("sys_id", "")

    # Live lookup — must search the correct table (RITM → sc_req_item, TASK → sc_task)
    records = reader.search_records(
        table=table,
        query=f"number={number}",
        limit=1,
        fields="sys_id,number,short_description,state",
    )
    return records[0].get("sys_id", "") if records else ""
