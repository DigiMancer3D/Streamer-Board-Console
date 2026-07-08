#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Streamer Board & Console selftest =="
echo

PYTHON="${PYTHON:-python3}"
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON="python3"
fi

echo "[1/7] Python compile check"
"$PYTHON" -m py_compile       streamer_board_console.py       pin_board_instance.py       sbc_core/*.py       tools/*.py       patches/sbc_app_bridge.py
echo "PASS: compile"
echo

echo "[2/7] Runtime import check"
./tools/sbc_runtime_import_check.py
echo "PASS: runtime imports"
echo

echo "[3/7] GUI smoke check"
./tools/sbc_gui_smoke_check.py
./tools/sbc_class_method_check.py
./tools/sbc_profile_gui_logic_check.py
./tools/sbc_profile_custom_check.py
./tools/sbc_profile_action_check.py
./tools/sbc_profile_action_strict_check.py
./tools/sbc_profile_dynamic_apps_check.py
./tools/sbc_profile_dynamic_editor_check.py
./tools/sbc_profile_streamlined_editor_check.py
./tools/sbc_profile_tool_dynamic_list_check.py
./tools/sbc_window_rescue_check.py
./tools/sbc_scrollable_tabs_check.py
./tools/sbc_process_scan_check.py
./tools/sbc_adapter_template_check.py
./tools/sbc_startup_profile_check.py
./tools/sbc_user_data_backup_check.py
./tools/sbc_backup_adapter_persistence_check.py
./tools/sbc_previous_build_migrate_check.py
./tools/sbc_console_copier_check.py
./tools/sbc_console_copier_launch_check.py
./tools/sbc_console_copier_cli_check.py
./tools/sbc_previous_build_console_copy_migrate_check.py
./tools/sbc_release_prep_check.py
echo "PASS: GUI smoke/class/profile logic/custom/strict-actions/streamlined-editor/window/scroll/process/adapters/startup/backup-persistence/migrate/console-copier-launch-cli/release-prep check"
echo

echo "[4/7] Process doctor"
./tools/sbc_process_doctor.sh
echo

echo "[5/7] Adapter doctor"
./tools/sbc_adapter_doctor.py >/tmp/sbc_adapter_doctor_selftest.json
cat /tmp/sbc_adapter_doctor_selftest.json
echo
echo "PASS: adapter doctor ran"
echo

echo "[6/7] Studio profile tool"
./tools/sbc_profile_tool.py --init --list >/tmp/sbc_profile_selftest.json
cat /tmp/sbc_profile_selftest.json
echo
echo "PASS: profile tool ran"
echo

echo "[7/7] Package folders"
test -d sbc_core
test -d tools
test -d patches
test -d adapters
test -d user_data/profiles
echo "PASS: package folders present"
echo

echo "SBC selftest complete."
