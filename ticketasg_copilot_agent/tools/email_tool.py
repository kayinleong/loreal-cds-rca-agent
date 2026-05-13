"""SMTP email notification for Ticket Assignment session completion."""

from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

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


# Session-level list of report paths saved via save_assignment_report this run.
_session_reports: list[str] = []


def register_report(path: str) -> None:
    """Track a report file saved in this server session."""
    if path not in _session_reports:
        _session_reports.append(path)


def get_session_reports() -> list[str]:
    return list(_session_reports)


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
    report_paths: list[str] | None = None,
    verify_ssl: bool = True,
) -> str:
    """Send an HTML email with assignment report attachments (only files that exist)."""
    if report_paths is None:
        report_paths = get_session_reports()

    html = _build_html(session_summary, report_paths)

    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_from
    msg["To"] = ", ".join(smtp_to)
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    attached: list[str] = []
    for path in report_paths:
        p = Path(path)
        if p.exists() and p.is_file():
            with p.open("rb") as fh:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(fh.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=p.name)
            msg.attach(part)
            attached.append(p.name)

    ctx = _ssl_context(verify=verify_ssl)
    try:
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
                s.starttls(context=ctx)
                if smtp_user and smtp_password:
                    s.login(smtp_user, smtp_password)
                s.sendmail(smtp_from, smtp_to, msg.as_bytes())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=30) as s:
                if smtp_user and smtp_password:
                    s.login(smtp_user, smtp_password)
                s.sendmail(smtp_from, smtp_to, msg.as_bytes())

        suffix = f" with {len(attached)} report(s) attached" if attached else " (no attachments)"
        return f"✓ Email sent to {', '.join(smtp_to)}{suffix}."
    except Exception as exc:
        return f"✗ Failed to send email: {type(exc).__name__}: {exc}"


def _build_html(session_summary: str, report_paths: list[str]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    summary_html = "".join(
        f"<p style='margin:4px 0'>{line}</p>" if line.strip() else "<br>"
        for line in session_summary.split("\n")
    )

    report_items = ""
    for path in report_paths:
        p = Path(path)
        icon = "✅" if p.exists() else "⚠️"
        label = p.name if p.exists() else f"{p.name} (not found — not attached)"
        report_items += f"<li>{icon} {label}</li>"

    attachment_section = ""
    if report_items:
        attachment_section = f"""
        <h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:6px;margin-top:24px;">
          Attached Reports
        </h2>
        <ul style="background:#fff;padding:16px 16px 16px 36px;border-radius:4px;line-height:2;">
          {report_items}
        </ul>"""

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
  <h1>&#128269; Ticket Assignment Analysis Complete &#8212; Action Required</h1>
  <p>Generated: {now}</p>
</div>
<div class="body">
  <span class="badge">&#10003; ASSIGNMENT COMPLETE</span>
  <h2 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:6px;">Session Summary</h2>
  <div class="summary">{summary_html}</div>
  {attachment_section}
  <div class="alert">
    <strong>&#9888;&#65039; Your verification is needed.</strong>
    The Ticket Assignment agent has completed its analysis. Please review the attached report(s)
    and confirm the assignment recommendations before reassigning the incident(s).
  </div>
  <div class="footer">Sent by Ticket Assignment Copilot Agent &middot; SPACE CDS Platform &middot; L&#8217;Or&#233;al</div>
</div>
</body>
</html>"""
