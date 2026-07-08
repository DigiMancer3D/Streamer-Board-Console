#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "== Streamer Board & Console installer =="
echo "This installs local Python dependencies into this app's own .venv."

if command -v apt >/dev/null 2>&1; then
  echo "Checking Kubuntu/Ubuntu packages..."
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip python3-tk
else
  echo "apt not found. Please install Python3, venv, pip, and Tk for your OS."
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

chmod +x launch_streamer_board_console.sh
chmod +x launch_pin_board.sh
chmod +x install_desktop_entry.sh
chmod +x tools/*.sh tools/*.py 2>/dev/null || true

echo
echo "Install complete."
echo "Run with:"
echo "  ./launch_streamer_board_console.sh"
