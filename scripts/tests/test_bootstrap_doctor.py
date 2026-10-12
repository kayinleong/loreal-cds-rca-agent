"""Offline unit tests for scripts/bootstrap.py, scripts/doctor.py, scripts/_reqs.py."""
import builtins
import io
import json
import os
import sys
import tempfile
import unittest
from collections import namedtuple
from contextlib import redirect_stdout
from unittest import mock

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)

import _reqs  # noqa: E402
import bootstrap  # noqa: E402
import doctor  # noqa: E402

VI = namedtuple("VI", "major minor micro releaselevel serial")


def vi(a, b, c=0):
    return VI(a, b, c, "final", 0)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def make_repo(tmp):
    write(os.path.join(tmp, "rca_copilot_agent", "requirements.txt"), "requests>=2.32,<3\npython-dotenv>=1.0,<2\n")
    write(os.path.join(tmp, "ticketasg_copilot_agent", "requirements.txt"), "requests>=2.32,<3\n")
    write(os.path.join(tmp, "ticketasg_copilot_agent", "requirements-retrieval.txt"),
          "sentence-transformers>=2.5,<6\nnumpy>=1.24,<3\n")
    write(os.path.join(tmp, "mockdata_copilot_agent", "requirements.txt"), "openpyxl>=3.1,<4\n")
    return tmp


class PipArgs(unittest.TestCase):
    def test_default_only_binary(self):
        a = bootstrap.build_pip_args("py", requirements="r.txt")
        self.assertEqual(a[:4], ["py", "-m", "pip", "install"])
        self.assertIn("--only-binary=:all:", a)
        self.assertEqual(a[-2:], ["-r", "r.txt"])
        self.assertNotIn("--trusted-host", a)

    def test_allow_source(self):
        a = bootstrap.build_pip_args("py", requirements="r.txt", allow_source=True)
        self.assertNotIn("--only-binary=:all:", a)

    def test_wheelhouse(self):
        a = bootstrap.build_pip_args("py", requirements="r.txt", wheelhouse="/w", index_url="http://x")
        self.assertIn("--no-index", a)
        i = a.index("--find-links")
        self.assertEqual(a[i + 1], "/w")
        self.assertNotIn("--index-url", a)

    def test_index_proxy(self):
        a = bootstrap.build_pip_args("py", requirements="r", index_url="http://m/simple",
                                     extra_index_url="http://e", proxy="http://p:1")
        self.assertEqual(a[a.index("--index-url") + 1], "http://m/simple")
        self.assertEqual(a[a.index("--extra-index-url") + 1], "http://e")
        self.assertEqual(a[a.index("--proxy") + 1], "http://p:1")

    def test_upgrade_pip(self):
        a = bootstrap.build_pip_args("py", upgrade_pip=True, proxy="http://p")
        self.assertEqual(a[-2:], ["--upgrade", "pip"])
        self.assertNotIn("--only-binary=:all:", a)
        self.assertIn("--proxy", a)

    def test_hints(self):
        self.assertTrue(any("Proxy" in h for h in bootstrap.pip_failure_hints("ProxyError 407")))
        self.assertTrue(any("SSL" in h for h in bootstrap.pip_failure_hints("CERTIFICATE_VERIFY_FAILED")))
        self.assertTrue(any("No wheel" in h for h in bootstrap.pip_failure_hints("No matching distribution found")))
        self.assertTrue(bootstrap.pip_failure_hints("weird"))


class Parsing(unittest.TestCase):
    def test_parse(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.txt")
            write(p, "# comment\n\n-r other.txt\n--index-url http://x\n"
                     "Requests[socks]>=2.0,<3  # inline\n"
                     "python_dotenv>=1.0 ; python_version >= '3.8'\n"
                     "pywin32; sys_platform == 'win32'\n")
            self.assertEqual(bootstrap.parse_requirements(p), [
                ("requests", ">=2.0,<3"), ("python-dotenv", ">=1.0"), ("pywin32", "")])


class Classify(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(bootstrap.classify_python(vi(3, 9), 8)[0], "fatal")
        self.assertEqual(bootstrap.classify_python(vi(3, 12), 4)[0], "fatal")
        self.assertEqual(bootstrap.classify_python(vi(3, 12), 8)[0], "ok")
        self.assertEqual(bootstrap.classify_python(vi(3, 10), 8)[0], "ok")
        self.assertEqual(bootstrap.classify_python(vi(3, 14), 8)[0], "warn")


class Summary(unittest.TestCase):
    def r(self, **kw):
        return [{"agent": k, "status": v, "note": ""} for k, v in kw.items()]

    def test_codes(self):
        self.assertEqual(bootstrap.summarize(self.r(rca_copilot="ok", ticketasg="ok", mockdata="ok")), 0)
        self.assertEqual(bootstrap.summarize(self.r(rca_copilot="ok", ticketasg="partial", mockdata="ok")), 2)
        self.assertEqual(bootstrap.summarize(self.r(rca_copilot="ok", ticketasg="failed", mockdata="ok")), 2)
        self.assertEqual(bootstrap.summarize(self.r(rca_copilot="failed", ticketasg="ok")), 1)
        self.assertEqual(bootstrap.summarize(self.r(ticketasg="failed", mockdata="failed")), 1)
        self.assertEqual(bootstrap.summarize([]), 1)


class DistMapping(unittest.TestCase):
    def test_table_and_fallback(self):
        self.assertEqual(doctor.import_name_for("python-dotenv"), "dotenv")
        self.assertEqual(doctor.import_name_for("foo-bar"), "foo_bar")
        self.assertEqual(doctor.import_name_for("weird", {"wmod": ["Weird"]}), "wmod")


class AgentChecks(unittest.TestCase):
    def levels(self, key, versions):
        with tempfile.TemporaryDirectory() as t:
            make_repo(t)
            res = doctor.check_agent(key, t, version_fn=lambda n: versions.get(n),
                                     find_spec_fn=lambda m: True, dist_map={})
        return [r["level"] for r in res], res

    def test_core_missing_fails(self):
        lv, _ = self.levels("rca_copilot", {"requests": "2.32"})
        self.assertEqual(lv, [doctor.OK, doctor.FAIL])

    def test_retrieval_missing_warns(self):
        lv, _ = self.levels("ticketasg", {"requests": "2"})
        self.assertEqual(lv, [doctor.OK, doctor.WARN, doctor.WARN])

    def test_openpyxl_missing_warns(self):
        lv, _ = self.levels("mockdata", {})
        self.assertEqual(lv, [doctor.WARN])

    def test_unimportable_module(self):
        with tempfile.TemporaryDirectory() as t:
            make_repo(t)
            res = doctor.check_agent("mockdata", t, version_fn=lambda n: "3.1",
                                     find_spec_fn=lambda m: False, dist_map={})
        self.assertEqual(res[0]["level"], doctor.WARN)

    def test_missing_requirements_file(self):
        with tempfile.TemporaryDirectory() as t:
            res = doctor.check_agent("rca_copilot", t, version_fn=lambda n: "1", find_spec_fn=lambda m: True, dist_map={})
        self.assertEqual(res[0]["level"], doctor.FAIL)


class ToolsAndAccount(unittest.TestCase):
    def test_gcloud_bare_name_not_found(self):
        self.assertEqual(doctor.check_tool("gcloud", "gcloud-does-not-exist", "x")["level"], doctor.FAIL)
        self.assertEqual(doctor.check_tool("gcloud", __file__, "x")["level"], doctor.OK)

    def test_account_masking(self):
        email = "first.last@loreal.com"
        r = doctor.check_account_output(email)
        self.assertEqual(r["level"], doctor.OK)
        self.assertNotIn(email, json.dumps(r))
        self.assertNotIn("first.last", json.dumps(r))
        self.assertIn("***@loreal.com", r["title"])
        other = doctor.check_account_output("me@gmail.com")
        self.assertEqual(other["level"], doctor.WARN)
        self.assertNotIn("me@", json.dumps(other))
        self.assertEqual(doctor.check_account_output("")["level"], doctor.WARN)

    def test_get_account_uses_timeout_15(self):
        calls = {}

        def fake(cmd, **kw):
            calls.update(kw)
            return mock.Mock(returncode=0, stdout="a@b.com\n")
        self.assertEqual(doctor.get_gcloud_account("g", run=fake), "a@b.com")
        self.assertEqual(calls["timeout"], 15)

    def test_edge(self):
        self.assertEqual(doctor.check_edge(exists=lambda p: True, environ={}, platform="darwin")["level"], doctor.OK)
        self.assertEqual(doctor.check_edge(exists=lambda p: False, environ={}, platform="darwin")["level"], doctor.WARN)
        c = doctor.edge_candidates({"ProgramFiles": "C:\\PF", "LOCALAPPDATA": "C:\\L"}, "win32")
        self.assertEqual(len(c), 2)
        self.assertTrue(all(x.endswith("msedge.exe") for x in c))


class FilesAndEnv(unittest.TestCase):
    def test_env_never_opened(self):
        real_open = builtins.open
        with tempfile.TemporaryDirectory() as t:
            write(os.path.join(t, "schema.json"), "{}")
            write(os.path.join(t, ".env"), "COOKIE=SECRETVALUE\n")

            def guard(path, *a, **k):
                if ".env" in os.path.basename(str(path)):
                    raise AssertionError(".env was opened")
                return real_open(path, *a, **k)
            with mock.patch("builtins.open", guard), \
                    mock.patch("pathlib.Path.read_text", side_effect=AssertionError("read_text")):
                res = doctor.check_files(t)
        self.assertEqual([r["level"] for r in res], [doctor.OK, doctor.OK])
        self.assertNotIn("SECRETVALUE", json.dumps(res))

    def test_missing_files(self):
        with tempfile.TemporaryDirectory() as t:
            res = doctor.check_files(t)
        self.assertEqual([r["level"] for r in res], [doctor.FAIL, doctor.WARN])

    def test_env_names_only(self):
        r = doctor.check_env({"HTTPS_PROXY": "http://secret-proxy:8080", "PIP_CERT": "/secret/cert.pem", "OTHER": "x"})
        text = json.dumps(r)
        self.assertIn("HTTPS_PROXY", text)
        self.assertIn("PIP_CERT", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("OTHER", text)


class PythonCheck(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(doctor.check_python(vi(3, 9), 8, "/x", "/r")[0]["level"], doctor.FAIL)
        self.assertEqual(doctor.check_python(vi(3, 12), 8, "/x", "/r")[0]["level"], doctor.OK)
        self.assertEqual(doctor.check_python(vi(3, 14), 8, "/x", "/r")[0]["level"], doctor.WARN)
        self.assertEqual(doctor.check_python(vi(3, 12), 8, "/x", "/r")[1]["level"], doctor.WARN)

    def test_in_venv(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, ".venv"))
            res = doctor.check_python(vi(3, 12), 8, os.path.join(t, ".venv"), t)
        self.assertEqual(res[1]["level"], doctor.OK)


class Reexec(unittest.TestCase):
    def test_decisions(self):
        self.assertTrue(_reqs.should_reexec(True, "/sys", "/repo/.venv", {}))
        self.assertFalse(_reqs.should_reexec(False, "/sys", "/repo/.venv", {}))
        self.assertFalse(_reqs.should_reexec(True, "/repo/.venv", "/repo/.venv", {}))
        self.assertFalse(_reqs.should_reexec(True, "/sys", "/repo/.venv", {"RCA_VENV_REEXEC": "1"}))


class Rendering(unittest.TestCase):
    def test_exit_and_render(self):
        res = [doctor.item(doctor.OK, "a"), doctor.item(doctor.WARN, "b", hint="h")]
        self.assertEqual(doctor.exit_code(res), 0)
        res.append(doctor.item(doctor.FAIL, "c", hint="fix"))
        self.assertEqual(doctor.exit_code(res), 1)
        self.assertIn("[FAIL]", doctor.render(res, "ascii"))
        self.assertIn("\u2717", doctor.render(res, "utf-8"))

    def test_json_main(self):
        buf = io.StringIO()
        with mock.patch.object(doctor, "maybe_reexec"), mock.patch.object(doctor, "run_checks",
                                                                          return_value=[doctor.item(doctor.OK, "x")]):
            with redirect_stdout(buf):
                rc = doctor.main(["--json"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(buf.getvalue())["ok"])


ROOT = os.path.dirname(SCRIPTS)


def read_bytes(name):
    with open(os.path.join(ROOT, name), "rb") as fh:
        return fh.read()


class SetupScripts(unittest.TestCase):
    def test_cmd_crlf_ascii(self):
        data = read_bytes("setup.cmd")
        data.decode("ascii")
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertIn(b"\r\n", data)

    def test_cmd_no_delayed_expansion_and_pause_guard(self):
        text = read_bytes("setup.cmd").decode("ascii")
        self.assertNotIn("enabledelayedexpansion", text.lower())
        self.assertNotIn("!PY!", text)
        self.assertNotIn("!ERRORLEVEL!", text)
        self.assertIn("cmdcmdline", text)
        self.assertIn("pause", text)
        self.assertIn("%*", text)
        # errorlevel is saved before pause, then returned
        self.assertLess(text.index('set "RC=%ERRORLEVEL%"'), text.index("if defined PAUSEIT pause"))
        self.assertIn("exit /b %RC%", text)
        # terminals / automation (Copilot in VS Code, Windows Terminal, Claude Code, CI) must never pause
        for var in ("SETUP_NOPAUSE", "TERM_PROGRAM", "VSCODE_PID", "WT_SESSION", "CLAUDECODE", "CI"):
            self.assertIn('if defined %s set "PAUSEIT="' % var, text)
        self.assertLess(text.index("if not errorlevel 1 set \"PAUSEIT=1\""),
                        text.index('if defined TERM_PROGRAM set "PAUSEIT="'))

    def test_sh_lf_and_candidate_order(self):
        data = read_bytes("setup.sh")
        self.assertNotIn(b"\r", data)
        text = data.decode("ascii")
        self.assertTrue(text.startswith("#!/bin/sh"))
        absolute = text.index("/opt/homebrew/bin")
        bare = text.index("for cand in python3.12")
        self.assertLess(absolute, bare)
        self.assertLess(text.index("/Library/Frameworks/Python.framework"), bare)
        self.assertLess(text.index("$HOME/.local/bin"), bare)
        self.assertIn("xcode-select -p", text)
        self.assertIn("/usr/bin/python3", text)

    def test_gitattributes_rules(self):
        lines = read_bytes(".gitattributes").decode("ascii").splitlines()
        for rule in ("setup.cmd text eol=crlf", "*.cmd text eol=crlf",
                     "setup.sh text eol=lf", "*.sh text eol=lf"):
            self.assertIn(rule, lines)


class FakeRun(object):
    """Scriptable stand-in for bootstrap.run_streaming; records every command."""

    def __init__(self, fail=None, network_fail_upgrade=False):
        self.calls = []
        self.fail = fail or {}
        self.network_fail_upgrade = network_fail_upgrade

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        joined = " ".join(cmd)
        if "--upgrade pip" in joined:
            if self.network_fail_upgrade:
                return 1, "NewConnectionError: Max retries exceeded"
            return 0, ""
        if "doctor.py" in joined:
            return 0, ""
        for needle, out in self.fail.items():
            if needle in joined:
                return 1, out
        return 0, ""

    def req_calls(self):
        return [c for c in self.calls if "-r" in c]


class MainFlow(unittest.TestCase):
    def run_main(self, argv, fake, repo_ok=True):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as t:
            make_repo(t)
            patches = [
                mock.patch.object(bootstrap, "REPO", t),
                mock.patch.object(bootstrap, "VENV_DIR", os.path.join(t, ".venv")),
                mock.patch.object(bootstrap, "ensure_venv", return_value=True),
                mock.patch.object(bootstrap, "venv_python", return_value="venvpy"),
                mock.patch.object(bootstrap, "run_streaming", fake),
            ]
            for p in patches:
                p.start()
            try:
                with redirect_stdout(buf):
                    rc = bootstrap.main(["--no-doctor"] + argv)
            finally:
                for p in patches:
                    p.stop()
        return rc, buf.getvalue()

    def test_all_ok(self):
        fake = FakeRun()
        rc, out = self.run_main([], fake)
        self.assertEqual(rc, 0)
        self.assertEqual(len(fake.req_calls()), 4)  # rca, ticketasg core+retrieval, mockdata

    def test_ticketasg_core_fail_isolated(self):
        fake = FakeRun(fail={os.path.join("ticketasg_copilot_agent", "requirements.txt"): "boom"})
        rc, out = self.run_main([], fake)
        self.assertEqual(rc, 2)
        joined = [" ".join(c) for c in fake.req_calls()]
        self.assertTrue(any("mockdata_copilot_agent" in j for j in joined))
        self.assertFalse(any("requirements-retrieval.txt" in j for j in joined))

    def test_rca_fail_is_fatal(self):
        fake = FakeRun(fail={os.path.join("rca_copilot_agent", "requirements.txt"): "boom"})
        rc, out = self.run_main([], fake)
        self.assertEqual(rc, 1)
        self.assertTrue(any("mockdata_copilot_agent" in " ".join(c) for c in fake.req_calls()))

    def test_retrieval_fail_partial(self):
        fake = FakeRun(fail={"requirements-retrieval.txt": "boom"})
        rc, out = self.run_main([], fake)
        self.assertEqual(rc, 2)
        self.assertIn("PARTIAL", out)

    def test_pip_upgrade_network_failure_stops_early(self):
        fake = FakeRun(network_fail_upgrade=True)
        rc, out = self.run_main([], fake)
        self.assertEqual(rc, 1)
        self.assertEqual(fake.req_calls(), [])
        self.assertIn("PyPI unreachable", out)
        self.assertIn("stopping early", out)

    def test_flags_present_on_every_pip_call(self):
        fake = FakeRun()
        self.run_main([], fake)
        pip_calls = [c for c in fake.calls if "pip" in c]
        self.assertTrue(pip_calls)
        for c in pip_calls:
            self.assertIn("--no-input", c)
            self.assertEqual(c[c.index("--retries") + 1], "3")
            self.assertEqual(c[c.index("--timeout") + 1], "30")

    def test_recreate_from_inside_venv_refused(self):
        fake = FakeRun()
        with tempfile.TemporaryDirectory() as t:
            venv = os.path.join(t, ".venv")
            os.makedirs(venv)
            buf = io.StringIO()
            with mock.patch.object(bootstrap, "VENV_DIR", venv), \
                    mock.patch.object(sys, "prefix", venv), \
                    mock.patch.object(bootstrap, "ensure_venv") as ev, \
                    mock.patch.object(bootstrap, "run_streaming", fake), \
                    redirect_stdout(buf):
                rc = bootstrap.main(["--recreate", "--no-doctor"])
        self.assertEqual(rc, 1)
        ev.assert_not_called()
        self.assertIn("--recreate", buf.getvalue())

    def test_long_path_warning_on_nt(self):
        long_repo = "C:\\" + "a" * 120
        self.assertIn("MAX_PATH", bootstrap.long_path_warning(long_repo, "nt"))
        self.assertIsNone(bootstrap.long_path_warning("C:\\short", "nt"))
        self.assertIsNone(bootstrap.long_path_warning(long_repo, "posix"))
        with mock.patch.object(bootstrap.os, "name", "nt"), mock.patch.object(bootstrap, "REPO", long_repo):
            self.assertIn("C:\\src\\rca", bootstrap.long_path_warning())

    def test_retrieval_fail_on_windows_adds_long_path_hint(self):
        fake = FakeRun(fail={"requirements-retrieval.txt": "boom"})
        with mock.patch.object(bootstrap.os, "name", "nt"):
            rc, out = self.run_main([], fake)
        self.assertIn("MAX_PATH", out)

    def test_run_streaming_uses_devnull_stdin(self):
        captured = {}

        class P(object):
            stdout = iter(["line\n"])
            returncode = 0

            def wait(self):
                pass

        def fake_popen(cmd, **kw):
            captured.update(kw)
            return P()
        with mock.patch.object(bootstrap.subprocess, "Popen", fake_popen), redirect_stdout(io.StringIO()):
            rc, out = bootstrap.run_streaming(["x"])
        self.assertEqual(rc, 0)
        self.assertIs(captured["stdin"], bootstrap.subprocess.DEVNULL)


class HintMatching(unittest.TestCase):
    def test_no_false_positives(self):
        hints = bootstrap.pip_failure_hints("sha256:403abc proxy-free connection-pool https://files/403/x")
        self.assertEqual(len(hints), 1)
        self.assertIn("See the pip output", hints[0])
        self.assertFalse(bootstrap.is_network_failure("hash 403abc"))

    def test_ssl_hint_first_and_mentions_pip_cert(self):
        hints = bootstrap.pip_failure_hints("SSLError CERTIFICATE_VERIFY_FAILED ProxyError")
        self.assertIn("PIP_CERT", hints[0])
        self.assertIn("global.cert", hints[0])

    def test_markers(self):
        self.assertTrue(any("unreachable" in h for h in bootstrap.pip_failure_hints("HTTP error 403")))
        self.assertTrue(any("Proxy" in h for h in bootstrap.pip_failure_hints("407 Proxy Authentication Required")))
        self.assertTrue(any("No wheel" in h for h in bootstrap.pip_failure_hints("Could not find a version that satisfies x")))
        self.assertTrue(bootstrap.is_network_failure("NewConnectionError"))


class DoctorRobustness(unittest.TestCase):
    def test_gcloud_auth_list_stdin_devnull(self):
        calls = {}

        def fake(cmd, **kw):
            calls.update(kw)
            return mock.Mock(returncode=0, stdout="a@b.com\n")
        doctor.get_gcloud_account("g", run=fake)
        self.assertIs(calls["stdin"], subprocess_devnull())

    def test_reexec_oserror_falls_back(self):
        with mock.patch.object(doctor._reqs, "should_reexec", return_value=True), \
                mock.patch.object(doctor.subprocess, "call", side_effect=OSError("bad")), \
                redirect_stdout(io.StringIO()) as buf:
            doctor.maybe_reexec([])  # must not raise or exit
        self.assertIn("--recreate", buf.getvalue())

    def test_env_never_touched_by_run_checks(self):
        real_open = builtins.open
        real_io_open = io.open

        def bad(path):
            return ".env" in os.path.basename(str(path)) and not str(path).endswith(".env.example")

        def guard_open(real):
            def g(path, *a, **k):
                if bad(path):
                    raise AssertionError(".env was opened")
                return real(path, *a, **k)
            return g
        real_path_open = doctor_pathlib().Path.open
        real_read_text = doctor_pathlib().Path.read_text
        real_read_bytes = doctor_pathlib().Path.read_bytes

        def p_open(self, *a, **k):
            if bad(self):
                raise AssertionError(".env Path.open")
            return real_path_open(self, *a, **k)

        def p_text(self, *a, **k):
            if bad(self):
                raise AssertionError(".env read_text")
            return real_read_text(self, *a, **k)

        def p_bytes(self, *a, **k):
            if bad(self):
                raise AssertionError(".env read_bytes")
            return real_read_bytes(self, *a, **k)
        with tempfile.TemporaryDirectory() as t:
            make_repo(t)
            write(os.path.join(t, "schema.json"), "{}")
            write(os.path.join(t, ".env"), "COOKIE=SECRETVALUE\n")
            with mock.patch("builtins.open", guard_open(real_open)), \
                    mock.patch("io.open", guard_open(real_io_open)), \
                    mock.patch("pathlib.Path.open", p_open), \
                    mock.patch("pathlib.Path.read_text", p_text), \
                    mock.patch("pathlib.Path.read_bytes", p_bytes), \
                    mock.patch.object(doctor, "find_gcloud", return_value="no-gcloud"), \
                    mock.patch.object(doctor, "find_bq", return_value="no-bq"):
                res = doctor.run_checks(t)
        self.assertNotIn("SECRETVALUE", json.dumps(res))
        self.assertTrue(any(r["title"] == ".env present" for r in res))


def subprocess_devnull():
    import subprocess
    return subprocess.DEVNULL


def doctor_pathlib():
    import pathlib
    return pathlib


if __name__ == "__main__":
    unittest.main()
