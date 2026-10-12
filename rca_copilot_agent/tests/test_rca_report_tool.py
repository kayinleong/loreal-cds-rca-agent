"""Offline tests for tools/rca_report_tool.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
