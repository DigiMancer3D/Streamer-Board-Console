#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

APP_DIR="$(pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/streamer-board-console.desktop"

mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Streamer Board & Console
Comment=Local streamer settings console and OBS pin board
Exec=$APP_DIR/launch_streamer_board_console.sh
Path=$APP_DIR
Terminal=false
Categories=AudioVideo;Utility;
EOF

chmod +x "$DESKTOP_FILE"
echo "Installed desktop entry:"
echo "  $DESKTOP_FILE"
