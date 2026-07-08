#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.studio_profiles import expand_profile_for_apps, profile_summary

profile = {
    "name": "Dynamic Test",
    "description": "Only old apps saved.",
    "apps": {
        "g502v": {"hotkeys_enabled": True, "mode": "local", "action": "keep"},
        "soundcard": {"hotkeys_enabled": False, "mode": "local", "action": "keep"},
    },
}
app_ids = ["g502v", "soundcard", "bitninja_mocap", "deck_card_widget", "swar"]
expanded = expand_profile_for_apps(profile, app_ids)
rows = profile_summary(profile, app_ids=app_ids)

expected = set(app_ids)
got = set(expanded.get("apps", {}).keys())
row_ids = {row.get("app_id") for row in rows}
new_defaults_ok = all(
    expanded["apps"][app_id].get("action") == "keep"
    and expanded["apps"][app_id].get("hotkeys_enabled") is True
    for app_id in ["bitninja_mocap", "deck_card_widget", "swar"]
)

passed = expected.issubset(got) and expected.issubset(row_ids) and new_defaults_ok

report = {
    "tool": "sbc_profile_dynamic_apps_check",
    "expected_app_ids": sorted(expected),
    "expanded_app_ids": sorted(got),
    "row_app_ids": sorted(row_ids),
    "new_defaults_ok": new_defaults_ok,
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
