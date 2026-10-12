"""Offline tests for run_tool argument parsing (never calls main())."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_tool import _build_parser, _load_arguments  # noqa: E402


class FakeStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


def load(argv, stdin=None):
    return _load_arguments(_build_parser().parse_args(argv), stdin=stdin)


def load_err(argv, stdin=None):
    err = io.StringIO()
    with redirect_stderr(err), unittest.TestCase().assertRaises(SystemExit) as cm:
        load(argv, stdin)
    return cm.exception.code, err.getvalue()


class RunToolArgsTests(unittest.TestCase):
    def _tmpfile(self, data: bytes) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.write(fd, data)
        os.close(fd)
        self.addCleanup(os.unlink, path)
        return path

    def test_no_args(self):
        self.assertEqual(load(["t"]), {})

    def test_json_object(self):
        self.assertEqual(load(["t", "--json", '{"a": 1}']), {"a": 1})

    def test_json_non_object(self):
        code, err = load_err(["t", "--json", "[1]"])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("Error:"))

    def test_json_invalid(self):
        code, err = load_err(["t", "--json", "{oops"])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("Error:"))

    def test_json_file_bom_unicode_sql(self):
        sql = "SELECT * FROM t\nWHERE a LIKE '%L'Oréal%' AND b = \"x\" -- 中文"
        import json
        payload = json.dumps({"sql": sql, "name": "L'Oréal 中文"}, ensure_ascii=False)
        path = self._tmpfile(b"\xef\xbb\xbf" + payload.encode("utf-8"))
        got = load(["t", "--json-file", path])
        self.assertEqual(got["sql"], sql)
        self.assertEqual(got["name"], "L'Oréal 中文")

    def test_json_file_missing(self):
        code, err = load_err(["t", "--json-file", "/nonexistent/zzz.json"])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("Error:"))

    def test_json_file_non_object(self):
        path = self._tmpfile(b'"str"')
        code, _ = load_err(["t", "--json-file", path])
        self.assertEqual(code, 1)

    def test_stdin(self):
        data = '﻿{"q": "L\'Oréal 中文"}'.encode("utf-8")
        self.assertEqual(load(["t", "--json", "-"], FakeStdin(data)), {"q": "L'Oréal 中文"})

    def test_arg_strings_and_bools(self):
        got = load(["t", "--arg", "a=INC1", "--arg", "b=TRUE", "--arg", "c=false", "--arg", "d=yes"])
        self.assertEqual(got, {"a": "INC1", "b": True, "c": False, "d": "yes"})

    def test_arg_value_with_equals(self):
        self.assertEqual(load(["t", "--arg", "u=http://x?a=b&c=d"]), {"u": "http://x?a=b&c=d"})

    def test_arg_overrides_json(self):
        got = load(["t", "--json", '{"a": "old", "k": 1}', "--arg", "a=new"])
        self.assertEqual(got, {"a": "new", "k": 1})

    def test_arg_merges_with_file(self):
        path = self._tmpfile(b'{"k": 1}')
        self.assertEqual(load(["t", "--json-file", path, "--arg", "z=1"]), {"k": 1, "z": "1"})

    def test_malformed_arg(self):
        for bad in ("noequals", "=v"):
            code, err = load_err(["t", "--arg", bad])
            self.assertEqual(code, 1)
            self.assertTrue(err.startswith("Error:"))

    def test_json_and_json_file_exclusive(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            load(["t", "--json", "{}", "--json-file", "x.json"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
