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


class SetupScripts(unittest.TestCase):
    def test_cmd_crlf_ascii(self):
        p = os.path.join(os.path.dirname(SCRIPTS), "setup.cmd")
        with open(p, "rb") as fh:
            data = fh.read()
        data.decode("ascii")
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))


if __name__ == "__main__":
    unittest.main()
