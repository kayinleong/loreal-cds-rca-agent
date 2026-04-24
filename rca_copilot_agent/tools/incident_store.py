"""
Incident Store — in-memory index of downloaded incident data.
=============================================================
Extracted from rca_agent/tools/snow_tool.py.
Loads _all_incidents.json produced by snow_reader.py and provides
fast search + identifier extraction. No LLM calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


class IncidentStore:
    """
    In-memory index built from _all_incidents.json.

    Expected per-incident structure:
      {
        "incident": { number, short_description, description, state, sys_id, ... },
        "comments":    [{ date, author, text }],
        "work_notes":  [{ date, author, text }],
        "attachments": { images: [...], files: [...] },
        "related_stories": [...],
        "downloaded_files": [...]
      }
    """

    def __init__(self) -> None:
        self.incidents: list[dict] = []
        self.by_number: dict[str, dict] = {}
        self.by_sys_id: dict[str, dict] = {}
        self._loaded_path: str = ""

    def load(self, incidents_path: str) -> int:
        """
        Load incidents from _all_incidents.json.

        Returns:
            Number of incidents loaded.
        Raises:
            FileNotFoundError if the file does not exist.
        """
        path = Path(incidents_path)
        if not path.exists():
            raise FileNotFoundError(f"Incidents file not found: {path}")

        with open(path, encoding="utf-8") as fh:
            self.incidents = json.load(fh)

        self.by_number = {}
        self.by_sys_id = {}
        for inc in self.incidents:
            i = inc.get("incident", {})
            number = i.get("number", "")
            sys_id = i.get("sys_id", "")
            if number:
                self.by_number[number] = inc
            if sys_id:
                self.by_sys_id[sys_id] = inc

        self._loaded_path = str(path)
        return len(self.incidents)

    def get_incident(self, identifier: str) -> Optional[dict]:
        """
        Look up a single incident by display number (INC...) or sys_id.
        Returns the full incident dict or None.
        """
        return self.by_number.get(identifier) or self.by_sys_id.get(identifier)

    def get_incident_summary(self, identifier: str) -> str:
        """
        Return a formatted text block with the full incident data —
        description, comments, work notes, attachments, related stories.
        Suitable for passing directly to GitHub Copilot as context.
        """
        inc = self.get_incident(identifier)
        if not inc:
            return (
                f"Incident '{identifier}' not found in local data. "
                "Run fetch_incidents first, or check the incident number."
            )

        i = inc.get("incident", {})
        lines = [
            f"INCIDENT: {i.get('number', 'N/A')}",
            f"Title:    {i.get('short_description', 'N/A')}",
            f"State:    {i.get('state', 'N/A')}",
            f"Priority: {i.get('priority', 'N/A')}",
            f"Severity: {i.get('severity', 'N/A')}",
            f"Assigned: {i.get('assigned_to', 'N/A')}",
            f"Group:    {i.get('assignment_group', 'N/A')}",
            f"Category: {i.get('category', 'N/A')} / {i.get('subcategory', 'N/A')}",
            f"Created:  {i.get('created', 'N/A')}",
            f"Updated:  {i.get('updated', 'N/A')}",
            "",
            "DESCRIPTION:",
            (i.get("description") or "(none)")[:3000],
            "",
        ]

        comments = inc.get("comments", [])
        lines.append(f"COMMENTS ({len(comments)}):")
        for c in comments[:30]:
            lines.append(f"  [{c.get('date', '?')}] {c.get('author', '?')}")
            lines.append(f"  {(c.get('text') or '')[:800]}")
            lines.append("")

        work_notes = inc.get("work_notes", [])
        lines.append(f"WORK NOTES ({len(work_notes)}):")
        for n in work_notes[:30]:
            lines.append(f"  [{n.get('date', '?')}] {n.get('author', '?')}")
            lines.append(f"  {(n.get('text') or '')[:800]}")
            lines.append("")

        att = inc.get("attachments", {})
        images = att.get("images", [])
        files = att.get("files", [])
        lines.append(f"ATTACHMENTS: {len(images)} image(s), {len(files)} file(s)")
        for a in images:
            lines.append(f"  [IMG] {a.get('name', 'N/A')}")
        for a in files:
            lines.append(f"  [FILE] {a.get('name', 'N/A')}")

        stories = inc.get("related_stories", [])
        if stories:
            lines.append(f"\nRELATED STORIES ({len(stories)}):")
            for s in stories:
                lines.append(
                    f"  {s.get('number', 'N/A')} | {s.get('state', '')} | "
                    f"{(s.get('short_description') or '')[:60]}"
                )

        return "\n".join(lines)

    def list_all(self, max_incidents: int = 100) -> str:
        """Return a brief listing of all loaded incidents."""
        if not self.incidents:
            return "No incidents loaded. Run fetch_incidents first."

        lines = [f"LOADED INCIDENTS ({len(self.incidents)} total):"]
        for inc in self.incidents[:max_incidents]:
            i = inc.get("incident", {})
            lines.append(
                f"  {i.get('number', 'N/A'):15} | "
                f"{i.get('state', ''):12} | "
                f"P{i.get('priority', '?')} | "
                f"{(i.get('short_description') or '')[:60]}"
            )
        if len(self.incidents) > max_incidents:
            lines.append(f"  ... ({len(self.incidents) - max_incidents} more)")
        return "\n".join(lines)

    def search(
        self,
        keyword: str,
        section: str = "all",
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search all incidents for keyword matches.

        Args:
            keyword:     Term to find (case-insensitive)
            section:     'description', 'comments', 'work_notes', or 'all'
            max_results: Cap on returned matches

        Returns:
            List of {incident, section, snippet} dicts.
        """
        results: list[dict] = []
        kw_lower = keyword.lower()
        sections = (
            ["description", "comments", "work_notes"]
            if section == "all"
            else [section]
        )

        for inc in self.incidents:
            i = inc.get("incident", {})
            number = i.get("number", "N/A")

            for sec in sections:
                if sec == "description":
                    text = i.get("description", "") or ""
                    if kw_lower in text.lower():
                        idx = text.lower().index(kw_lower)
                        snippet = text[max(0, idx - 150): idx + 150]
                        results.append({"incident": number, "section": "description", "snippet": f"...{snippet}..."})

                elif sec == "comments":
                    for c in inc.get("comments", []):
                        text = c.get("text", "") or ""
                        if kw_lower in text.lower():
                            idx = text.lower().index(kw_lower)
                            snippet = text[max(0, idx - 150): idx + 150]
                            results.append({
                                "incident": number,
                                "section": f"comment ({c.get('date', '?')} by {c.get('author', '?')})",
                                "snippet": f"...{snippet}...",
                            })

                elif sec == "work_notes":
                    for n in inc.get("work_notes", []):
                        text = n.get("text", "") or ""
                        if kw_lower in text.lower():
                            idx = text.lower().index(kw_lower)
                            snippet = text[max(0, idx - 150): idx + 150]
                            results.append({
                                "incident": number,
                                "section": f"work_note ({n.get('date', '?')} by {n.get('author', '?')})",
                                "snippet": f"...{snippet}...",
                            })

            if len(results) >= max_results:
                break

        return results[:max_results]

    def extract_identifiers(self, identifier: str) -> dict:
        """
        Extract order IDs, user IDs, EAN codes, and email addresses
        from all text fields of an incident. Useful for building queries.

        Args:
            identifier: Incident number (INC...) or sys_id.

        Returns:
            Dict with keys: order_ids, user_ids, ean_codes, emails.
        """
        inc = self.get_incident(identifier)
        if not inc:
            return {}

        i = inc.get("incident", {})
        parts: list[str] = [
            i.get("description", "") or "",
            i.get("short_description", "") or "",
        ]
        for c in inc.get("comments", []):
            parts.append(c.get("text", "") or "")
        for n in inc.get("work_notes", []):
            parts.append(n.get("text", "") or "")
        combined = "\n".join(parts)

        ids: dict[str, list[str]] = {}

        for pat in [
            r"(?:order[_ ]?(?:id|number|no)?\s*[:=]?\s*)([A-Z]{2,5}[A-Z0-9]{6,20})",
            r"(YSL[A-Z]{2}\d{7,})",
            r"(LOE[A-Z]{2}\d{7,})",
        ]:
            matches = re.findall(pat, combined, re.IGNORECASE)
            if matches:
                ids.setdefault("order_ids", []).extend(matches)

        for pat in [
            r"(?:user[_ ]?id|customer[_ ]?id|member[_ ]?id|MARSID)\s*[:=]?\s*([A-Z0-9]{8,30})",
            r"(C\d[A-Z]{2}\d{8,})",
        ]:
            matches = re.findall(pat, combined, re.IGNORECASE)
            if matches:
                ids.setdefault("user_ids", []).extend(matches)

        eans = re.findall(r"\b(\d{13})\b", combined)
        if eans:
            ids["ean_codes"] = list(set(eans))

        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", combined)
        if emails:
            ids["emails"] = list(set(emails))

        # Deduplicate lists
        for key in ids:
            if isinstance(ids[key], list):
                ids[key] = list(set(ids[key]))

        return ids


# ── Module-level singleton ────────────────────────────────────────────────────

_store: Optional[IncidentStore] = None


def get_store() -> IncidentStore:
    global _store
    if _store is None:
        _store = IncidentStore()
    return _store


def load_store(incidents_path: str) -> int:
    """Load (or reload) the global incident store. Returns count loaded."""
    global _store
    _store = IncidentStore()
    return _store.load(incidents_path)
