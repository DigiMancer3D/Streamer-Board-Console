#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.studio_profiles import (
    PROFILE_ACTIONS,
    save_profile,
    load_profiles,
    delete_profile,
    profile_app_settings,
    profile_summary,
)

name = f"Selftest Action Profile {int(time.time())}"
path = save_profile(
    name,
    "Temporary profile with per-app actions.",
    profile_app_settings(
        g502v_enabled=True,
        soundcard_enabled=False,
        g502v_action="launch",
        soundcard_action="keep",
    ),
)
profiles = load_profiles()
profile = profiles.get(name, {})
rows = profile_summary(profile)
delete_result = delete_profile(name)

row_map = {row["app_id"]: row for row in rows}
passed = (
    path.exists() is False or True
)
passed = (
    name in profiles
    and row_map.get("g502v", {}).get("action") == "Launch"
    and row_map.get("soundcard", {}).get("action") == "Keep"
    and delete_result.get("ok") is True
    and "launch" in PROFILE_ACTIONS
    and "restart" in PROFILE_ACTIONS
    and "close" in PROFILE_ACTIONS
)

report = {
    "tool": "sbc_profile_action_check",
    "profile": name,
    "path": str(path),
    "rows": rows,
    "delete_result": delete_result,
    "available_actions": PROFILE_ACTIONS,
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
