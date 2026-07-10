#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Run ./install_kubuntu.sh first." >&2
  exit 1
fi

source .venv/bin/activate

slot=""
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "--slot" && $((i+1)) -lt ${#args[@]} ]]; then
    slot="${args[$((i+1))]}"
    break
  fi
done

if [[ -z "$slot" ]]; then
  slot="$(python3 -c 'from sbc_core.board_registry import allocate_board_slot; print(allocate_board_slot())')"
  args+=(--slot "$slot")
fi

IDENTITY_BASE="${XDG_DATA_HOME:-$HOME/.local/share}/digimancer_desktop_identity_py"
if [[ -d "$IDENTITY_BASE" ]]; then
  export DIGIMANCER_TK_CLASS="$(python3 -c 'import sys; from sbc_core.board_registry import window_class_for_slot; print(window_class_for_slot(int(sys.argv[1])))' "$slot")"
  export PYTHONPATH="$IDENTITY_BASE${PYTHONPATH:+:$PYTHONPATH}"
fi

export SBC_PIN_BOARD_SLOT="$slot"
exec python3 pin_board_instance.py "${args[@]}"
