#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.console_copier import create_console_copy, read_console_file, list_console_files, cleanup_selftest_and_broken_copies
import sbc_core.paths as paths

name = f"Selftest Console Copy {int(time.time())}"
created = create_console_copy(name, clone_current=True)
inspected = read_console_file(created.get("console_id", "")) if created.get("ok") else {"ok": False}
listed = list_console_files()

console = inspected.get("console", {})
exists = inspected.get("exists", {})
validation = inspected.get("validation", {})

checks = {
    "create_ok": bool(created.get("ok")),
    "file_extension_ok": str(created.get("console_file", "")).endswith(".sbconsole"),
    "filename_is_epoch_hex": created.get("console_id", "").isalnum() and created.get("console_id", "") == console.get("created_epoch_hex", ""),
    "inspect_ok": bool(inspected.get("ok")),
    "data_root_exists": bool(exists.get("data_root")),
    "adapter_dir_exists": bool(exists.get("adapter_dir")),
    "template_dir_exists": bool(exists.get("template_dir")),
    "launch_validation_result_present": "launchable" in validation,
    "list_ok": bool(listed.get("ok")),
    "env_paths_supported": all(hasattr(paths, name) for name in ["USER_DATA", "ADAPTER_DIR", "TEMPLATE_DIR", "SBC_CONSOLE_FILE"]),
}

cleanup = cleanup_selftest_and_broken_copies()

report = {
    "tool": "sbc_console_copier_check",
    "checks": checks,
    "created_console_file": created.get("console_file", ""),
    "created_console_id": created.get("console_id", ""),
    "cleanup": cleanup,
    "listed_count_before_cleanup": listed.get("count", 0),
    "passed": all(checks.values()) and bool(cleanup.get("ok")),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
