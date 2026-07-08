#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.app_registry import load_apps
from sbc_core.studio_profiles import (
    PROFILE_ACTIONS,
    ensure_default_profiles,
    load_profiles,
    apply_profile,
    active_profile_name,
    profile_summary,
    save_profile,
    delete_profile,
    profile_app_settings,
    is_default_profile,
    normalize_action,
)

def onoff_to_bool(value: str) -> bool:
    return str(value).strip().lower() in ("on", "true", "1", "yes", "enabled")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Create default profiles if missing.")
    parser.add_argument("--list", action="store_true", help="List profiles.")
    parser.add_argument("--apply", help="Apply profile by name.")
    parser.add_argument("--launch", action="store_true", help="Compatibility flag. Per-app actions are strict; Keep is not converted to Launch.")

    parser.add_argument("--save", help="Create/update a custom profile by name.")
    parser.add_argument("--description", default="", help="Description for --save.")
    parser.add_argument("--g502v", choices=["on", "off"], default="on", help="G502V hotkeys for --save.")
    parser.add_argument("--soundcard", choices=["on", "off"], default="on", help="Soundcard hotkeys for --save.")
    parser.add_argument("--g502v-action", choices=PROFILE_ACTIONS, default="keep", help="G502V app action for --save.")
    parser.add_argument("--soundcard-action", choices=PROFILE_ACTIONS, default="keep", help="Soundcard app action for --save.")
    parser.add_argument("--delete", help="Delete a custom profile by name. Built-in profiles are protected.")

    args = parser.parse_args()
    report = {"tool": "sbc_profile_tool"}

    if args.init:
        report["created"] = [str(p) for p in ensure_default_profiles()]

    if args.save:
        app_settings = profile_app_settings(
            g502v_enabled=onoff_to_bool(args.g502v),
            soundcard_enabled=onoff_to_bool(args.soundcard),
            g502v_action=normalize_action(args.g502v_action),
            soundcard_action=normalize_action(args.soundcard_action),
        )
        path = save_profile(args.save, args.description, app_settings)
        report["save_result"] = {
            "ok": True,
            "profile": args.save,
            "path": str(path),
            "is_default_profile_name": is_default_profile(args.save),
            "apps": app_settings,
        }

    if args.delete:
        report["delete_result"] = delete_profile(args.delete)

    if args.list:
        profiles = load_profiles()
        active_apps = load_apps()
        active_app_ids = list(active_apps.keys())
        report["active_profile"] = active_profile_name()
        report["active_app_ids"] = active_app_ids
        report["profiles"] = {
            name: {
                "description": data.get("description", ""),
                "built_in": is_default_profile(name),
                "rows": profile_summary(data, app_ids=active_app_ids),
            }
            for name, data in profiles.items()
        }

    if args.apply:
        apps = load_apps()
        report["apply_result"] = apply_profile(args.apply, apps, launch_apps=args.launch)

    if not any([args.init, args.list, args.apply, args.save, args.delete]):
        parser.print_help()
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
