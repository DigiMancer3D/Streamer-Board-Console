#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.studio_profiles import ACTIVE_PROFILE_PATH, active_profile_name

data = {}
if ACTIVE_PROFILE_PATH.exists():
    try:
        data = json.loads(ACTIVE_PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        data = {"error": str(exc)}

report = {
    "tool": "sbc_profile_status",
    "active_profile": active_profile_name(),
    "active_profile_path": str(ACTIVE_PROFILE_PATH),
    "exists": ACTIVE_PROFILE_PATH.exists(),
    "data": data,
}
print(json.dumps(report, indent=2, sort_keys=True))
