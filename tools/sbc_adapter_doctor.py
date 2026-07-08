#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.app_registry import load_apps
from sbc_core.adapter_control import native_adapter_status

def main():
    apps = load_apps()
    report = {
        "tool": "sbc_adapter_doctor",
        "protocol": "SBC_ADAPTER_CONTROL_V1",
        "project_root": str(APP_ROOT),
        "apps": {},
        "summary": {"ready": 0, "total": len(apps)},
    }

    for app_id, app in apps.items():
        status = native_adapter_status(app)
        report["apps"][app_id] = status
        if status["native_ready"]:
            report["summary"]["ready"] += 1

    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
