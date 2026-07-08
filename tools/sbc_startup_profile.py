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
from sbc_core.startup_profile import (
    read_startup_config,
    save_startup_config,
    clear_startup_config,
    validate_startup_config,
    apply_startup_profile,
)

def parse_onoff(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("on", "true", "1", "yes", "enabled")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="Show startup profile config.")
    parser.add_argument("--set", help="Set startup profile name.")
    parser.add_argument("--enable", action="store_true", help="Enable startup profile.")
    parser.add_argument("--disable", action="store_true", help="Disable startup profile.")
    parser.add_argument("--launch", choices=["on", "off"], help="Compatibility setting. Per-app actions are strict; Keep is not converted to Launch.")
    parser.add_argument("--clear", action="store_true", help="Disable and reset startup profile config.")
    parser.add_argument("--apply-now", action="store_true", help="Apply configured startup profile now.")
    args = parser.parse_args()

    report = {"tool": "sbc_startup_profile"}

    if args.clear:
        report["clear_result"] = clear_startup_config()

    if args.set or args.enable or args.disable or args.launch:
        current = read_startup_config()
        profile = args.set if args.set else current.get("profile", "Gaming")
        enabled = bool(current.get("enabled", False))
        if args.enable:
            enabled = True
        if args.disable:
            enabled = False
        launch_apps = parse_onoff(args.launch, default=bool(current.get("launch_apps", False)))
        report["save_result"] = save_startup_config(profile, enabled=enabled, launch_apps=launch_apps)

    if args.apply_now:
        report["apply_now_result"] = apply_startup_profile(load_apps())

    if args.show or not any([args.clear, args.set, args.enable, args.disable, args.launch, args.apply_now]):
        cfg = read_startup_config()
        report["config"] = cfg
        report["validation"] = validate_startup_config(cfg)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
