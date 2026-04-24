"""
ServiceNow Tool — Incident Loader & Search
============================================
Loads incident data from snow_story_reader.py output (_all_incidents.json)
and provides structured search + extraction for the RCA agent.
"""

from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class IncidentLoader:
    """
    Load and index incident data from _all_incidents.json for fast search.
    
    The JSON structure (per incident):
      {
        "incident": { number, short_description, description, state, ... },
        "comments": [{ date, author, text }],
        "work_notes": [{ date, author, text }],
        "attachments": { images: [...], files: [...] },
        "related_stories": [...],
        "downloaded_files": [...]
      }
    
    If OCR data exists (_ocr_consolidated.json), it's merged in.
    """

    def __init__(self):
        self.incidents: list[dict] = []
        self.by_number: dict[str, dict] = {}
        self.ocr_data: dict[str, list[dict]] = {}  # number -> OCR entries

    def load(self, incidents_path: str, ocr_path: str = None) -> int:
        """Load incidents JSON. Returns count loaded."""
        path = Path(incidents_path)
        if not path.exists():
            raise FileNotFoundError(f"Incidents file not found: {path}")

        with open(path, encoding="utf-8") as f:
            self.incidents = json.load(f)

        self.by_number = {}
        for inc in self.incidents:
            number = inc.get("incident", {}).get("number", "")
            if number:
                self.by_number[number] = inc

        # Merge OCR data if available
        if ocr_path:
            self._load_ocr(ocr_path)
        else:
            # Try auto-detect alongside incidents file
            ocr_candidate = path.parent / "_ocr_consolidated.json"
            if ocr_candidate.exists():
                self._load_ocr(str(ocr_candidate))

        logger.info(f"[SNOW] Loaded {len(self.incidents)} incidents")
        return len(self.incidents)

    def _load_ocr(self, ocr_path: str):
        """Load OCR consolidated data and index by incident number."""
        try:
            with open(ocr_path, encoding="utf-8") as f:
                ocr_entries = json.load(f)
            for entry in ocr_entries:
                number = entry.get("number", "")
                ocr_images = entry.get("image_ocr", [])
                if number and ocr_images:
                    self.ocr_data[number] = ocr_images
            logger.info(f"[SNOW] Loaded OCR data for {len(self.ocr_data)} incidents")
        except Exception as e:
            logger.warning(f"[SNOW] Could not load OCR data: {e}")

    def get_incident(self, number: str) -> Optional[dict]:
        """Get a single incident by number (e.g., INC0012345)."""
        return self.by_number.get(number)

    def get_incident_summary(self, number: str) -> str:
        """Get a condensed summary suitable for LLM context."""
        inc = self.get_incident(number)
        if not inc:
            return f"Incident {number} not found in loaded data."

        i = inc.get("incident", {})
        lines = [
            f"INCIDENT: {i.get('number', 'N/A')}",
            f"Title: {i.get('short_description', 'N/A')}",
            f"State: {i.get('state', 'N/A')}",
            f"Priority: {i.get('priority', 'N/A')}",
            f"Severity: {i.get('severity', 'N/A')}",
            f"Assigned: {i.get('assigned_to', 'N/A')}",
            f"Group: {i.get('assignment_group', 'N/A')}",
            f"Category: {i.get('category', 'N/A')} / {i.get('subcategory', 'N/A')}",
            f"Created: {i.get('created', 'N/A')}",
            f"Updated: {i.get('updated', 'N/A')}",
            "",
            "DESCRIPTION:",
            (i.get("description") or "(none)")[:2000],
            "",
        ]

        # Comments
        comments = inc.get("comments", [])
        lines.append(f"COMMENTS ({len(comments)}):")
        for c in comments[:20]:  # Cap for context window
            lines.append(f"  [{c.get('date', '?')}] {c.get('author', '?')}")
            lines.append(f"  {(c.get('text') or '')[:500]}")
            lines.append("")

        # Work notes
        notes = inc.get("work_notes", [])
        lines.append(f"WORK NOTES ({len(notes)}):")
        for n in notes[:20]:
            lines.append(f"  [{n.get('date', '?')}] {n.get('author', '?')}")
            lines.append(f"  {(n.get('text') or '')[:500]}")
            lines.append("")

        # Attachments
        att = inc.get("attachments", {})
        images = att.get("images", [])
        files = att.get("files", [])
        lines.append(f"ATTACHMENTS: {len(images)} image(s), {len(files)} file(s)")
        for a in images:
            lines.append(f"  [IMG] {a.get('name', 'N/A')}")
        for a in files:
            lines.append(f"  [FILE] {a.get('name', 'N/A')}")

        # OCR text
        ocr = self.ocr_data.get(i.get("number", ""), [])
        if ocr:
            lines.append(f"\nATTACHMENT OCR TEXT ({len(ocr)} image(s)):")
            for o in ocr:
                fname = Path(o.get("original_path", "unknown")).name
                text = o.get("ocr_text", "")[:1000]
                lines.append(f"  [{fname}]:")
                lines.append(f"  {text}")
                lines.append("")

        # Related stories
        stories = inc.get("related_stories", [])
        if stories:
            lines.append(f"\nRELATED STORIES ({len(stories)}):")
            for s in stories:
                lines.append(f"  {s.get('number', 'N/A')} | {s.get('state', '')} | "
                             f"{s.get('short_description', '')[:60]}")

        return "\n".join(lines)

    def get_all_summaries(self, max_incidents: int = 50) -> str:
        """Get brief summaries of all loaded incidents."""
        lines = [f"LOADED INCIDENTS ({len(self.incidents)} total):"]
        for inc in self.incidents[:max_incidents]:
            i = inc.get("incident", {})
            lines.append(
                f"  {i.get('number', 'N/A'):15} | {i.get('state', ''):10} | "
                f"P{i.get('priority', '?')} | {i.get('short_description', 'N/A')[:60]}"
            )
        if len(self.incidents) > max_incidents:
            lines.append(f"  ...({len(self.incidents) - max_incidents} more)")
        return "\n".join(lines)

    def search(self, keyword: str, section: str = "all",
               max_results: int = 20) -> list[dict]:
        """
        Search across all incidents for a keyword.
        
        Returns list of {incident_number, section, snippet} dicts.
        """
        results = []
        kw_lower = keyword.lower()
        sections_to_search = (
            ["description", "comments", "work_notes", "attachments_ocr"]
            if section == "all"
            else [section]
        )

        for inc in self.incidents:
            i = inc.get("incident", {})
            number = i.get("number", "N/A")

            for sec in sections_to_search:
                if sec == "description":
                    text = i.get("description", "") or ""
                    if kw_lower in text.lower():
                        idx = text.lower().index(kw_lower)
                        snippet = text[max(0, idx-150):idx+150]
                        results.append({
                            "incident": number,
                            "section": "description",
                            "snippet": f"...{snippet}...",
                        })

                elif sec == "comments":
                    for c in inc.get("comments", []):
                        text = c.get("text", "") or ""
                        if kw_lower in text.lower():
                            idx = text.lower().index(kw_lower)
                            snippet = text[max(0, idx-150):idx+150]
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
                            snippet = text[max(0, idx-150):idx+150]
                            results.append({
                                "incident": number,
                                "section": f"work_note ({n.get('date', '?')} by {n.get('author', '?')})",
                                "snippet": f"...{snippet}...",
                            })

                elif sec == "attachments_ocr":
                    for o in self.ocr_data.get(number, []):
                        text = o.get("ocr_text", "") or ""
                        if kw_lower in text.lower():
                            idx = text.lower().index(kw_lower)
                            snippet = text[max(0, idx-150):idx+150]
                            fname = Path(o.get("original_path", "")).name
                            results.append({
                                "incident": number,
                                "section": f"attachment_ocr ({fname})",
                                "snippet": f"...{snippet}...",
                            })

            if len(results) >= max_results:
                break

        return results[:max_results]

    def extract_identifiers(self, number: str) -> dict:
        """
        Extract likely identifiers from incident text for BQ queries.
        Looks for order IDs, user IDs, EAN codes, MARS IDs, etc.
        """
        inc = self.get_incident(number)
        if not inc:
            return {}

        # Gather all text
        all_text = []
        i = inc.get("incident", {})
        all_text.append(i.get("description", "") or "")
        all_text.append(i.get("short_description", "") or "")
        for c in inc.get("comments", []):
            all_text.append(c.get("text", "") or "")
        for n in inc.get("work_notes", []):
            all_text.append(n.get("text", "") or "")
        for o in self.ocr_data.get(number, []):
            all_text.append(o.get("ocr_text", "") or "")
        combined = "\n".join(all_text)

        identifiers = {}

        # Order IDs (common patterns)
        order_patterns = [
            r"(?:order[_ ]?(?:id|number|no)?\s*[:=]?\s*)([A-Z]{2,5}[A-Z0-9]{6,20})",
            r"(YSL[A-Z]{2}\d{7,})",
            r"(LOE[A-Z]{2}\d{7,})",
        ]
        for pat in order_patterns:
            matches = re.findall(pat, combined, re.IGNORECASE)
            if matches:
                identifiers.setdefault("order_ids", []).extend(matches)

        # User/Customer IDs
        user_patterns = [
            r"(?:user[_ ]?id|customer[_ ]?id|member[_ ]?id|MARSID)\s*[:=]?\s*([A-Z0-9]{8,30})",
            r"(C\d[A-Z]{2}\d{8,})",
        ]
        for pat in user_patterns:
            matches = re.findall(pat, combined, re.IGNORECASE)
            if matches:
                identifiers.setdefault("user_ids", []).extend(matches)

        # EAN codes
        ean_matches = re.findall(r"\b(\d{13})\b", combined)
        if ean_matches:
            identifiers["ean_codes"] = list(set(ean_matches))

        # Email addresses
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", combined)
        if emails:
            identifiers["emails"] = list(set(emails))

        # Deduplicate
        for key in identifiers:
            if isinstance(identifiers[key], list):
                identifiers[key] = list(set(identifiers[key]))

        return identifiers


# ── Module-level singleton and tool functions ────────────────────────────────

_loader: Optional[IncidentLoader] = None


def init_loader(incidents_path: str, ocr_path: str = None) -> IncidentLoader:
    """Initialize the global incident loader."""
    global _loader
    _loader = IncidentLoader()
    _loader.load(incidents_path, ocr_path)
    return _loader


def get_loader() -> IncidentLoader:
    global _loader
    if _loader is None:
        raise RuntimeError("Incident loader not initialized. Call init_loader() first.")
    return _loader


def search_incident(keyword: str, section: str = "all") -> str:
    """Search loaded incidents for keyword matches. Returns formatted results."""
    loader = get_loader()
    results = loader.search(keyword, section)
    if not results:
        return f"No matches for '{keyword}' in {section}"

    lines = [f"Found {len(results)} match(es) for '{keyword}':"]
    for r in results:
        lines.append(f"\n  [{r['incident']}] {r['section']}:")
        lines.append(f"  {r['snippet']}")
    return "\n".join(lines)
