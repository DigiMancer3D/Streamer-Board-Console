#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

report = {
    "tool": "sbc_runtime_import_check",
    "checks": {},
    "passed": False,
}

try:
    import sbc_core.paths as paths
    report["checks"]["paths"] = {
        "ok": True,
        "has_USER_DATA": hasattr(paths, "USER_DATA"),
        "USER_DATA": str(getattr(paths, "USER_DATA", "")),
        "ADAPTER_DIR": str(getattr(paths, "ADAPTER_DIR", "")),
        "TEMPLATE_DIR": str(getattr(paths, "TEMPLATE_DIR", "")),
    }
except Exception as exc:
    report["checks"]["paths"] = {"ok": False, "error": str(exc)}

try:
    from sbc_core.studio_profiles import ensure_default_profiles, load_profiles
    created = ensure_default_profiles()
    profiles = load_profiles()
    report["checks"]["studio_profiles"] = {
        "ok": True,
        "created_count": len(created),
        "profile_names": sorted(profiles.keys()),
    }
except Exception as exc:
    report["checks"]["studio_profiles"] = {"ok": False, "error": str(exc)}

try:
    from sbc_core.console_copier import list_console_files
    consoles = list_console_files()
    report["checks"]["console_copier"] = {
        "ok": True,
        "console_dir": consoles.get("console_dir", ""),
        "count": consoles.get("count", 0),
    }
except Exception as exc:
    report["checks"]["console_copier"] = {"ok": False, "error": str(exc)}

try:
    from sbc_core.app_registry import load_apps
    from sbc_core.adapter_control import native_adapter_status
    apps = load_apps()
    report["checks"]["app_registry"] = {
        "ok": True,
        "apps": sorted(apps.keys()),
        "adapter_status": {app_id: native_adapter_status(app) for app_id, app in apps.items()},
    }
except Exception as exc:
    report["checks"]["app_registry"] = {"ok": False, "error": str(exc)}

report["passed"] = all(item.get("ok") for item in report["checks"].values())
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
