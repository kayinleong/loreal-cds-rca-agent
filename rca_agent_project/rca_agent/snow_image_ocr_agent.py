"""
ServiceNow Image OCR Agent
==========================
Reads _all_incidents.json (produced by snow_story_reader.py --list-link),
extracts text from every downloaded image attachment using OCR, and writes
a consolidated report.

SETUP:
    pip install pytesseract pillow

    Also install Tesseract OCR binary for Windows:
    https://github.com/UB-Mannheim/tesseract/wiki
    (default install path: C:\\Program Files\\Tesseract-OCR\\tesseract.exe)

USAGE:
    # Use default paths (./my_reports/_all_incidents.json, attachments in ./attachments)
    python snow_image_ocr_agent.py

    # Custom paths
    python snow_image_ocr_agent.py --input ./my_reports/_all_incidents.json \\
                                   --attachments-root ./attachments \\
                                   --output ./my_reports/_ocr_consolidated.json \\
                                   --txt-output ./my_reports/_ocr_consolidated.txt

OUTPUT:
    _ocr_consolidated.json — structured JSON with OCR text per incident/image
    _ocr_consolidated.txt  — human-readable consolidated text report
"""

import os
import sys
import json
import argparse
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
except ImportError:
    print("[ERROR] Missing dependencies. Run:")
    print("    pip install pytesseract pillow")
    print()
    print("Also install Tesseract binary:")
    print("    https://github.com/UB-Mannheim/tesseract/wiki")
    sys.exit(1)


# ── Tesseract binary path (Windows default) ─────────────────────────────────
TESSERACT_CMD_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(
        os.environ.get("USERNAME", "")
    ),
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


def configure_tesseract():
    """Locate and configure the Tesseract binary."""
    for path in TESSERACT_CMD_CANDIDATES:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"[OCR] Tesseract found at: {path}")
            return True

    # Check if it's on PATH
    import shutil
    if shutil.which("tesseract"):
        print("[OCR] Tesseract found on PATH")
        return True

    print("[ERROR] Tesseract binary not found.")
    print("        Install from: https://github.com/UB-Mannheim/tesseract/wiki")
    print("        Or set the path manually at the top of this script.")
    sys.exit(1)


def is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def resolve_path(path: str, base_dir: Path) -> Path:
    """
    Resolve a (possibly relative) path from the JSON to an absolute Path.
    Tries the path as-is first, then relative to base_dir.
    """
    p = Path(path)
    if p.is_absolute() and p.exists():
        return p

    # Normalize: strip leading ./ or .\\
    normalized = Path(str(p).lstrip("./").lstrip(".\\"))
    candidate = base_dir / normalized
    if candidate.exists():
        return candidate

    # Try directly under base_dir with original name
    candidate2 = base_dir / p
    if candidate2.exists():
        return candidate2

    # Try path relative to the script's working directory
    cwd_candidate = Path.cwd() / normalized
    if cwd_candidate.exists():
        return cwd_candidate

    # Try the path relative to base_dir but stripping leading 'attachments'
    parts = normalized.parts
    if parts and parts[0].lower() == "attachments":
        alt = base_dir / Path(*parts[1:])
        if alt.exists():
            return alt

    return None


def extract_text_from_image(image_path: Path) -> str:
    """Run Tesseract OCR on a single image and return extracted text."""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        return f"[OCR ERROR: {e}]"


def build_consolidated_report(all_incidents_path: Path, attachments_root: Path) -> list:
    """
    For every incident in _all_incidents.json, include all details
    (fields, comments, work notes, attachments metadata, related stories)
    plus OCR text extracted from any downloaded image attachments.
    """
    with open(all_incidents_path, encoding="utf-8") as f:
        incidents = json.load(f)

    report = []
    total_images = 0
    processed_images = 0

    for inc_data in incidents:
        incident = inc_data.get("incident", {})
        number = incident.get("number", "N/A")
        short_desc = incident.get("short_description", "")
        downloaded_files = inc_data.get("downloaded_files", [])

        # Filter to image files only
        image_paths = [fp for fp in downloaded_files if is_image_path(fp)]

        if image_paths:
            total_images += len(image_paths)
            print(f"\n[{number}] {short_desc[:70]}")
            print(f"  → {len(image_paths)} image(s) found")

        images_ocr = []
        for raw_path in image_paths:
            resolved = resolve_path(raw_path, attachments_root)
            if not resolved:
                print(f"  [SKIP] File not found: {raw_path}")
                images_ocr.append({
                    "original_path": raw_path,
                    "resolved_path": None,
                    "ocr_text": "[FILE NOT FOUND]",
                })
                continue

            print(f"  [OCR]  {resolved.name} ...", end=" ", flush=True)
            text = extract_text_from_image(resolved)
            word_count = len(text.split()) if text and not text.startswith("[OCR ERROR") else 0
            print(f"{word_count} word(s) extracted")
            processed_images += 1

            images_ocr.append({
                "original_path": str(raw_path),
                "resolved_path": str(resolved),
                "ocr_text": text,
            })

        report.append({
            # ── Core incident fields ──────────────────────────────────────
            "number": number,
            "sys_id": incident.get("sys_id"),
            "short_description": short_desc,
            "description": incident.get("description"),
            "state": incident.get("state"),
            "priority": incident.get("priority"),
            "severity": incident.get("severity"),
            "assigned_to": incident.get("assigned_to"),
            "assignment_group": incident.get("assignment_group"),
            "category": incident.get("category"),
            "subcategory": incident.get("subcategory"),
            "created": incident.get("created"),
            "updated": incident.get("updated"),
            # ── Activity ─────────────────────────────────────────────────
            "comments": inc_data.get("comments", []),
            "work_notes": inc_data.get("work_notes", []),
            # ── Attachments metadata ──────────────────────────────────────
            "attachments": inc_data.get("attachments", {"images": [], "files": []}),
            # ── Related stories ───────────────────────────────────────────
            "related_stories": inc_data.get("related_stories", []),
            # ── OCR results from downloaded images ────────────────────────
            "image_ocr": images_ocr,
        })

    print(f"\n[OCR] Processed {processed_images}/{total_images} image(s) "
          f"across {len(incidents)} incident(s) total.")
    return report


def write_json_report(report: list, output_path: Path):
    """Write the full structured JSON report."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] JSON report → {output_path}")


def write_txt_report(report: list, output_path: Path):
    """Write a human-readable consolidated text report with all incident details."""
    lines = []
    lines.append("=" * 70)
    lines.append("SERVICENOW INCIDENT CONSOLIDATED REPORT (with Image OCR)")
    lines.append("=" * 70)
    lines.append(f"Total incidents: {len(report)}")
    lines.append(f"Incidents with images: {sum(1 for e in report if e.get('image_ocr'))}")
    lines.append("")

    for entry in report:
        lines.append("=" * 70)
        lines.append(f"Incident  : {entry['number']}")
        lines.append(f"Sys ID    : {entry.get('sys_id', 'N/A')}")
        lines.append(f"Title     : {entry['short_description']}")
        lines.append(f"State     : {entry.get('state', 'N/A')}")
        lines.append(f"Priority  : {entry.get('priority', 'N/A')}")
        lines.append(f"Severity  : {entry.get('severity') or 'N/A'}")
        lines.append(f"Assigned  : {entry.get('assigned_to') or 'N/A'}")
        lines.append(f"Group     : {entry.get('assignment_group') or 'N/A'}")
        lines.append(f"Category  : {entry.get('category') or 'N/A'}")
        lines.append(f"Subcategory: {entry.get('subcategory') or 'N/A'}")
        lines.append(f"Created   : {entry.get('created', 'N/A')}")
        lines.append(f"Updated   : {entry.get('updated', 'N/A')}")
        lines.append("")

        # Description
        lines.append("  ── Description:")
        desc = entry.get("description") or "(none)"
        for dl in desc.splitlines():
            lines.append(f"    {dl}")
        lines.append("")

        # Comments
        comments = entry.get("comments", [])
        lines.append(f"  ── Comments ({len(comments)}):")
        if comments:
            for c in comments:
                lines.append(f"    [{c.get('date', 'N/A')}] {c.get('author', 'N/A')}")
                for cl in (c.get("text") or "").splitlines():
                    lines.append(f"      {cl}")
                lines.append("")
        else:
            lines.append("    (none)")
            lines.append("")

        # Work Notes
        work_notes = entry.get("work_notes", [])
        lines.append(f"  ── Work Notes ({len(work_notes)}):")
        if work_notes:
            for n in work_notes:
                lines.append(f"    [{n.get('date', 'N/A')}] {n.get('author', 'N/A')}")
                for nl in (n.get("text") or "").splitlines():
                    lines.append(f"      {nl}")
                lines.append("")
        else:
            lines.append("    (none)")
            lines.append("")

        # Attachments metadata
        att = entry.get("attachments", {})
        img_att = att.get("images", [])
        file_att = att.get("files", [])
        lines.append(f"  ── Attachments: {len(img_att)} image(s), {len(file_att)} file(s)")
        for a in img_att:
            lines.append(f"    [IMG] {a.get('name')} (id: {a.get('id')}, type: {a.get('type')})")
        for a in file_att:
            lines.append(f"    [FILE] {a.get('name')} (id: {a.get('id')}, type: {a.get('type')})")
        lines.append("")

        # Related Stories
        stories = entry.get("related_stories", [])
        lines.append(f"  ── Related Stories ({len(stories)}):")
        if stories:
            for s in stories:
                lines.append(f"    {s.get('number', 'N/A')} | {s.get('state', 'N/A')} | "
                             f"{s.get('short_description', 'N/A')[:60]}")
        else:
            lines.append("    (none)")
        lines.append("")

        # Image OCR
        ocr_entries = entry.get("image_ocr", [])
        lines.append(f"  ── Image OCR ({len(ocr_entries)} image(s)):")
        if ocr_entries:
            for img in ocr_entries:
                lines.append(f"    ── {Path(img['original_path']).name}")
                lines.append(f"       Path: {img.get('resolved_path') or img['original_path']}")
                lines.append("       Extracted Text:")
                ocr_text = img.get("ocr_text") or "(no text extracted)"
                for tl in ocr_text.splitlines():
                    lines.append(f"         {tl}")
                lines.append("")
        else:
            lines.append("    (no images)")
            lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[SAVED] TXT report  → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="ServiceNow Incident Image OCR Agent")
    parser.add_argument(
        "--input", type=str,
        default="./my_reports/_all_incidents.json",
        help="Path to _all_incidents.json (default: ./my_reports/_all_incidents.json)",
    )
    parser.add_argument(
        "--attachments-root", type=str,
        default="./attachments",
        help="Root folder where downloaded attachments are stored (default: ./attachments)",
    )
    parser.add_argument(
        "--output", type=str,
        default="./my_reports/_ocr_consolidated.json",
        help="Output JSON report path (default: ./my_reports/_ocr_consolidated.json)",
    )
    parser.add_argument(
        "--txt-output", type=str,
        default="./my_reports/_ocr_consolidated.txt",
        help="Output TXT report path (default: ./my_reports/_ocr_consolidated.txt)",
    )
    args = parser.parse_args()

    configure_tesseract()

    all_incidents_path = Path(args.input).resolve()
    attachments_root = Path(args.attachments_root).resolve()
    json_output = Path(args.output).resolve()
    txt_output = Path(args.txt_output).resolve()

    if not all_incidents_path.exists():
        print(f"[ERROR] Input file not found: {all_incidents_path}")
        sys.exit(1)

    if not attachments_root.exists():
        print(f"[ERROR] Attachments root not found: {attachments_root}")
        sys.exit(1)

    print(f"[OCR AGENT] Input      : {all_incidents_path}")
    print(f"[OCR AGENT] Attachments: {attachments_root}")
    print(f"[OCR AGENT] JSON Out   : {json_output}")
    print(f"[OCR AGENT] TXT Out    : {txt_output}")
    print()

    report = build_consolidated_report(all_incidents_path, attachments_root)

    if not report:
        print("[INFO] No incidents with downloaded images found. Nothing to write.")
        sys.exit(0)

    os.makedirs(json_output.parent, exist_ok=True)
    os.makedirs(txt_output.parent, exist_ok=True)

    write_json_report(report, json_output)
    write_txt_report(report, txt_output)

    print(f"\n[DONE] OCR consolidation complete.")


if __name__ == "__main__":
    main()
