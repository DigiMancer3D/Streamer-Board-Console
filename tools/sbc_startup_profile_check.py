#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.startup_profile import (
    STARTUP_PROFILE_PATH,
    read_startup_config,
    save_startup_config,
    validate_startup_config,
)

existed = STARTUP_PROFILE_PATH.exists()
old_text = STARTUP_PROFILE_PATH.read_text(encoding="utf-8") if existed else ""

try:
    saved = save_startup_config("Gaming", enabled=True, launch_apps=False)
    read_back = read_startup_config()
    validation = validate_startup_config(read_back)
    passed = (
        saved.get("profile") == "Gaming"
        and read_back.get("enabled") is True
        and read_back.get("launch_apps") is False
        and validation.get("ok") is True
    )
finally:
    if existed:
        STARTUP_PROFILE_PATH.write_text(old_text, encoding="utf-8")
    else:
        try:
            STARTUP_PROFILE_PATH.unlink()
        except FileNotFoundError:
            pass

report = {
    "tool": "sbc_startup_profile_check",
    "path": str(STARTUP_PROFILE_PATH),
    "saved": saved,
    "read_back": read_back,
    "validation": validation,
    "restored_previous_file": existed,
    "passed": passed,
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
