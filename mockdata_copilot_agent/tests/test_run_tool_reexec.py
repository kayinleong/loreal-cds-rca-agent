"""Offline tests for run_tool's venv re-exec and missing-package hint (stdlib only)."""
import importlib.util
import io
import os
import shutil
import subprocess
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
            pkg = repo / "mockdata_copilot_agent"
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
        for mod in run_tool._LOCAL_MODULES:
            boom = ModuleNotFoundError("No module named '%s'" % mod, name=mod)
            with mock.patch.dict(os.environ, {run_tool.REEXEC_ENV: "1"}), \
                    mock.patch.object(run_tool, "_main", side_effect=boom), \
                    self.assertRaises(ModuleNotFoundError):
                run_tool.main()


if __name__ == "__main__":
    unittest.main()
