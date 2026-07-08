#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.paths import USER_DATA
from sbc_core.user_data_backup import create_backup, inspect_backup, import_backup

test_dir = USER_DATA / "cache"
test_dir.mkdir(parents=True, exist_ok=True)
backup_path = test_dir / f"sbc_selftest_backup_{int(time.time())}.zip"

export_result = create_backup(backup_path)
inspect_result = inspect_backup(backup_path)
dry_import_result = import_backup(backup_path, dry_run=True, make_preimport_backup=False)

passed = (
    export_result.get("ok")
    and inspect_result.get("ok")
    and dry_import_result.get("ok")
    and Path(export_result.get("backup_path", "")).exists()
)

try:
    backup_path.unlink()
except Exception:
    pass

report = {
    "tool": "sbc_user_data_backup_check",
    "export_result": {
        "ok": export_result.get("ok"),
        "backup_path": export_result.get("backup_path"),
        "item_count": export_result.get("item_count"),
    },
    "inspect_ok": inspect_result.get("ok"),
    "dry_import_ok": dry_import_result.get("ok"),
    "dry_import_copied_count": dry_import_result.get("copied_count"),
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
