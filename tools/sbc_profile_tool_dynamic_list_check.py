#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

source = APP_ROOT / "tools" / "sbc_profile_tool.py"
text = source.read_text(encoding="utf-8")

checks = {
    "loads_active_apps_for_list": "active_apps = load_apps()" in text,
    "reports_active_app_ids": '"active_app_ids"' in text,
    "profile_summary_uses_app_ids": "profile_summary(data, app_ids=active_app_ids)" in text,
}
report = {
    "tool": "sbc_profile_tool_dynamic_list_check",
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
