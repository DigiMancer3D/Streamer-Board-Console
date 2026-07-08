#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

APP="${1:-}"
LINES="${2:-80}"

if [ -z "$APP" ]; then
  echo "Usage: ./tools/sbc_tail_logs.sh <soundcard|g502v> [lines]"
  echo
  echo "Available logs:"
  ls -1 user_data/logs/*.log 2>/dev/null || true
  exit 1
fi

LOG="user_data/logs/${APP}.log"
if [ ! -f "$LOG" ]; then
  echo "No log found: $LOG"
  exit 1
fi

echo "== Tail: $LOG =="
tail -n "$LINES" "$LOG"
