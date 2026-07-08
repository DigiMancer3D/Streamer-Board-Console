#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

APP_DIR="${1:-$HOME/sound card}"

echo "== Soundcard adapter safe cycle =="
echo "App dir: $APP_DIR"
echo

echo "[1/5] Current compile check"
if ./tools/repair_soundcard_adapter.py --app-dir "$APP_DIR" --compile-only; then
  echo "Current source compiles."
else
  echo "Current source does not compile. Restoring latest backup..."
  ./tools/repair_soundcard_adapter.py --app-dir "$APP_DIR" --restore-latest
fi

echo
echo "[2/5] Dry-run safer patch"
./tools/patch_soundcard_adapter.py --app-dir "$APP_DIR"

echo
echo "[3/5] Apply safer patch"
./tools/patch_soundcard_adapter.py --app-dir "$APP_DIR" --apply

echo
echo "[4/5] Compile after patch"
./tools/repair_soundcard_adapter.py --app-dir "$APP_DIR" --compile-only

echo
echo "[5/5] Inspect after patch"
./tools/inspect_soundcard_adapter.py --app-dir "$APP_DIR" > soundcard_inspection.json
echo "Wrote: soundcard_inspection.json"
echo
echo "Soundcard adapter safe cycle complete."
