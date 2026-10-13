#!/usr/bin/env bash
# start.sh — one-command launcher for Grabio (macOS & Linux)
# Usage: ./start.sh [port]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV=".venv"
PORT="${1:-5000}"

# ── 1. Find Python 3.9+ ────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c 'import sys; print(sys.version_info >= (3,9))' 2>/dev/null || true)
    if [[ "$ver" == "True" ]]; then
      PYTHON="$cmd"; break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "❌  Python 3.9 or newer is required."
  echo "    macOS:  brew install python  or  https://python.org"
  echo "    Linux:  sudo apt install python3  (or your distro's equivalent)"
  exit 1
fi
echo "✓  $($PYTHON --version)"

# ── 2. Create / reuse venv ─────────────────────────────────────────────────
if [[ ! -f "$VENV/bin/python" ]]; then
  echo "→  Creating virtual environment…"
  "$PYTHON" -m venv "$VENV"
fi

# Prefer uv for speed; fall back to pip inside the venv
if command -v uv &>/dev/null; then
  echo "→  Installing / updating packages (uv)…"
  uv pip install --quiet -r requirements.txt
else
  echo "→  Installing / updating packages (pip)…"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r requirements.txt
fi
echo "✓  Packages ready"

# ── 3. Open browser after server is up ────────────────────────────────────
(
  for _ in $(seq 1 40); do
    sleep 0.5
    if curl -sf "http://127.0.0.1:$PORT" &>/dev/null; then
      if command -v open &>/dev/null; then        # macOS
        open "http://127.0.0.1:$PORT"
      elif command -v xdg-open &>/dev/null; then  # Linux (X11/Wayland)
        xdg-open "http://127.0.0.1:$PORT"
      fi
      break
    fi
  done
) &

# ── 4. Launch ──────────────────────────────────────────────────────────────
echo ""
echo "  Grabio → http://127.0.0.1:$PORT"
echo "  Press Ctrl-C to quit"
echo ""
exec "$VENV/bin/python" app.py
