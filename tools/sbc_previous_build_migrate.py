#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.previous_build_migrate import find_previous_builds, migrate_from_build, migrate_latest_previous_build

def main() -> int:
    parser = argparse.ArgumentParser(description="Carry adapter templates, active adapters, and user_data forward from an older SBC build folder.")
    parser.add_argument("--list", action="store_true", help="List previous SBC build folders.")
    parser.add_argument("--latest", action="store_true", help="Migrate from the most recent previous SBC build.")
    parser.add_argument("--from-build", dest="from_build", help="Migrate from a specific previous build folder.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without writing.")
    parser.add_argument("--no-overwrite", action="store_true", help="Skip files that already exist.")
    args = parser.parse_args()

    report = {"tool": "sbc_previous_build_migrate"}

    if args.list:
        report["previous_builds"] = find_previous_builds()
    if args.latest:
        report["migrate_latest_result"] = migrate_latest_previous_build(overwrite=not args.no_overwrite, dry_run=args.dry_run)
    if args.from_build:
        report["migrate_from_build_result"] = migrate_from_build(args.from_build, overwrite=not args.no_overwrite, dry_run=args.dry_run)

    if not any([args.list, args.latest, args.from_build]):
        parser.print_help()
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
