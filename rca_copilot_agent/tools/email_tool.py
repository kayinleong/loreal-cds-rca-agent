"""SMTP email notification for RCA session completion."""

from __future__ import annotations

import html as _html
import smtplib
import ssl
from datetime import datetime
from email import policy
from email.message import EmailMessage
from pathlib import Path

MAX_INLINE_CHARS = 20_000
_EVIDENCE_MARKER = "## Evidence"

def _ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Return an SSL context. If verify=False, skip certificate verification (corporate proxies)."""
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _esc(value: object) -> str:
    return _html.escape("" if value is None else str(value), quote=True)


def send_rca_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from: str,
    smtp_to: list[str],
    use_tls: bool,
    subject: str,
    session_summary: str,
    report_entries: list[dict] | None = None,
    verify_ssl: bool = True,
) -> str:
    """Send an HTML email with RCA reports inline and attached (only files that exist).

    report_entries items: {"incident_number", "path", "short_description", "root_cause"}.
    """
    entries = list(report_entries or [])
    html = _build_html(session_summary, entries)

    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = smtp_from
    msg["To"] = ", ".join(smtp_to)
    msg["Subject"] = subject
    msg.set_content(html, subtype="html", charset="utf-8", cte="base64")

    attached: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        path = str(entry.get("path") or "")
        if not path or path in seen:
            continue
        seen.add(path)
        p = Path(path)
        if p.is_file():
            msg.add_attachment(
                p.read_bytes(),
                maintype="text",
                subtype="markdown",
                params={"charset": "utf-8"},
                filename=p.name,
                cte="base64",
            )
            attached.append(p.name)

    ctx = _ssl_context(verify=verify_ssl)
    try:
        raw = msg.as_bytes()
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
                s.starttls(context=ctx)
                if smtp_user and smtp_password:
                    s.login(smtp_user, smtp_password)
                s.sendmail(smtp_from, smtp_to, raw)
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=30) as s:
                if smtp_user and smtp_password:
                    s.login(smtp_user, smtp_password)
                s.sendmail(smtp_from, smtp_to, raw)

        suffix = f" with {len(attached)} report(s) attached" if attached else " (no attachments)"
        return f"✓ Email sent to {', '.join(smtp_to)}{suffix}."
    except Exception as exc:
        return f"✗ Failed to send email: {type(exc).__name__}: {exc}"


def _read_inline_markdown(path: Path) -> str:
    """Read a report as UTF-8 and drop the evidence appendix (kept only in the attachment)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(_EVIDENCE_MARKER):
            lines = lines[:i]
            break
    return "\n".join(lines).strip()


def _render_markdown(text: str) -> str:
    """Render a small, safe markdown subset. Every dynamic string is escaped first."""
    out: list[str] = []
    state = {"ul": False, "pre": []}  # type: ignore[var-annotated]
    in_fence = False

    def close_ul() -> None:
        if state["ul"]:
            out.append("</ul>")
            state["ul"] = False

    def flush_pre() -> None:
        if state["pre"]:
            out.append(
                "<pre style='background:#f1f3f4;padding:10px;border-radius:4px;"
                "overflow-x:auto;font-size:12px;'>" + "\n".join(state["pre"]) + "</pre>"
            )
            state["pre"] = []

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            close_ul()
            if in_fence:
                flush_pre()
            in_fence = not in_fence
            continue
        if in_fence:
            state["pre"].append(_esc(line))
            continue
        if stripped.startswith("|"):
            close_ul()
            state["pre"].append(_esc(line))
            continue
        flush_pre()
        if not stripped:
            close_ul()
            continue
        hashes = len(stripped) - len(stripped.lstrip("#"))
        if 1 <= hashes <= 4 and stripped[hashes:hashes + 1] == " ":
            close_ul()
            tag = "h3" if hashes <= 2 else "h4"
            out.append(f"<{tag} style='color:#1a73e8;margin:16px 0 6px;'>{_esc(stripped[hashes + 1:])}</{tag}>")
            continue
        item = None
        for marker in ("→", "->", "- ", "* "):
            if stripped.startswith(marker):
                item = stripped[len(marker):].strip()
                break
        if item is not None:
            if not state["ul"]:
                out.append("<ul style='margin:4px 0;padding-left:22px;'>")
                state["ul"] = True
            out.append(f"<li>{_esc(item)}</li>")
            continue
        close_ul()
        out.append(f"<p style='margin:4px 0'>{_esc(stripped)}</p>")
    close_ul()
    flush_pre()
    return "".join(out)


def _build_html(session_summary: str, report_entries: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary_html = "".join(
        f"<p style='margin:4px 0'>{_esc(line)}</p>" if line.strip() else "<br>"
        for line in (session_summary or "").split("\n")
    )

    td = "style='padding:6px 8px;border:1px solid #dadce0;vertical-align:top;'"
    th = "style='padding:6px 8px;border:1px solid #dadce0;background:#e8f0fe;text-align:left;'"
    rows = ""
    inline_sections = ""
    for entry in report_entries:
        path = str(entry.get("path") or "")
        p = Path(path) if path else None
        exists = bool(p and p.is_file())
        name = p.name if p else "(no path)"
        status = f"✅ {_esc(name)} (attached)" if exists else f"⚠️ {_esc(name)} (not found — not attached)"
        rows += (
            f"<tr><td {td}>{_esc(entry.get('incident_number'))}</td>"
            f"<td {td}>{_esc(entry.get('short_description'))}</td>"
            f"<td {td}>{_esc(entry.get('root_cause'))}</td>"
            f"<td {td}>{status}</td></tr>"
        )
        if exists:
            try:
                md = _read_inline_markdown(p)
            except OSError:
                continue
            note = ""
            if len(md) > MAX_INLINE_CHARS:
                md = md[:MAX_INLINE_CHARS]
                note = "<p style='color:#999;'><em>…truncated — see attachment</em></p>"
            inline_sections += (
                "<div style='background:#fff;padding:12px 16px;border-radius:4px;margin:12px 0;'>"
                f"<h3 style='margin:0 0 8px;'>RCA — {_esc(entry.get('incident_number') or name)}</h3>"
                f"{_render_markdown(md)}{note}</div>"
            )

    attachment_section = ""
    if rows:
        attachment_section = f"""
        <h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:6px;margin-top:24px;">
          Reports
        </h2>
        <table style="border-collapse:collapse;width:100%;background:#fff;font-size:13px;">
          <tr><th {th}>Incident</th><th {th}>Short description</th><th {th}>Root cause</th><th {th}>Report file</th></tr>
          {rows}
        </table>"""
    if inline_sections:
        attachment_section += f"""
        <h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:6px;margin-top:24px;">
          RCA Details
        </h2>
        {inline_sections}"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body{{font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:16px;color:#333;}}
  .hdr{{background:#1a73e8;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;}}
  .hdr h1{{margin:0;font-size:22px;}}
  .hdr p{{margin:4px 0 0;opacity:.85;font-size:13px;}}
  .body{{background:#f8f9fa;padding:24px;border-radius:0 0 8px 8px;}}
  .badge{{display:inline-block;background:#34a853;color:#fff;padding:3px 12px;
          border-radius:12px;font-size:12px;font-weight:bold;margin-bottom:16px;}}
  .summary{{background:#fff;border-left:4px solid #1a73e8;padding:16px 20px;
            border-radius:4px;margin:16px 0;}}
  .alert{{margin-top:24px;padding:16px;background:#fff3cd;border-radius:4px;
          border-left:4px solid #ffc107;}}
  .footer{{font-size:11px;color:#999;margin-top:20px;text-align:center;}}
</style>
</head>
<body>
<div class="hdr">
  <h1>&#128269; RCA Analysis Complete &#8212; Action Required</h1>
  <p>Generated: {now}</p>
</div>
<div class="body">
  <span class="badge">&#10003; ANALYSIS COMPLETE</span>
  <h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:6px;">Session Summary</h2>
  <div class="summary">{summary_html}</div>
  {attachment_section}
  <div class="alert">
    <strong>&#9888;&#65039; Your verification is needed.</strong>
    The RCA agent has completed its analysis. Please review the attached report(s)
    and confirm the findings before closing the incident(s).
  </div>
  <div class="footer">Sent by RCA Copilot Agent &middot; SPACE CDS Platform &middot; L&#8217;Or&#233;al</div>
</div>
</body>
</html>"""
