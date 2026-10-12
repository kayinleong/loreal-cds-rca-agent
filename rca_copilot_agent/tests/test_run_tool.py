"""Offline tests for run_tool argument parsing (never calls main())."""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PKG))

import run_tool  # noqa: E402
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


class UnknownToolTests(unittest.TestCase):
    def test_rejected_before_auth_checks(self):
        err = io.StringIO()
        # Stub modules so the test needs no third-party packages (dotenv, ...).
        auth = mock.Mock(side_effect=AssertionError("auth called"))
        gcl = mock.Mock(side_effect=AssertionError("gcloud called"))
        stubs = {
            "tools.auth_tool": mock.Mock(ensure_credentials=auth),
            "tools.gcloud_tool": mock.Mock(ensure_gcloud_auth=gcl),
        }
        with mock.patch.dict(os.environ, {run_tool.REEXEC_ENV: "1"}), \
                mock.patch.dict(sys.modules, stubs), \
                mock.patch.object(sys, "argv", ["run_tool.py", "no_such_tool"]), \
                redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            run_tool.main()
        self.assertEqual(cm.exception.code, 1)
        auth.assert_not_called()
        gcl.assert_not_called()
        out = err.getvalue()
        self.assertIn("unknown tool 'no_such_tool'", out)
        self.assertIn("list_incidents", out)
        self.assertIn("send_rca_email", out)

    def test_tool_help_covers_every_tool(self):
        import dispatcher
        self.assertEqual(set(dispatcher.TOOL_HELP), set(dispatcher.TOOL_NAMES))


class ReexecTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.other_prefix = str(self.root / "elsewhere")

    def _make_venv(self, *sub):
        py = self.root.joinpath(".venv", *sub)
        py.parent.mkdir(parents=True)
        py.write_text("")
        return py

    def _call(self, environ=None, prefix=None, os_name=None):
        with mock.patch("run_tool.subprocess.call", return_value=7) as call:
            try:
                run_tool._reexec_in_repo_venv(
                    repo_root=self.root,
                    prefix=prefix or self.other_prefix,
                    environ={} if environ is None else environ,
                    argv=["list_incidents", "--arg", "a=b"],
                    script="/x/run_tool.py",
                    os_name=os_name,
                )
                exited = None
            except SystemExit as e:
                exited = e.code
        return call, exited

    def test_posix_reexec(self):
        py = self._make_venv("bin", "python")
        call, exited = self._call(environ={"KEEP": "1"}, os_name="posix")
        call.assert_called_once()
        argv = call.call_args[0][0]
        self.assertEqual(argv, [str(py), "/x/run_tool.py", "list_incidents", "--arg", "a=b"])
        env = call.call_args[1]["env"]
        self.assertEqual(env[run_tool.REEXEC_ENV], "1")
        self.assertEqual(env["KEEP"], "1")
        self.assertEqual(exited, 7)

    def test_windows_layout(self):
        py = self._make_venv("Scripts", "python.exe")
        call, exited = self._call(os_name="nt")
        self.assertEqual(call.call_args[0][0][0], str(py))
        self.assertEqual(exited, 7)

    def test_not_invoked_when_marker_set(self):
        self._make_venv("bin", "python")
        call, exited = self._call(environ={run_tool.REEXEC_ENV: "1"}, os_name="posix")
        call.assert_not_called()
        self.assertIsNone(exited)

    def test_not_invoked_when_venv_missing(self):
        call, exited = self._call(os_name="posix")
        call.assert_not_called()
        self.assertIsNone(exited)

    def test_not_invoked_when_wrong_os_layout(self):
        self._make_venv("bin", "python")
        call, _ = self._call(os_name="nt")
        call.assert_not_called()

    def test_not_invoked_when_already_in_venv(self):
        self._make_venv("bin", "python")
        call, exited = self._call(prefix=str(self.root / ".venv"), os_name="posix")
        call.assert_not_called()
        self.assertIsNone(exited)


class ReexecFailureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        py = self.root / ".venv" / "bin" / "python"
        py.parent.mkdir(parents=True)
        py.write_text("")

    def _run(self, **call_kwargs):
        err = io.StringIO()
        with mock.patch.object(run_tool.subprocess, "call", **call_kwargs), \
                redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            run_tool._reexec_in_repo_venv(
                repo_root=self.root, prefix=str(self.root / "elsewhere"),
                environ={}, argv=["t"], script="/x/run_tool.py", os_name="posix")
        return cm.exception.code, err.getvalue()

    def test_oserror_gives_recreate_hint(self):
        code, err = self._run(side_effect=OSError(8, "Exec format error"))
        self.assertEqual(code, 1)
        self.assertIn("`.venv` exists but its Python can't start", err)
        self.assertIn("OSError", err)
        self.assertIn("Exec format error", err)
        self.assertIn("./setup.sh --recreate", err)
        self.assertIn("setup.cmd --recreate", err)

    def test_permission_error_is_oserror(self):
        code, err = self._run(side_effect=PermissionError(13, "Permission denied"))
        self.assertEqual(code, 1)
        self.assertIn("PermissionError", err)

    def test_keyboard_interrupt_exits_130_quietly(self):
        code, err = self._run(side_effect=KeyboardInterrupt())
        self.assertEqual(code, 130)
        self.assertEqual(err, "")

    def test_negative_returncode_maps_to_128_plus_signal(self):
        code, _ = self._run(return_value=-9)
        self.assertEqual(code, 137)
        code, _ = self._run(return_value=-15)
        self.assertEqual(code, 143)

    def test_zero_and_positive_returncode_passthrough(self):
        self.assertEqual(self._run(return_value=0)[0], 0)
        self.assertEqual(self._run(return_value=3)[0], 3)


@unittest.skipIf(os.name == "nt", "fake POSIX venv python needs /bin/sh")
class RealReexecTests(unittest.TestCase):
    """No mocks: a copied run_tool.py really spawns a fake <repo>/.venv/bin/python."""

    def test_real_reexec_passes_argv_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            pkg = repo / "rca_copilot_agent"
            pkg.mkdir(parents=True)
            script = pkg / "run_tool.py"
            shutil.copy(_PKG / "run_tool.py", script)
            out = Path(tmp) / "child_out.txt"
            fake = repo / ".venv" / "bin" / "python"
            fake.parent.mkdir(parents=True)
            fake.write_text(
                "#!/bin/sh\n"
                "{ echo \"marker=$RCA_VENV_REEXEC\"; for a in \"$@\"; do echo \"arg=$a\"; done; }"
                " > \"$CHILD_OUT\"\n"
                "exit 7\n"
            )
            fake.chmod(0o755)
            env = {k: v for k, v in os.environ.items() if k != run_tool.REEXEC_ENV}
            env["CHILD_OUT"] = str(out)
            args = ["some_tool", "--arg", "name=L'Oréal", "--arg", "q=a b  c"]
            proc = subprocess.run(
                [sys.executable, str(script), *args], env=env, cwd=tmp,
                stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 7, proc.stderr.decode("utf-8", "replace"))
            lines = out.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "marker=1")
            self.assertEqual(
                lines[1:],
                ["arg=" + str(script.resolve()), "arg=some_tool", "arg=--arg",
                 "arg=name=L'Oréal", "arg=--arg", "arg=q=a b  c"])


class MissingModuleTests(unittest.TestCase):
    def test_hint_printed(self):
        err = io.StringIO()
        boom = ModuleNotFoundError("No module named 'dotenv'", name="dotenv")
        with mock.patch.dict(os.environ, {run_tool.REEXEC_ENV: "1"}), \
                mock.patch.object(run_tool, "_main", side_effect=boom), \
                redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            run_tool.main()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Missing Python package 'dotenv'", err.getvalue())
        self.assertIn("./setup.sh", err.getvalue())
        self.assertIn("setup.cmd", err.getvalue())

    def test_local_module_error_not_masked(self):
        boom = ModuleNotFoundError("No module named 'config'", name="config")
        with mock.patch.dict(os.environ, {run_tool.REEXEC_ENV: "1"}), \
                mock.patch.object(run_tool, "_main", side_effect=boom), \
                self.assertRaises(ModuleNotFoundError):
            run_tool.main()


if __name__ == "__main__":
    unittest.main()
