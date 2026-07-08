#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.adapter_templates import (
    TEMPLATE_DIR, adapter_path, ensure_adapter_templates, list_templates,
    enable_template, disable_adapter, update_template, create_custom_template,
    create_template_from_path_entry, load_template, integration_guide_text,
)

ensure_adapter_templates()
stamp = int(time.time())
app_id = f"selftest_adapter_{stamp}"
auto_folder = f"selftest_auto_app_{stamp}"
auto_app_id = auto_folder
tpath = TEMPLATE_DIR / f"{app_id}.json"
apath = adapter_path(app_id)
auto_tpath = TEMPLATE_DIR / f"{auto_app_id}.json"

try:
    create = create_custom_template(app_id, "Selftest Adapter", "~/SBC_SELFTEST_MISSING_APP", "launch_missing.sh")
    create_auto = create_template_from_path_entry(f"~/{auto_folder}", "launch_auto.sh")
    update1 = update_template(app_id, default_path="~/SBC_SELFTEST_UPDATED_APP")
    update2 = update_template(app_id, entry_file="launch_updated.sh")
    loaded = load_template(app_id)
    listed = list_templates()
    enable = enable_template(app_id)
    active_after_enable = apath.exists()
    disable = disable_adapter(app_id)
    active_after_disable = apath.exists()
    guide = integration_guide_text()

    passed = (
        create.get("ok") and create_auto.get("ok") and update1.get("ok") and update2.get("ok")
        and loaded.get("default_path") == "~/SBC_SELFTEST_UPDATED_APP"
        and loaded.get("entry_file") == "launch_updated.sh"
        and listed.get("ok") and enable.get("ok") and active_after_enable
        and disable.get("ok") and not active_after_disable
        and "How 2 Integrate" in guide
    )
finally:
    for cleanup_path in (apath, tpath, auto_tpath, adapter_path(auto_app_id)):
        try:
            cleanup_path.unlink()
        except FileNotFoundError:
            pass

report = {
    "tool": "sbc_adapter_template_check",
    "app_id": app_id,
    "create_result": create,
    "create_from_path_entry_result": create_auto,
    "update_path_result": update1,
    "update_entry_result": update2,
    "enable_result": enable,
    "disable_result": disable,
    "active_after_enable": active_after_enable,
    "active_after_disable": active_after_disable,
    "template_count": listed.get("count"),
    "guide_present": "How 2 Integrate" in guide,
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
