"""Offline tests for tools.email_tool (smtplib is always mocked)."""

from __future__ import annotations

import email
import sys
import tempfile
import unittest
from email import policy
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import email_tool  # noqa: E402

SMTP_ARGS = dict(
    smtp_host="smtp.example.test", smtp_port=587, smtp_user="u", smtp_password="p",
    smtp_from="from@example.test", smtp_to=["to@example.test"], use_tls=True,
)


def _send(entries, subject="Subj", summary="Sum", **over):
    args = {**SMTP_ARGS, **over}
    with mock.patch("smtplib.SMTP") as smtp, mock.patch("smtplib.SMTP_SSL") as ssl_:
        result = email_tool.send_rca_email(
            subject=subject, session_summary=summary, report_entries=entries, **args
        )
    return result, smtp, ssl_


def _sent_bytes(mock_cls) -> bytes:
    inst = mock_cls.return_value.__enter__.return_value
    return inst.sendmail.call_args[0][2]


def _html_of(raw: bytes) -> str:
    msg = email.message_from_bytes(raw, policy=policy.default)
    return msg.get_body(preferencelist=("html",)).get_content()


class EmailToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _report(self, name="INC1.md", text="# Title\n- item\n"):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def _entry(self, path, inc="INC1", sd="short", rc="cause"):
        return {"incident_number": inc, "path": str(path), "short_description": sd, "root_cause": rc}

    def test_escaping(self):
        p = self._report(text="# H <script>alert(1)</script>\nbody <script>x</script>\n")
        res, smtp, _ = _send(
            [self._entry(p, sd="<script>sd</script>")], summary="<script>sum</script>\nline2"
        )
        html = _html_of(_sent_bytes(smtp))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;sum", html)
        self.assertIn("&lt;script&gt;sd", html)
        self.assertIn("&lt;script&gt;x", html)
        self.assertIn("line2", html)

    def test_summary_table_and_attached(self):
        p = self._report()
        res, smtp, _ = _send([self._entry(p, inc="INC42", sd="SD42", rc="RC42")])
        html = _html_of(_sent_bytes(smtp))
        for token in ("INC42", "SD42", "RC42", "✅", "INC1.md"):
            self.assertIn(token, html)
        self.assertEqual(res, "✓ Email sent to to@example.test with 1 report(s) attached.")

    def test_evidence_not_inlined_but_attached(self):
        p = self._report(text="# R\nroot cause text\n## Evidence\nSECRET_EVIDENCE_ROW\n")
        _, smtp, _ = _send([self._entry(p)])
        raw = _sent_bytes(smtp)
        self.assertNotIn("SECRET_EVIDENCE_ROW", _html_of(raw))
        msg = email.message_from_bytes(raw, policy=policy.default)
        atts = list(msg.iter_attachments())
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0].get_content_type(), "text/markdown")
        self.assertIn("SECRET_EVIDENCE_ROW", atts[0].get_content())
        self.assertIn("root cause text", _html_of(raw))

    def test_missing_file(self):
        p = self._report()
        missing = self.dir / "nope.md"
        res, smtp, _ = _send([self._entry(p), self._entry(missing, inc="INC2")])
        raw = _sent_bytes(smtp)
        self.assertIn("1 report(s) attached", res)
        self.assertIn("⚠️", _html_of(raw))
        self.assertIn("not attached", _html_of(raw))
        self.assertEqual(len(list(email.message_from_bytes(raw, policy=policy.default).iter_attachments())), 1)

    def test_no_entries(self):
        for entries in (None, []):
            res, smtp, _ = _send(entries)
            self.assertEqual(res, "✓ Email sent to to@example.test (no attachments).")

    def test_non_ascii_roundtrip(self):
        p = self._report(name="报告-Oréal.md", text="# 根因\n- L'Oréal 中文\n")
        subject = "RCA Complete — L'Oréal 中文"
        _, smtp, _ = _send([self._entry(p)], subject=subject, summary="摘要 é")
        raw = _sent_bytes(smtp)
        raw.decode("ascii")  # headers/body must be 7-bit clean
        msg = email.message_from_bytes(raw, policy=policy.default)
        self.assertEqual(msg["Subject"], subject)
        html = msg.get_body(preferencelist=("html",)).get_content()
        self.assertIn("摘要 é", html)
        self.assertIn("L'Oréal 中文".replace("'", "&#x27;"), html)
        att = list(msg.iter_attachments())[0]
        self.assertEqual(att.get_filename(), "报告-Oréal.md")
        self.assertIn("根因", att.get_content())

    def test_starttls_vs_ssl(self):
        _, smtp, ssl_ = _send(None, use_tls=True)
        smtp.assert_called_once()
        ssl_.assert_not_called()
        smtp.return_value.__enter__.return_value.starttls.assert_called_once()
        smtp.return_value.__enter__.return_value.login.assert_called_once_with("u", "p")
        self.assertEqual(smtp.call_args.kwargs["timeout"], 30)

        _, smtp, ssl_ = _send(None, use_tls=False)
        ssl_.assert_called_once()
        smtp.assert_not_called()
        self.assertEqual(ssl_.call_args.kwargs["timeout"], 30)

    def test_no_login_without_credentials(self):
        _, smtp, _ = _send(None, smtp_user="", smtp_password="")
        smtp.return_value.__enter__.return_value.login.assert_not_called()

    def test_smtp_failure(self):
        with mock.patch("smtplib.SMTP", side_effect=ConnectionRefusedError("boom")):
            res = email_tool.send_rca_email(subject="s", session_summary="x", **SMTP_ARGS)
        self.assertEqual(res, "✗ Failed to send email: ConnectionRefusedError: boom")

    def test_truncation(self):
        long_body = "line\n" * 10_000
        p = self._report(text="# R\n" + long_body)
        _, smtp, _ = _send([self._entry(p)])
        html = _html_of(_sent_bytes(smtp))
        self.assertIn("truncated — see attachment", html)
        self.assertLess(html.count("<p style='margin:4px 0'>line</p>"), 10_000)

    def test_markdown_subset(self):
        p = self._report(text="# A\n#### B\n→ arrow\n* star\n| a | b |\n```\ncode <b>\n```\nplain\n")
        _, smtp, _ = _send([self._entry(p)])
        html = _html_of(_sent_bytes(smtp))
        self.assertIn("<h3", html)
        self.assertIn("<h4", html)
        self.assertIn("<li>arrow</li>", html)
        self.assertIn("<li>star</li>", html)
        self.assertIn("<pre", html)
        self.assertIn("code &lt;b&gt;", html)

    def test_removed_session_state(self):
        for name in ("_session_reports", "register_report", "get_session_reports"):
            self.assertFalse(hasattr(email_tool, name))


if __name__ == "__main__":
    unittest.main()
