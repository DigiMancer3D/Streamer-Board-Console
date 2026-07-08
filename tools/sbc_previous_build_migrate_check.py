#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.paths import USER_DATA
from sbc_core.previous_build_migrate import migrate_from_build

stamp = int(time.time())
src = USER_DATA / "cache" / f"Fake_Previous_SBC_{stamp}"
(src / "user_data" / "profiles").mkdir(parents=True, exist_ok=True)
(src / "adapter_templates").mkdir(parents=True, exist_ok=True)
(src / "adapters").mkdir(parents=True, exist_ok=True)

(src / "user_data" / "profiles" / "carry_forward_test.json").write_text('{"name":"Carry Forward Test"}', encoding="utf-8")
(src / "adapter_templates" / "carry_forward_template.json").write_text('{"app_id":"carry_forward_template"}', encoding="utf-8")
(src / "adapters" / "carry_forward_adapter.json").write_text('{"app_id":"carry_forward_adapter"}', encoding="utf-8")
(src / "adapters" / "g502v.json").write_text('{"app_id":"bad_core_overwrite"}', encoding="utf-8")

result = migrate_from_build(src, dry_run=True)
copied = set(result.get("copied", []))
passed = (
    result.get("ok")
    and "profiles/carry_forward_test.json" in copied
    and "adapter_templates/carry_forward_template.json" in copied
    and "adapters/carry_forward_adapter.json" in copied
    and "adapters/g502v.json" not in copied
)

shutil.rmtree(src, ignore_errors=True)

report = {
    "tool": "sbc_previous_build_migrate_check",
    "copied": sorted(copied),
    "core_adapter_skipped": "adapters/g502v.json" not in copied,
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
