"""
ServiceNow Reader — read/download/post with no LLM calls.
=========================================================
Extracted from rca_agent/snow_story_reader.py.
All ServiceNow REST interactions live here.
GitHub Copilot (or any external LLM) supplies the reasoning.

Authentication:
    Reads COOKIE and X_USERTOKEN from .env or environment variables.
    Get fresh values from DevTools → Network tab after logging in.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


_INCIDENT_TABLE = "incident"
_STORY_TABLE = "rm_story"
_TERMINAL_STATES = frozenset({"resolved", "closed", "cancelled", "complete", "completed"})


class ServiceNowReader:
    """
    Read-only ServiceNow client using cookies + X-UserToken from .env.

    Supports:
      - Fetching incident/story details, comments, work notes, attachments
      - Downloading attachment files to disk
      - Processing a full list-view URL into per-incident JSON
      - Posting comments (or work notes) back to a ticket
    """

    def __init__(self, instance_url: str):
        self.instance = instance_url.rstrip("/")
        self.domain = self.instance.replace("https://", "").replace("http://", "")
        self.session = requests.Session()
        self.authenticated = False

        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    # ── AUTHENTICATION ────────────────────────────────────────────────────────

    def authenticate(self, cookie: str, x_user_token: str) -> None:
        """
        Set session authentication from COOKIE and X-UserToken strings.

        Args:
            cookie:       Full Cookie header value from DevTools
            x_user_token: X-UserToken CSRF token from DevTools
        """
        if not cookie:
            raise ValueError("COOKIE is required. See .env.example for instructions.")
        if not x_user_token:
            raise ValueError("X_USERTOKEN is required. See .env.example for instructions.")

        for part in cookie.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                self.session.cookies.set(key.strip(), value.strip(), domain=self.domain)

        self.session.headers.update({
            "Accept": "application/json",
            "X-UserToken": x_user_token,
        })
        self.authenticated = True

    def validate(self) -> bool:
        """Quick check that the current session can reach the API."""
        try:
            resp = self.session.get(
                f"{self.instance}/api/now/table/{_INCIDENT_TABLE}",
                params={"sysparm_limit": 1, "sysparm_fields": "sys_id"},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ── CORE HTTP ─────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict = None, **kwargs) -> requests.Response:
        resp = self.session.get(
            f"{self.instance}{path}", params=params, timeout=30, **kwargs
        )
        if resp.status_code == 401:
            raise PermissionError(
                "401 Unauthorized — session expired. "
                "Log into ServiceNow and update COOKIE + X_USERTOKEN in .env."
            )
        if resp.status_code == 403:
            raise PermissionError(
                "403 Forbidden — missing CSRF token or insufficient permissions."
            )
        resp.raise_for_status()
        return resp

    # ── URL PARSING ───────────────────────────────────────────────────────────

    def parse_record_link(self, link: str, default_table: str = _INCIDENT_TABLE) -> tuple[str, str]:
        """
        Extract (table, sys_id) from a ServiceNow record URL or plain sys_id.
        Handles /now/nav/ui/classic/params/target/<encoded> navigation URLs.
        """
        value = (link or "").strip()
        if not value:
            raise ValueError("Empty link provided")

        nav_prefix = "/now/nav/ui/classic/params/target/"
        decoded = unquote(value)
        if nav_prefix in decoded:
            target = decoded[decoded.index(nav_prefix) + len(nav_prefix):]
            return self.parse_record_link(f"{self.instance}/{target}", default_table=default_table)

        # Plain sys_id (no URL structure)
        if "sys_id=" not in value and "://" not in value and "/" not in value:
            return default_table, value

        def _extract(url_text: str) -> tuple[str, str]:
            parsed = urlparse(url_text)
            query = parse_qs(parsed.query)

            if "uri" in query and query["uri"]:
                return _extract(unquote(query["uri"][0]))
            if "target" in query and query["target"]:
                return _extract(unquote(query["target"][0]))

            sys_id = (query.get("sys_id") or [""])[0]
            table = (query.get("sysparm_table") or [""])[0]

            if not table:
                path_seg = parsed.path.strip("/")
                if path_seg.endswith(".do"):
                    table = path_seg[:-3].split("/")[-1]

            return table or default_table, sys_id

        table, sys_id = _extract(value)
        if not sys_id:
            raise ValueError(f"Could not extract sys_id from: {link!r}")
        return table, sys_id

    def parse_list_url(self, url: str) -> tuple[str, str]:
        """
        Parse a ServiceNow list-view URL into (table_name, sysparm_query).
        Handles sysparm_tiny short links and /now/nav/ui/classic navigation URLs.
        """
        nav_prefix = "/now/nav/ui/classic/params/target/"
        parsed_url = urlparse(url)
        decoded_path = unquote(parsed_url.path)

        if nav_prefix in decoded_path:
            target = decoded_path[decoded_path.index(nav_prefix) + len(nav_prefix):]
            return self.parse_list_url(f"{self.instance}/{target}")

        path_segment = decoded_path.strip("/").split("/")[-1]
        table_name = None
        if path_segment.endswith("_list.do"):
            table_name = path_segment[:-8]
        elif path_segment.endswith(".do"):
            table_name = path_segment[:-3]

        if not table_name:
            raise ValueError(
                f"Cannot determine table name from URL: {path_segment!r}. "
                "Expected a URL like incident_list.do"
            )

        qs = parse_qs(parsed_url.query)
        tiny = (qs.get("sysparm_tiny") or [""])[0]
        query = (qs.get("sysparm_query") or [""])[0]

        if tiny and not query:
            resolved = self._resolve_tiny_url(tiny)
            if resolved:
                resolved_qs = parse_qs(urlparse(resolved).query)
                query = (resolved_qs.get("sysparm_query") or [""])[0] or resolved

        if not query:
            query = "active=true"

        return table_name, query

    def _resolve_tiny_url(self, tiny_code: str) -> str:
        """Resolve a sysparm_tiny code to the full query string via sys_tiny_url table."""
        try:
            resp = self._get(
                "/api/now/table/sys_tiny_url",
                params={
                    "sysparm_query": f"tiny={tiny_code}",
                    "sysparm_fields": "url",
                    "sysparm_limit": 1,
                    "sysparm_display_value": "true",
                },
            )
            results = resp.json().get("result", [])
            if results:
                return results[0].get("url", "")
        except Exception as e:
            print(f"[TINY] Failed to resolve '{tiny_code}': {e}", file=sys.stderr)
        return ""

    # ── RECORD FETCHING ───────────────────────────────────────────────────────

    def get_record(self, table: str, sys_id: str) -> dict:
        """Fetch a single record (any table) by sys_id."""
        params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
        }
        resp = self._get(f"/api/now/table/{table}/{sys_id}", params=params)
        return resp.json().get("result", {})

    def search_records(
        self,
        table: str,
        query: str,
        limit: int = 100,
        fields: str = None,
    ) -> list[dict]:
        """
        Search/list records with pagination.

        Args:
            table:  Table name (e.g., 'incident', 'rm_story')
            query:  ServiceNow encoded query string
            limit:  Max records to return
            fields: Comma-separated field names (all fields if None)
        """
        default_fields = {
            _INCIDENT_TABLE: (
                "sys_id,number,short_description,description,state,"
                "priority,severity,assigned_to,assignment_group,"
                "category,subcategory,sys_updated_on,sys_created_on"
            ),
            _STORY_TABLE: (
                "sys_id,number,short_description,description,state,"
                "priority,assigned_to,story_points,sprint,epic,"
                "acceptance_criteria,sys_updated_on,sys_created_on"
            ),
        }

        all_records: list[dict] = []
        offset = 0
        batch_size = min(limit, 100)

        while len(all_records) < limit:
            params = {
                "sysparm_query": f"{query}^ORDERBYDESCsys_updated_on",
                "sysparm_fields": fields or default_fields.get(table),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_limit": batch_size,
                "sysparm_offset": offset,
            }
            resp = self._get(f"/api/now/table/{table}", params=params)
            batch = resp.json().get("result", [])
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        return all_records[:limit]

    def get_incident_by_number(self, number: str) -> dict | None:
        """
        Look up an incident by its display number (e.g., INC10403788).
        Returns the raw incident record dict, or None if not found.
        """
        records = self.search_records(
            table=_INCIDENT_TABLE,
            query=f"number={number}",
            limit=1,
            fields="sys_id,number,short_description,state",
        )
        return records[0] if records else None

    # ── COMMENTS & WORK NOTES ─────────────────────────────────────────────────

    def get_comments(
        self,
        sys_id: str,
        include_work_notes: bool = True,
        table_name: str = None,
    ) -> list[dict]:
        """
        Get structured journal entries (comments + work notes) for a record.

        Returns list of dicts: {element, value, sys_created_on, sys_created_by}
        """
        query_parts = [f"element_id={sys_id}"]
        # ServiceNow ACLs on sys_journal_field require the source table name;
        # without it, entries for non-incident tables (e.g. sc_req_item) are
        # silently filtered out.
        if table_name:
            query_parts.append(f"name={table_name}")
        if not include_work_notes:
            query_parts.append("element=comments")
        query_parts.append("ORDERBYDESCsys_created_on")

        try:
            resp = self._get(
                "/api/now/table/sys_journal_field",
                params={
                    "sysparm_query": "^".join(query_parts),
                    "sysparm_limit": 500,
                    "sysparm_display_value": "true",
                },
            )
            result = resp.json().get("result", [])
            if result:
                return result
            # sys_journal_field returned 200 but empty list — ACLs silently
            # filter work notes for many cookie-auth sessions; fall through to inline.
            print("[COMMENTS] sys_journal_field returned empty; falling back to inline.", file=sys.stderr)
        except Exception as e:
            print(f"[COMMENTS] sys_journal_field failed: {e}; trying inline.", file=sys.stderr)
        return self._get_inline_comments(sys_id, table_name=table_name or _INCIDENT_TABLE)

    def _get_inline_comments(self, sys_id: str, table_name: str = _STORY_TABLE) -> list[dict]:
        """Fallback: read comments directly from the record when journal access is restricted."""
        params = {
            "sysparm_fields": "comments,work_notes",
            "sysparm_display_value": "true",
        }
        resp = self._get(f"/api/now/table/{table_name}/{sys_id}", params=params)
        record = resp.json().get("result", {})
        entries = []
        for field in ("comments", "work_notes"):
            value = record.get(field, "")
            if value:
                entries.append({
                    "element": field,
                    "value": value,
                    "sys_created_on": "N/A (inline)",
                    "sys_created_by": "N/A (inline)",
                })
        return entries

    # ── ATTACHMENTS ───────────────────────────────────────────────────────────

    def get_attachments_for(self, table_name: str, sys_id: str) -> list[dict]:
        """List all attachments for a record."""
        resp = self._get(
            "/api/now/attachment",
            params={"sysparm_query": f"table_name={table_name}^table_sys_id={sys_id}"},
        )
        return resp.json().get("result", [])

    def download_attachment(
        self,
        attachment_sys_id: str,
        file_name: str,
        output_dir: str,
    ) -> str:
        """
        Download a single attachment file.

        Returns:
            Absolute path to the downloaded file.
        """
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, file_name)

        resp = self._get(
            f"/api/now/attachment/{attachment_sys_id}/file",
            stream=True,
        )
        with open(filepath, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"[DOWNLOAD] {file_name} ({size_kb:.1f} KB) → {filepath}", file=sys.stderr)
        return filepath

    def download_all_attachments(
        self,
        table_name: str,
        sys_id: str,
        output_dir: str,
    ) -> list[str]:
        """
        Download all attachments for a record.

        Returns:
            List of downloaded file paths.
        """
        attachments = self.get_attachments_for(table_name, sys_id)
        paths = []
        for att in attachments:
            path = self.download_attachment(
                attachment_sys_id=att["sys_id"],
                file_name=att.get("file_name", f"file_{att['sys_id']}"),
                output_dir=output_dir,
            )
            paths.append(path)
        return paths

    # ── FULL INCIDENT REPORT ──────────────────────────────────────────────────

    def get_full_incident_report(
        self,
        sys_id: str,
        table_name: str = _INCIDENT_TABLE,
        download_files: bool = False,
        attachments_dir: str = "./reports/attachments",
    ) -> dict:
        """
        Fetch incident details, comments, work notes, and attachment metadata.
        Optionally download attachment files to disk.

        Returns:
            Structured report dict compatible with IncidentStore.
        """
        incident = self.get_record(table_name, sys_id)
        journal = self.get_comments(sys_id, include_work_notes=True, table_name=table_name)
        comments = [e for e in journal if e.get("element") == "comments"]
        work_notes = [e for e in journal if e.get("element") == "work_notes"]

        attachments = self.get_attachments_for(table_name, sys_id)
        images = [a for a in attachments if a.get("content_type", "").startswith("image/")]
        files = [a for a in attachments if not a.get("content_type", "").startswith("image/")]

        downloaded_paths: list[str] = []
        if download_files and attachments:
            incident_number = incident.get("number") or sys_id
            safe_number = str(incident_number).replace("/", "_").replace("\\", "_")
            save_dir = os.path.join(attachments_dir, safe_number)
            downloaded_paths = self.download_all_attachments(table_name, sys_id, save_dir)

        related_stories = self._get_related_stories(sys_id)

        return {
            "incident": {
                "sys_id": incident.get("sys_id"),
                "number": incident.get("number"),
                "short_description": incident.get("short_description"),
                "description": incident.get("description"),
                "state": incident.get("state"),
                "priority": incident.get("priority"),
                "severity": incident.get("severity"),
                "assigned_to": incident.get("assigned_to"),
                "assignment_group": incident.get("assignment_group"),
                "category": incident.get("category"),
                "subcategory": incident.get("subcategory"),
                "created": incident.get("sys_created_on"),
                "updated": incident.get("sys_updated_on"),
            },
            "comments": [
                {
                    "date": c.get("sys_created_on"),
                    "author": c.get("sys_created_by"),
                    "text": c.get("value"),
                }
                for c in comments
            ],
            "work_notes": [
                {
                    "date": n.get("sys_created_on"),
                    "author": n.get("sys_created_by"),
                    "text": n.get("value"),
                }
                for n in work_notes
            ],
            "attachments": {
                "images": [
                    {"name": a["file_name"], "id": a["sys_id"], "type": a["content_type"]}
                    for a in images
                ],
                "files": [
                    {"name": a["file_name"], "id": a["sys_id"], "type": a["content_type"]}
                    for a in files
                ],
            },
            "related_stories": related_stories,
            "downloaded_files": downloaded_paths,
        }

    def _get_related_stories(self, incident_sys_id: str, limit: int = 20) -> list[dict]:
        """Find stories linked to an incident via direct parent or task_rel_task."""
        related: list[dict] = []
        seen: set[str] = set()

        try:
            direct = self.search_records(
                _STORY_TABLE,
                query=f"parent={incident_sys_id}",
                limit=limit,
            )
            for row in direct:
                sid = row.get("sys_id")
                if sid and sid not in seen:
                    related.append({
                        "sys_id": sid,
                        "number": row.get("number"),
                        "short_description": row.get("short_description"),
                        "state": row.get("state"),
                        "updated": row.get("sys_updated_on"),
                    })
                    seen.add(sid)
        except Exception:
            pass

        return related[:limit]

    # ── LIST VIEW BULK DOWNLOAD ───────────────────────────────────────────────

    def fetch_incidents_from_list(
        self,
        list_url: str,
        output_dir: str,
        download_files: bool = False,
        limit: int = 1000,
    ) -> tuple[list[dict], str]:
        """
        Fetch all incidents from a ServiceNow list-view URL.

        Steps:
          1. Parse the URL to extract table + query
          2. Fetch lightweight list (sys_id, number, state)
          3. For each non-terminal incident, fetch full report
          4. Write individual JSON and combined _all_incidents.json

        Args:
            list_url:      ServiceNow list-view URL (sysparm_tiny supported)
            output_dir:    Directory for JSON output
            download_files: Also download attachment files
            limit:         Max incidents to process

        Returns:
            (reports, combined_json_path)
        """
        table_name, query = self.parse_list_url(list_url)
        print(f"[FETCH] Table: {table_name}, limit: {limit}", file=sys.stderr)

        records = self.search_records(
            table=table_name,
            query=query,
            limit=limit,
            fields="sys_id,number,short_description,state,priority",
        )

        if not records:
            print("[FETCH] No records found.", file=sys.stderr)
            return [], ""

        # For the incident table, skip terminal states
        if table_name == _INCIDENT_TABLE:
            records = [
                r for r in records
                if (r.get("state") or "").strip().lower() not in _TERMINAL_STATES
            ]
            print(f"[FETCH] {len(records)} non-terminal incidents.", file=sys.stderr)

        os.makedirs(output_dir, exist_ok=True)
        all_reports: list[dict] = []
        errors: list[dict] = []

        for idx, rec in enumerate(records, 1):
            sys_id = rec.get("sys_id", "")
            number = rec.get("number", sys_id)
            short = rec.get("short_description", "")[:60]
            print(f"[{idx}/{len(records)}] {number} — {short}", file=sys.stderr)

            try:
                report = self.get_full_incident_report(
                    sys_id=sys_id,
                    table_name=table_name,
                    download_files=download_files,
                    attachments_dir=os.path.join(output_dir, "attachments"),
                )
                all_reports.append(report)

                safe_number = number.replace("/", "_").replace("\\", "_")
                with open(os.path.join(output_dir, f"{safe_number}.json"), "w", encoding="utf-8") as fh:
                    json.dump(report, fh, indent=2, ensure_ascii=False)

            except Exception as exc:
                print(f"  [ERROR] {number}: {exc}", file=sys.stderr)
                errors.append({"number": number, "error": str(exc)})

        combined_path = os.path.join(output_dir, "_all_incidents.json")
        with open(combined_path, "w", encoding="utf-8") as fh:
            json.dump(all_reports, fh, indent=2, ensure_ascii=False)

        print(
            f"[FETCH] Done: {len(all_reports)} processed, {len(errors)} errors. "
            f"Saved to {combined_path}",
            file=sys.stderr,
        )
        return all_reports, combined_path

    def upsert_incident_report(self, report: dict, reports_dir: str) -> tuple[str, str]:
        """
        Save/merge one incident report into per-incident JSON and _all_incidents.json.

        Returns:
            (individual_json_path, combined_json_path)
        """
        os.makedirs(reports_dir, exist_ok=True)
        incident = report.get("incident", {})
        number = incident.get("number") or incident.get("sys_id") or "unknown"
        safe_number = str(number).replace("/", "_").replace("\\", "_")

        individual_path = os.path.join(reports_dir, f"{safe_number}.json")
        with open(individual_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

        combined_path = os.path.join(reports_dir, "_all_incidents.json")
        combined: list[dict] = []
        if os.path.exists(combined_path):
            try:
                with open(combined_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        combined = data
            except Exception:
                pass

        target_sys_id = incident.get("sys_id")
        target_number = incident.get("number")
        replaced = False
        for i, item in enumerate(combined):
            existing = item.get("incident", {}) if isinstance(item, dict) else {}
            if (
                (target_sys_id and existing.get("sys_id") == target_sys_id)
                or (target_number and existing.get("number") == target_number)
            ):
                combined[i] = report
                replaced = True
                break

        if not replaced:
            combined.append(report)

        with open(combined_path, "w", encoding="utf-8") as fh:
            json.dump(combined, fh, indent=2, ensure_ascii=False)

        return individual_path, combined_path

    # ── COMMENT POSTING ───────────────────────────────────────────────────────

    def post_comment(
        self,
        incident_sys_id: str,
        text: str,
        as_work_note: bool = False,
        table: str = None,
    ) -> bool:
        """
        Post a comment (or work note) to a ServiceNow record.

        Args:
            incident_sys_id: The record sys_id (NOT the number like INC0012345)
            text:            Plain-text comment body
            as_work_note:    True → internal work note; False → customer-visible comment
            table:           Table name (defaults to 'incident')

        Returns:
            True on success, False on failure.
        """
        target_table = table or _INCIDENT_TABLE
        field = "work_notes" if as_work_note else "comments"
        label = "work note" if as_work_note else "comment"

        try:
            resp = self.session.patch(
                f"{self.instance}/api/now/table/{target_table}/{incident_sys_id}",
                json={field: text},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                print(f"[COMMENT] ✓ Posted {label} to {incident_sys_id}", file=sys.stderr)
                return True
            print(
                f"[COMMENT] ✗ HTTP {resp.status_code}: {resp.text[:200]}",
                file=sys.stderr,
            )
            return False
        except Exception as e:
            print(f"[COMMENT] ✗ Exception: {e}", file=sys.stderr)
            return False
