"""Offline tests for tools/rca_report_tool.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import rca_report_tool as rr  # noqa: E402

GOOD = """### WHAT HAPPENED
Order 123 is not visible in the portal.

### WHAT WE CHECKED
→ Checked BigQuery sales_order — 0 rows
→ Checked work notes — HIP returned 400

### WHAT WE FOUND
Upstream HIP rejected the order.
Second line.

### WHAT WE NEED / DID
- Escalate to APAC - SGP - SPACE CDS SAPMENA L3 Support
"""


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.dir = self._td.name


class TemplateTests(unittest.TestCase):
    def test_template_contents(self):
        t = rr.get_rca_template()
        for s in rr.RCA_SECTIONS:
            self.assertIn(f"### {s}", t)
        self.assertIn("`APAC - CHN - SPACE Loyalty L3 Support`", t)
        self.assertIn("`CDS L3`", t)
        self.assertIn("INFRA - WW - Linux Unix ACN - L3", t)
        self.assertIn("[USER-CONFIRM]", t)
        self.assertIn("→ Checked", t)

    def test_template_itself_validates_structurally(self):
        errors, _ = rr.validate_rca_report(rr.get_rca_template().split("```")[1])
        self.assertEqual(errors, [])


class ParseValidateTests(unittest.TestCase):
    def test_good(self):
        errors, warnings = rr.validate_rca_report(GOOD)
        self.assertEqual((errors, warnings), ([], []))
        sec = rr.parse_sections(GOOD)
        self.assertEqual(list(sec), list(rr.RCA_SECTIONS))
        self.assertIn("Second line.", sec["WHAT WE FOUND"])

    def test_heading_variants(self):
        txt = (
            "# what happened\nA\n## **WHAT WE CHECKED**:\n→ x\n"
            "#### What We Found:\nC\n### WHAT WE NEED/DID\nD\n"
        )
        self.assertEqual(rr.validate_rca_report(txt)[0], [])
        alt = "### WHAT WE NEED / WHAT WE DID\nD"
        self.assertEqual(rr.parse_sections(alt), {"WHAT WE NEED / DID": "D"})

    def test_missing_and_empty(self):
        txt = "### WHAT HAPPENED\nA\n### WHAT WE CHECKED\n\n### WHAT WE FOUND\nC\n"
        errors, _ = rr.validate_rca_report(txt)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("WHAT WE NEED / DID" in e for e in errors))
        self.assertTrue(any("empty" in e and "CHECKED" in e for e in errors))

    def test_body_stops_at_evidence(self):
        txt = GOOD + "\n" + rr.EVIDENCE_HEADING + "\n1. foo\n"
        self.assertNotIn("Evidence", rr.parse_sections(txt)["WHAT WE NEED / DID"])

    def test_warnings(self):
        txt = GOOD.replace("→ Checked BigQuery sales_order — 0 rows\n→ Checked work notes — HIP returned 400",
                           "just prose").replace("Second line.", "{result} then CDS L3 and LOY team")
        errors, warnings = rr.validate_rca_report(txt)
        self.assertEqual(errors, [])
        joined = "\n".join(warnings)
        self.assertIn("no evidence lines", joined)
        self.assertIn("{result}", joined)
        self.assertIn("'CDS L3'", joined)
        self.assertIn("'LOY team'", joined)

    def test_canonical_loyalty_l3_not_flagged(self):
        txt = GOOD.replace("APAC - SGP - SPACE CDS SAPMENA L3 Support", "APAC - CHN - SPACE Loyalty L3 Support")
        self.assertEqual(rr.validate_rca_report(txt)[1], [])

    def test_canonical_cds_l3_not_flagged(self):
        self.assertEqual(rr.validate_rca_report(GOOD)[1], [])


class EvidenceRenderTests(_Tmp):
    def test_record_load_non_ascii(self):
        rr.record_query(self.dir, "INC1", sql="SELECT 'Oréal'", rationale="ñ check",
                        success=True, row_count=3, error=None)
        rr.record_query(self.dir, "INC1", sql="BAD", rationale="r", success=False,
                        row_count=0, error="x" * 500)
        p = Path(self.dir) / "rca_reports" / ".evidence" / "INC1.jsonl"
        with p.open("a", encoding="utf-8") as fh:
            fh.write("{corrupt\n")
        ev = rr.load_evidence(self.dir, "INC1")
        self.assertEqual(len(ev), 2)
        self.assertEqual(ev[0]["rationale"], "ñ check")
        self.assertIn("Oréal", p.read_text(encoding="utf-8"))
        self.assertEqual(len(ev[1]["error"]), 300)
        self.assertEqual(set(ev[0]), {"ts", "sql", "rationale", "success", "row_count", "error"})
        self.assertEqual(rr.load_evidence(self.dir, "NOPE"), [])

    def test_render(self):
        ev = [{"sql": "SELECT 1\nFROM t", "rationale": "why", "success": True, "row_count": 2},
              {"sql": "BAD", "rationale": "", "success": False, "row_count": 0, "error": "boom"}]
        out = rr.render_report("INC9", GOOD, {"state": "New", "caller_id": "Jane Doe",
                                              "short_description": "a|b"}, ev)
        self.assertTrue(out.startswith("# RCA Report — INC9"))
        self.assertIn("| state | New |", out)
        self.assertIn("a\\|b", out)
        self.assertNotIn("Jane", out)
        self.assertIn("_Generated: ", out)
        self.assertIn("### WHAT HAPPENED", out)
        self.assertIn(rr.EVIDENCE_HEADING, out)
        self.assertIn("✓ 2 row(s)", out)
        self.assertIn("✗ boom", out)
        self.assertIn("```sql", out)
        self.assertIn("FROM t", out)

    def test_render_no_evidence_and_no_dup(self):
        out = rr.render_report("INC9", GOOD + "\n" + rr.EVIDENCE_HEADING + "\nold", None, [])
        self.assertEqual(out.count(rr.EVIDENCE_HEADING), 1)
        self.assertNotIn("old", out)
        self.assertIn("No BigQuery queries were recorded", out)


class SaveRegistryTests(_Tmp):
    def test_save_writes_files(self):
        rr.record_query(self.dir, "INC1", sql="S", rationale="r", success=True, row_count=1, error=None)
        res = rr.save_report(self.dir, "INC1", GOOD, {"short_description": "sd"})
        self.assertTrue(Path(res["path"]).is_file())
        data = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
        self.assertEqual(data["incident_number"], "INC1")
        self.assertEqual(res["evidence_count"], 1)
        self.assertEqual(set(data), {"incident_number", "generated_at", "sections", "warnings", "evidence"})
        reg = json.loads((Path(self.dir) / "rca_reports" / ".registry.json").read_text(encoding="utf-8"))
        self.assertEqual(reg[0]["root_cause"], "Upstream HIP rejected the order.")
        self.assertIsNone(reg[0]["emailed_at"])

    def test_invalid_raises(self):
        with self.assertRaises(ValueError) as cm:
            rr.save_report(self.dir, "INC1", "### WHAT HAPPENED\nx")
        self.assertIn("WHAT WE FOUND", str(cm.exception))
        self.assertEqual(rr.pending_reports(self.dir), [])

    def test_same_second_collision(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        b = rr.save_report(self.dir, "INC1", GOOD)
        c = rr.save_report(self.dir, "INC1", GOOD)
        self.assertEqual(len({a["path"], b["path"], c["path"]}), 3)

    def test_supersede_pending_and_mark_emailed(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        b = rr.save_report(self.dir, "inc1", GOOD)
        c = rr.save_report(self.dir, "INC2", GOOD)
        pend = rr.pending_reports(self.dir)
        self.assertEqual({p["path"] for p in pend}, {b["path"], c["path"]})
        self.assertEqual([p["path"] for p in rr.pending_reports(self.dir, ["Inc2"])], [c["path"]])
        self.assertEqual(set(pend[0]), {"incident_number", "path", "saved_at", "short_description", "root_cause"})
        rr.mark_emailed(self.dir, [b["path"]])
        self.assertEqual([p["path"] for p in rr.pending_reports(self.dir)], [c["path"]])
        # emailed entries are not superseded by a later save
        d = rr.save_report(self.dir, "INC1", GOOD)
        self.assertEqual({p["path"] for p in rr.pending_reports(self.dir)}, {c["path"], d["path"]})
        self.assertNotIn(a["path"], {p["path"] for p in rr.pending_reports(self.dir)})

    def test_missing_file_not_pending(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        os.unlink(a["path"])
        self.assertEqual(rr.pending_reports(self.dir), [])

    def test_corrupt_registry_recovery(self):
        reg = Path(self.dir) / "rca_reports" / ".registry.json"
        reg.parent.mkdir(parents=True)
        reg.write_text("{not json", encoding="utf-8")
        self.assertEqual(rr.pending_reports(self.dir), [])
        a = rr.save_report(self.dir, "INC1", GOOD)
        self.assertEqual([p["path"] for p in rr.pending_reports(self.dir)], [a["path"]])

    def test_safe_inc_no_traversal(self):
        res = rr.save_report(self.dir, "INC/../x", GOOD)
        p = Path(res["path"]).resolve()
        self.assertEqual(p.parent, (Path(self.dir) / "rca_reports").resolve())
        self.assertNotIn("/", Path(res["path"]).name)
        rr.record_query(self.dir, "..\\..\\evil", sql="S", rationale="r", success=True, row_count=0, error=None)
        files = list((Path(self.dir) / "rca_reports" / ".evidence").iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(rr._safe_inc("INC/../x"), "INC____x")


def _iso(delta_hours: float) -> str:
    return (datetime.now().astimezone() + timedelta(hours=delta_hours)).isoformat(timespec="seconds")


def _write_ev(d, inc, ts, sql="S"):
    p = Path(d) / "rca_reports" / ".evidence"
    p.mkdir(parents=True, exist_ok=True)
    with open(p / f"{rr._safe_inc(inc)}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": ts, "sql": sql, "rationale": "r", "success": True,
                             "row_count": 1, "error": None}) + "\n")


def _reg(d):
    return json.loads((Path(d) / "rca_reports" / ".registry.json").read_text(encoding="utf-8"))


def _set_reg(d, reg):
    (Path(d) / "rca_reports" / ".registry.json").write_text(json.dumps(reg), encoding="utf-8")


class HeadingStyleTests(unittest.TestCase):
    NAMES = {
        "WHAT HAPPENED": ["WHAT HAPPENED"],
        "WHAT WE CHECKED": ["WHAT WE CHECKED"],
        "WHAT WE FOUND": ["WHAT WE FOUND"],
        "WHAT WE NEED / DID": [
            "WHAT WE NEED / DID", "WHAT WE NEED/DID", "WHAT WE NEED & DID", "WHAT WE NEED AND DID",
            "WHAT WE DID / NEED", "WHAT WE NEED / WHAT WE DID", "WHAT WE NEED TO DO", "WHAT WE NEED",
            "NEXT STEPS / WHAT WE NEED",
        ],
    }

    def _check(self, line_fmt, **kw):
        for canon, variants in self.NAMES.items():
            for v in variants:
                for text in (v, v.title()):
                    line = line_fmt.format(n=text)
                    got = rr.parse_sections(line + "\nBODY")
                    self.assertEqual(got, {canon: "BODY"}, line)

    def test_hash_levels_and_indent(self):
        for h in ("#", "##", "###", "####", "#####", "######"):
            self._check(h + " {n}")
        self._check("   ### {n}")

    def test_numbering_and_emoji(self):
        for fmt in ("### 1. {n}", "### 2) {n}", "## Step 1: {n}", "### \U0001F50D {n}",
                    "### \u2705 3. {n}", "**1. {n}**"):
            self._check(fmt)

    def test_bold_only_and_plain(self):
        for fmt in ("**{n}**", "**{n}:**", "**{n}**:", "{n}", "{n}:", "**{n}**  ", "1. {n}"):
            self._check(fmt)

    def test_trailing_descriptive_text(self):
        self.assertEqual(rr.parse_sections("### WHAT HAPPENED (symptom)\nA"), {"WHAT HAPPENED": "A"})
        self.assertEqual(rr.parse_sections("### WHAT WE FOUND \u2014 root cause\nA"), {"WHAT WE FOUND": "A"})
        self.assertEqual(rr.parse_sections("**WHAT WE CHECKED (systems)**\nA"), {"WHAT WE CHECKED": "A"})

    def test_crlf(self):
        txt = GOOD.replace("\n", "\r\n")
        self.assertEqual(rr.validate_rca_report(txt), ([], []))
        self.assertEqual(rr.parse_sections("**WHAT HAPPENED**\r\nA\r\n"), {"WHAT HAPPENED": "A"})

    def test_body_sentences_not_headings(self):
        txt = (
            "### WHAT HAPPENED\nA\nWe checked what we found in BigQuery\n"
            "\u2192 Checked purchase \u2014 what happened was a timeout\n"
            "I know what we need to do next\n"
            "    ### WHAT WE FOUND\n"
        )
        self.assertEqual(list(rr.parse_sections(txt)), ["WHAT HAPPENED"])
        self.assertIn("what we found in BigQuery", rr.parse_sections(txt)["WHAT HAPPENED"])

    def test_no_warn_for_ordinary_prose(self):
        txt = GOOD.replace("Second line.", "MARS Ops looked and the Azure team replied.")
        self.assertEqual(rr.validate_rca_report(txt)[1], [])


class PendingFilterTests(_Tmp):
    def test_string_filters(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        b = rr.save_report(self.dir, "INC2", GOOD)
        c = rr.save_report(self.dir, "INC3", GOOD)
        paths = lambda f: {p["path"] for p in rr.pending_reports(self.dir, f)}  # noqa: E731
        self.assertEqual(paths("INC1"), {a["path"]})
        self.assertEqual(paths("inc1, INC2"), {a["path"], b["path"]})
        self.assertEqual(paths("INC1 INC3"), {a["path"], c["path"]})
        self.assertEqual(paths(("INC2",)), {b["path"]})
        self.assertEqual(paths(["INC3"]), {c["path"]})
        self.assertEqual(paths(None), {a["path"], b["path"], c["path"]})
        self.assertEqual(paths(""), {a["path"], b["path"], c["path"]})
        self.assertEqual(paths(" , "), {a["path"], b["path"], c["path"]})
        self.assertEqual(paths([]), {a["path"], b["path"], c["path"]})

    def test_stale_unfiltered_excluded_filtered_included(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        reg = _reg(self.dir)
        reg[0]["saved_at"] = _iso(-30)
        _set_reg(self.dir, reg)
        self.assertEqual(rr.pending_reports(self.dir), [])
        self.assertEqual([p["path"] for p in rr.pending_reports(self.dir, "INC1")], [a["path"]])
        with mock.patch.dict(os.environ, {"RCA_SESSION_WINDOW_HOURS": "48"}):
            self.assertEqual([p["path"] for p in rr.pending_reports(self.dir)], [a["path"]])

    def test_naive_saved_at_supported(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        reg = _reg(self.dir)
        reg[0]["saved_at"] = datetime.now().isoformat(timespec="seconds")
        _set_reg(self.dir, reg)
        self.assertEqual([p["path"] for p in rr.pending_reports(self.dir)], [a["path"]])


class WindowEnvTests(unittest.TestCase):
    def test_parsing(self):
        for val, exp in (("", 24), ("abc", 24), ("0", 24), ("-5", 24), ("nan", 24), ("6", 6), ("1.5", 1.5)):
            with mock.patch.dict(os.environ, {"RCA_SESSION_WINDOW_HOURS": val}):
                self.assertEqual(rr._session_window_hours(), exp, val)
        env = {k: v for k, v in os.environ.items() if k != "RCA_SESSION_WINDOW_HOURS"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(rr._session_window_hours(), 24)


class EvidenceWindowTests(_Tmp):
    def test_load_evidence_since(self):
        _write_ev(self.dir, "INC1", _iso(-5), "old")
        _write_ev(self.dir, "INC1", datetime.now().isoformat(timespec="seconds"), "naive-new")
        _write_ev(self.dir, "INC1", _iso(1), "new")
        self.assertEqual(len(rr.load_evidence(self.dir, "INC1")), 3)
        got = rr.load_evidence(self.dir, "INC1", since=datetime.now().astimezone() - timedelta(hours=1))
        self.assertEqual([e["sql"] for e in got], ["naive-new", "new"])

    def test_record_query_ts_is_aware(self):
        rr.record_query(self.dir, "INC1", sql="S", rationale="r", success=True, row_count=1, error=None)
        self.assertIsNotNone(rr._parse_ts(rr.load_evidence(self.dir, "INC1")[0]["ts"]).tzinfo)

    def test_old_evidence_beyond_window_excluded(self):
        _write_ev(self.dir, "INC1", _iso(-30), "ancient")
        _write_ev(self.dir, "INC1", _iso(-1), "recent")
        res = rr.save_report(self.dir, "INC1", GOOD)
        self.assertEqual(res["evidence_count"], 1)
        self.assertEqual(len(rr.load_evidence(self.dir, "INC1")), 2)

    def test_evidence_before_emailed_save_excluded(self):
        _write_ev(self.dir, "INC1", _iso(-3), "first-rca")
        a = rr.save_report(self.dir, "INC1", GOOD)
        self.assertEqual(a["evidence_count"], 1)
        reg = _reg(self.dir)
        reg[0]["saved_at"] = _iso(-2)  # the emailed report was saved 2h ago
        _set_reg(self.dir, reg)
        rr.mark_emailed(self.dir, [a["path"]])
        _write_ev(self.dir, "INC1", _iso(-1), "second-rca")
        b = rr.save_report(self.dir, "inc1", GOOD)
        self.assertEqual(b["evidence_count"], 1)
        data = json.loads(Path(b["json_path"]).read_text(encoding="utf-8"))
        self.assertEqual([e["sql"] for e in data["evidence"]], ["second-rca"])

    def test_resave_before_email_keeps_evidence(self):
        _write_ev(self.dir, "INC1", _iso(-3), "q1")
        a = rr.save_report(self.dir, "INC1", GOOD)
        b = rr.save_report(self.dir, "INC1", GOOD)
        self.assertEqual((a["evidence_count"], b["evidence_count"]), (1, 1))


class LockTests(_Tmp):
    def test_acquire_release(self):
        lock = rr._lock_path(self.dir)
        with rr._registry_lock(self.dir) as held:
            self.assertTrue(held)
            self.assertTrue(lock.exists())
        self.assertFalse(lock.exists())

    def test_released_on_exception(self):
        with self.assertRaises(RuntimeError):
            with rr._registry_lock(self.dir):
                raise RuntimeError("x")
        self.assertFalse(rr._lock_path(self.dir).exists())

    def test_save_and_mark_leave_no_lock(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        rr.mark_emailed(self.dir, [a["path"]])
        self.assertFalse(rr._lock_path(self.dir).exists())

    def test_stale_lock_removed(self):
        lock = rr._lock_path(self.dir)
        lock.parent.mkdir(parents=True)
        lock.write_text("")
        old = lock.stat().st_mtime - 120
        os.utime(lock, (old, old))
        with rr._registry_lock(self.dir) as held:
            self.assertTrue(held)
        self.assertFalse(lock.exists())

    def test_timeout_proceeds_and_keeps_foreign_lock(self):
        lock = rr._lock_path(self.dir)
        lock.parent.mkdir(parents=True)
        lock.write_text("")  # fresh lock held by "another process"
        with mock.patch.object(rr, "_LOCK_TIMEOUT_S", 0.2), mock.patch.object(rr, "_LOCK_POLL_S", 0.02):
            with self.assertLogs(rr.logger, level="WARNING"):
                with rr._registry_lock(self.dir) as held:
                    self.assertFalse(held)
                a = rr.save_report(self.dir, "INC1", GOOD)
        self.assertTrue(lock.exists())
        self.assertTrue(Path(a["path"]).is_file())


class PathAndTitleTests(_Tmp):
    def test_abspath_stored_and_old_relative_entries_match(self):
        a = rr.save_report(self.dir, "INC1", GOOD)
        self.assertTrue(os.path.isabs(_reg(self.dir)[0]["path"]))
        self.assertTrue(os.path.isabs(a["path"]))
        reg = _reg(self.dir)
        rel = os.path.relpath(reg[0]["path"])
        reg[0]["path"] = rel
        _set_reg(self.dir, reg)
        rr.mark_emailed(self.dir, [a["path"]])
        self.assertTrue(_reg(self.dir)[0]["emailed_at"])

    def test_title_sanitised(self):
        out = rr.render_report("INC1\n# injected\r\n## more", "### WHAT HAPPENED\nA", None, [])
        self.assertEqual(out.splitlines()[0], "# RCA Report \u2014 INC1 # injected ## more")
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("# ")), 1)
        res = rr.save_report(self.dir, "INC9\n# x", GOOD)
        self.assertNotIn("\n", Path(res["path"]).name)
        self.assertEqual(_reg(self.dir)[0]["incident_number"], "INC9 # x")


if __name__ == "__main__":
    unittest.main()
