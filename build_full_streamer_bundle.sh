#!/usr/bin/env bash
set -euo pipefail

# build_full_streamer_bundle.sh
# Build a sanitized full bundle that includes Streamer Board & Console plus local companion app copies.
# This is intended for preparing a curated zip. It excludes common private/runtime folders.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${VERSION:-v0_4_5}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_BASE="${OUT_BASE:-$ROOT/export}"
BUNDLE_DIR="$OUT_BASE/Streamer_Board_Console_FULL_BUNDLE_${VERSION}_${STAMP}"
ZIP_PATH="$OUT_BASE/Streamer_Board_Console_FULL_BUNDLE_${VERSION}_${STAMP}.zip"

# Local app source defaults. Override any of these with environment variables before running.
BITNINJA_PATH="${BITNINJA_PATH:-$HOME/BitninjaMocapLite_dev_export/BitninjaMocapLite_extended_service_update_sources_20260704_102145}"
BITNINJA_ENTRY="${BITNINJA_ENTRY:-run_bitninja_lite_nvidia_desktopgl.sh}"

DECK_CARD_PATH="${DECK_CARD_PATH:-$HOME/Deck_Card_Widget/program}"
DECK_CARD_ENTRY="${DECK_CARD_ENTRY:-launch_deck_card_widget_venv.sh}"

G502V_PATH="${G502V_PATH:-$HOME/g502 vis}"
G502V_ENTRY="${G502V_ENTRY:-g502viz.py}"

SOUNDCARD_PATH="${SOUNDCARD_PATH:-$HOME/sound card}"
SOUNDCARD_ENTRY="${SOUNDCARD_ENTRY:-soundcard.py}"

SWAR_PATH="${SWAR_PATH:-$HOME/SWAR/SWAR_v0_6_0_RC1_R2}"
SWAR_READER_ENTRY="${SWAR_READER_ENTRY:-launch_reader.sh}"
SWAR_STANDARD_ENTRY="${SWAR_STANDARD_ENTRY:-launch_standard.sh}"

EMOJI_FILE="${EMOJI_FILE:-$ROOT/user_data/current.emoji}"

copy_clean_dir() {
  local src="$1"
  local dst="$2"
  if [ ! -d "$src" ]; then
    echo "WARN: missing source folder, skipping: $src"
    return 0
  fi

  mkdir -p "$dst"
  (cd "$src" && tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='logs' \
    --exclude='cache' \
    --exclude='web_cache' \
    --exclude='backups' \
    --exclude='board_instances' \
    --exclude='console_copies' \
    --exclude='console_instances' \
    --exclude='export' \
    --exclude='*.zip' \
    --exclude='*.tar.gz' \
    -cf - .) | (cd "$dst" && tar -xf -)

  find "$dst" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  find "$dst" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
}

copy_emoji() {
  local dst="$1"
  [ -f "$EMOJI_FILE" ] || return 0
  [ -d "$dst" ] || return 0
  cp -f "$EMOJI_FILE" "$dst/current.emoji" || true
}

mkdir -p "$OUT_BASE"
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/external_apps"

echo "== Copying Streamer Board & Console =="
copy_clean_dir "$ROOT" "$BUNDLE_DIR/Streamer_Board_Console"

echo "== Copying optional companion apps =="
copy_clean_dir "$BITNINJA_PATH" "$BUNDLE_DIR/external_apps/bitninja_mocap"
copy_clean_dir "$DECK_CARD_PATH" "$BUNDLE_DIR/external_apps/deck_card_widget"
copy_clean_dir "$G502V_PATH" "$BUNDLE_DIR/external_apps/g502v"
copy_clean_dir "$SOUNDCARD_PATH" "$BUNDLE_DIR/external_apps/soundcard"
copy_clean_dir "$SWAR_PATH" "$BUNDLE_DIR/external_apps/swar"

copy_emoji "$BUNDLE_DIR/Streamer_Board_Console/user_data"
copy_emoji "$BUNDLE_DIR/external_apps/bitninja_mocap"
copy_emoji "$BUNDLE_DIR/external_apps/deck_card_widget"
copy_emoji "$BUNDLE_DIR/external_apps/g502v"
copy_emoji "$BUNDLE_DIR/external_apps/soundcard"
copy_emoji "$BUNDLE_DIR/external_apps/swar"

cat > "$BUNDLE_DIR/install_full_bundle_kubuntu.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SBC="$BUNDLE_ROOT/Streamer_Board_Console"

python3 - <<PY
import json
from pathlib import Path

root = Path("$BUNDLE_ROOT")
sbc = Path("$SBC")

mapping = {
    "bitninja_mocap": (root / "external_apps" / "bitninja_mocap", "run_bitninja_lite_nvidia_desktopgl.sh"),
    "deck_card_widget": (root / "external_apps" / "deck_card_widget", "launch_deck_card_widget_venv.sh"),
    "g502v": (root / "external_apps" / "g502v", "g502viz.py"),
    "soundcard": (root / "external_apps" / "soundcard", "soundcard.py"),
    "swar": (root / "external_apps" / "swar", "launch_reader.sh"),
    "swar_v0_6_0_rc1_r2": (root / "external_apps" / "swar", "launch_standard.sh"),
}

for folder_name in ("adapters", "adapter_templates"):
    folder = sbc / folder_name
    if not folder.exists():
        continue
    for app_id, (path, entry) in mapping.items():
        file = folder / f"{app_id}.json"
        if not file.exists():
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        data["default_path"] = str(path)
        data["entry_file"] = entry
        file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

cd "$SBC"
chmod +x install_kubuntu.sh launch_streamer_board_console.sh launch_streamer_board_console_rescue.sh tools/*.sh tools/*.py 2>/dev/null || true
./install_kubuntu.sh

cat <<EOF

Bundle setup complete.

Launch with:
  cd "$SBC"
  ./launch_streamer_board_console.sh

The adapter JSON files were patched to point at this bundle's external_apps folder.
EOF
EOS
chmod +x "$BUNDLE_DIR/install_full_bundle_kubuntu.sh"

cat > "$BUNDLE_DIR/BUNDLE_README.md" <<EOF
# Streamer Board & Console Full Bundle

This bundle contains Streamer Board & Console plus sanitized local copies of companion app folders.

Run:

\`\`\`bash
chmod +x install_full_bundle_kubuntu.sh
./install_full_bundle_kubuntu.sh
\`\`\`

Then launch:

\`\`\`bash
cd Streamer_Board_Console
./launch_streamer_board_console.sh
\`\`\`

The install script patches adapter paths to the local \`external_apps/\` folders inside this bundle.
EOF

cat > "$BUNDLE_DIR/FULL_BUNDLE_MANIFEST.json" <<EOF
{
  "format": "SBC_FULL_BUNDLE_V1",
  "version": "$VERSION",
  "created_at_text": "$(date '+%Y-%m-%d %H:%M:%S')",
  "included_external_apps": {
    "bitninja_mocap": "$BITNINJA_PATH",
    "deck_card_widget": "$DECK_CARD_PATH",
    "g502v": "$G502V_PATH",
    "soundcard": "$SOUNDCARD_PATH",
    "swar": "$SWAR_PATH"
  },
  "privacy_note": "Common runtime/private folders were excluded: .git, .venv, venv, node_modules, logs, cache, backups, console instances, board instances, export, zip/tar artifacts."
}
EOF

if command -v zip >/dev/null 2>&1; then
  (cd "$OUT_BASE" && zip -qr "$(basename "$ZIP_PATH")" "$(basename "$BUNDLE_DIR")")
  echo "Created zip: $ZIP_PATH"
else
  echo "zip command not found. Folder created at: $BUNDLE_DIR"
  echo "Install zip with: sudo apt install -y zip"
fi

echo "Bundle folder: $BUNDLE_DIR"
