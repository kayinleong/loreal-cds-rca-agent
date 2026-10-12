---
status: complete
---
## Goal
Rework RCA email: persistent-registry-friendly `report_entries`, escaped HTML, summary table, inline RCA sections, proper attachments and RFC-compliant headers.

## Changes Made
- `rca_copilot_agent/tools/email_tool.py` — removed `_session_reports`/`register_report`/`get_session_reports`; `send_rca_email(..., report_entries=None, verify_ssl=True)`; EmailMessage + SMTP policy (base64 bodies, RFC2231 filenames); attachments as text/markdown; `_render_markdown`, `_read_inline_markdown` (drops `## Evidence`), 20k-char cap; all dynamic text html-escaped.
- `rca_copilot_agent/tests/test_email_tool.py` — 12 offline tests.

## Verification
py_compile OK; unittest test_email_tool.py: 12 tests pass.

## Regression
Only caller of removed functions: `rca_copilot_agent/mcp_server.py:714-715` (register_report) and `:719+` (send_rca_email call) — rewired in wave 2. `ticketasg_copilot_agent` copy untouched.

## Blockers
mcp_server.py temporarily broken at save_rca_report (expected).
