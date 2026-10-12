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


def _popen(stdout=b"[]", stderr=b"", rc=0, pid=4242, communicate_effects=None):
    proc = mock.MagicMock()
    proc.pid = pid
    proc.returncode = rc
    if communicate_effects is not None:
        proc.communicate.side_effect = communicate_effects
    else:
        proc.communicate.return_value = (stdout, stderr)
    return proc


def _b(s):
    return s.encode("utf-8")


class ExecuteTests(unittest.TestCase):
    def _run(self, stdout="[]", rc=0, sql=SQL, stderr=b""):
        proc = _popen(_b(stdout), stderr, rc)
        with mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq.subprocess, "Popen", return_value=proc) as popen:
            res = bq._bq_cli_execute(sql, "proj", max_rows=7)
        return res, popen, proc

    def test_sql_via_stdin_bytes_not_argv(self):
        _, popen, proc = self._run()
        args, kwargs = popen.call_args
        argv = args[0]
        sent = proc.communicate.call_args.kwargs["input"]
        self.assertIsInstance(sent, bytes)
        self.assertEqual(sent, SQL.encode("utf-8"))
        self.assertNotIn(b"\r\n", sent)
        self.assertIn(b"\n", sent)
        self.assertFalse(any("SELECT" in a for a in argv))
        self.assertIn("--headless", argv)
        self.assertIn("--quiet", argv)
        self.assertIn("--project_id=proj", argv)
        self.assertIn("--max_rows=7", argv)
        self.assertLess(argv.index("--headless"), argv.index("query"))
        for k in ("encoding", "text", "universal_newlines", "errors"):
            self.assertNotIn(k, kwargs)
        self.assertEqual(kwargs["env"]["PYTHONUTF8"], "1")
        self.assertEqual(kwargs["env"]["CLOUDSDK_CORE_DISABLE_PROMPTS"], "1")
        self.assertEqual(proc.communicate.call_args.kwargs["timeout"], 120)

    def test_special_chars_verbatim(self):
        weird = 'SELECT "a" , \'b\' , 100%, <>|&^ , L\'Oréal, 中文\nFROM t'
        _, _, proc = self._run(sql=weird)
        self.assertEqual(proc.communicate.call_args.kwargs["input"], weird.encode("utf-8"))

    def test_utf8_json_parses(self):
        rows = [{"name": "L'Oréal", "zh": "中文"}]
        res, _, _ = self._run(json.dumps(rows, ensure_ascii=False))
        self.assertTrue(res.success)
        self.assertEqual(res.data, rows)
        self.assertEqual(res.columns, ["name", "zh"])

    def test_nonzero_exit(self):
        res, _, _ = self._run("", rc=1, stderr=b"boom")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "boom")

    def test_stderr_invalid_utf8_replaced(self):
        res, _, _ = self._run("", rc=1, stderr=b"bad \xff\xfe byte")
        self.assertFalse(res.success)
        self.assertIn("bad \ufffd", res.error)

    def test_posix_new_session(self):
        with mock.patch.object(bq.os, "name", "posix"):
            _, popen, _ = self._run()
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_windows_no_new_session(self):
        proc = _popen(b"[]")
        with mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq, "_sdk_env", return_value={}), \
             mock.patch.object(bq.os, "name", "nt"), \
             mock.patch.object(bq.subprocess, "Popen", return_value=proc) as popen:
            bq._bq_cli_execute("SELECT 1", "p")
        self.assertNotIn("start_new_session", popen.call_args.kwargs)

    def _timeout(self, osname, effects=None, **extra):
        te = subprocess.TimeoutExpired("bq", 45)
        proc = _popen(communicate_effects=effects or [te, (b"", b"")], pid=999)
        patches = [
            mock.patch.dict(os.environ, {"BQ_CLI_TIMEOUT": "45"}),
            mock.patch.object(bq, "_find_bq", return_value="bq"),
            mock.patch.object(bq, "_sdk_env", return_value={}),
            mock.patch.object(bq.os, "name", osname),
            mock.patch.object(bq.subprocess, "Popen", return_value=proc),
            mock.patch.object(bq.subprocess, "run") if osname == "nt" else mock.patch.object(bq.os, "killpg", create=True),
        ]
        mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        res = bq._bq_cli_execute("SELECT 1", "p")
        return res, proc, mocks[-1]

    def test_timeout_windows_taskkill(self):
        res, proc, run = self._timeout("nt")
        self.assertFalse(res.success)
        self.assertEqual(res.error, "bq CLI query timed out (45s)")
        self.assertEqual(proc.communicate.call_args_list[0].kwargs["timeout"], 45)
        self.assertEqual(run.call_args.args[0], ["taskkill", "/T", "/F", "/PID", "999"])
        proc.kill.assert_not_called()
        self.assertEqual(proc.communicate.call_count, 2)

    def test_timeout_posix_kills_group(self):
        import signal
        res, proc, killpg = self._timeout("posix")
        self.assertFalse(res.success)
        self.assertIn("45s", res.error)
        killpg.assert_called_once_with(999, signal.SIGKILL)
        self.assertEqual(proc.communicate.call_count, 2)

    def test_timeout_posix_falls_back_to_proc_kill(self):
        te = subprocess.TimeoutExpired("bq", 45)
        proc = _popen(communicate_effects=[te, (b"", b"")], pid=999)
        with mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq, "_sdk_env", return_value={}), \
             mock.patch.object(bq.os, "name", "posix"), \
             mock.patch.object(bq.os, "killpg", side_effect=ProcessLookupError, create=True), \
             mock.patch.object(bq.subprocess, "Popen", return_value=proc):
            res = bq._bq_cli_execute("SELECT 1", "p")
        self.assertFalse(res.success)
        proc.kill.assert_called_once_with()

    def test_second_timeout_during_cleanup_does_not_hang_or_raise(self):
        te = subprocess.TimeoutExpired("bq", 5)
        for osname in ("nt", "posix"):
            res, proc, _ = self._timeout(osname, effects=[subprocess.TimeoutExpired("bq", 45), te])
            self.assertFalse(res.success)
            self.assertIn("timed out (45s)", res.error)
            self.assertEqual(proc.communicate.call_args_list[1].kwargs["timeout"], 5)

    def test_taskkill_failure_does_not_raise(self):
        te = subprocess.TimeoutExpired("bq", 45)
        proc = _popen(communicate_effects=[te, (b"", b"")], pid=1)
        with mock.patch.object(bq, "_find_bq", return_value="bq"), \
             mock.patch.object(bq, "_sdk_env", return_value={}), \
             mock.patch.object(bq.os, "name", "nt"), \
             mock.patch.object(bq.subprocess, "Popen", return_value=proc), \
             mock.patch.object(bq.subprocess, "run", side_effect=FileNotFoundError):
            res = bq._bq_cli_execute("SELECT 1", "p")
        self.assertIn("timed out", res.error)
        proc.kill.assert_called_once_with()


class OverrideWarningTests(unittest.TestCase):
    def setUp(self):
        for m in (bq, gc):
            m._warned_overrides.clear()
            self.addCleanup(m._warned_overrides.clear)

    def test_bad_bq_bin_warns_once_and_falls_through(self):
        with mock.patch.dict(os.environ, {"BQ_BIN": "/nonexistent/bq"}), \
             mock.patch.object(bq.shutil, "which", return_value="/usr/bin/bq"):
            with self.assertLogs(bq.logger, level="WARNING") as cm:
                self.assertEqual(bq._find_bq(), "/usr/bin/bq")
                self.assertEqual(bq._find_bq(), "/usr/bin/bq")
            self.assertEqual(len(cm.records), 1)
            self.assertIn("BQ_BIN", cm.output[0])

    def test_bad_gcloud_bin_warns_once_and_falls_through(self):
        with mock.patch.dict(os.environ, {"GCLOUD_BIN": "/nonexistent/gcloud"}), \
             mock.patch.object(gc.shutil, "which", return_value="/usr/bin/gcloud"):
            with self.assertLogs(gc._logger, level="WARNING") as cm:
                self.assertEqual(gc._find_gcloud(), "/usr/bin/gcloud")
                self.assertEqual(gc._find_gcloud(), "/usr/bin/gcloud")
            self.assertEqual(len(cm.records), 1)
            self.assertIn("GCLOUD_BIN", cm.output[0])

    def test_valid_override_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, "bq")
            f.write_text("x")
            f.chmod(0o755)
            with mock.patch.dict(os.environ, {"BQ_BIN": str(f)}):
                with self.assertNoLogs(bq.logger, level="WARNING"):
                    self.assertEqual(bq._find_bq(), str(f))


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
        with mock.patch.object(bq.subprocess, "Popen") as run:
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
             mock.patch.object(bq.subprocess, "Popen",
                               side_effect=lambda *a, **k: _popen(_b(json.dumps(rows, ensure_ascii=False)))):
            res = bq.query_bigquery_result("SELECT 1", "why")
            text = bq.query_bigquery("SELECT 1", "why")
        self.assertTrue(res.success)
        self.assertEqual(res.data, rows)
        self.assertEqual(text, res.to_llm_context())

    def test_no_executors_raises(self):
        with mock.patch.object(bq, "_executors", {}):
            with self.assertRaises(RuntimeError):
                bq.query_bigquery_result("SELECT 1")


class EnsureGcloudAuthNoAdcTests(unittest.TestCase):
    """ensure_gcloud_auth must never touch Application Default Credentials."""

    def _run(self, account, token_rc, login_ok=True):
        calls = []

        def fake_run(*args, timeout=15):
            calls.append(args)
            if args[:2] == ("auth", "list"):
                return _cp(stdout=(account or "") + "\n")
            if args[:2] == ("auth", "print-access-token"):
                return _cp(rc=token_rc)
            return _cp()

        def fake_interactive(*args, timeout=600):
            calls.append(args)
            return login_ok

        with mock.patch.object(gc, "_run_gcloud", side_effect=fake_run), \
                mock.patch.object(gc, "_interactive_gcloud", side_effect=fake_interactive), \
                mock.patch.object(gc.subprocess, "run", side_effect=AssertionError("direct subprocess")):
            gc.ensure_gcloud_auth()
        return calls

    def test_valid_user_creds_no_adc(self):
        calls = self._run("me@loreal.com", 0)
        self.assertFalse(any("application-default" in c for c in calls))
        self.assertNotIn(("auth", "login"), calls)

    def test_login_flow_still_runs_without_adc(self):
        calls = self._run("me@gmail.com", 1)
        self.assertIn(("auth", "login"), calls)
        self.assertTrue(any(c[:3] == ("config", "set", "project") for c in calls))
        self.assertFalse(any("application-default" in c for c in calls))

    def test_adc_helpers_removed(self):
        for name in ("is_adc_configured", "run_adc_login", "set_quota_project"):
            self.assertFalse(hasattr(gc, name), name)


if __name__ == "__main__":
    unittest.main()
