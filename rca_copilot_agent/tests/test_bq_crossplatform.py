"""Offline tests for cross-platform bq/gcloud execution (phase-kayinleong-03, A)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import bigquery_tool as bq  # noqa: E402
from tools import gcloud_tool as gc  # noqa: E402

SQL = (
    "SELECT 'L''Oréal' AS a, \"中文\" AS b, 5 % 2 AS c, 1 < 2 AS d, 3 > 2 AS e,\n"
    "  'x|y&z^w' AS f\nFROM `p.d.t`\nWHERE x = 'a' LIMIT 5"
)


def _cp(stdout="[]", stderr="", rc=0):
    return subprocess.CompletedProcess([], rc, stdout=stdout, stderr=stderr)


class ExecuteTests(unittest.TestCase):
    def _run(self, stdout="[]", rc=0, sql=SQL):
        with mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq.subprocess, "run", return_value=_cp(stdout, rc=rc)) as run:
            res = bq._bq_cli_execute(sql, "proj", max_rows=7)
        return res, run

    def test_sql_via_stdin_not_argv(self):
        _, run = self._run()
        args, kwargs = run.call_args
        argv = args[0]
        self.assertEqual(kwargs["input"], SQL)
        self.assertFalse(any("SELECT" in a for a in argv))
        self.assertIn("--headless", argv)
        self.assertIn("--quiet", argv)
        self.assertIn("--project_id=proj", argv)
        self.assertIn("--max_rows=7", argv)
        self.assertLess(argv.index("--headless"), argv.index("query"))
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertNotIn("text", kwargs)

    def test_special_chars_verbatim(self):
        weird = 'SELECT "a" , \'b\' , 100%, <>|&^ , L\'Oréal, 中文\nFROM t'
        _, run = self._run(sql=weird)
        self.assertEqual(run.call_args.kwargs["input"], weird)

    def test_utf8_json_parses(self):
        rows = [{"name": "L'Oréal", "zh": "中文"}]
        res, _ = self._run(json.dumps(rows, ensure_ascii=False))
        self.assertTrue(res.success)
        self.assertEqual(res.data, rows)
        self.assertEqual(res.columns, ["name", "zh"])

    def test_nonzero_exit(self):
        res, _ = self._run("", rc=1)
        self.assertFalse(res.success)

    def test_timeout_message(self):
        with mock.patch.dict(os.environ, {"BQ_CLI_TIMEOUT": "45"}), \
             mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("bq", 45)) as run:
            res = bq._bq_cli_execute("SELECT 1", "p")
        self.assertFalse(res.success)
        self.assertIn("45s", res.error)
        self.assertEqual(run.call_args.kwargs["timeout"], 45)


class EnvTests(unittest.TestCase):
    def test_sdk_env(self):
        with mock.patch.object(bq, "_find_bq", return_value=os.path.join("/x", "bin", "bq")):
            env = bq._sdk_env()
        self.assertTrue(env["PATH"].startswith(os.path.abspath(os.path.join("/x", "bin")) + os.pathsep))
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["CLOUDSDK_CORE_DISABLE_PROMPTS"], "1")

    def test_sdk_env_uses_pathsep_semicolon(self):
        with mock.patch.object(bq, "_find_bq", return_value=os.path.join("/x", "bin", "bq")), \
             mock.patch.object(bq.os, "pathsep", ";"), \
             mock.patch.dict(os.environ, {"PATH": "C:\\Windows"}):
            env = bq._sdk_env()
        self.assertTrue(env["PATH"].endswith(";C:\\Windows"))
        self.assertNotIn(":C:", env["PATH"].replace("C:\\Windows", ""))

    def test_timeout_parsing(self):
        for val, want in [("30", 30), ("abc", 120), ("", 120), ("0", 120), ("-5", 120)]:
            with mock.patch.dict(os.environ, {"BQ_CLI_TIMEOUT": val}):
                self.assertEqual(bq._bq_cli_timeout(), want, val)
        env = {k: v for k, v in os.environ.items() if k != "BQ_CLI_TIMEOUT"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(bq._bq_cli_timeout(), 120)

    def test_bq_timeout_var_ignored(self):
        env = {k: v for k, v in os.environ.items() if k != "BQ_CLI_TIMEOUT"}
        env["BQ_TIMEOUT"] = "30"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(bq._bq_cli_timeout(), 120)


class WindowsFindTests(unittest.TestCase):
    def _sdk(self, tmp, name):
        d = Path(tmp, "Google", "Cloud SDK", "google-cloud-sdk", "bin")
        d.mkdir(parents=True, exist_ok=True)
        f = d / name
        f.write_text("@echo off")
        return str(f)

    def _clean_env(self, tmp, **extra):
        env = {k: v for k, v in os.environ.items()
               if k not in ("BQ_BIN", "GCLOUD_BIN", "ProgramFiles", "ProgramFiles(x86)")}
        env["LOCALAPPDATA"] = tmp
        env.update(extra)
        return env

    def test_find_bq_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._sdk(tmp, "bq.cmd")
            with mock.patch.dict(os.environ, self._clean_env(tmp), clear=True), \
                 mock.patch.object(bq.os, "name", "nt"), \
                 mock.patch.object(bq.shutil, "which", return_value=None):
                self.assertEqual(bq._find_bq(), f)

    def test_find_gcloud_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._sdk(tmp, "gcloud.cmd")
            with mock.patch.dict(os.environ, self._clean_env(tmp), clear=True), \
                 mock.patch.object(gc.os, "name", "nt"), \
                 mock.patch.object(gc.shutil, "which", return_value=None):
                self.assertEqual(gc._find_gcloud(), f)

    def test_program_files_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._sdk(tmp, "bq.cmd")
            env = self._clean_env("", **{"ProgramFiles(x86)": tmp})
            env.pop("LOCALAPPDATA")
            with mock.patch.dict(os.environ, env, clear=True), \
                 mock.patch.object(bq.os, "name", "nt"), \
                 mock.patch.object(bq.shutil, "which", return_value=None):
                self.assertEqual(bq._find_bq(), f)

    def test_overrides_win(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdk_bq = self._sdk(tmp, "bq.cmd")
            sdk_gc = self._sdk(tmp, "gcloud.cmd")
            ob = Path(tmp, "custom_bq.cmd"); ob.write_text("x")
            og = Path(tmp, "custom_gcloud.cmd"); og.write_text("x")
            env = self._clean_env(tmp, BQ_BIN=str(ob), GCLOUD_BIN=str(og))
            with mock.patch.dict(os.environ, env, clear=True), \
                 mock.patch.object(bq.os, "name", "nt"), \
                 mock.patch.object(bq.shutil, "which", return_value=sdk_bq), \
                 mock.patch.object(gc.shutil, "which", return_value=sdk_gc):
                self.assertEqual(bq._find_bq(), str(ob))
                self.assertEqual(gc._find_gcloud(), str(og))

    def test_not_found_returns_bare_name(self):
        env = {k: v for k, v in os.environ.items() if k not in ("BQ_BIN", "GCLOUD_BIN")}
        env.pop("LOCALAPPDATA", None); env.pop("ProgramFiles", None); env.pop("ProgramFiles(x86)", None)
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(bq.os, "name", "nt"), \
             mock.patch.object(bq.shutil, "which", return_value=None):
            self.assertEqual(bq._find_bq(), "bq")


class GcloudRunTests(unittest.TestCase):
    def test_run_gcloud_utf8(self):
        with mock.patch.object(gc, "_find_gcloud", return_value="gcloud"), \
             mock.patch.object(gc.subprocess, "run", return_value=_cp()) as run:
            gc._run_gcloud("auth", "list")
        kw = run.call_args.kwargs
        self.assertEqual(kw["encoding"], "utf-8")
        self.assertEqual(kw["errors"], "replace")
        self.assertNotIn("text", kw)

    def test_interactive_login_not_env_overridden(self):
        with mock.patch.object(gc, "_find_gcloud", return_value="gcloud"), \
             mock.patch.object(gc.subprocess, "run", return_value=_cp()) as run:
            gc._interactive_gcloud("auth", "login")
        self.assertNotIn("env", run.call_args.kwargs)


class QueryApiTests(unittest.TestCase):
    def setUp(self):
        ex = bq.SafeBigQueryExecutor(project="proj")
        p = mock.patch.object(bq, "_executors", {"proj": ex})
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(bq, "_default_project", "proj")
        p2.start()
        self.addCleanup(p2.stop)

    def test_blocked_sql_no_subprocess(self):
        with mock.patch.object(bq.subprocess, "run") as run:
            res = bq.query_bigquery_result("DELETE FROM `p.d.t` WHERE 1=1")
            text = bq.query_bigquery("DELETE FROM `p.d.t` WHERE 1=1")
        self.assertFalse(res.success)
        self.assertTrue(res.error)
        run.assert_not_called()
        self.assertIsInstance(text, str)
        self.assertIn("QUERY FAILED", text)

    def test_success_returns_result_and_string(self):
        rows = [{"n": "中文"}]
        with mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq.subprocess, "run",
                               return_value=_cp(json.dumps(rows, ensure_ascii=False))):
            res = bq.query_bigquery_result("SELECT 1", "why")
            text = bq.query_bigquery("SELECT 1", "why")
        self.assertTrue(res.success)
        self.assertEqual(res.data, rows)
        self.assertEqual(text, res.to_llm_context())

    def test_no_executors_raises(self):
        with mock.patch.object(bq, "_executors", {}):
            with self.assertRaises(RuntimeError):
                bq.query_bigquery_result("SELECT 1")


if __name__ == "__main__":
    unittest.main()
