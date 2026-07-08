#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.studio_profiles import save_profile, delete_profile, profile_app_settings, apply_profile

class DummyApp:
    def __init__(self, app_id: str, display_name: str):
        self.app_id = app_id
        self.display_name = display_name
        self.calls: list[str] = []
        self.supports_native_control = True
        self.app_path = APP_ROOT / "user_data" / "cache" / "dummy_apps" / app_id
        self.app_path.mkdir(parents=True, exist_ok=True)
        self.entry_file = "dummy.py"
        self.control_file = f"user_data/cache/dummy_apps/{app_id}/{app_id}.central.control.json"
        self.default_hotkeys = []

    def launch(self):
        self.calls.append("launch")
        return f"{self.display_name} launch called"

    def close(self):
        self.calls.append("close")
        return f"{self.display_name} close called"

    def restart(self):
        self.calls.append("restart")
        return f"{self.display_name} restart called"

    def pause_park(self):
        self.calls.append("pause")
        return f"{self.display_name} pause called"

    def resume(self):
        self.calls.append("resume")
        return f"{self.display_name} resume called"

active_profile_path = APP_ROOT / "user_data" / "active_studio_profile.json"
previous_active_profile_text = active_profile_path.read_text(encoding="utf-8") if active_profile_path.exists() else None

name = f"Strict Action Test {int(time.time())}"
save_profile(
    name,
    "G502V launch only; Soundcard keep.",
    profile_app_settings(
        g502v_enabled=True,
        soundcard_enabled=False,
        g502v_action="launch",
        soundcard_action="keep",
    ),
)

g502v = DummyApp("g502v", "G502V")
soundcard = DummyApp("soundcard", "Soundcard")
g502v2 = DummyApp("g502v", "G502V")
soundcard2 = DummyApp("soundcard", "Soundcard")

try:
    result_normal = apply_profile(name, {"g502v": g502v, "soundcard": soundcard}, launch_apps=False)
    result_launch_flag = apply_profile(name, {"g502v": g502v2, "soundcard": soundcard2}, launch_apps=True)
    passed = (
        result_normal.get("ok")
        and result_launch_flag.get("ok")
        and g502v.calls == ["launch"]
        and soundcard.calls == []
        and g502v2.calls == ["launch"]
        and soundcard2.calls == []
    )
finally:
    delete_profile(name)
    try:
        if previous_active_profile_text is None:
            active_profile_path.unlink(missing_ok=True)
        else:
            active_profile_path.write_text(previous_active_profile_text, encoding="utf-8")
    except Exception:
        pass

report = {
    "tool": "sbc_profile_action_strict_check",
    "profile": name,
    "normal_calls": {"g502v": g502v.calls, "soundcard": soundcard.calls},
    "launch_flag_calls": {"g502v": g502v2.calls, "soundcard": soundcard2.calls},
    "result_normal_ok": result_normal.get("ok"),
    "result_launch_flag_ok": result_launch_flag.get("ok"),
    "passed": bool(passed),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
