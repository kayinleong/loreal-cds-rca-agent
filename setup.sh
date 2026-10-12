#!/bin/sh
# One-command setup for the RCA Copilot agents (macOS/Linux). Finds a suitable Python, then runs scripts/bootstrap.py.
set -eu
cd "$(dirname "$0")"

PROBE='import sys,struct; sys.exit(0 if sys.version_info>=(3,10) and struct.calcsize("P")==8 else 1)'
PY=""
for cand in python3.12 python3.11 python3.13 python3.10 python3.14 python3 python \
    /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 "$HOME/.local/bin/python3.12" \
    /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 "$HOME/.local/bin/python3.11" \
    /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "$PROBE" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
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
