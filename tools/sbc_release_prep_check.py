#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.paths import USER_DATA
from sbc_core.release_prep import build_github_upload, inspect_release_folder, build_share_bundle, inspect_share_bundle

out = USER_DATA / "cache" / f"sbc_release_prep_selftest_{int(time.time())}"
try:
    build = build_github_upload(out)
    inspect = inspect_release_folder(out)
    share_zip = USER_DATA / "cache" / f"sbc_share_bundle_selftest_{int(time.time())}.zip"
    share_build = build_share_bundle(share_zip)
    share_inspect = inspect_share_bundle(share_zip)
    checks = {
        "build_ok": bool(build.get("ok")),
        "inspect_ok": bool(inspect.get("ok")),
        "manifest_exists": (out / "SBC_PUBLIC_RELEASE_MANIFEST.json").exists(),
        "checklist_exists": (out / "PUBLIC_RELEASE_CHECKLIST.md").exists(),
        "github_notes_exists": (out / "GITHUB_UPLOAD_NOTES.md").exists(),
        "original_app_notes_exists": (out / "UPDATE_ORIGINAL_APP_REPOS.md").exists(),
        "external_update_notes_exist": (out / "external_app_updates" / "soundcard" / "SOUNDCARD_SBC_UPDATE.md").exists(),
        "release_verify_exists": (out / "tools" / "release_verify.sh").exists(),
        "share_build_ok": bool(share_build.get("ok")),
        "share_inspect_ok": bool(share_inspect.get("ok")),
        "friend_share_manifest_exists": share_inspect.get("manifest", {}).get("format") == "SBC_FRIEND_SHARE_BUNDLE_V1",
        "friend_share_no_private_markers": not share_inspect.get("private_marker_hits"),
        "no_runtime_console_copies": not (out / "user_data" / "console_copies").exists(),
        "no_runtime_console_instances": not (out / "user_data" / "console_instances").exists(),
        "no_runtime_logs": not (out / "user_data" / "logs").exists(),
        "no_export_recursion": not (out / "export").exists(),
    }
    report = {
        "tool": "sbc_release_prep_check",
        "passed": all(checks.values()),
        "checks": checks,
        "release_dir": str(out),
        "copied_count": build.get("copied_count", 0),
        "inspect_required_missing": [k for k, v in inspect.get("required", {}).items() if not v],
        "inspect_forbidden_present": inspect.get("forbidden_present", {}),
        "share_private_marker_hits": share_inspect.get("private_marker_hits", []),
        "share_forbidden_present": share_inspect.get("forbidden_present", []),
    }
finally:
    if out.exists():
        shutil.rmtree(out)
    try:
        if 'share_zip' in globals() and share_zip.exists():
            share_zip.unlink()
    except Exception:
        pass

print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
