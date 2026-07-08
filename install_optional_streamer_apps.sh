#!/usr/bin/env bash
set -euo pipefail

# install_optional_streamer_apps.sh
# Clone/update optional companion apps for Streamer Board & Console.
# Edit the INSTALL_* values if you only want specific apps.

BASE_DIR="${BASE_DIR:-$HOME/SBC_Streamer_Apps}"
SBC_ROOT="${SBC_ROOT:-$(pwd)}"
EMOJI_FILE="${EMOJI_FILE:-$SBC_ROOT/user_data/current.emoji}"

INSTALL_SOUNDCARD="${INSTALL_SOUNDCARD:-1}"
INSTALL_G502V="${INSTALL_G502V:-1}"
INSTALL_BITNINJA="${INSTALL_BITNINJA:-1}"
INSTALL_DECK_CARD_WIDGET="${INSTALL_DECK_CARD_WIDGET:-1}"
INSTALL_SWAR="${INSTALL_SWAR:-1}"

REPO_OWNER="DigiMancer3D"

clone_or_update() {
  local name="$1"
  local url="$2"
  local dest="$BASE_DIR/$name"

  if [ -d "$dest/.git" ]; then
    echo "== Updating $name =="
    git -C "$dest" pull --ff-only || {
      echo "WARN: git pull failed for $name. Keeping existing local copy."
      return 0
    }
  elif [ -e "$dest" ]; then
    echo "WARN: $dest exists but is not a git repo. Skipping clone."
  else
    echo "== Cloning $name =="
    git clone "$url" "$dest"
  fi
}

copy_emoji() {
  local dest="$1"
  [ -f "$EMOJI_FILE" ] || return 0
  [ -d "$dest" ] || return 0
  cp -f "$EMOJI_FILE" "$dest/current.emoji" || true
}

if ! command -v git >/dev/null 2>&1; then
  echo "git is required. On Kubuntu/Ubuntu, install it with:"
  echo "  sudo apt update && sudo apt install -y git"
  exit 1
fi

mkdir -p "$BASE_DIR"

[ "$INSTALL_SOUNDCARD" = "1" ] && clone_or_update "soundcard" "https://github.com/${REPO_OWNER}/soundcard.git"
[ "$INSTALL_G502V" = "1" ] && clone_or_update "G502V" "https://github.com/${REPO_OWNER}/G502V.git"
[ "$INSTALL_BITNINJA" = "1" ] && clone_or_update "Bitninja-Mocap-Lite" "https://github.com/${REPO_OWNER}/Bitninja-Mocap-Lite.git"
[ "$INSTALL_DECK_CARD_WIDGET" = "1" ] && clone_or_update "Deck-Card-Widget" "https://github.com/${REPO_OWNER}/Deck-Card-Widget.git"
[ "$INSTALL_SWAR" = "1" ] && clone_or_update "3DChangesPerspectives" "https://github.com/${REPO_OWNER}/3DChangesPerspectives.git"

copy_emoji "$BASE_DIR/soundcard"
copy_emoji "$BASE_DIR/G502V"
copy_emoji "$BASE_DIR/Bitninja-Mocap-Lite"
copy_emoji "$BASE_DIR/Deck-Card-Widget"
copy_emoji "$BASE_DIR/Deck-Card-Widget/program"
copy_emoji "$BASE_DIR/3DChangesPerspectives"
copy_emoji "$BASE_DIR/3DChangesPerspectives/SWAR"

cat <<EOF

Done.

Next steps:
1. Launch Streamer Board & Console.
2. Open Apps -> Adapter Templates.
3. Update paths/entries as needed.

Suggested public clone paths:
  Soundcard:             $BASE_DIR/soundcard
  G502V:                 $BASE_DIR/G502V
  Bitninja Mocap Lite:   $BASE_DIR/Bitninja-Mocap-Lite
  Deck Card Widget:      $BASE_DIR/Deck-Card-Widget
  SWAR:                  $BASE_DIR/3DChangesPerspectives/SWAR

The shared emoji file was copied when possible from:
  $EMOJI_FILE
EOF
