"""Offline tests for the RCA flow wiring in dispatcher._dispatch."""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dispatcher  # noqa: E402
from tools import rca_report_tool  # noqa: E402
from tools.bigquery_tool import QueryResult  # noqa: E402

VALID_REPORT = """### WHAT HAPPENED
Order ORD123 is not visible in the CDS portal.

### WHAT WE CHECKED
→ Checked BigQuery purchase table — 0 rows for ORD123

### WHAT WE FOUND
The order never reached CDS because the upstream feed dropped it.

### WHAT WE NEED / DID
- Escalate to `APAC - SGP - SPACE CDS SAPMENA L3 Support` to replay the order
"""

INVALID_REPORT = """### WHAT HAPPENED
Something broke.

### WHAT WE CHECKED
→ Checked nothing
"""


def run(name, args, reports_dir):
    return asyncio.run(dispatcher._dispatch(name, args, reports_dir))


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name


class QueryBigQueryTests(_Base):
    def _patches(self, result=None):
        result = result or QueryResult(success=True, row_count=2, columns=["a"], data=[{"a": 1}, {"a": 2}], sql="SELECT 1")
        return (
            mock.patch("tools.bigquery_tool.is_enabled", return_value=True),
            mock.patch("tools.bigquery_tool.query_bigquery_result", return_value=result),
        )

    def test_with_incident_number_records_evidence(self):
        p1, p2 = self._patches()
        with p1, p2:
            out = run("query_bigquery", {"sql": "SELECT 1", "rationale": "r", "incident_number": "INC1"}, self.dir)
        self.assertIn("a", out)
        ev = rca_report_tool.load_evidence(self.dir, "INC1")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["sql"], "SELECT 1")
        self.assertEqual(ev[0]["row_count"], 2)

    def test_without_incident_number_no_evidence(self):
        p1, p2 = self._patches()
        with p1, p2:
            run("query_bigquery", {"sql": "SELECT 1"}, self.dir)
        self.assertEqual(list(Path(self.dir).rglob("*.jsonl")), [])
        self.assertEqual(rca_report_tool.load_evidence(self.dir, "INC1"), [])

    def test_record_failure_still_returns_result(self):
        p1, p2 = self._patches()
        with p1, p2, mock.patch.object(rca_report_tool, "record_query", side_effect=OSError("disk")):
            out = run("query_bigquery", {"sql": "SELECT 1", "incident_number": "INC1"}, self.dir)
        self.assertNotIn("Tool error", out)
        self.assertIn("a", out)

    def test_disabled_guard(self):
        with mock.patch("tools.bigquery_tool.is_enabled", return_value=False):
            out = run("query_bigquery", {"sql": "SELECT 1"}, self.dir)
        self.assertIn("BigQuery", out)


class TemplateAndSaveTests(_Base):
    def test_template_has_sections(self):
        out = run("get_rca_template", {}, self.dir)
        for sec in ("WHAT HAPPENED", "WHAT WE CHECKED", "WHAT WE FOUND", "WHAT WE NEED / DID"):
            self.assertIn(sec, out)

    def test_save_valid_appends_evidence(self):
        rca_report_tool.record_query(
            self.dir, "INC1", sql="SELECT EVIDENCE_MARKER", rationale="r", success=True, row_count=0, error=None
        )
        out = run("save_rca_report", {"incident_number": "INC1", "report_text": VALID_REPORT}, self.dir)
        self.assertTrue(out.startswith("✓ RCA report saved: "), out)
        path = out.splitlines()[0].split(": ", 1)[1]
        self.assertTrue(Path(path).is_file())
        self.assertIn("EVIDENCE_MARKER", Path(path).read_text(encoding="utf-8"))
        self.assertIn("Evidence: 1", out)

    def test_save_invalid_not_saved(self):
        out = run("save_rca_report", {"incident_number": "INC1", "report_text": INVALID_REPORT}, self.dir)
        self.assertTrue(out.startswith("✗ RCA report NOT saved"), out)
        self.assertIn("get_rca_template", out)
        self.assertEqual(list(Path(self.dir).rglob("*.md")), [])

    def test_save_includes_store_metadata_with_dict_values(self):
        inc = {
            "incident": {
                "short_description": "Order missing UNIQUE_DESC",
                "state": {"display_value": "In Progress", "link": "http://x"},
                "priority": {"value": "2"},
                "assignment_group": None,
                "sys_id": "abc",
            }
        }
        store = SimpleNamespace(get_incident=lambda n: inc if n == "INC1" else None, incidents={"INC1": inc})
        with mock.patch("tools.incident_store.get_store", return_value=store):
            out = run("save_rca_report", {"incident_number": "INC1", "report_text": VALID_REPORT}, self.dir)
        self.assertTrue(out.startswith("✓"), out)
        text = Path(out.splitlines()[0].split(": ", 1)[1]).read_text(encoding="utf-8")
        self.assertIn("UNIQUE_DESC", text)
        self.assertIn("In Progress", text)
        self.assertNotIn("http://x", text)

    def test_display_value_helper(self):
        f = dispatcher._display_value
        self.assertEqual(f(None), "")
        self.assertEqual(f("x"), "x")
        self.assertEqual(f({"display_value": "D", "value": "V"}), "D")
        self.assertEqual(f({"value": "V"}), "V")


class SendEmailTests(_Base):
    def setUp(self):
        super().setUp()
        self.smtp = SimpleNamespace(
            enabled=True, host="h", port=25, user="u", password="p", from_addr="f@x", to_addrs=["t@x"],
            use_tls=False, verify_ssl=True,
        )
        for n in ("INC1", "INC2"):
            run("save_rca_report", {"incident_number": n, "report_text": VALID_REPORT}, self.dir)

    def _send(self, args, ret="✓ Email sent to t@x"):
        captured = {}

        def fake(**kw):
            captured.update(kw)
            return ret

        with mock.patch("config.load_smtp_config", return_value=self.smtp), \
                mock.patch("tools.email_tool.send_rca_email", side_effect=fake):
            out = run("send_rca_email", {"session_summary": "s", **args}, self.dir)
        return out, captured.get("report_entries")

    def test_pending_then_marked(self):
        out, entries = self._send({})
        self.assertTrue(out.startswith("✓"))
        self.assertEqual({e["incident_number"] for e in entries}, {"INC1", "INC2"})
        _, entries2 = self._send({})
        self.assertEqual(entries2, [])

    def test_incident_numbers_filter(self):
        _, entries = self._send({"incident_numbers": ["inc1"]})
        self.assertEqual([e["incident_number"] for e in entries], ["INC1"])
        _, rest = self._send({})
        self.assertEqual([e["incident_number"] for e in rest], ["INC2"])

    def test_failure_does_not_mark(self):
        out, entries = self._send({}, ret="✗ SMTP error")
        self.assertTrue(out.startswith("✗"))
        self.assertEqual(len(entries), 2)
        _, again = self._send({})
        self.assertEqual(len(again), 2)

    def test_mark_emailed_failure_still_success(self):
        with mock.patch("tools.rca_report_tool.mark_emailed", side_effect=OSError("disk full")):
            out, _ = self._send({})
        self.assertTrue(out.startswith("✓"))
        self.assertIn("⚠ Email sent, but reports could not be marked as emailed (OSError: disk full)", out)

    def test_attached_incidents_line(self):
        out, _ = self._send({})
        self.assertIn("Attached incidents: INC1, INC2", out)
        out2, _ = self._send({})
        self.assertIn("Attached incidents: none", out2)
        self.assertNotIn("⚠", out2)

    def test_incident_numbers_string_normalised(self):
        with mock.patch("tools.rca_report_tool.pending_reports", return_value=[]) as pr:
            self._send({"incident_numbers": "INC1, INC2  inc3"})
        self.assertEqual(pr.call_args[0][1], ["INC1", "INC2", "inc3"])
        with mock.patch("tools.rca_report_tool.pending_reports", return_value=[]) as pr:
            self._send({"incident_numbers": ["", " INC1 "]})
        self.assertEqual(pr.call_args[0][1], ["INC1"])
        with mock.patch("tools.rca_report_tool.pending_reports", return_value=[]) as pr:
            self._send({"incident_numbers": "  "})
        self.assertIsNone(pr.call_args[0][1])

    def test_smtp_disabled_message(self):
        self.smtp.enabled = False
        with mock.patch("config.load_smtp_config", return_value=self.smtp):
            out = run("send_rca_email", {"session_summary": "s"}, self.dir)
        self.assertTrue(out.startswith("✗ SMTP not configured."))


class PostCommentTests(_Base):
    def test_unconfirmed_preview_no_reader(self):
        with mock.patch.object(dispatcher, "_build_reader", side_effect=AssertionError("reader built")):
            out = run("post_comment", {"incident_number": "INC1", "text": "hello there", "as_work_note": True}, self.dir)
        self.assertTrue(out.startswith("⚠ NOT POSTED — preview only."))
        self.assertIn("INC1", out)
        self.assertIn("incident", out)
        self.assertIn("work note", out)
        self.assertIn("---\nhello there\n---", out)
        self.assertIn("confirmed=true", out)

    def test_confirmed_false_string_is_unconfirmed(self):
        with mock.patch.object(dispatcher, "_build_reader", side_effect=AssertionError("reader built")):
            out = run("post_comment", {"incident_number": "INC1", "text": "t", "confirmed": "false"}, self.dir)
        self.assertTrue(out.startswith("⚠ NOT POSTED"))

    def test_confirmed_posts_to_right_table(self):
        for confirmed in (True, "TRUE", "true"):
            for number, table in (("INC1", "incident"), ("RITM2", "sc_req_item"), ("TASK3", "sc_task")):
                reader = mock.Mock()
                reader.post_comment.return_value = True
                with mock.patch.object(dispatcher, "_build_reader", return_value=(reader, None)), \
                        mock.patch.object(dispatcher, "_resolve_sys_id", return_value="sid"):
                    out = run("post_comment", {"incident_number": number, "text": "t", "confirmed": confirmed}, self.dir)
                self.assertTrue(out.startswith("✓ Posted comment"), out)
                reader.post_comment.assert_called_once_with(
                    incident_sys_id="sid", text="t", as_work_note=False, table=table
                )


class ToolNamesTests(unittest.TestCase):
    def test_matches_dispatch_branches(self):
        src = inspect.getsource(dispatcher._dispatch)
        branches = set(re.findall(r'(?:if|elif) name == "([a-z_]+)"', src))
        self.assertEqual(set(dispatcher.TOOL_NAMES), branches)
        self.assertEqual(len(dispatcher.TOOL_NAMES), 15)
        self.assertEqual(len(set(dispatcher.TOOL_NAMES)), 15)


if __name__ == "__main__":
    unittest.main()
