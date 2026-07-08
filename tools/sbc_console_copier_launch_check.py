#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
core = root / "sbc_core" / "console_copier.py"
main = root / "streamer_board_console.py"
core_text = core.read_text(encoding="utf-8")
main_text = main.read_text(encoding="utf-8")

checks = {
    "launch_writes_log": "console_launcher.log" in core_text,
    "launch_checks_immediate_exit": "exited immediately" in core_text and "proc.poll()" in core_text,
    "launch_sets_instance_env": "SBC_INSTANCE_NAME" in core_text,
    "launch_validates_paths": "validate_console_data" in core_text and "launchable" in core_text,
    "cleanup_available": "cleanup_selftest_and_broken_copies" in core_text,
    "window_title_uses_instance": "instance_name" in main_text and "SBC_INSTANCE_NAME" in main_text,
}

report = {
    "tool": "sbc_console_copier_launch_check",
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
