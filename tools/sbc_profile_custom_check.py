#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.studio_profiles import save_profile, load_profiles, delete_profile, profile_app_settings

name = f"Selftest Custom Profile {int(time.time())}"
path = save_profile(
    name,
    "Temporary profile created by selftest.",
    profile_app_settings(g502v_enabled=True, soundcard_enabled=False),
)
profiles = load_profiles()
exists_after_save = name in profiles
delete_result = delete_profile(name)
profiles_after_delete = load_profiles()
exists_after_delete = name in profiles_after_delete

report = {
    "tool": "sbc_profile_custom_check",
    "profile": name,
    "path": str(path),
    "exists_after_save": exists_after_save,
    "delete_result": delete_result,
    "exists_after_delete": exists_after_delete,
    "passed": exists_after_save and delete_result.get("ok") and not exists_after_delete,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
