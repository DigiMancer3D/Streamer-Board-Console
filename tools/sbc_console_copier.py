#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.console_copier import (
    cleanup_selftest_and_broken_copies,
    create_console_copy,
    launch_console_copy,
    list_console_files,
    read_console_file,
)

def main() -> int:
    ap = argparse.ArgumentParser(description="Streamer Board & Console copier / instance manager")
    ap.add_argument("--list", action="store_true", help="List .sbconsole console-copy files")
    ap.add_argument("--create", metavar="NAME", help="Create a new console copy from current data")
    ap.add_argument("--blank", action="store_true", help="When creating, do not clone current data")
    ap.add_argument("--inspect", metavar="FILE_OR_ID", help="Inspect a .sbconsole file or console id")
    ap.add_argument("--launch", metavar="FILE_OR_ID", help="Launch a .sbconsole copy")
    ap.add_argument("--cleanup-selftests", action="store_true", help="Remove selftest/broken packaged console-copy rows")
    args = ap.parse_args()

    if args.cleanup_selftests:
        out = {"tool": "sbc_console_copier", "cleanup_result": cleanup_selftest_and_broken_copies()}
    elif args.create:
        out = {"tool": "sbc_console_copier", "create_result": create_console_copy(args.create, clone_current=not args.blank)}
    elif args.inspect:
        out = {"tool": "sbc_console_copier", "inspect_result": read_console_file(args.inspect)}
    elif args.launch:
        out = {"tool": "sbc_console_copier", "launch_result": launch_console_copy(args.launch)}
    else:
        out = {"tool": "sbc_console_copier", "list_result": list_console_files()}

    print(json.dumps(out, indent=2, sort_keys=True))
    ok = True
    for key, value in out.items():
        if key.endswith("_result") and isinstance(value, dict):
            ok = bool(value.get("ok", True))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
