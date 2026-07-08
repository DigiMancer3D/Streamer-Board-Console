#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Missing .venv. Run ./install_kubuntu.sh first."
  exit 1
fi

source .venv/bin/activate
exec python3 streamer_board_console.py
