#!/usr/bin/env bash
set -euo pipefail

echo "This will kill only user-level SBC-related app processes matching:"
echo "  streamer_board_console.py, pin_board_instance.py, soundcard.py, g502viz.py"
echo
read -r -p "Proceed? [y/N] " ans
case "$ans" in
  y|Y|yes|YES)
    pkill -u "$USER" -f 'streamer_board_console.py|pin_board_instance.py|soundcard.py|g502viz.py' || true
    echo "Kill request sent."
    ;;
  *)
    echo "Cancelled."
    ;;
esac
