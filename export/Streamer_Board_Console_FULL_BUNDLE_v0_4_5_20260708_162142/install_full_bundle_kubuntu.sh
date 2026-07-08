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
