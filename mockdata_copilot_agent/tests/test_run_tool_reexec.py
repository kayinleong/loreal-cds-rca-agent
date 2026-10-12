"""Offline tests for run_tool's venv re-exec and missing-package hint (stdlib only)."""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

_PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PKG))

# Unique module name so several packages' run_tool.py never collide in one process.
_NAME = "mockdata_run_tool_under_test"
_spec = importlib.util.spec_from_file_location(_NAME, _PKG / "run_tool.py")
run_tool = importlib.util.module_from_spec(_spec)
sys.modules[_NAME] = run_tool
_spec.loader.exec_module(run_tool)


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
        with mock.patch.object(run_tool.subprocess, "call", return_value=7) as call:
            try:
                run_tool._reexec_in_repo_venv(
                    repo_root=self.root,
                    prefix=prefix or self.other_prefix,
                    environ={} if environ is None else environ,
                    argv=["list_incidents", "--json", "{}"],
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
        self.assertEqual(call.call_args[0][0],
                         [str(py), "/x/run_tool.py", "list_incidents", "--json", "{}"])
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
        for mod in run_tool._LOCAL_MODULES:
            boom = ModuleNotFoundError("No module named '%s'" % mod, name=mod)
            with mock.patch.dict(os.environ, {run_tool.REEXEC_ENV: "1"}), \
                    mock.patch.object(run_tool, "_main", side_effect=boom), \
                    self.assertRaises(ModuleNotFoundError):
                run_tool.main()


if __name__ == "__main__":
    unittest.main()
