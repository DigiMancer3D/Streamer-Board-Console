#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

APP_DIR="${1:-$HOME/g502 vis}"

echo "== G502V yaw direction safe cycle =="
echo "App dir: $APP_DIR"
echo

echo "[1/5] Current compile check"
./tools/repair_g502v_adapter.py --app-dir "$APP_DIR" --compile-only

echo
echo "[2/5] Dry-run yaw direction patch"
./tools/patch_g502v_yaw_direction.py --app-dir "$APP_DIR"

echo
echo "[3/5] Apply yaw direction patch"
./tools/patch_g502v_yaw_direction.py --app-dir "$APP_DIR" --apply

echo
echo "[4/5] Compile after yaw patch"
./tools/repair_g502v_adapter.py --app-dir "$APP_DIR" --compile-only

echo
echo "[5/5] Inspect after yaw patch"
./tools/inspect_g502v_adapter.py --app-dir "$APP_DIR" > g502v_inspection_after_yaw_patch.json
echo "Wrote: g502v_inspection_after_yaw_patch.json"
echo
echo "G502V yaw direction safe cycle complete."
