#!/usr/bin/env bash
set -euo pipefail

# Streamer Board & Console desktop launcher installer.
# Run this from the project folder:
#   chmod +x install_desktop_entry.sh
#   ./install_desktop_entry.sh

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Streamer Board & Console"
APP_ID="streamer-board-console"

DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/${APP_ID}.desktop"

BIN_DIR="$HOME/.local/bin"
BIN_FILE="$BIN_DIR/${APP_ID}"

ICON_SRC="$APP_DIR/icon.png"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/${APP_ID}.png"

mkdir -p "$DESKTOP_DIR" "$BIN_DIR"

chmod +x "$APP_DIR/launch_streamer_board_console.sh" 2>/dev/null || true
chmod +x "$APP_DIR/launch_streamer_board_console_rescue.sh" 2>/dev/null || true
chmod +x "$APP_DIR/launch_pin_board.sh" 2>/dev/null || true

# Create a stable wrapper so the .desktop Exec line works even if APP_DIR contains spaces.
APP_DIR_Q="$(printf '%q' "$APP_DIR")"
cat > "$BIN_FILE" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd $APP_DIR_Q
exec ./launch_streamer_board_console.sh "\$@"
EOF
chmod +x "$BIN_FILE"

ICON_LINE=""
if [ -f "$ICON_SRC" ]; then
  mkdir -p "$ICON_DIR"
  cp -f "$ICON_SRC" "$ICON_FILE"
  chmod 644 "$ICON_FILE"
  ICON_LINE="Icon=$ICON_FILE"
else
  echo "Warning: icon.png not found at:"
  echo "  $ICON_SRC"
  echo "The launcher will still work, but it will use the system default app icon."
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_NAME
Comment=Local streamer settings console and OBS pin board
Exec=$BIN_FILE
Path=$APP_DIR
Terminal=false
Categories=AudioVideo;Utility;
StartupNotify=true
StartupWMClass=Streamer Board & Console
$ICON_LINE
EOF

chmod 644 "$DESKTOP_FILE"

# Refresh desktop/icon caches when available. These are optional.
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
  kbuildsycoca5 >/dev/null 2>&1 || true
fi

echo "Installed desktop launcher:"
echo "  $DESKTOP_FILE"
echo
echo "Installed command wrapper:"
echo "  $BIN_FILE"
echo
if [ -f "$ICON_FILE" ]; then
  echo "Installed icon:"
  echo "  $ICON_FILE"
fi
echo
echo "Next steps:"
echo "  1. Open your application launcher and search: Streamer Board & Console"
echo "  2. Right-click it and choose Add to Panel / Pin to Task Manager if desired."
echo "  3. If it does not appear immediately, log out/in or run: kbuildsycoca6"
