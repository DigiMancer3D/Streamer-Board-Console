#!/usr/bin/env bash
set -euo pipefail

PATTERN='streamer_board_console\.py|pin_board_instance\.py|soundcard\.py|g502viz\.py'

echo "== Streamer Board & Console process doctor =="
echo
echo "Tracked SBC-related Python app processes:"
pgrep -a -f "$PATTERN" || true
echo
echo "This pattern only matches actual runtime script names, not folders like 'g502 vis' or editor windows."
echo
echo "Tip: 'ps aux | grep python' always shows the grep command itself as a temporary process."
echo "Use this instead:"
echo "  pgrep -a -f '$PATTERN'"
