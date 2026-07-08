#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cli = root / "tools" / "sbc_console_copier.py"

help_run = subprocess.run([sys.executable, str(cli), "--help"], cwd=str(root), text=True, capture_output=True)
cleanup_run = subprocess.run([sys.executable, str(cli), "--cleanup-selftests"], cwd=str(root), text=True, capture_output=True)

checks = {
    "help_ok": help_run.returncode == 0,
    "cleanup_arg_in_help": "--cleanup-selftests" in help_run.stdout,
    "cleanup_command_ok": cleanup_run.returncode == 0,
    "cleanup_result_printed": "cleanup_result" in cleanup_run.stdout,
}

report = {
    "tool": "sbc_console_copier_cli_check",
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
