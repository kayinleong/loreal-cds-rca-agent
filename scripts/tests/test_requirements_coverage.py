"""Guarantee that no third-party library an agent imports is missing from its requirement files.

Offline, stdlib only. Run from the repo root:
    python -m unittest discover -s scripts/tests -p 'test_requirements_coverage.py' -v
"""
from __future__ import annotations

import ast
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("REQ_COVERAGE_ROOT", Path(__file__).resolve().parents[2]))

# package -> requirement files (relative to ROOT) that declare its dependencies
PACKAGES = {
    "rca_copilot_agent": ["rca_copilot_agent/requirements.txt"],
    "ticketasg_copilot_agent": [
        "ticketasg_copilot_agent/requirements.txt",
        "ticketasg_copilot_agent/requirements-retrieval.txt",
    ],
    "mockdata_copilot_agent": ["mockdata_copilot_agent/requirements.txt"],
}
MCP_FILE = "requirements-mcp.txt"
ROOT_FILE = "requirements.txt"

# import name -> distribution name (default: identical)
IMPORT_TO_DIST = {
    "dotenv": "python-dotenv",
    "sentence_transformers": "sentence-transformers",
    "google": "google-cloud-bigquery",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
}

# Distributions allowed to be imported but undeclared. Every entry needs a reason.
KNOWN_UNDECLARED = {
    # Only referenced by unreachable SafeBigQueryExecutor code; all agents query via the `bq` CLI.
    "google-cloud-bigquery": "dead code path (bq CLI subprocess is used instead)",
    # Optional lazy import in try/except ImportError; always installed transitively by requests.
    "certifi": "transitive dependency of requests",
}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def req_lines(path: Path):
    """Yield (lineno, raw_line, requirement_text) for non-comment, non-blank lines."""
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.split(" #", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if text:
            yield no, raw, text


def declared(paths) -> set:
    names = set()
    for p in paths:
        for _, _, text in req_lines(ROOT / p):
            if text.startswith("-"):
                continue
            names.add(norm(re.split(r"[<>=!~;\[ ]", text, 1)[0]))
    return names


def local_names(pkg_dir: Path) -> set:
    names = set()
    for child in pkg_dir.iterdir():
        if child.suffix == ".py":
            names.add(child.stem)
        elif child.is_dir():
            names.add(child.name)
    return names


def scan_imports(pkg: str):
    """Return {top_level_import: [(relpath, lineno), ...]} for third-party candidates."""
    pkg_dir = ROOT / pkg
    local = local_names(pkg_dir) | {pkg}
    found = {}
    for py in sorted(pkg_dir.rglob("*.py")):
        rel = py.relative_to(ROOT)
        if "tests" in rel.parts or "__pycache__" in rel.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [(a.name, node.lineno) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [(node.module, node.lineno)]
            else:
                continue
            for mod, lineno in mods:
                top = mod.split(".")[0]
                if top in sys.stdlib_module_names or top in local or top == "__future__":
                    continue
                found.setdefault(top, []).append((str(rel), lineno))
    return found


class RequirementsCoverage(unittest.TestCase):
    def test_every_import_is_declared(self):
        mcp = declared([MCP_FILE])
        problems = []
        for pkg, files in PACKAGES.items():
            ok = declared(files) | mcp | {norm(k) for k in KNOWN_UNDECLARED}
            for top, locs in scan_imports(pkg).items():
                dist = norm(IMPORT_TO_DIST.get(top, top))
                if dist not in ok:
                    where = ", ".join(f"{f}:{n}" for f, n in locs[:5])
                    problems.append(
                        f"{where}: imports '{top}' (distribution '{dist}') which is not in "
                        f"{' / '.join(files)} or {MCP_FILE}; add it there (or to KNOWN_UNDECLARED with a reason)"
                    )
        self.assertFalse(problems, "Undeclared third-party imports:\n  " + "\n  ".join(problems))

    def test_known_undeclared_is_not_stale(self):
        used = set()
        for pkg in PACKAGES:
            for top in scan_imports(pkg):
                used.add(norm(IMPORT_TO_DIST.get(top, top)))
        stale = [k for k in KNOWN_UNDECLARED if norm(k) not in used]
        self.assertFalse(stale, f"KNOWN_UNDECLARED entries no longer imported anywhere: {stale}")

    def test_root_requirements_includes_exactly_agent_files(self):
        expected = sorted(f for files in PACKAGES.values() for f in files)
        actual = []
        for no, raw, text in req_lines(ROOT / ROOT_FILE):
            self.assertTrue(text.startswith("-r "), f"{ROOT_FILE}:{no}: only '-r <file>' lines allowed, got {raw!r}")
            actual.append(text[3:].strip())
        self.assertEqual(sorted(actual), expected)
        self.assertNotIn(MCP_FILE, actual, "requirements-mcp.txt must stay opt-in")

    def test_no_exact_pins_and_no_includes_in_agent_files(self):
        files = [f for fs in PACKAGES.values() for f in fs] + [MCP_FILE]
        for f in files:
            for no, raw, text in req_lines(ROOT / f):
                self.assertNotIn("==", text, f"{f}:{no}: exact pin not allowed: {raw!r}")
                self.assertFalse(text.startswith("-"), f"{f}:{no}: '-r' not allowed in per-agent files")
                self.assertIn(",<", text.replace(" ", ""), f"{f}:{no}: needs an upper bound: {raw!r}")

    def test_mcp_is_bounded_below_2(self):
        txt = " ".join(t for _, _, t in req_lines(ROOT / MCP_FILE))
        self.assertRegex(txt, r"^mcp>=[\d.]+,<2\b")


if __name__ == "__main__":
    unittest.main()
