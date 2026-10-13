#!/usr/bin/env bash
# start.sh — one-command launcher for YT Grab
# Creates the venv, installs deps, starts the server, opens the browser.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV=".venv"
PORT=5000

# ── 1. Find Python 3.9+ ─────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python3.12 python3.11 python3.10 python3.9; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c 'import sys; print(sys.version_info >= (3,9))' 2>/dev/null)
    if [[ "$ver" == "True" ]]; then
      PYTHON="$cmd"; break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "❌  Python 3.9 or newer is required. Install it from https://python.org" >&2
  exit 1
fi
echo "✓  Python: $($PYTHON --version)"

# ── 2. Create / reuse venv ──────────────────────────────────────────────────
if [[ ! -f "$VENV/bin/python" && ! -f "$VENV/Scripts/python.exe" ]]; then
  echo "→  Creating virtual environment…"
  "$PYTHON" -m venv "$VENV"
fi

# Use uv for speed if available, otherwise fall back to pip
if command -v uv &>/dev/null; then
  echo "→  Installing / updating packages (uv)…"
  uv pip install --quiet -r requirements.txt
else
  PIP="$VENV/bin/pip"
  [[ -f "$VENV/Scripts/pip" ]] && PIP="$VENV/Scripts/pip"
  echo "→  Installing / updating packages (pip)…"
  "$PIP" install --quiet --upgrade pip
  "$PIP" install --quiet -r requirements.txt
fi
echo "✓  Packages ready"

# ── 3. Wait for server to be ready, then open browser ───────────────────────
PYTHON_VENV="$VENV/bin/python"
[[ -f "$VENV/Scripts/python.exe" ]] && PYTHON_VENV="$VENV/Scripts/python.exe"

(
  for i in $(seq 1 30); do
    sleep 0.5
    if curl -sf "http://127.0.0.1:$PORT" &>/dev/null; then
      # macOS
      if command -v open &>/dev/null; then open "http://127.0.0.1:$PORT"; fi
      # Linux
      if command -v xdg-open &>/dev/null; then xdg-open "http://127.0.0.1:$PORT"; fi
      break
    fi
  done
) &

# ── 4. Start the server (blocking) ──────────────────────────────────────────
echo "✓  Starting YT Grab at http://127.0.0.1:$PORT  (Ctrl-C to quit)"
echo ""
exec "$PYTHON_VENV" app.py
