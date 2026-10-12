#!/bin/sh
# One-command setup for the RCA Copilot agents (macOS/Linux). Finds a suitable Python, then runs scripts/bootstrap.py.
set -eu
cd "$(dirname "$0")"

PROBE='import sys,struct; sys.exit(0 if sys.version_info>=(3,10) and struct.calcsize("P")==8 else 1)'
PY=""

have_clt=1
if [ "$(uname -s)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
  have_clt=0
fi

# try_cand <name-or-path>: sets PY and returns 0 if it is a suitable interpreter.
try_cand() {
  resolved=$(command -v "$1" 2>/dev/null || true)
  [ -n "$resolved" ] || return 1
  # Skip the macOS /usr/bin stub when the Command Line Tools are missing (would open an install dialog).
  if [ "$have_clt" = "0" ] && [ "$resolved" = "/usr/bin/python3" ]; then
    return 1
  fi
  if "$resolved" -c "$PROBE" >/dev/null 2>&1; then
    PY="$resolved"
    return 0
  fi
  return 1
}

# Absolute candidates first: probing a bare python3 on a Mac without the Command Line Tools
# pops the xcode-select install dialog, so bare names (and /usr/bin/python3) come last.
for dir in /opt/homebrew/bin /usr/local/bin /Library/Frameworks/Python.framework/Versions/3.12/bin \
    /Library/Frameworks/Python.framework/Versions/3.11/bin /Library/Frameworks/Python.framework/Versions/3.13/bin \
    "$HOME/.local/bin"; do
  for v in 3.12 3.11 3.13 3.10; do
    if [ -z "$PY" ]; then try_cand "$dir/python$v" || true; fi
  done
done
for cand in python3.12 python3.11 python3.13 python3.10 python3.14 python3 python; do
  if [ -z "$PY" ]; then try_cand "$cand" || true; fi
done

if [ -z "$PY" ]; then
  echo "ERROR: no suitable Python found (need 3.10+ 64-bit; 3.12 recommended)." >&2
  echo "Install one of:" >&2
  echo "  - python.org installer: https://www.python.org/downloads/" >&2
  echo "  - Homebrew:             brew install python@3.12" >&2
  if command -v uv >/dev/null 2>&1; then
    echo "  - uv (found):           uv python install 3.12" >&2
  fi
  echo "Then re-run ./setup.sh" >&2
  exit 1
fi

echo "Using Python: $PY"
exec "$PY" scripts/bootstrap.py "$@"
