#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.adapter_templates import (
    ensure_adapter_templates,
    list_templates,
    enable_template,
    disable_adapter,
    load_template,
    update_template,
    create_custom_template,
    create_template_from_path_entry,
    integration_guide_text,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Create built-in adapter templates if missing.")
    parser.add_argument("--list", action="store_true", help="List available adapter templates.")
    parser.add_argument("--inspect", help="Inspect one template by app_id.")
    parser.add_argument("--enable", help="Enable a template by app_id.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing active adapter when enabling.")
    parser.add_argument("--disable", help="Disable a non-core adapter by app_id.")
    parser.add_argument("--set-path", nargs=2, metavar=("APP_ID", "PATH"), help="Update a template default_path.")
    parser.add_argument("--set-entry", nargs=2, metavar=("APP_ID", "ENTRY"), help="Update a template entry_file.")
    parser.add_argument("--create-template", nargs=4, metavar=("APP_ID", "DISPLAY", "PATH", "ENTRY"), help="Create a simple custom template.")
    parser.add_argument("--create-from-path-entry", nargs=2, metavar=("PATH", "ENTRY"), help="Create a template and derive app_id/display from path + entry.")
    parser.add_argument("--guide", action="store_true", help="Print the How 2 Integrate guide.")
    args = parser.parse_args()

    report = {"tool": "sbc_adapter_template_tool"}

    if args.init:
        report["created"] = [str(p) for p in ensure_adapter_templates()]
    if args.list:
        report["templates"] = list_templates()
    if args.inspect:
        try:
            report["inspect_result"] = {"ok": True, "template": load_template(args.inspect)}
        except Exception as exc:
            report["inspect_result"] = {"ok": False, "error": str(exc), "app_id": args.inspect}
    if args.enable:
        report["enable_result"] = enable_template(args.enable, overwrite=args.overwrite)
    if args.disable:
        report["disable_result"] = disable_adapter(args.disable)
    if args.set_path:
        app_id, path_value = args.set_path
        report["set_path_result"] = update_template(app_id, default_path=path_value)
    if args.set_entry:
        app_id, entry_value = args.set_entry
        report["set_entry_result"] = update_template(app_id, entry_file=entry_value)
    if args.create_template:
        app_id, display, path_value, entry_value = args.create_template
        report["create_template_result"] = create_custom_template(app_id, display, path_value, entry_value)
    if args.create_from_path_entry:
        path_value, entry_value = args.create_from_path_entry
        report["create_from_path_entry_result"] = create_template_from_path_entry(path_value, entry_value)
    if args.guide:
        report["guide"] = integration_guide_text()

    if not any([args.init, args.list, args.inspect, args.enable, args.disable, args.set_path, args.set_entry, args.create_template, args.create_from_path_entry, args.guide]):
        parser.print_help()
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
