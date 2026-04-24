"""
ServiceNow Reader — .env Authentication
=======================================
Reads stories (and incidents for search) from L'Oréal ServiceNow
using Cookie and X-UserToken values from a local .env file.

SETUP:
    pip install requests

Required .env keys:
    COOKIE=<full cookie header value>
    X_USERTOKEN=<value from request header X-UserToken>

USAGE:
    python snow_story_reader.py --snow-instance https://loreal.service-now.com --story <sys_id>
    python snow_story_reader.py --snow-instance https://loreal.service-now.com --incident-link "https://.../incident.do?sys_id=..."
    python snow_story_reader.py --snow-instance https://loreal.service-now.com --search "failed login" --search-table incident
    python snow_story_reader.py --snow-instance https://loreal.service-now.com --list-link "https://loreal.service-now.com/now/nav/ui/classic/params/target/incident_list.do%3Fsysparm_tiny%3D..."
    python snow_story_reader.py --snow-instance https://loreal.service-now.com --list-link "<list-url>" --download --report-dir ./my_reports --limit 500
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

INSTANCE_URL = ""
TABLE = "rm_story"
INCIDENT_TABLE = "incident"
DOWNLOAD_DIR = "./attachments"


# ─────────────────────────────────────────────
# SERVICENOW CLIENT
# ─────────────────────────────────────────────

class ServiceNowReader:
    """
    Read-only ServiceNow client using cookies and token from .env.
    
    Supports:
      - Fetching story details (description, fields, acceptance criteria)
      - Fetching structured comments and work notes
      - Listing and downloading attachments/images
    """

    def __init__(self, instance_url: str = INSTANCE_URL):
        self.instance = instance_url.rstrip("/")
        self.domain = self.instance.replace("https://", "").replace("http://", "")
        self.session = requests.Session()
        self.authenticated = False

        # Retry config for reliability
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    # ── AUTHENTICATION ──────────────────────

    @staticmethod
    def load_env_file(env_path: Path) -> dict:
        """Load simple KEY=VALUE entries from a .env file."""
        data = {}
        if not env_path.exists():
            return data

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            data[key] = value

        return data

    def authenticate_from_env(self, env_file: str = ".env"):
        """
        Authenticate using COOKIE and X-UserToken from .env.

        Required keys:
          - COOKIE
          - X_USERTOKEN (or X-UserToken / X-usertoken)
        """
        env_candidates = [
            Path.cwd() / env_file,
            Path(__file__).resolve().parent / env_file,
        ]

        env_data = {}
        selected_env = None
        for candidate in env_candidates:
            env_data = self.load_env_file(candidate)
            if env_data:
                selected_env = candidate
                break

        if not selected_env:
            print("[AUTH] ✗ .env file not found or empty.")
            print("       Expected keys: COOKIE and X_USERTOKEN")
            sys.exit(1)

        cookie_string = env_data.get("COOKIE", "").strip()
        csrf_token = (
            env_data.get("X_USERTOKEN")
            or env_data.get("X-UserToken")
            or env_data.get("X-usertoken")
            or ""
        ).strip()

        if not cookie_string:
            print(f"[AUTH] ✗ Missing COOKIE in {selected_env}")
            sys.exit(1)
        if not csrf_token:
            print(f"[AUTH] ✗ Missing X_USERTOKEN in {selected_env}")
            sys.exit(1)

        print(f"[AUTH] Loading auth values from {selected_env}")
        self.authenticate_manual(cookie_string=cookie_string, csrf_token=csrf_token)

    def authenticate_manual(self, cookie_string: str, csrf_token: str = ""):
        """
        Authenticate with manually copied values from DevTools.
        
        Args:
            cookie_string: Full Cookie header from Network tab
                           e.g., "JSESSIONID=ABC123; glide_user_session=XYZ789"
            csrf_token:    X-UserToken value (optional, will try to bootstrap if empty)
        """
        print("[AUTH] Using manual cookie authentication...")

        # Parse cookie string
        for part in cookie_string.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                self.session.cookies.set(key.strip(), value.strip(), domain=self.domain)

        if csrf_token:
            self.session.headers.update({
                "Accept": "application/json",
                "X-UserToken": csrf_token,
            })
            self.authenticated = True
            print("[AUTH] ✓ Manual authentication configured with CSRF token")
        else:
            print("[AUTH] ✗ X-UserToken was empty")
            sys.exit(1)

    def _bootstrap_csrf_token(self):
        """
        Get CSRF token using the sn_devstudio endpoint.
        This endpoint returns the 'ck' token using only session cookies.
        """
        print("[AUTH] Bootstrapping CSRF token...")

        try:
            resp = self.session.get(
                f"{self.instance}/sn_devstudio_/v1/get_publish_info",
                timeout=15
            )

            if resp.status_code == 200:
                data = resp.json()
                ck = data.get("ck", "")
                if ck:
                    self.session.headers.update({
                        "Accept": "application/json",
                        "X-UserToken": ck,
                    })
                    self.authenticated = True
                    print("[AUTH] ✓ CSRF token obtained successfully")
                    return
                else:
                    print("[AUTH] ✗ CSRF token was empty in response")

            elif resp.status_code == 401:
                print("[AUTH] ✗ 401 — Session expired or invalid")

            elif resp.status_code == 403:
                print("[AUTH] ✗ 403 — Forbidden (endpoint may be blocked)")

            else:
                print(f"[AUTH] ✗ Unexpected status: {resp.status_code}")

        except Exception as e:
            print(f"[AUTH] ✗ Failed to bootstrap CSRF: {e}")

        # Fallback: try without CSRF (some instances allow GET without it)
        print("[AUTH] Attempting without CSRF token (read-only may still work)...")
        self.session.headers.update({"Accept": "application/json"})
        self.authenticated = True

    def validate(self) -> bool:
        """Quick validation that the session works."""
        try:
            resp = self.session.get(
                f"{self.instance}/api/now/table/{TABLE}",
                params={"sysparm_limit": 1, "sysparm_fields": "sys_id"},
                timeout=15
            )
            if resp.status_code == 200:
                print("[AUTH] ✓ Session validated — API access confirmed")
                return True
            else:
                print(f"[AUTH] ✗ Validation failed with status {resp.status_code}")
                if resp.status_code == 401:
                    print("       → Session expired. Log into ServiceNow again and retry.")
                return False
        except Exception as e:
            print(f"[AUTH] ✗ Validation error: {e}")
            return False

    # ── CORE API METHOD ─────────────────────

    def _get(self, path: str, params: dict = None, **kwargs) -> requests.Response:
        """Authenticated GET request with error handling."""
        resp = self.session.get(f"{self.instance}{path}", params=params, timeout=30, **kwargs)

        if resp.status_code == 401:
            raise PermissionError(
                "\n401 Unauthorized — Session expired.\n"
                "Fix: Log into ServiceNow in your browser and re-run the script."
            )
        if resp.status_code == 403:
            raise PermissionError(
                "\n403 Forbidden — Missing CSRF token or insufficient permissions.\n"
                "Fix: Try --manual mode and provide X-UserToken from DevTools."
            )

        resp.raise_for_status()
        return resp

    def parse_record_link(self, link: str, default_table: str = INCIDENT_TABLE) -> tuple:
        """
        Extract (table, sys_id) from a ServiceNow URL or plain sys_id.
        Supports nav_to links with encoded uri.
        """
        value = (link or "").strip()
        if not value:
            raise ValueError("Empty link provided")

        # Handle classic navigation URLs where target URL is URL-encoded in path.
        nav_prefix = "/now/nav/ui/classic/params/target/"
        decoded_value = unquote(value)
        if nav_prefix in decoded_value:
            target = decoded_value[decoded_value.index(nav_prefix) + len(nav_prefix):]
            return self.parse_record_link(f"{self.instance}/{target}", default_table=default_table)

        if "sys_id=" not in value and "://" not in value and "/" not in value:
            return default_table, value

        def _extract(url_text: str) -> tuple:
            parsed = urlparse(url_text)
            query = parse_qs(parsed.query)

            if "uri" in query and query["uri"]:
                return _extract(unquote(query["uri"][0]))

            if "target" in query and query["target"]:
                return _extract(unquote(query["target"][0]))

            sys_id = (query.get("sys_id") or [""])[0]
            table = (query.get("sysparm_table") or [""])[0]

            if not table:
                path = parsed.path.strip("/")
                if path.endswith(".do"):
                    table = path[:-3].split("/")[-1]

            return table, sys_id

        table, sys_id = _extract(value)
        if not sys_id:
            raise ValueError("Could not find sys_id in link")

        return (table or default_table), sys_id

    # ── STORY DETAILS ───────────────────────

    def get_story(self, sys_id: str) -> dict:
        """
        Get full details of a single story.
        
        Args:
            sys_id: The story's sys_id (from the URL)
        
        Returns:
            Dict with all story fields (display values)
        """
        params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
        }
        resp = self._get(f"/api/now/table/{TABLE}/{sys_id}", params=params)
        record = resp.json().get("result", {})
        print(f"[STORY] Fetched: {record.get('number', 'N/A')} — {record.get('short_description', 'N/A')}")
        return record

    def get_incident(self, sys_id: str) -> dict:
        """Get full details of a single incident."""
        return self.get_record(INCIDENT_TABLE, sys_id)

    def get_record(self, table: str, sys_id: str) -> dict:
        """Get full details of a single record from any table."""
        params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
        }
        resp = self._get(f"/api/now/table/{table}/{sys_id}", params=params)
        record = resp.json().get("result", {})
        print(f"[{table.upper()}] Fetched: {record.get('number', 'N/A')} — {record.get('short_description', 'N/A')}")
        return record

    def search_records(self, table: str, query: str, limit: int = 50,
                       fields: str = None) -> list:
        """
        Search/list records with filtering and pagination.
        
        Args:
            table:  Table name to query (e.g., rm_story, incident)
            query:  ServiceNow encoded query (e.g., "active=true^priority=1")
            limit:  Max records to return
            fields: Comma-separated field names (returns all if None)
        
        Returns:
            List of record dicts
        """
        default_fields_by_table = {
            TABLE: (
                "sys_id,number,short_description,description,state,"
                "priority,assigned_to,story_points,sprint,epic,"
                "acceptance_criteria,sys_updated_on,sys_created_on"
            ),
            INCIDENT_TABLE: (
                "sys_id,number,short_description,description,state,"
                "priority,severity,assigned_to,assignment_group,"
                "category,subcategory,sys_updated_on,sys_created_on"
            ),
        }

        all_records = []
        offset = 0
        batch_size = min(limit, 100)

        while len(all_records) < limit:
            params = {
                "sysparm_query": f"{query}^ORDERBYDESCsys_updated_on",
                "sysparm_fields": fields or default_fields_by_table.get(table),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
                "sysparm_limit": batch_size,
                "sysparm_offset": offset,
            }

            resp = self._get(f"/api/now/table/{table}", params=params)
            records = resp.json().get("result", [])

            if not records:
                break

            all_records.extend(records)
            if len(records) < batch_size:
                break
            offset += batch_size

        print(f"[SEARCH] Found {len(all_records)} records in table '{table}'")
        return all_records[:limit]

    def search_stories(self, query: str = "active=true", limit: int = 50,
                       fields: str = None) -> list:
        """Search/list stories with filtering and pagination."""
        return self.search_records(table=TABLE, query=query, limit=limit, fields=fields)

    def search_incidents(self, query: str = "active=true", limit: int = 50,
                         fields: str = None) -> list:
        """Search/list incidents with filtering and pagination."""
        return self.search_records(table=INCIDENT_TABLE, query=query, limit=limit, fields=fields)

    # ── COMMENTS & WORK NOTES ───────────────

    def get_comments(self, sys_id: str, include_work_notes: bool = True) -> list:
        """
        Get structured comments and work notes for a story.
        
        Queries sys_journal_field table for individual entries with
        timestamp, author, and content.
        
        Args:
            sys_id:             Story sys_id
            include_work_notes: Also fetch work_notes (not just comments)
        
        Returns:
            List of dicts with: element, value, sys_created_on, sys_created_by
        """
        query_parts = [f"element_id={sys_id}"]

        if not include_work_notes:
            query_parts.append("element=comments")

        query_parts.append("ORDERBYDESCsys_created_on")

        params = {
            "sysparm_query": "^".join(query_parts),
            "sysparm_limit": 500,
        }

        try:
            resp = self._get("/api/now/table/sys_journal_field", params=params)
            entries = resp.json().get("result", [])
            print(f"[COMMENTS] Found {len(entries)} journal entries for {sys_id}")
            return entries

        except Exception as e:
            # Fallback: get comments inline from the story record itself
            print(f"[COMMENTS] sys_journal_field query failed: {e}")
            print("[COMMENTS] Falling back to inline comments...")
            return self._get_inline_comments(sys_id)

    def _get_inline_comments(self, sys_id: str) -> list:
        """
        Fallback: get comments from the story record using sysparm_display_value.
        Less structured but works when sys_journal_field access is restricted.
        """
        params = {
            "sysparm_fields": "comments,work_notes",
            "sysparm_display_value": "true",
        }
        resp = self._get(f"/api/now/table/{TABLE}/{sys_id}", params=params)
        record = resp.json().get("result", {})

        entries = []
        for field in ["comments", "work_notes"]:
            value = record.get(field, "")
            if value:
                entries.append({
                    "element": field,
                    "value": value,
                    "sys_created_on": "N/A (inline)",
                    "sys_created_by": "N/A (inline)",
                    "note": "Retrieved via inline display_value — individual entries not separated"
                })

        return entries

    # ── ATTACHMENTS ─────────────────────────

    def get_attachments_for(self, table_name: str, sys_id: str) -> list:
        """
        List all attachments for a given table record.
        
        Returns:
            List of attachment metadata dicts
        """
        params = {
            "sysparm_query": f"table_name={table_name}^table_sys_id={sys_id}",
        }
        resp = self._get("/api/now/attachment", params=params)
        attachments = resp.json().get("result", [])
        print(f"[ATTACH] Found {len(attachments)} attachments for {table_name}:{sys_id}")
        return attachments

    def get_attachments(self, sys_id: str) -> list:
        """Backward-compatible wrapper for story attachments."""
        return self.get_attachments_for(TABLE, sys_id)

    def download_attachment(self, attachment_sys_id: str, file_name: str,
                            content_type: str = "*/*", output_dir: str = DOWNLOAD_DIR) -> str:
        """
        Download a single attachment file.
        
        Returns:
            Path to downloaded file
        """
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, file_name)

        resp = self._get(
            f"/api/now/attachment/{attachment_sys_id}/file",
            stream=True,
        )

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"[DOWNLOAD] {file_name} ({size_kb:.1f} KB) → {filepath}")
        return filepath

    def download_all_attachments(self, sys_id: str, output_dir: str = None,
                                 table_name: str = TABLE) -> list:
        """
        Download all attachments for a story.
        
        Returns:
            List of downloaded file paths
        """
        attachments = self.get_attachments_for(table_name, sys_id)
        if not attachments:
            return []

        save_dir = output_dir or os.path.join(DOWNLOAD_DIR, sys_id)
        paths = []

        for att in attachments:
            path = self.download_attachment(
                attachment_sys_id=att["sys_id"],
                file_name=att.get("file_name", f"file_{att['sys_id']}"),
                content_type=att.get("content_type", "*/*"),
                output_dir=save_dir,
            )
            paths.append(path)

        return paths

    # ── COMBINED: FULL STORY REPORT ─────────

    def get_full_story_report(self, sys_id: str, download_files: bool = False) -> dict:
        """
        Get everything about a story in one call:
        details, comments, work notes, and attachment list.
        
        Args:
            sys_id:         Story sys_id
            download_files: Also download attachment files to disk
        
        Returns:
            Complete story report dict
        """
        print(f"\n{'='*60}")
        print(f"Fetching full report for story: {sys_id}")
        print(f"{'='*60}")

        # 1. Story details
        story = self.get_story(sys_id)

        # 2. Comments and work notes
        journal = self.get_comments(sys_id, include_work_notes=True)
        comments = [e for e in journal if e.get("element") == "comments"]
        work_notes = [e for e in journal if e.get("element") == "work_notes"]

        # 3. Attachments
        attachments = self.get_attachments_for(TABLE, sys_id)
        images = [a for a in attachments if a.get("content_type", "").startswith("image/")]
        files = [a for a in attachments if not a.get("content_type", "").startswith("image/")]

        downloaded_paths = []
        if download_files and attachments:
            downloaded_paths = self.download_all_attachments(sys_id, table_name=TABLE)

        report = {
            "story": {
                "sys_id": story.get("sys_id"),
                "number": story.get("number"),
                "short_description": story.get("short_description"),
                "description": story.get("description"),
                "state": story.get("state"),
                "priority": story.get("priority"),
                "assigned_to": story.get("assigned_to"),
                "story_points": story.get("story_points"),
                "sprint": story.get("sprint"),
                "epic": story.get("epic"),
                "acceptance_criteria": story.get("acceptance_criteria"),
                "created": story.get("sys_created_on"),
                "updated": story.get("sys_updated_on"),
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
                "images": [{"name": a["file_name"], "id": a["sys_id"],
                            "type": a["content_type"]} for a in images],
                "files": [{"name": a["file_name"], "id": a["sys_id"],
                           "type": a["content_type"]} for a in files],
            },
            "downloaded_files": downloaded_paths,
        }

        # Print summary
        s = report["story"]
        print(f"\n--- Story: {s['number']} ---")
        print(f"Title:       {s['short_description']}")
        print(f"State:       {s['state']}")
        print(f"Priority:    {s['priority']}")
        print(f"Assigned To: {s['assigned_to']}")
        print(f"Points:      {s['story_points']}")
        print(f"Sprint:      {s['sprint']}")
        print(f"Description: {(s['description'] or 'N/A')[:200]}...")
        print(f"Comments:    {len(report['comments'])}")
        print(f"Work Notes:  {len(report['work_notes'])}")
        print(f"Images:      {len(report['attachments']['images'])}")
        print(f"Files:       {len(report['attachments']['files'])}")

        return report

    # ── LIST VIEW + TINY URL ────────────────

    def get_incident_by_number(self, number: str, reports_dir: str = "./my_reports") -> dict:
        """
        Fetch a single incident by its number (e.g., INC10403788), upsert it into
        _all_incidents.json, and return the full report dict.
        Raises ValueError if the incident cannot be found.
        """
        print(f"\n[FETCH] Looking up {number} by number...")
        records = self.search_records(
            table=INCIDENT_TABLE,
            query=f"number={number}",
            limit=1,
            fields="sys_id,number,short_description,state",
        )
        if not records:
            raise ValueError(f"Incident {number} not found in ServiceNow.")

        sys_id = records[0].get("sys_id")
        report = self.get_full_incident_report(sys_id, table_name=INCIDENT_TABLE)
        self.upsert_incident_report(report, reports_dir=reports_dir)
        return report

    def resolve_tiny_url(self, tiny_code: str) -> str:
        """
        Resolve a sysparm_tiny code to the actual URL/query string
        by querying the sys_tiny_url table.

        Returns the resolved URL string, or empty string if unavailable.
        """
        try:
            params = {
                "sysparm_query": f"tiny={tiny_code}",
                "sysparm_fields": "url",
                "sysparm_limit": 1,
                "sysparm_display_value": "true",
            }
            resp = self._get("/api/now/table/sys_tiny_url", params=params)
            results = resp.json().get("result", [])
            if results:
                resolved = results[0].get("url", "")
                print(f"[TINY] Resolved tiny='{tiny_code}' → {resolved[:120]}")
                return resolved
            else:
                print(f"[TINY] No record found for tiny='{tiny_code}'")
        except Exception as e:
            print(f"[TINY] Failed to resolve sysparm_tiny '{tiny_code}': {e}")
        return ""

    def parse_list_url(self, url: str) -> tuple:
        """
        Parse a ServiceNow list view URL into (table_name, sysparm_query).

        Handles:
          - /now/nav/ui/classic/params/target/<encoded> navigation URLs
          - incident_list.do?sysparm_tiny=...
          - incident_list.do?sysparm_query=...

        Returns:
            (table_name, encoded_query) tuple
        """
        nav_prefix = "/now/nav/ui/classic/params/target/"
        parsed_url = urlparse(url)
        # Decode percent-encoding in path so ?/= inside it become visible
        decoded_path = unquote(parsed_url.path)

        if nav_prefix in decoded_path:
            # Target is embedded in the path after the prefix
            target = decoded_path[decoded_path.index(nav_prefix) + len(nav_prefix):]
            return self.parse_list_url(f"{self.instance}/{target}")

        # At this point path looks like /incident_list.do and query is normal
        path_segment = decoded_path.strip("/").split("/")[-1]

        table_name = None
        if path_segment.endswith("_list.do"):
            table_name = path_segment[:-8]
        elif path_segment.endswith(".do"):
            table_name = path_segment[:-3]

        if not table_name:
            raise ValueError(
                f"Cannot determine table name from URL path: {path_segment!r}. "
                "Expected a URL like incident_list.do or .../incident_list.do"
            )

        qs = parse_qs(parsed_url.query)
        tiny = (qs.get("sysparm_tiny") or [""])[0]
        query = (qs.get("sysparm_query") or [""])[0]

        if tiny and not query:
            resolved = self.resolve_tiny_url(tiny)
            if resolved:
                resolved_qs = parse_qs(urlparse(resolved).query)
                query = (resolved_qs.get("sysparm_query") or [""])[0]
                if not query:
                    # Some instances store bare query strings without a key
                    query = resolved

        if not query:
            print(f"[LIST] Could not resolve query; fetching all active records from '{table_name}'")
            query = "active=true"

        return table_name, query

    def process_incident_list(
        self,
        list_url: str,
        download_files: bool = False,
        output_dir: str = "./incident_reports",
        limit: int = 1000,
    ) -> list:
        """
        Fetch all incidents from a ServiceNow list view URL and produce
        full reports (details, comments, work notes, attachments) for each.

        Each incident is saved as an individual JSON file.  A combined
        _all_incidents.json is written at the end.

        Args:
            list_url:       A ServiceNow list-view URL (sysparm_tiny supported)
            download_files: Also download attachment files to disk
            output_dir:     Directory to write JSON reports (and attachments)
            limit:          Maximum number of incidents to process

        Returns:
            List of full incident report dicts
        """
        table_name, query = self.parse_list_url(list_url)
        print(f"\n{'='*60}")
        print(f"Processing incident list")
        print(f"Table : {table_name}")
        print(f"Query : {query[:160]}")
        print(f"Limit : {limit}")
        print(f"Output: {output_dir}")
        print(f"{'='*60}")

        # Fetch lightweight list first (just sys_id + display fields)
        minimal_fields = "sys_id,number,short_description,state,priority"
        records = self.search_records(
            table=table_name, query=query, limit=limit, fields=minimal_fields
        )

        if not records:
            print("[LIST] No records found for this list URL.")
            return []

        _TERMINAL_STATES = frozenset({"resolved", "closed", "cancelled", "complete", "completed"})

        # For the incident table, exclude terminal states (closed/resolved/cancelled).
        # This preserves Active, In Progress, New, Pending, etc.
        # For other tables (sc_req_item, etc.) the ServiceNow query already handles
        # filtering, so we process all returned records.
        if table_name == INCIDENT_TABLE:
            active_records = [
                r for r in records
                if (r.get("state") or "").strip().lower() not in _TERMINAL_STATES
            ]
            print(f"[LIST] {len(records)} total record(s) fetched; {len(active_records)} non-terminal.")
            if not active_records:
                print("[LIST] No open incidents found — nothing to process.")
                return []
            records = active_records
        else:
            print(f"[LIST] {len(records)} record(s) fetched from '{table_name}'.")

        print(f"\n[LIST] {len(records)} record(s) to process...\n")
        os.makedirs(output_dir, exist_ok=True)

        all_reports = []
        errors = []

        for idx, rec in enumerate(records, 1):
            sys_id = rec.get("sys_id", "")
            number = rec.get("number", sys_id)
            short_desc = rec.get("short_description", "")[:60]
            print(f"[{idx}/{len(records)}] {number} — {short_desc}")

            try:
                # Download attachments into a per-incident sub-folder
                inc_dir = os.path.join(output_dir, number) if download_files else output_dir
                report = self.get_full_incident_report(
                    sys_id, download_files=download_files, table_name=table_name
                )
                all_reports.append(report)

                safe_number = number.replace("/", "_").replace("\\", "_")
                report_path = os.path.join(output_dir, f"{safe_number}.json")
                with open(report_path, "w", encoding="utf-8") as fh:
                    json.dump(report, fh, indent=2, ensure_ascii=False)

            except Exception as exc:
                print(f"  [ERROR] {number}: {exc}")
                errors.append({"number": number, "sys_id": sys_id, "error": str(exc)})

        # Write combined report
        combined_path = os.path.join(output_dir, "_all_incidents.json")
        with open(combined_path, "w", encoding="utf-8") as fh:
            json.dump(all_reports, fh, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"[DONE] Processed : {len(all_reports)}/{len(records)} incidents")
        if errors:
            print(f"[DONE] Errors    : {len(errors)} (see below)")
            for e in errors:
                print(f"         {e['number']}: {e['error']}")
        print(f"[DONE] Reports   : {output_dir}/")
        print(f"[DONE] Combined  : {combined_path}")
        print(f"{'='*60}")

        return all_reports

    def get_related_stories_for_incident(self, incident_sys_id: str, limit: int = 50) -> list:
        """
        Find stories related to an incident via direct parent or task_rel_task.
        """
        related = []
        seen = set()

        try:
            direct = self.search_stories(query=f"parent={incident_sys_id}", limit=limit)
            for row in direct:
                sys_id = row.get("sys_id")
                if sys_id and sys_id not in seen:
                    related.append(row)
                    seen.add(sys_id)
        except Exception as e:
            print(f"[REL] Direct story relation lookup failed: {e}")

        if len(related) < limit:
            try:
                rel_params = {
                    "sysparm_query": f"parent={incident_sys_id}^ORchild={incident_sys_id}",
                    "sysparm_fields": "parent,child",
                    "sysparm_limit": 500,
                    "sysparm_display_value": "false",
                    "sysparm_exclude_reference_link": "true",
                }
                rel_resp = self._get("/api/now/table/task_rel_task", params=rel_params)
                rel_rows = rel_resp.json().get("result", [])

                candidate_story_ids = []
                for rel in rel_rows:
                    parent_id = rel.get("parent")
                    child_id = rel.get("child")
                    for candidate in [parent_id, child_id]:
                        if candidate and candidate != incident_sys_id and candidate not in seen:
                            candidate_story_ids.append(candidate)

                if candidate_story_ids:
                    uniq_ids = list(dict.fromkeys(candidate_story_ids))
                    remaining = max(limit - len(related), 1)
                    story_rows = self.search_stories(
                        query=f"sys_idIN{','.join(uniq_ids)}",
                        limit=remaining,
                    )
                    for row in story_rows:
                        sys_id = row.get("sys_id")
                        if sys_id and sys_id not in seen:
                            related.append(row)
                            seen.add(sys_id)
            except Exception as e:
                print(f"[REL] task_rel_task lookup failed: {e}")

        return related[:limit]

    def get_full_incident_report(self, incident_input: str, download_files: bool = False,
                                 table_name: str = None) -> dict:
        """
        Fetch incident/request-item details from a URL/sys_id including comments,
        attachments, and related story details. Works for any table (incident,
        sc_req_item, etc.) — pass table_name to skip URL parsing.
        """
        if table_name:
            incident_sys_id = incident_input
        else:
            table_name, incident_sys_id = self.parse_record_link(
                incident_input, default_table=INCIDENT_TABLE
            )

        print(f"\n{'='*60}")
        print(f"Fetching full report for {table_name}: {incident_sys_id}")
        print(f"{'='*60}")

        incident = self.get_record(table_name, incident_sys_id)
        journal = self.get_comments(incident_sys_id, include_work_notes=True)
        comments = [e for e in journal if e.get("element") == "comments"]
        work_notes = [e for e in journal if e.get("element") == "work_notes"]

        attachments = self.get_attachments_for(table_name, incident_sys_id)
        images = [a for a in attachments if a.get("content_type", "").startswith("image/")]
        files = [a for a in attachments if not a.get("content_type", "").startswith("image/")]

        downloaded_paths = []
        if download_files and attachments:
            incident_number = incident.get("number") or incident_sys_id
            safe_number = str(incident_number).replace("/", "_").replace("\\", "_")
            save_dir = os.path.join(DOWNLOAD_DIR, safe_number)
            downloaded_paths = self.download_all_attachments(
                incident_sys_id,
                output_dir=save_dir,
                table_name=table_name,
            )

        related_stories = self.get_related_stories_for_incident(incident_sys_id, limit=100)

        report = {
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
                "images": [{"name": a["file_name"], "id": a["sys_id"],
                            "type": a["content_type"]} for a in images],
                "files": [{"name": a["file_name"], "id": a["sys_id"],
                           "type": a["content_type"]} for a in files],
            },
            "related_stories": [
                {
                    "sys_id": s.get("sys_id"),
                    "number": s.get("number"),
                    "short_description": s.get("short_description"),
                    "state": s.get("state"),
                    "priority": s.get("priority"),
                    "assigned_to": s.get("assigned_to"),
                    "updated": s.get("sys_updated_on"),
                }
                for s in related_stories
            ],
            "downloaded_files": downloaded_paths,
        }

        i = report["incident"]
        print(f"\n--- Incident: {i['number']} ---")
        print(f"Title:           {i['short_description']}")
        print(f"State:           {i['state']}")
        print(f"Priority:        {i['priority']}")
        print(f"Severity:        {i['severity']}")
        print(f"Assigned To:     {i['assigned_to']}")
        print(f"Group:           {i['assignment_group']}")
        print(f"Description:     {(i['description'] or 'N/A')[:200]}...")
        print(f"Comments:        {len(report['comments'])}")
        print(f"Work Notes:      {len(report['work_notes'])}")
        print(f"Images:          {len(report['attachments']['images'])}")
        print(f"Files:           {len(report['attachments']['files'])}")
        print(f"Related Stories: {len(report['related_stories'])}")

        return report

    def post_comment(self, incident_sys_id: str, text: str, as_work_note: bool = False,
                     table: str = None) -> bool:
        """
        Post a comment (or work note) to a ServiceNow record.

        Args:
            incident_sys_id: The record sys_id (not the number)
            text:            Plain-text comment body
            as_work_note:    If True, posts as a work note (internal); else as a customer comment
            table:           ServiceNow table name (defaults to INCIDENT_TABLE)

        Returns:
            True on success, False on failure
        """
        target_table = table or INCIDENT_TABLE
        field = "work_notes" if as_work_note else "comments"
        label = "work note" if as_work_note else "comment"

        try:
            resp = self.session.patch(
                f"{self.instance}/api/now/table/{target_table}/{incident_sys_id}",
                json={field: text},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                print(f"[COMMENT] ✓ Posted {label} to {incident_sys_id}")
                return True
            else:
                print(f"[COMMENT] ✗ Failed to post {label} — HTTP {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"[COMMENT] ✗ Exception posting {label}: {e}")
            return False

    def upsert_incident_report(self, report: dict, reports_dir: str = "./my_reports") -> tuple:
        """
        Save/merge one incident report into per-incident JSON and _all_incidents.json.

        Returns:
            (incident_file_path, combined_file_path)
        """
        os.makedirs(reports_dir, exist_ok=True)

        incident = report.get("incident", {})
        incident_number = incident.get("number") or incident.get("sys_id") or "unknown_incident"
        safe_number = str(incident_number).replace("/", "_").replace("\\", "_")

        incident_path = os.path.join(reports_dir, f"{safe_number}.json")
        with open(incident_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

        combined_path = os.path.join(reports_dir, "_all_incidents.json")
        combined = []
        if os.path.exists(combined_path):
            try:
                with open(combined_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        combined = data
            except Exception as e:
                print(f"[WARN] Could not read existing _all_incidents.json: {e}")

        target_sys_id = incident.get("sys_id")
        target_number = incident.get("number")

        replaced = False
        for idx, item in enumerate(combined):
            existing = item.get("incident", {}) if isinstance(item, dict) else {}
            if (
                (target_sys_id and existing.get("sys_id") == target_sys_id)
                or (target_number and existing.get("number") == target_number)
            ):
                combined[idx] = report
                replaced = True
                break

        if not replaced:
            combined.append(report)

        with open(combined_path, "w", encoding="utf-8") as fh:
            json.dump(combined, fh, indent=2, ensure_ascii=False)

        action = "updated" if replaced else "added"
        print(f"[REPORT] Incident {incident_number} {action} in {combined_path}")
        print(f"[REPORT] Individual report saved to {incident_path}")

        return incident_path, combined_path


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ServiceNow Story/Incident Reader")
    parser.add_argument("--snow-instance", type=str, required=True,
                        help="ServiceNow instance URL (e.g. https://loreal.service-now.com)")
    parser.add_argument("--env-file", type=str, default=".env",
                        help="Path to .env file (default: .env)")
    parser.add_argument("--story", type=str,
                        help="Fetch a specific story by sys_id")
    parser.add_argument("--incident-link", type=str,
                        help="Fetch an incident by URL or sys_id and include details/comments/attachments/stories")
    parser.add_argument("--search", type=str, default="",
                        help="Search records (ServiceNow query or text)")
    parser.add_argument("--search-table", type=str, default="story",
                        choices=["story", "incident", "both"],
                        help="Table to search: story, incident, or both (default: story)")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max records to return in search")
    parser.add_argument("--download", action="store_true",
                        help="Download attachments to disk")
    parser.add_argument("--output", type=str, default="",
                        help="Save report to JSON file")
    parser.add_argument("--list-link", type=str,
                        help="Fetch ALL incidents from a ServiceNow list view URL "
                             "(sysparm_tiny supported) and save full reports")
    parser.add_argument("--report-dir", type=str, default="./my_reports",
                        help="Directory for per-incident JSON reports and _all_incidents.json "
                            "(default: ./my_reports)")
    args = parser.parse_args()

    # Initialize client
    client = ServiceNowReader(args.snow_instance)

    # Authenticate from .env (always)
    client.authenticate_from_env(args.env_file)

    # Validate session
    if not client.validate():
        print("\n[FAIL] Could not connect. Try:")
        print("  1. Ensure .env has valid COOKIE and X_USERTOKEN values")
        print("  2. Verify values are from a live logged-in ServiceNow session")
        print("  3. Try: python snow_story_reader.py --env-file .env")
        sys.exit(1)

    # Execute requested action
    if args.list_link:
        reports = client.process_incident_list(
            list_url=args.list_link,
            download_files=args.download,
            output_dir=args.report_dir,
            limit=args.limit,
        )
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(reports, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] Combined report saved to {args.output}")

    elif args.incident_link:
        report = client.get_full_incident_report(args.incident_link, download_files=args.download)

        # Keep single-incident runs in sync with the master report set.
        client.upsert_incident_report(report, reports_dir=args.report_dir)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] Report saved to {args.output}")

    elif args.story:
        # Fetch specific story
        # Handles both sys_id and story number
        sys_id = args.story

        # If user passed a URL, extract sys_id
        if "sys_id=" in sys_id:
            sys_id = sys_id.split("sys_id=")[1].split("&")[0].split("%")[0]

        report = client.get_full_story_report(sys_id, download_files=args.download)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] Report saved to {args.output}")

    elif args.search:
        # Search records
        if "=" in args.search:
            # Treat as encoded query
            query = args.search
        else:
            # Treat as text search
            query = (
                f"short_descriptionLIKE{args.search}"
                f"^ORdescriptionLIKE{args.search}"
            )

        selected_tables = {
            "story": [TABLE],
            "incident": [INCIDENT_TABLE],
            "both": [TABLE, INCIDENT_TABLE],
        }[args.search_table]

        search_results = {}
        for table in selected_tables:
            records = client.search_records(table=table, query=query, limit=args.limit)
            search_results[table] = records

            print(f"\n[{table}] {len(records)} result(s)")
            for r in records:
                print(f"  {r.get('number', 'N/A'):12} | {r.get('state', ''):20} | "
                      f"{r.get('short_description', 'N/A')[:60]}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(search_results, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] Results saved to {args.output}")

    else:
        # Default: show recent stories
        print("\n[INFO] No --story or --search specified. Showing recent stories...\n")
        stories = client.search_stories(query="active=true", limit=args.limit)

        for s in stories:
            print(f"  {s.get('number', 'N/A'):12} | {s.get('state', ''):20} | "
                  f"{s.get('short_description', 'N/A')[:60]}")

        print(f"\n[TIP] To get full details for a story:")
        print(f"  python snow_story_reader.py --story <sys_id>")
        print(f"  python snow_story_reader.py --story <sys_id> --download")
        print(f"\n[TIP] Your story sys_id from the URL:")
        print(f"  a344dbf72bf3b6503c04fb76fe91bf95")


if __name__ == "__main__":
    main()
