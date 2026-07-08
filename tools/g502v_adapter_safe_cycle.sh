#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

APP_DIR="${1:-$HOME/g502 vis}"

echo "== G502V adapter safe cycle =="
echo "App dir: $APP_DIR"
echo

echo "[1/6] Current compile check"
if ./tools/repair_g502v_adapter.py --app-dir "$APP_DIR" --compile-only; then
  echo "Current source compiles."
else
  echo "Current source does not compile. Restoring latest backup..."
  ./tools/repair_g502v_adapter.py --app-dir "$APP_DIR" --restore-latest
fi

echo
echo "[2/6] Inspect before patch"
./tools/inspect_g502v_adapter.py --app-dir "$APP_DIR" > g502v_inspection_before_patch.json
echo "Wrote: g502v_inspection_before_patch.json"

echo
echo "[3/6] Dry-run G502V patch"
./tools/patch_g502v_adapter.py --app-dir "$APP_DIR"

echo
echo "[4/6] Apply G502V patch"
./tools/patch_g502v_adapter.py --app-dir "$APP_DIR" --apply

echo
echo "[5/6] Compile after patch"
./tools/repair_g502v_adapter.py --app-dir "$APP_DIR" --compile-only

echo
echo "[6/6] Adapter doctor"
./tools/sbc_adapter_doctor.py

echo
echo "G502V adapter safe cycle complete."
