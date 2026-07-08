#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.user_data_backup import create_backup, inspect_backup, import_backup
from sbc_core.paths import USER_DATA

stamp = int(time.time())
template_dir = APP_ROOT / "adapter_templates"
adapter_dir = APP_ROOT / "adapters"
template_dir.mkdir(exist_ok=True)
adapter_dir.mkdir(exist_ok=True)

template_path = template_dir / f"selftest_persist_template_{stamp}.json"
adapter_path = adapter_dir / f"selftest_persist_adapter_{stamp}.json"
template_path.write_text(json.dumps({"app_id": f"selftest_persist_template_{stamp}", "display_name": "Persist Template"}, indent=2), encoding="utf-8")
adapter_path.write_text(json.dumps({"app_id": f"selftest_persist_adapter_{stamp}", "display_name": "Persist Adapter"}, indent=2), encoding="utf-8")

backup_path = USER_DATA / "cache" / f"sbc_adapter_persist_backup_{stamp}.zip"
backup_path.parent.mkdir(parents=True, exist_ok=True)

try:
    export_result = create_backup(backup_path)
    inspect_result = inspect_backup(backup_path)
    dry_result = import_backup(backup_path, dry_run=True, make_preimport_backup=False)
    items = set(inspect_result.get("items", []))
    expected_template = f"adapter_templates/{template_path.name}"
    expected_adapter = f"adapters/{adapter_path.name}"
    passed = (
        export_result.get("ok")
        and inspect_result.get("ok")
        and dry_result.get("ok")
        and expected_template in items
        and expected_adapter in items
        and "adapters/g502v.json" not in items
        and "adapters/soundcard.json" not in items
    )
finally:
    for p in (template_path, adapter_path, backup_path):
        try:
            p.unlink()
        except FileNotFoundError:
            pass

report = {
    "tool": "sbc_backup_adapter_persistence_check",
    "expected_template": expected_template,
    "expected_adapter": expected_adapter,
    "item_count": inspect_result.get("item_count"),
    "has_expected_template": expected_template in items,
    "has_expected_adapter": expected_adapter in items,
    "core_adapters_excluded": "adapters/g502v.json" not in items and "adapters/soundcard.json" not in items,
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
