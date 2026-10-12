"""Shared helpers for bootstrap.py and doctor.py (stdlib only; parses on Python 3.6+)."""
import os
import re

MIN_PYTHON = (3, 10)

# key, package directory, [(requirements file, kind)]
# kind: "core" (required), "retrieval" (optional feature, failure tolerated)
AGENTS = [
    ("rca_copilot", "rca_copilot_agent", [("requirements.txt", "core")]),
    ("ticketasg", "ticketasg_copilot_agent",
     [("requirements.txt", "core"), ("requirements-retrieval.txt", "retrieval")]),
    ("mockdata", "mockdata_copilot_agent", [("requirements.txt", "core")]),
]
AGENT_KEYS = [a[0] for a in AGENTS]

# Distributions whose absence is only a warning (optional feature).
OPTIONAL_DISTS = ("openpyxl",)

# dist name (normalised) -> top-level import name, where they differ or to avoid lookups.
DIST_TO_IMPORT = {
    "python-dotenv": "dotenv",
    "sentence-transformers": "sentence_transformers",
    "playwright": "playwright",
    "requests": "requests",
    "urllib3": "urllib3",
    "numpy": "numpy",
    "openpyxl": "openpyxl",
    "mcp": "mcp",
    "pyyaml": "yaml",
    "pillow": "PIL",
    "beautifulsoup4": "bs4",
}

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


def normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements(path):
    """Return [(normalised_name, specifier_string)] from a requirements file.

    Skips blank lines, comments, pip options (-r, --index-url, ...), and URLs.
    Strips inline comments, extras and environment markers from the specifier.
    """
    out = []
    with open(str(path), "r") as fh:
        for raw in fh:
            line = raw.split(" #", 1)[0].strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if "://" in line.split(";")[0] and "@" not in line.split(";")[0]:
                continue
            line = line.split(";", 1)[0].strip()  # drop environment marker
            m = _NAME_RE.match(line)
            if not m:
                continue
            spec = m.group(3).strip()
            if spec.startswith("@"):
                spec = ""
            out.append((normalize_name(m.group(1)), spec))
    return out


def requirement_files(repo, agent_key):
    """Return [(absolute path, kind)] for an agent."""
    for key, pkg, files in AGENTS:
        if key == agent_key:
            return [(os.path.join(repo, pkg, f), kind) for f, kind in files]
    raise KeyError(agent_key)


def venv_python_path(repo):
    sub = os.path.join("Scripts", "python.exe") if os.name == "nt" else os.path.join("bin", "python")
    return os.path.join(repo, ".venv", sub)


def should_reexec(venv_py_exists, prefix_real, venv_real, env):
    """True when we should re-launch inside <repo>/.venv (mirrors run_tool re-exec rule)."""
    if not venv_py_exists:
        return False
    if env.get("RCA_VENV_REEXEC"):
        return False
    return prefix_real != venv_real
