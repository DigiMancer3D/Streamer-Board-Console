#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Run ./install_kubuntu.sh first." >&2
  exit 1
fi

# Repo-safe desktop identity: the installer creates this helper under the
# current user's XDG data directory. No personal absolute path is stored here.
IDENTITY_BASE="${XDG_DATA_HOME:-$HOME/.local/share}/digimancer_desktop_identity_py"
if [[ -d "$IDENTITY_BASE" ]]; then
  export DIGIMANCER_TK_CLASS="Streamerboardconsole"
  export PYTHONPATH="$IDENTITY_BASE${PYTHONPATH:+:$PYTHONPATH}"
fi

source .venv/bin/activate
exec python3 streamer_board_console.py "$@"
