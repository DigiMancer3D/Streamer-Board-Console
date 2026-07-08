#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "== SBC public release verify =="
python3 -m py_compile streamer_board_console.py pin_board_instance.py sbc_core/*.py tools/*.py patches/sbc_app_bridge.py
./tools/sbc_runtime_import_check.py >/tmp/sbc_release_runtime_import_check.json
./tools/sbc_gui_smoke_check.py >/tmp/sbc_release_gui_smoke_check.json
echo "PASS: public release verify"
