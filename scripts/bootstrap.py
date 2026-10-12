#!/usr/bin/env python3
"""One-command setup: create <repo>/.venv and install the three Copilot agents.

Stdlib only. Run via ./setup.sh (macOS/Linux) or setup.cmd (Windows); see --help.
Exit codes: 0 all ok, 2 partial (an agent or optional extra failed, rca_copilot ok), 1 fatal.
"""
import sys

if sys.version_info < (3, 10):  # keep this module parseable on old interpreters
    sys.stderr.write(
        "ERROR: Python 3.10 or newer (64-bit) is required; this is Python {}.{}.\n"
        "Install Python 3.12 (python.org installer, Homebrew `brew install python@3.12`, "
        "or `uv python install 3.12`) and re-run ./setup.sh (macOS/Linux) or setup.cmd (Windows).\n"
        .format(sys.version_info[0], sys.version_info[1]))
    if __name__ == "__main__":
        sys.exit(1)

import argparse
import os
import shutil
import struct
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _reqs  # noqa: E402

REPO = os.path.dirname(HERE)
VENV_DIR = os.path.join(REPO, ".venv")


# ---------------------------------------------------------------- pure helpers

def classify_python(version_info, pointer_size):
    """Return (level, message); level is 'ok' | 'warn' | 'fatal'."""
    ver = "{}.{}".format(version_info[0], version_info[1])
    if tuple(version_info[:2]) < _reqs.MIN_PYTHON:
        return "fatal", "Python {} is too old; need 3.10 or newer".format(ver)
    if pointer_size != 8:
        return "fatal", "32-bit Python detected; 64-bit is required (torch/numpy wheels)"
    if tuple(version_info[:2]) >= (3, 14):
        return "warn", ("Python {} is very new: ticketasg kNN retrieval (torch) may have no "
                        "wheels yet; Python 3.12 is recommended".format(ver))
    return "ok", "Python {}".format(ver)


def _net_args(index_url=None, extra_index_url=None, wheelhouse=None, proxy=None):
    args = []
    if wheelhouse:
        args += ["--no-index", "--find-links", wheelhouse]
    else:
        if index_url:
            args += ["--index-url", index_url]
        if extra_index_url:
            args += ["--extra-index-url", extra_index_url]
    if proxy:
        args += ["--proxy", proxy]
    return args


def build_pip_args(python, requirements=None, upgrade_pip=False, index_url=None,
                   extra_index_url=None, wheelhouse=None, proxy=None, allow_source=False):
    """Build the full pip command line. Never adds --trusted-host.

    --no-input: never block on a credential prompt (stdout is piped, it would look like a hang).
    --retries/--timeout: fail in seconds, not minutes, when PyPI is blocked.
    """
    cmd = [python, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
           "--retries", "3", "--timeout", "30"]
    cmd += _net_args(index_url, extra_index_url, wheelhouse, proxy)
    if upgrade_pip:
        return cmd + ["--upgrade", "pip"]
    if not allow_source:
        cmd.append("--only-binary=:all:")
    if requirements:
        cmd += ["-r", requirements]
    return cmd


def parse_requirements(path):
    return _reqs.parse_requirements(path)


def summarize(results):
    """results: list of dicts {agent, status: ok|partial|failed, note}. Return exit code."""
    if not results:
        return 1
    failed = [r for r in results if r["status"] == "failed"]
    if len(failed) == len(results):
        return 1
    for r in failed:
        if r["agent"] == "rca_copilot":
            return 1
    if any(r["status"] != "ok" for r in results):
        return 2
    return 0


NETWORK_MARKERS = (
    "ProxyError", "407 Proxy Authentication", "SSLError", "CERTIFICATE_VERIFY_FAILED",
    "ConnectionError", "NewConnectionError", "Max retries exceeded", "HTTP error 403",
    "Could not fetch URL", "Temporary failure in name resolution", "getaddrinfo failed",
    "Name or service not known", "ReadTimeoutError", "ConnectTimeoutError",
)


def is_network_failure(output):
    """True if pip's output looks like a network/proxy/TLS problem (not a missing wheel)."""
    text = output or ""
    return any(m.lower() in text.lower() for m in NETWORK_MARKERS)


def pip_failure_hints(output):
    """Targeted hints from pip's output text. Matches specific markers, not bare substrings."""
    text = output or ""
    low = text.lower()

    def has(*markers):
        return any(m.lower() in low for m in markers)

    hints = []
    if has("CERTIFICATE_VERIFY_FAILED", "SSLError"):
        hints.append("SSL inspection suspected: set PIP_CERT=<corporate-root.pem> (or pass --cert <pem>) first; "
                     "persist it with `python -m pip config set global.cert <path>`. pip on Python 3.10/3.11 "
                     "may be too old to use the OS trust store, so even the pip upgrade can fail until then.")
    if has("ProxyError", "407 Proxy Authentication"):
        hints.append("Proxy problem: set HTTPS_PROXY / HTTP_PROXY, or pass --proxy http://user@host:port.")
    if has("No matching distribution found", "Could not find a version that satisfies"):
        hints.append("No wheel for this Python/platform: install Python 3.12 and re-run, "
                     "or use --allow-source if you have a compiler.")
    if has("ConnectionError", "NewConnectionError", "Max retries exceeded", "HTTP error 403",
           "Could not fetch URL", "Temporary failure in name resolution", "getaddrinfo failed",
           "Name or service not known", "ReadTimeoutError", "ConnectTimeoutError"):
        hints.append("PyPI unreachable/blocked: use --index-url <internal mirror> or "
                     "--wheelhouse <dir with pre-downloaded wheels>.")
    if not hints:
        hints.append("See the pip output above. Options: --index-url <mirror>, --wheelhouse <dir>, --proxy <url>.")
    return hints


LONG_PATH_LIMIT = 100


def long_path_hint():
    return ("Windows MAX_PATH: torch/sentence-transformers have very deep file paths and can fail to install. "
            "Clone the repo to a short path such as C:\\src\\rca, or enable LongPathsEnabled "
            "(Windows setting 'Enable Win32 long paths'; needs admin/IT) and use a new terminal.")


def long_path_warning(repo=None, osname=None):
    """Return the warning text when on Windows with a long repo path, else None."""
    repo = REPO if repo is None else repo
    osname = os.name if osname is None else osname
    if osname == "nt" and len(str(repo)) > LONG_PATH_LIMIT:
        return "WARNING: repo path is {} characters long. ".format(len(str(repo))) + long_path_hint()
    return None


# ---------------------------------------------------------------- side-effecting

def banner(text):
    sys.stdout.write("\n==== {} ====\n".format(text))
    sys.stdout.flush()


def _safe_write(text):
    """Write to stdout without ever raising on an un-encodable character (cp1252 consoles)."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.write(text.encode(enc, "replace").decode(enc))
    sys.stdout.flush()


def _reconfigure_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def running_inside_venv():
    return os.path.realpath(sys.prefix) == os.path.realpath(VENV_DIR)


def run_streaming(cmd):
    """Run cmd, echo output live, return (returncode, captured_text)."""
    sys.stdout.write("$ {}\n".format(" ".join(cmd)))
    sys.stdout.flush()
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, universal_newlines=True,
                                errors="replace", cwd=REPO)
    except OSError as exc:
        msg = "could not start {}: {}".format(cmd[0], exc)
        sys.stdout.write(msg + "\n")
        return 127, msg
    captured = []
    for line in proc.stdout:
        _safe_write(line)
        captured.append(line)
    proc.wait()
    return proc.returncode, "".join(captured)


def venv_python():
    return _reqs.venv_python_path(REPO)


def venv_python_version(py):
    """Return (major, minor) of a venv python, or None if it cannot run."""
    try:
        out = subprocess.check_output(
            [py, "-c", "import sys,struct;print('%d.%d.%d'%tuple(sys.version_info[:3])+' '+str(struct.calcsize('P')))"],
            stderr=subprocess.STDOUT, universal_newlines=True, timeout=60)
        ver, ptr = out.split()
        parts = ver.split(".")
        return (int(parts[0]), int(parts[1])), int(ptr)
    except Exception:
        return None


def ensure_venv(recreate):
    py = venv_python()
    if os.path.isdir(VENV_DIR):
        reason = None
        if recreate:
            reason = "--recreate requested"
        elif not os.path.exists(py):
            reason = "no python inside .venv"
        else:
            info = venv_python_version(py)
            if info is None:
                reason = "venv python fails to start (broken venv)"
            elif info[0] < _reqs.MIN_PYTHON or info[1] != 8:
                reason = "venv python is {}.{} / {}-bit; need >=3.10 64-bit".format(
                    info[0][0], info[0][1], info[1] * 8)
        if reason is None:
            print("Reusing existing virtualenv: {}".format(VENV_DIR))
            return True
        print("Recreating virtualenv ({}).".format(reason))
        if os.path.basename(VENV_DIR) == ".venv":
            shutil.rmtree(VENV_DIR, ignore_errors=True)
    print("Creating virtualenv: {}".format(VENV_DIR))
    rc, out = run_streaming([sys.executable, "-m", "venv", VENV_DIR])
    if rc != 0 or not os.path.exists(py):
        print("ERROR: could not create the virtualenv.")
        if "ensurepip" in out:
            print("Hint: on Debian/Ubuntu run `sudo apt install python3-venv`.")
        print("Hint: if antivirus/AppLocker blocks .venv, ask IT, or try another Python (3.12).")
        return False
    return True


def install_file(py, req_file, opts):
    return run_streaming(build_pip_args(
        py, requirements=req_file, index_url=opts.index_url,
        extra_index_url=opts.extra_index_url, wheelhouse=opts.wheelhouse,
        proxy=opts.proxy, allow_source=opts.allow_source))


def install_agent(py, key, opts):
    """Install one agent. Returns result dict {agent, status, note}."""
    banner("Installing agent: {}".format(key))
    notes = []
    status = "ok"
    for path, kind in _reqs.requirement_files(REPO, key):
        if kind == "retrieval" and opts.skip_retrieval:
            notes.append("kNN retrieval skipped (--skip-retrieval)")
            status = "partial"
            continue
        if not os.path.isfile(path):
            if kind == "core":
                return {"agent": key, "status": "failed",
                        "note": "missing {}".format(os.path.relpath(path, REPO))}
            notes.append("missing {}".format(os.path.relpath(path, REPO)))
            status = "partial"
            continue
        print("-- {}".format(os.path.relpath(path, REPO)))
        rc, out = install_file(py, path, opts)
        if rc != 0:
            for h in pip_failure_hints(out):
                print("HINT: " + h)
            if kind == "retrieval" and os.name == "nt":
                print("HINT: " + long_path_hint())
            if kind == "core":
                return {"agent": key, "status": "failed", "note": "pip install failed"}
            notes.append("installed, kNN retrieval unavailable")
            status = "partial"
    return {"agent": key, "status": status, "note": "; ".join(notes) or "installed"}


def print_summary(results):
    banner("Summary")
    rows = [("Agent", "Result", "Note")]
    label = {"ok": "OK", "partial": "PARTIAL", "failed": "FAILED"}
    for r in results:
        rows.append((r["agent"], label[r["status"]], r["note"]))
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    for i, row in enumerate(rows):
        print("  ".join(c.ljust(widths[j]) for j, c in enumerate(row)).rstrip())
        if i == 0:
            print("  ".join("-" * w for w in widths))


def print_next_steps(py):
    banner("Next steps")
    print("1. Log in to Google Cloud once:   gcloud auth login   (use your @loreal.com account)")
    print("2. Re-check anytime:              {} scripts/doctor.py".format(
        "py -3" if os.name == "nt" else "python3"))
    print("3. Open this folder in VS Code and use the Copilot agents (rca_copilot / ticketasg / mockdata).")
    print("   No venv activation needed: run_tool.py re-launches itself in .venv.")


def build_parser():
    p = argparse.ArgumentParser(description="Create .venv and install the Copilot agents.")
    p.add_argument("--agents", default=",".join(_reqs.AGENT_KEYS),
                   help="comma list of: " + ",".join(_reqs.AGENT_KEYS) + " (default: all)")
    p.add_argument("--skip-retrieval", action="store_true", help="skip ticketasg kNN retrieval deps (torch)")
    p.add_argument("--with-mcp", action="store_true", help="also install requirements-mcp.txt")
    p.add_argument("--index-url", help="package index (internal mirror)")
    p.add_argument("--extra-index-url", help="extra package index")
    p.add_argument("--wheelhouse", help="directory of pre-downloaded wheels (offline install)")
    p.add_argument("--proxy", help="proxy URL for pip, e.g. http://user@host:8080")
    p.add_argument("--allow-source", action="store_true", help="allow source builds (drop --only-binary)")
    p.add_argument("--recreate", action="store_true", help="delete and recreate .venv")
    p.add_argument("--no-doctor", action="store_true", help="do not run scripts/doctor.py at the end")
    return p


def main(argv=None):
    _reconfigure_streams()
    opts = build_parser().parse_args(argv)
    keys = [k.strip() for k in opts.agents.split(",") if k.strip()]
    bad = [k for k in keys if k not in _reqs.AGENT_KEYS]
    if bad:
        print("ERROR: unknown agent(s): {}. Valid: {}".format(", ".join(bad), ", ".join(_reqs.AGENT_KEYS)))
        return 1
    keys = [k for k in _reqs.AGENT_KEYS if k in keys]  # canonical order

    banner("Checking Python")
    level, msg = classify_python(sys.version_info, struct.calcsize("P"))
    print(msg)
    if level == "fatal":
        return 1
    if level == "warn":
        print("WARNING: " + msg)

    if opts.recreate and running_inside_venv():
        print("ERROR: --recreate would delete the .venv this Python is running from. "
              "Run setup with a system Python instead (./setup.sh --recreate or setup.cmd --recreate), "
              "not from inside .venv.")
        return 1

    warn = long_path_warning()
    if warn:
        print(warn)

    banner("Virtualenv")
    if not ensure_venv(opts.recreate):
        return 1
    py = venv_python()

    banner("Upgrading pip")
    rc, out = run_streaming(build_pip_args(
        py, upgrade_pip=True, index_url=opts.index_url, extra_index_url=opts.extra_index_url,
        wheelhouse=opts.wheelhouse, proxy=opts.proxy))
    if rc != 0:
        for h in pip_failure_hints(out):
            print("HINT: " + h)
        if is_network_failure(out) and not opts.wheelhouse:
            print("ERROR: cannot reach the package index; stopping early instead of retrying every agent.")
            return 1
        print("WARNING: pip upgrade failed; continuing with the bundled pip.")

    results = [install_agent(py, k, opts) for k in keys]

    if opts.with_mcp:
        banner("Installing MCP extras")
        mcp_file = os.path.join(REPO, "requirements-mcp.txt")
        if os.path.isfile(mcp_file):
            rc, out = install_file(py, mcp_file, opts)
            if rc != 0:
                for h in pip_failure_hints(out):
                    print("HINT: " + h)
                results.append({"agent": "mcp (extra)", "status": "partial",
                                "note": "requirements-mcp.txt failed"})
            else:
                results.append({"agent": "mcp (extra)", "status": "ok", "note": "installed"})
        else:
            results.append({"agent": "mcp (extra)", "status": "partial",
                            "note": "requirements-mcp.txt not found"})

    print_summary(results)
    code = summarize([r for r in results if not r["agent"].endswith("(extra)")] or results)
    if code == 0 and any(r["status"] != "ok" for r in results):
        code = 2

    if not opts.no_doctor:
        banner("Doctor")
        doc_rc, _ = run_streaming([py, os.path.join(HERE, "doctor.py")])
        if doc_rc != 0:
            print("Doctor reported problems (see above).")
            code = max(code, 2) if code != 1 else 1

    print_next_steps(py)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        sys.exit(130)
