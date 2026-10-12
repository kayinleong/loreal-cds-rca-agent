#!/usr/bin/env python3
"""Offline environment check for the RCA Copilot agents (stdlib only).

No network, no logins, never reads .env. Exit 0 if no failures, else 1. Use --json for machine output.
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _reqs  # noqa: E402

REPO = os.path.dirname(HERE)
ENV_VARS = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "REQUESTS_CA_BUNDLE",
            "SSL_CERT_FILE", "PIP_INDEX_URL", "PIP_CERT")

OK, WARN, FAIL = "ok", "warn", "fail"


def item(level, title, detail="", hint=""):
    return {"level": level, "title": title, "detail": detail, "hint": hint}


def realpath(p):
    return os.path.realpath(p)


# ------------------------------------------------------------------ checks

def check_python(version_info=None, pointer_size=None, prefix=None, repo=None):
    version_info = version_info or sys.version_info
    pointer_size = pointer_size or struct.calcsize("P")
    prefix = prefix or sys.prefix
    repo = repo or REPO
    ver = "{}.{}.{}".format(*tuple(version_info[:3]))
    out = []
    if tuple(version_info[:2]) < _reqs.MIN_PYTHON or pointer_size != 8:
        out.append(item(FAIL, "Python {} ({}-bit)".format(ver, pointer_size * 8),
                        hint="Need Python 3.10+ 64-bit (3.12 recommended). Install it, then run setup.sh / setup.cmd."))
    elif tuple(version_info[:2]) >= (3, 14):
        out.append(item(WARN, "Python {} (64-bit)".format(ver),
                        hint="Very new: torch (ticketasg retrieval) may lack wheels. Prefer Python 3.12."))
    else:
        out.append(item(OK, "Python {} (64-bit)".format(ver)))
    venv_dir = os.path.join(repo, ".venv")
    if realpath(prefix) == realpath(venv_dir):
        out.append(item(OK, "Running inside repo .venv"))
    else:
        out.append(item(WARN, "Not running inside repo .venv",
                        hint="Run ./setup.sh (macOS/Linux) or setup.cmd (Windows) to create it."))
    return out


def _default_version(name):
    try:
        from importlib import metadata
    except ImportError:
        return None
    try:
        return metadata.version(name)
    except Exception:
        return None


def _default_find_spec(modname):
    import importlib.util
    try:
        return importlib.util.find_spec(modname) is not None
    except Exception:
        return False


def _default_dist_map():
    try:
        from importlib import metadata
        return metadata.packages_distributions()
    except Exception:
        return {}


def import_name_for(dist, dist_map=None):
    if dist in _reqs.DIST_TO_IMPORT:
        return _reqs.DIST_TO_IMPORT[dist]
    for top, dists in (dist_map or {}).items():
        if dist in [_reqs.normalize_name(d) for d in dists]:
            return top
    return dist.replace("-", "_")


def check_agent(key, repo=None, version_fn=None, find_spec_fn=None, dist_map=None):
    repo = repo or REPO
    version_fn = version_fn or _default_version
    find_spec_fn = find_spec_fn or _default_find_spec
    if dist_map is None:
        dist_map = _default_dist_map()
    out = []
    for path, kind in _reqs.requirement_files(repo, key):
        rel = os.path.relpath(path, repo)
        if not os.path.isfile(path):
            level = FAIL if kind == "core" else WARN
            out.append(item(level, "{}: {} not found".format(key, rel), hint="Re-pull the repo."))
            continue
        for name, _spec in _reqs.parse_requirements(path):
            optional = kind != "core" or name in _reqs.OPTIONAL_DISTS
            miss_level = WARN if optional else FAIL
            version = version_fn(name)
            if version is None:
                what = "optional feature unavailable" if optional else "required"
                out.append(item(miss_level, "{}: {} not installed ({})".format(key, name, what),
                                hint="Run ./setup.sh / setup.cmd"
                                     + (" (kNN retrieval will be unavailable until then)" if kind == "retrieval" else "")))
                continue
            mod = import_name_for(name, dist_map)
            if not find_spec_fn(mod):
                out.append(item(miss_level, "{}: {} {} installed but module '{}' not importable".format(
                    key, name, version, mod), hint="Re-run setup with --recreate."))
            else:
                out.append(item(OK, "{}: {} {}".format(key, name, version)))
    return out


def _load_finder(relpath, attr, fallback_name):
    """Reuse the agents' own discovery logic; fall back to shutil.which if it cannot be imported."""
    path = os.path.join(REPO, relpath)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_doctor_" + fallback_name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, attr)()
    except Exception:
        env_var = fallback_name.upper() + "_BIN"
        return os.environ.get(env_var) or shutil.which(fallback_name) or fallback_name


def find_gcloud():
    return _load_finder(os.path.join("rca_copilot_agent", "tools", "gcloud_tool.py"), "_find_gcloud", "gcloud")


def find_bq():
    return _load_finder(os.path.join("rca_copilot_agent", "tools", "bigquery_tool.py"), "_find_bq", "bq")


def check_tool(name, found_path, install_hint):
    if found_path and os.path.isfile(found_path):
        return item(OK, "{} found".format(name), detail=found_path)
    return item(FAIL, "{} not found".format(name), hint=install_hint)


def edge_candidates(environ=None, platform=None):
    environ = os.environ if environ is None else environ
    platform = platform or sys.platform
    if platform.startswith("win"):
        out = []
        for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            base = environ.get(var)
            if base:
                out.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
        return out
    if platform == "darwin":
        return ["/Applications/Microsoft Edge.app"]
    return []


def check_edge(exists=os.path.exists, environ=None, platform=None):
    for c in edge_candidates(environ, platform):
        if exists(c):
            return item(OK, "Microsoft Edge installed")
    return item(WARN, "Microsoft Edge not found",
                hint="SSO cookie capture needs Edge (macOS: install to /Applications, not ~/Applications); "
                     "otherwise paste cookies manually.")


def mask_account(account):
    account = (account or "").strip()
    if "@" not in account:
        return "***"
    return "***@" + account.rsplit("@", 1)[1]


def check_account_output(account):
    """account: first active gcloud account string or ''/None."""
    account = (account or "").strip()
    if not account:
        return item(WARN, "No active gcloud account", hint="Run: gcloud auth login")
    masked = mask_account(account)
    if not account.lower().endswith("@loreal.com"):
        return item(WARN, "Active gcloud account {} is not @loreal.com".format(masked),
                    hint="Run: gcloud auth login with your @loreal.com account")
    return item(OK, "Active gcloud account {}".format(masked))


def get_gcloud_account(gcloud_path, run=subprocess.run):
    try:
        res = run([gcloud_path, "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=15)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return ""


def check_files(repo=None):
    repo = repo or REPO
    out = []
    if os.path.isfile(os.path.join(repo, "schema.json")):
        out.append(item(OK, "schema.json present"))
    else:
        out.append(item(FAIL, "schema.json missing at repo root", hint="Re-pull the repo (git checkout schema.json)."))
    # Presence only: .env is never opened.
    if os.path.exists(os.path.join(repo, ".env")):
        out.append(item(OK, ".env present"))
    else:
        out.append(item(WARN, ".env not present",
                        hint="Created automatically at first SSO login (auth_tool writes COOKIE / X_USERTOKEN)."))
    return out


def check_env(environ=None):
    environ = os.environ if environ is None else environ
    names = [n for n in ENV_VARS if environ.get(n)]
    if not names:
        return item(OK, "No proxy/cert environment variables set")
    return item(OK, "Proxy/cert variables set (names only): " + ", ".join(names),
                hint="If pip/requests fail with SSL errors behind inspection, set REQUESTS_CA_BUNDLE to the corporate CA bundle.")


def run_checks(repo=None):
    repo = repo or REPO
    results = []
    results += check_python(repo=repo)
    for key in _reqs.AGENT_KEYS:
        results += check_agent(key, repo)
    gcloud = find_gcloud()
    results.append(check_tool("gcloud", gcloud, "Install the Google Cloud SDK (or set GCLOUD_BIN)."))
    results.append(check_tool("bq", find_bq(), "Install the Google Cloud SDK bq component (or set BQ_BIN)."))
    results.append(check_edge())
    if os.path.isfile(gcloud):
        results.append(check_account_output(get_gcloud_account(gcloud)))
    results += check_files(repo)
    results.append(check_env())
    return results


# ------------------------------------------------------------------ output

def symbols(encoding=None):
    enc = encoding or getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        u"✓⚠✗".encode(enc)
        return {OK: u"✓", WARN: u"⚠", FAIL: u"✗"}
    except Exception:
        return {OK: "[OK]", WARN: "[WARN]", FAIL: "[FAIL]"}


def exit_code(results):
    return 1 if any(r["level"] == FAIL for r in results) else 0


def render(results, encoding=None):
    sym = symbols(encoding)
    lines = []
    for r in results:
        line = "{} {}".format(sym[r["level"]], r["title"])
        if r["detail"]:
            line += " ({})".format(r["detail"])
        lines.append(line)
        if r["level"] != OK and r["hint"]:
            lines.append("    -> " + r["hint"])
    fails = sum(1 for r in results if r["level"] == FAIL)
    warns = sum(1 for r in results if r["level"] == WARN)
    lines.append("")
    lines.append("Result: {} failure(s), {} warning(s).".format(fails, warns))
    return "\n".join(lines)


def maybe_reexec(argv):
    """Re-launch inside <repo>/.venv when present (same rule as run_tool)."""
    vpy = _reqs.venv_python_path(REPO)
    if _reqs.should_reexec(os.path.exists(vpy), realpath(sys.prefix),
                           realpath(os.path.join(REPO, ".venv")), os.environ):
        env = dict(os.environ)
        env["RCA_VENV_REEXEC"] = "1"
        sys.exit(subprocess.call([vpy, os.path.abspath(__file__)] + list(argv), env=env))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    maybe_reexec(argv)
    results = run_checks()
    if "--json" in argv:
        print(json.dumps({"ok": exit_code(results) == 0, "checks": results}, indent=2))
    else:
        print(render(results))
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
