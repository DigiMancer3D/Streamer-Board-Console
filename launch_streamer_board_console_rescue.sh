#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export SBC_FORCE_WINDOW_RESCUE=1
export SBC_ALWAYS_CENTER_WINDOW=1
export SBC_WINDOW_GEOMETRY="${SBC_WINDOW_GEOMETRY:-1180x760+80+80}"
exec ./launch_streamer_board_console.sh
