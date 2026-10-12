"""RCA report template, validation, evidence log, storage and delivery registry.

Pure module: stdlib only, no network, no LLM calls. Filesystem access is
confined to ``<reports_dir>/rca_reports/``.

Layout::

    <reports_dir>/rca_reports/<SAFE_INC>_rca_<YYYYmmdd_HHMMSS>.md      report
    <reports_dir>/rca_reports/<SAFE_INC>_rca_<YYYYmmdd_HHMMSS>.json    sidecar
    <reports_dir>/rca_reports/.evidence/<SAFE_INC>.jsonl               query audit log
    <reports_dir>/rca_reports/.registry.json                           email registry

The evidence log stores SQL + outcome only, never result rows (PII).
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

RCA_SECTIONS: tuple[str, ...] = (
    "WHAT HAPPENED",
    "WHAT WE CHECKED",
    "WHAT WE FOUND",
    "WHAT WE NEED / DID",
)
EVIDENCE_HEADING = "## Evidence — BigQuery queries run"

_META_KEYS = (
    "short_description",
    "state",
    "priority",
    "assignment_group",
    "opened_at",
    "sys_updated_on",
)

# ---------------------------------------------------------------------------
# Assignment-group table (single source of truth; copied from the instruction files)
# ---------------------------------------------------------------------------

_GROUP_MAP: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("CDS L2", "CDS L2 team", "SAPMENA CDS group"), "", "APAC - SGP - SPACE CDS SAPMENA L2 Support"),
    (("CDS L3", "CDS L3 team"), "", "APAC - SGP - SPACE CDS SAPMENA L3 Support"),
    (("LOY", "LOY team", "Loyalty", "Loyalty team"), " (loyalty backend)", "APAC - ZN - O+O.NGLORA - L2"),
    (("LOY L3", "Loyalty L3"), "", "APAC - CHN - SPACE Loyalty L3 Support"),
    (("MARS", "MARS team", "MARS Ops", "MARS Operations", "retail Ops team"), "",
     "APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2"),
    (("iBeauty", "iBeauty team", "IBeauty team", "iBeauty L2"), "", "APAC - ZN - iBeauty 2.0 - Retail - L2"),
    (("SFCC", "SFCC L2"), "", "APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2"),
    (("CRM", "SFMC team", "SFDC team", "CE team", "CE Ops team"), "", "APAC - ZN - O+O.CRM - L2"),
    (("NGL", "NGL L2", "NGLORA"), "", "APAC - ZN - O+O.NGLORA - L2"),
    (("Operations", "Ops", "OPS team"), " (only when no more specific match)", "APAC - ZN - O+O.OPERATIONS - L2"),
    (("Hypercare", "Hypercare team", "Hypercare group", "LS team", "LS Hypercare", "Aesop hypercare"), "",
     "APAC - ZN - SPACE B2C Hypercare"),
    (("HIP", "HIP team", "Infrastructure team", "Azure team"), " (HIP-adjacent)", "TECH FNDN - WW - HIP INCIDENT L2"),
    (("THN Retail", "Thailand Retail"), "", "APAC - THN - Retail IT"),
)

_L3_GROUPS: tuple[str, ...] = (
    "APAC - SGP - SPACE CDS SAPMENA L3 Support",
    "APAC - CHN - SPACE Loyalty L3 Support",
    "APAC - SGP - SPACE Loyalty L3 Support",
    "INFRA - WW - Linux Unix ACN - L3",
)

# Bare single words (LOY, MARS, HIP, CRM, Ops...) double as legitimate system names in
# prose, so only multi-word shortforms and these distinctive tokens are flagged.
_DISTINCTIVE_SINGLE = {"iBeauty", "SFCC"}


def _canonical_groups() -> list[str]:
    names = {canon for _, _, canon in _GROUP_MAP} | set(_L3_GROUPS)
    return sorted(names, key=len, reverse=True)


def _shortforms() -> list[str]:
    out: list[str] = []
    for forms, _, _ in _GROUP_MAP:
        for f in forms:
            if " " not in f and f not in _DISTINCTIVE_SINGLE:
                continue
            out.append(f)
    return sorted(set(out), key=len, reverse=True)


def _shortform_pattern(form: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(form) + r"(?![A-Za-z0-9])")


_SHORTFORM_RES: list[tuple[str, re.Pattern[str]]] = [(f, _shortform_pattern(f)) for f in _shortforms()]

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


def get_rca_template() -> str:
    """Return the canonical RCA template + writing rules (single source of truth)."""
    rows = "\n".join(
        "| " + ", ".join(f"`{f}`" for f in forms) + note + f" | `{canon}` |"
        for forms, note, canon in _GROUP_MAP
    )
    l3 = "\n".join(f"- `{g}`" for g in _L3_GROUPS)
    return f"""## RCA Report Format (MANDATORY)

Always produce the RCA in this exact structure (use `###` headings, exactly these four sections):

```
### WHAT HAPPENED
One sentence. The symptom as reported by the user — not the root cause.
Example: "Order YSL001234 placed on 2025-11-01 is not visible in the CDS portal."

### WHAT WE CHECKED
→ Checked [source] — [what you found]
→ Checked [source] — [what you found]

### WHAT WE FOUND
One or two sentences stating the root cause with evidence.
If the root cause is unclear, state what is known vs. unknown.

### WHAT WE NEED / DID
Bullet list of action items. Include owner if named in the ticket.
- Escalate to [full canonical assignment group] to verify [system] (by [date if given])
- Request transaction logs from [system] for order ID [X]
```

### Writing rules
- Only use data actually returned by tools (incident fields, comments, work notes, attachments, BigQuery results). Never invent facts.
- Zero rows returned is a finding — state it explicitly (e.g. "CDS has no record of order X in BigQuery").
- Every check goes in WHAT WE CHECKED as its own line: `→ Checked <system> — <result>`. Be specific: quote dates, authors, error messages, data points.
- Pass `incident_number` to `query_bigquery` so each query is recorded; the saved report appends a numbered evidence list automatically — do not write that section yourself.
- Action items must name an owner (a full canonical assignment group or a named person from the ticket).
- Do not leave template placeholders such as `{{incident_number}}` or `[source]` in the final text.

### Rule: FULL canonical assignment-group names — never shortforms

When the report references a SNOW assignment group (action items in `### WHAT WE NEED / DID`, evidence in `### WHAT WE CHECKED`, etc.), **always write the verbatim canonical group name as it appears in ServiceNow.** Never use operator shortforms (`CDS L3`, `LOY`, `MARS team`, `iBeauty`, `NGL`, etc.) — they're ambiguous outside the team and they don't match the SNOW Reassign-Group picker.

Example:
- ✓ "Assign to `APAC - SGP - SPACE CDS SAPMENA L3 Support` as the issue is tracked in DFCT0268807."
- ✗ "Assign to CDS L3 team as the issue is tracked in DFCT0268807."

Use this shortform → canonical mapping to translate work-note shorthand to the full SNOW group name:

| Shorthand seen in work-notes | Full canonical SNOW group |
|---|---|
{rows}

L3 / specialised groups that appear in real work-notes (also use full names — never the shorthand):
{l3}

If the right canonical group is uncertain, pick the closest match and add `[USER-CONFIRM]` after it in the report so the reviewer knows to verify.
"""


# ---------------------------------------------------------------------------
# Parsing & validation
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: dict[str, str] = {
    "WHAT HAPPENED": r"WHAT\s+HAPPENED",
    "WHAT WE CHECKED": r"WHAT\s+WE\s+CHECKED",
    "WHAT WE FOUND": r"WHAT\s+WE\s+FOUND",
    "WHAT WE NEED / DID": r"WHAT\s+WE\s+NEED(?:\s*/\s*(?:WHAT\s+WE\s+)?DID)?",
}
_HEADING_RES: dict[str, re.Pattern[str]] = {
    name: re.compile(
        r"^[ \t]{0,3}#{1,4}[ \t]*\**[ \t]*" + pat + r"[ \t]*:?[ \t]*\**[ \t]*:?[ \t]*$",
        re.IGNORECASE,
    )
    for name, pat in _SECTION_PATTERNS.items()
}
_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_ ]*\}")


def _heading_name(line: str) -> str | None:
    for name, rx in _HEADING_RES.items():
        if rx.match(line):
            return name
    return None


def parse_sections(report_text: str) -> dict[str, str]:
    """Return canonical section name -> body text for each recognised section."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in (report_text or "").splitlines():
        if line.strip() == EVIDENCE_HEADING:
            current = None
            continue
        name = _heading_name(line)
        if name is not None:
            current = name
            sections.setdefault(name, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def validate_rca_report(report_text: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block saving; warnings never do."""
    errors: list[str] = []
    warnings: list[str] = []
    sections = parse_sections(report_text)

    for name in RCA_SECTIONS:
        if name not in sections:
            errors.append(f"Missing section: '### {name}'")
        elif not sections[name].strip():
            errors.append(f"Section is empty: '### {name}'")

    checked = sections.get("WHAT WE CHECKED", "")
    if checked.strip() and not any(
        ln.lstrip().startswith(("→", "->", "- ")) for ln in checked.splitlines()
    ):
        warnings.append(
            "WHAT WE CHECKED has no evidence lines; use '→ Checked <system> — <result>' for each check."
        )

    text = report_text or ""
    placeholders = sorted(set(_PLACEHOLDER_RE.findall(text)))
    if placeholders:
        warnings.append("Unfilled template placeholders: " + ", ".join(placeholders))

    stripped = text
    for canon in _canonical_groups():
        stripped = stripped.replace(canon, " ")
    found = [f for f, rx in _SHORTFORM_RES if rx.search(stripped)]
    if found:
        warnings.append(
            "Operator shortform group name(s) used: "
            + ", ".join(f"'{f}'" for f in found)
            + " — use the full canonical SNOW assignment-group name."
        )
    return errors, warnings


# ---------------------------------------------------------------------------
# Paths & atomic IO
# ---------------------------------------------------------------------------


def _safe_inc(incident_number: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(incident_number or "").strip())
    return safe or "UNKNOWN"


def _rca_dir(reports_dir: str) -> Path:
    return Path(reports_dir) / "rca_reports"


def _evidence_path(reports_dir: str, incident_number: str) -> Path:
    return _rca_dir(reports_dir) / ".evidence" / f"{_safe_inc(incident_number)}.jsonl"


def _registry_path(reports_dir: str) -> Path:
    return _rca_dir(reports_dir) / ".registry.json"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Evidence log
# ---------------------------------------------------------------------------


def record_query(
    reports_dir: str,
    incident_number: str,
    *,
    sql: str,
    rationale: str,
    success: bool,
    row_count: int,
    error: str | None,
) -> None:
    """Append one JSON line describing a BigQuery query (never result rows)."""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "sql": sql,
        "rationale": rationale,
        "success": bool(success),
        "row_count": int(row_count or 0),
        "error": (str(error)[:300] if error else None),
    }
    path = _evidence_path(reports_dir, incident_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_evidence(reports_dir: str, incident_number: str) -> list[dict]:
    """Return recorded query entries for an incident (corrupt lines skipped)."""
    path = _evidence_path(reports_dir, incident_number)
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    logger.warning("Skipping corrupt evidence line in %s", path)
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
    except OSError as exc:
        logger.warning("Could not read evidence log %s: %s", path, exc)
    return out


# ---------------------------------------------------------------------------
# Rendering & saving
# ---------------------------------------------------------------------------


def render_report(
    incident_number: str,
    report_text: str,
    incident_meta: dict[str, str] | None,
    evidence: list[dict],
) -> str:
    """Compose the final Markdown: title, metadata, body, evidence list."""
    lines = [f"# RCA Report — {incident_number}", ""]
    meta = incident_meta or {}
    rows = [(k, meta[k]) for k in _META_KEYS if meta.get(k)]
    if rows:
        lines += ["| Field | Value |", "|---|---|"]
        for k, v in rows:
            val = str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
            lines.append(f"| {k} | {val} |")
        lines.append("")
    lines += [f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_", ""]

    body = report_text or ""
    idx = body.find(EVIDENCE_HEADING)
    if idx != -1:  # evidence is generated from the log; never duplicate it
        body = body[:idx]
    lines += [body.strip(), "", EVIDENCE_HEADING, ""]

    if not evidence:
        lines.append(
            "_No BigQuery queries were recorded for this incident "
            "(pass `incident_number` to `query_bigquery` to log them)._"
        )
    else:
        for i, ev in enumerate(evidence, 1):
            rationale = (ev.get("rationale") or "").strip() or "(no rationale given)"
            if ev.get("success"):
                outcome = f"✓ {int(ev.get('row_count') or 0)} row(s)"
            else:
                outcome = f"✗ {ev.get('error') or 'failed'}"
            lines += [
                f"{i}. {rationale} — {outcome}",
                "",
                "   ```sql",
                *["   " + s for s in str(ev.get("sql") or "").strip().splitlines()],
                "   ```",
                "",
            ]
    return "\n".join(lines).rstrip() + "\n"


def _first_line(text: str, limit: int = 200) -> str:
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if ln:
            return ln[:limit]
    return ""


def save_report(
    reports_dir: str,
    incident_number: str,
    report_text: str,
    incident_meta: dict[str, str] | None = None,
) -> dict:
    """Validate, render and persist an RCA report; register it for email.

    Raises ValueError listing all errors if the report is structurally invalid.
    """
    errors, warnings = validate_rca_report(report_text)
    if errors:
        raise ValueError(
            "RCA report failed validation:\n- " + "\n- ".join(errors)
            + "\n\nCall get_rca_template and follow it exactly."
        )
    evidence = load_evidence(reports_dir, incident_number)
    content = render_report(incident_number, report_text, incident_meta, evidence)
    sections = parse_sections(report_text)

    now = datetime.now()
    out_dir = _rca_dir(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe_inc(incident_number)}_rca_{now.strftime('%Y%m%d_%H%M%S')}"
    path = out_dir / f"{stem}.md"
    n = 2
    while path.exists() or path.with_suffix(".json").exists():
        path = out_dir / f"{stem}_{n}.md"
        n += 1
    json_path = path.with_suffix(".json")

    _atomic_write(path, content)
    sidecar = {
        "incident_number": incident_number,
        "generated_at": now.isoformat(timespec="seconds"),
        "sections": sections,
        "warnings": warnings,
        "evidence": evidence,
    }
    _atomic_write(json_path, json.dumps(sidecar, ensure_ascii=False, indent=2))

    meta = incident_meta or {}
    registry = _load_registry(reports_dir)
    inc_key = str(incident_number).strip().lower()
    for entry in registry:
        if (
            str(entry.get("incident_number", "")).strip().lower() == inc_key
            and not entry.get("emailed_at")
        ):
            entry["superseded"] = True
    registry.append(
        {
            "incident_number": incident_number,
            "path": str(path),
            "saved_at": now.isoformat(timespec="seconds"),
            "short_description": meta.get("short_description", "") or "",
            "root_cause": _first_line(sections.get("WHAT WE FOUND", "")),
            "emailed_at": None,
            "superseded": False,
        }
    )
    _save_registry(reports_dir, registry)

    return {
        "path": str(path),
        "json_path": str(json_path),
        "warnings": warnings,
        "evidence_count": len(evidence),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def _load_registry(reports_dir: str) -> list[dict]:
    path = _registry_path(reports_dir)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Registry %s unreadable (%s); treating as empty", path, exc)
        return []
    if not isinstance(data, list):
        logger.warning("Registry %s is not a list; treating as empty", path)
        return []
    return [e for e in data if isinstance(e, dict)]


def _save_registry(reports_dir: str, registry: list[dict]) -> None:
    _atomic_write(_registry_path(reports_dir), json.dumps(registry, ensure_ascii=False, indent=2))


def pending_reports(reports_dir: str, incident_numbers: list[str] | None = None) -> list[dict]:
    """Registry entries not yet emailed, not superseded, whose file still exists."""
    wanted = {str(n).strip().lower() for n in incident_numbers} if incident_numbers else None
    out: list[dict] = []
    for e in _load_registry(reports_dir):
        if e.get("emailed_at") or e.get("superseded"):
            continue
        path = e.get("path")
        if not path or not Path(path).is_file():
            continue
        if wanted is not None and str(e.get("incident_number", "")).strip().lower() not in wanted:
            continue
        out.append(
            {
                "incident_number": e.get("incident_number", ""),
                "path": path,
                "saved_at": e.get("saved_at", ""),
                "short_description": e.get("short_description", ""),
                "root_cause": e.get("root_cause", ""),
            }
        )
    return out


def mark_emailed(reports_dir: str, paths: list[str]) -> None:
    """Record that the reports at ``paths`` were emailed."""
    targets = {os.path.normcase(os.path.abspath(str(p))) for p in paths}
    registry = _load_registry(reports_dir)
    stamp = datetime.now().isoformat(timespec="seconds")
    changed = False
    for e in registry:
        p = e.get("path")
        if p and os.path.normcase(os.path.abspath(str(p))) in targets and not e.get("emailed_at"):
            e["emailed_at"] = stamp
            changed = True
    if changed:
        _save_registry(reports_dir, registry)
