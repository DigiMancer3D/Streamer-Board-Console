#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.app_registry import load_apps

apps = load_apps()
results = {}
ok = True
for app_id, app in apps.items():
    try:
        pids = app.external_pids()
        pids2 = app.external_pids()
        results[app_id] = {
            "pids": pids,
            "second_cached_call_pids": pids2,
            "ok": isinstance(pids, list) and isinstance(pids2, list),
        }
        ok = ok and results[app_id]["ok"]
    except Exception as exc:
        results[app_id] = {"ok": False, "error": str(exc)}
        ok = False

report = {
    "tool": "sbc_process_scan_check",
    "apps": results,
    "passed": bool(ok),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if ok else 1)
