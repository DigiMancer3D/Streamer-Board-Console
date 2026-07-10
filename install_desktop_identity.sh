#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/install_desktop_identity.py \
  --desktop-id streamer-board-console \
  --wrapper-name streamer-board-console \
  --name "Streamer Board & Console" \
  --comment "Launch Streamer Board & Console" \
  --exec "./launch_streamer_board_console.sh" \
  --wm-class Streamerboardconsole \
  --icon-name digimancer-sbc-pin \
  --text-icon-line1 SBC \
  --text-icon-line2 PIN \
  --text-icon-bg '#10351f' \
  --text-icon-fg '#00ff75' \
  --tk-class Streamerboardconsole
