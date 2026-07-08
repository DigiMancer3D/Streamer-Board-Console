#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
prev = root / "sbc_core" / "previous_build_migrate.py"
text = prev.read_text(encoding="utf-8")

checks = {
    "skips_console_copies_in_generic_iter": 'if dirname == "console_copies":' in text,
    "has_console_copy_special_migration": "_migrate_console_copies" in text,
    "skips_selftest_copies": "selftest_console_copy" in text,
    "skips_packaged_mnt_paths": "invalid_packaged_path" in text,
    "rewrites_app_root": 'data["app_root"] = str(APP_ROOT)' in text,
    "rewrites_data_root": 'data["data_root"] = str(new_data_root)' in text,
    "copies_instance_root": "_safe_copy_tree(old_console_root, new_console_root" in text,
    "reports_console_copy_migration": "console_copy_migration" in text,
}

report = {
    "tool": "sbc_previous_build_console_copy_migrate_check",
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
