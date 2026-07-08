#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.app_registry import load_apps
from sbc_core.adapter_control import write_default_control, default_hotkey_map

def main():
    apps = load_apps()
    report = {"tool": "sbc_write_initial_controls", "apps": {}}

    for app_id, app in apps.items():
        paths = write_default_control(app, hotkeys_enabled=True, mode="local")
        report["apps"][app_id] = {
            "display_name": app.display_name,
            "hotkeys_enabled": True,
            "hotkey_map": default_hotkey_map(app),
            "written": [str(p) for p in paths],
        }

    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
